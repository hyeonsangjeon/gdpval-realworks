"""Offline tar-filter compatibility; Backend collects this on Python 3.10.12."""

import io
import os
import socket
import tarfile

import pytest

import ghcp_ahp_probe as probe


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("archive fixture attempted a process or network operation")
    monkeypatch.setattr(probe.subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(probe.urllib.request, "build_opener", forbidden)


def _link_archive(path, linkname, kind=tarfile.SYMTYPE):
    with tarfile.open(path, "w:gz") as archive:
        content = b"inert offline SDK fixture"
        target = tarfile.TarInfo("node_modules/@openai/codex/bin/codex.js")
        target.size = len(content)
        archive.addfile(target, io.BytesIO(content))
        link = tarfile.TarInfo("node_modules/.bin/codex")
        link.type, link.linkname = kind, linkname
        archive.addfile(link)


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE])
@pytest.mark.parametrize("legacy_filter", [False, True])
def test_internal_archive_links_keep_their_correct_resolution(tmp_path, monkeypatch, kind, legacy_filter):
    original_filter = tarfile.data_filter
    calls = []

    def checked_filter(member, destination):
        calls.append(member.name)
        if legacy_filter and (member.issym() or member.islnk()):
            # CPython v3.10.12 tarfile.py:801-806. Exercise this incorrect
            # symlink origin even when the test runs with a newer Python.
            root = os.path.realpath(destination)
            target = os.path.realpath(os.path.join(root, member.linkname))
            if os.path.commonpath([root, target]) != root:
                raise tarfile.LinkOutsideDestinationError(member, target)
        return original_filter(member, destination)

    monkeypatch.setattr(tarfile, "data_filter", checked_filter)
    linkname = ("../@openai/codex/bin/codex.js" if kind == tarfile.SYMTYPE
                else "node_modules/@openai/codex/bin/codex.js")
    archive = tmp_path / "sdk.tgz"
    _link_archive(archive, linkname, kind)
    destination = tmp_path / "out"
    probe.extract_archive(archive, destination)
    link = destination / "node_modules/.bin/codex"
    target = destination / "node_modules/@openai/codex/bin/codex.js"
    assert link.read_bytes() == target.read_bytes() == b"inert offline SDK fixture"
    assert link.is_symlink() is (kind == tarfile.SYMTYPE)
    if kind == tarfile.SYMTYPE:
        assert os.readlink(link) == linkname
        assert link.resolve() == target.resolve()
    else:
        assert link.stat().st_ino == target.stat().st_ino
    assert calls == ["node_modules/@openai/codex/bin/codex.js", "node_modules/.bin/codex"]


@pytest.mark.parametrize("kind,linkname,error", [
    (tarfile.SYMTYPE, "/absolute", tarfile.AbsoluteLinkError),
    (tarfile.SYMTYPE, "../../../escaped", tarfile.LinkOutsideDestinationError),
    (tarfile.LNKTYPE, "/absolute", tarfile.AbsoluteLinkError),
    (tarfile.LNKTYPE, "../escaped", tarfile.LinkOutsideDestinationError),
])
def test_archive_links_outside_destination_remain_refused(tmp_path, kind, linkname, error):
    archive = tmp_path / "sdk.tgz"
    _link_archive(archive, linkname, kind)
    destination = tmp_path / "out"
    with pytest.raises(error):
        probe.extract_archive(archive, destination)
    assert not (destination / "node_modules/.bin/codex").is_symlink()
    assert not (tmp_path / "escaped").exists()


def test_archive_symlink_cannot_escape_through_an_existing_link(tmp_path):
    destination, outside = tmp_path / "out", tmp_path / "outside"
    (destination / "node_modules/.bin").mkdir(parents=True)
    outside.mkdir()
    (outside / "target").write_bytes(b"outside sentinel")
    (destination / "node_modules/.bin/alias").symlink_to(outside, target_is_directory=True)
    archive = tmp_path / "sdk.tgz"
    _link_archive(archive, "alias/target")
    with pytest.raises(tarfile.LinkOutsideDestinationError):
        probe.extract_archive(archive, destination)
    assert (outside / "target").read_bytes() == b"outside sentinel"
    assert not (destination / "node_modules/.bin/codex").is_symlink()


def test_archive_hardlink_cannot_escape_through_an_existing_link(tmp_path):
    destination, outside = tmp_path / "out", tmp_path / "outside"
    destination.mkdir()
    outside.mkdir()
    (outside / "target").write_bytes(b"outside sentinel")
    (destination / "alias").symlink_to(outside, target_is_directory=True)
    archive = tmp_path / "sdk.tgz"
    _link_archive(archive, "alias/target", tarfile.LNKTYPE)
    with pytest.raises(tarfile.LinkOutsideDestinationError):
        probe.extract_archive(archive, destination)
    assert (outside / "target").read_bytes() == b"outside sentinel"
    assert not (destination / "node_modules/.bin/codex").exists()
    assert not (destination / "node_modules/.bin/codex").is_symlink()


@pytest.mark.parametrize("terminal_kind", [tarfile.SYMTYPE, tarfile.LNKTYPE])
@pytest.mark.parametrize("reverse_order", [False, True])
def test_archive_created_link_chain_cannot_escape(tmp_path, terminal_kind, reverse_order):
    destination, outside = tmp_path / "out", tmp_path / "outside"
    outside.mkdir()
    (outside / "target").write_bytes(b"outside sentinel")
    archive = tmp_path / "chain.tgz"
    first = tarfile.TarInfo("first")
    first.type, first.linkname = tarfile.SYMTYPE, "second"
    second = tarfile.TarInfo("second")
    second.type = terminal_kind
    second.linkname = "../outside" if terminal_kind == tarfile.SYMTYPE else "../outside/target"
    with tarfile.open(archive, "w:gz") as output:
        for member in ([second, first] if reverse_order else [first, second]):
            output.addfile(member)
        content = b"must never escape"
        payload = tarfile.TarInfo("first/escaped")
        payload.size = len(content)
        output.addfile(payload, io.BytesIO(content))
    with pytest.raises(tarfile.LinkOutsideDestinationError):
        probe.extract_archive(archive, destination)
    assert (outside / "target").read_bytes() == b"outside sentinel"
    assert not (outside / "escaped").exists()
    assert not (destination / "second").exists()
    assert not (destination / "second").is_symlink()


@pytest.mark.parametrize("kind", [tarfile.CHRTYPE, tarfile.BLKTYPE])
def test_archive_device_is_refused_before_any_member_is_extracted(tmp_path, kind):
    archive = tmp_path / "device.tgz"
    with tarfile.open(archive, "w:gz") as output:
        content = b"must not be partially extracted"
        regular = tarfile.TarInfo("regular.txt")
        regular.size = len(content)
        output.addfile(regular, io.BytesIO(content))
        device = tarfile.TarInfo("device")
        device.type, device.devmajor, device.devminor = kind, 1, 3
        output.addfile(device)
    destination = tmp_path / "out"
    with pytest.raises(probe.Refused, match="^archive_special_file$"):
        probe.extract_archive(archive, destination)
    assert not destination.exists()


def test_archive_symlink_member_path_still_uses_the_data_filter(tmp_path):
    destination, outside = tmp_path / "out", tmp_path / "outside/nested"
    (destination / "node_modules").mkdir(parents=True)
    outside.mkdir(parents=True)
    (destination / "node_modules/.bin").symlink_to(outside, target_is_directory=True)
    archive = tmp_path / "sdk.tgz"
    # The target is inside, but the member would be created outside. The
    # stdlib's independent member-path check must still reject this view.
    _link_archive(archive, "../../out/node_modules/@openai/codex/bin/codex.js")
    with pytest.raises(tarfile.OutsideDestinationError):
        probe.extract_archive(archive, destination)
    assert not (outside / "codex").is_symlink()


def test_archive_symlink_keeps_data_filter_metadata_sanitization(tmp_path):
    member = tarfile.TarInfo("node_modules/.bin/codex")
    member.type, member.linkname = tarfile.SYMTYPE, "../@openai/codex/bin/codex.js"
    member.uid, member.gid, member.uname, member.gname, member.mode = 123, 456, "user", "group", 0o6777
    filtered = probe._archive_data_filter(member, tmp_path)
    assert filtered.issym() and filtered.linkname == member.linkname
    assert (filtered.uid, filtered.gid, filtered.uname, filtered.gname, filtered.mode) == (None,) * 5
    assert member.mode == 0o6777 and member.uid == 123  # No mutation of the archive entry.


def test_archive_symlink_never_swallows_data_filter_refusal(tmp_path, monkeypatch):
    member = tarfile.TarInfo("node_modules/.bin/codex")
    member.type, member.linkname = tarfile.SYMTYPE, "../@openai/codex/bin/codex.js"
    def refused(*args):
        raise tarfile.FilterError("independent data-filter refusal")
    monkeypatch.setattr(tarfile, "data_filter", refused)
    with pytest.raises(tarfile.FilterError, match="^independent data-filter refusal$"):
        probe._archive_data_filter(member, tmp_path)
