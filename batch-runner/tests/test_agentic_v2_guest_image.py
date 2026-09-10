"""What the two guest images have to be before anything boots from them.

The tests here are mostly refusals. That is the shape of the module: a rootfs
assembled from an image whose layers were not checked, or a kernel that is not
the object the pin names, is not a weaker version of the containment — it is a
guest whose contents nobody knows, and every rule underneath it is then a rule
about something unidentified.

The disclaimers get tests of their own, which is unusual and deliberate. A hash
printed next to the word "verified" reads as a signature check to anybody who
does not already know that Firecracker's CI bucket publishes neither a checksum
nor a signature. The sentence that says otherwise is load-bearing, so it is held
in place the same way a limit would be.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from core.agentic_v2_guest_image import (
    GUEST_INIT,
    GUEST_INIT_PATH,
    PINNED_GUEST_KERNEL,
    ImageRefused,
    add_guest_init,
    anonymous_pull_token,
    ext4_image_arguments,
    fetch_pinned_kernel,
    pull_image_by_digest,
    require_same_kernel,
    rootfs_size_mib,
    unpack_layers,
)


def _digest(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _layer(entries: dict[str, bytes | None], tmp_path: Path, name: str) -> dict:
    """A gzip-free tar layer. ``None`` as a value means a directory."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for member_name, content in entries.items():
            info = tarfile.TarInfo(member_name)
            if content is None:
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                archive.addfile(info)
            else:
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
    path = tmp_path / name
    path.write_bytes(buffer.getvalue())
    return {"digest": _digest(buffer.getvalue()), "path": path.as_posix()}


def _special(kind: str, name: str, target: str, tmp_path: Path, file_name: str) -> dict:
    """A one-member layer holding a symbolic or hard link."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo(name)
        info.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
        info.linkname = target
        archive.addfile(info)
    path = tmp_path / file_name
    path.write_bytes(buffer.getvalue())
    return {"digest": _digest(buffer.getvalue()), "path": path.as_posix()}


class _Registry:
    """Enough of a registry to answer by digest, and to be told to lie."""

    def __init__(self, *, manifests: dict[str, bytes], blobs: dict[str, bytes]):
        self.manifests = manifests
        self.blobs = blobs
        self.asked_for: list[str] = []

    def __call__(self, url: str, headers=None) -> bytes:
        self.asked_for.append(url)
        if "/token" in url:
            return json.dumps({"token": "anonymous-and-not-a-credential"}).encode()
        reference = url.rsplit("/", 1)[1]
        if "/manifests/" in url:
            return self.manifests[reference]
        return self.blobs[reference]


def _index(child_digest: str, *, architecture: str = "amd64") -> bytes:
    return json.dumps(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "manifests": [
                {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": child_digest,
                    "platform": {"architecture": architecture, "os": "linux"},
                }
            ],
        }
    ).encode()


def _manifest(layers: list[dict]) -> bytes:
    return json.dumps(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "layers": [
                {
                    "digest": layer["digest"],
                    "mediaType": "application/vnd.oci.image.layer.v1.tar",
                    "size": Path(layer["path"]).stat().st_size,
                }
                for layer in layers
            ],
        }
    ).encode()


# --------------------------------------------------------------------------
# the kernel, and the three things about it that are easy to lose
# --------------------------------------------------------------------------


def test_the_pinned_kernel_is_one_exact_key_and_not_a_search():
    assert PINNED_GUEST_KERNEL["key"].endswith("vmlinux-6.1.141")
    assert PINNED_GUEST_KERNEL["url"].startswith("https://")
    assert PINNED_GUEST_KERNEL["key"] in PINNED_GUEST_KERNEL["url"]


def test_the_kernel_reading_refuses_to_claim_upstream_vouched_for_it(tmp_path):
    body = b"k" * PINNED_GUEST_KERNEL["size_bytes"]
    reading = fetch_pinned_kernel(tmp_path / "vmlinux", fetch=lambda url, h: body)

    assert reading["vouched_for_by_upstream"] is False
    assert reading["sha256"] == hashlib.sha256(body).hexdigest()
    explanation = reading["what_the_digest_means"]
    assert "not a signature" in explanation
    assert "computed here" in explanation
    assert reading["source"]["upstream_publishes_a_signature"] is False
    assert reading["source"]["upstream_publishes_a_checksum"] is False


def test_the_lapsed_support_window_travels_with_the_pin(tmp_path):
    """Recorded as lapsed rather than pinned in silence.

    Firecracker's kernel policy at v1.13.1 validates two guest kernels and both
    of their minimum end-of-support dates are in the past. Using one anyway is a
    decision; using one without saying so is an omission, and this is the field
    that makes it the first.
    """
    reading = fetch_pinned_kernel(
        tmp_path / "vmlinux",
        fetch=lambda url, h: b"k" * PINNED_GUEST_KERNEL["size_bytes"],
    )
    assert reading["source"]["support_window_has_lapsed"] is True
    assert reading["source"]["minimum_end_of_support"] == "2026-09-02"


def test_a_kernel_of_the_wrong_length_is_not_the_object_the_key_names(tmp_path):
    with pytest.raises(ImageRefused, match="one exact object"):
        fetch_pinned_kernel(tmp_path / "vmlinux", fetch=lambda url, h: b"short")


def test_a_kernel_that_changed_under_its_key_is_refused(tmp_path):
    reading = fetch_pinned_kernel(
        tmp_path / "vmlinux",
        fetch=lambda url, h: b"k" * PINNED_GUEST_KERNEL["size_bytes"],
    )
    require_same_kernel(reading, reading["sha256"])
    with pytest.raises(ImageRefused, match="moving target"):
        require_same_kernel(reading, "0" * 64)


# --------------------------------------------------------------------------
# the image, where every blob is checked against the name it arrived under
# --------------------------------------------------------------------------


def test_an_index_digest_is_exact_but_the_artefact_still_names_the_child(tmp_path):
    """An index digest does not say which of its children was unpacked.

    ``parent.lock.json`` pins the index. That is a reproducible pin, so the
    temptation is to record only it — but a reader of the artefact wants to know
    which architecture booted, and the index digest cannot tell them.
    """
    layer = _layer({"etc/hostname": b"guest\n"}, tmp_path, "layer0.tar")
    manifest = _manifest([layer])
    index = _index(_digest(manifest))
    registry = _Registry(
        manifests={_digest(index): index, _digest(manifest): manifest},
        blobs={layer["digest"]: Path(layer["path"]).read_bytes()},
    )

    pulled = pull_image_by_digest(
        "owner/image", _digest(index), tmp_path / "oci", fetch=registry
    )

    assert pulled["pinned_digest"] == _digest(index)
    assert pulled["pinned_digest_is_an_index"] is True
    assert pulled["manifest_digest"] == _digest(manifest)
    assert pulled["manifest_digest"] != pulled["pinned_digest"]
    assert pulled["layer_count"] == 1


def test_a_manifest_that_does_not_hash_to_its_own_name_is_refused(tmp_path):
    layer = _layer({"a": b"a"}, tmp_path, "layer0.tar")
    manifest = _manifest([layer])
    registry = _Registry(
        manifests={"sha256:" + "1" * 64: manifest},
        blobs={layer["digest"]: Path(layer["path"]).read_bytes()},
    )
    with pytest.raises(ImageRefused, match="pinning by digest"):
        pull_image_by_digest(
            "owner/image", "sha256:" + "1" * 64, tmp_path / "oci", fetch=registry
        )


def test_a_layer_that_does_not_hash_to_its_own_name_is_refused(tmp_path):
    layer = _layer({"a": b"a"}, tmp_path, "layer0.tar")
    manifest = _manifest([layer])
    registry = _Registry(
        manifests={_digest(manifest): manifest},
        blobs={layer["digest"]: b"something else entirely"},
    )
    with pytest.raises(ImageRefused, match="nothing from this image is used"):
        pull_image_by_digest(
            "owner/image", _digest(manifest), tmp_path / "oci", fetch=registry
        )


def test_an_index_with_no_manifest_for_the_platform_is_refused(tmp_path):
    layer = _layer({"a": b"a"}, tmp_path, "layer0.tar")
    manifest = _manifest([layer])
    index = _index(_digest(manifest), architecture="arm64")
    registry = _Registry(
        manifests={_digest(index): index, _digest(manifest): manifest},
        blobs={layer["digest"]: Path(layer["path"]).read_bytes()},
    )
    with pytest.raises(ImageRefused, match="names 0 manifests"):
        pull_image_by_digest(
            "owner/image", _digest(index), tmp_path / "oci", fetch=registry
        )


def test_a_manifest_with_no_layers_has_no_rootfs_in_it(tmp_path):
    manifest = _manifest([])
    registry = _Registry(manifests={_digest(manifest): manifest}, blobs={})
    with pytest.raises(ImageRefused, match="no layers"):
        pull_image_by_digest(
            "owner/image", _digest(manifest), tmp_path / "oci", fetch=registry
        )


def test_the_pull_token_is_anonymous_and_is_not_a_credential(tmp_path):
    registry = _Registry(manifests={}, blobs={})
    assert anonymous_pull_token("owner/image", fetch=registry).startswith("anonymous")
    assert any("scope=repository:owner/image:pull" in url for url in registry.asked_for)


# --------------------------------------------------------------------------
# unpacking, where a skipped whiteout leaves a file the image says is not there
# --------------------------------------------------------------------------


def test_layers_are_applied_in_order_and_later_ones_win(tmp_path):
    first = _layer({"etc/version": b"one\n"}, tmp_path, "l0.tar")
    second = _layer({"etc/version": b"two\n"}, tmp_path, "l1.tar")

    report = unpack_layers([first, second], tmp_path / "root")

    assert (tmp_path / "root" / "etc" / "version").read_bytes() == b"two\n"
    assert report["layers_applied_in_order"] == [first["digest"], second["digest"]]


def test_a_whiteout_removes_what_an_earlier_layer_put_there(tmp_path):
    first = _layer({"usr/secret": b"still here\n"}, tmp_path, "l0.tar")
    second = _layer({"usr/.wh.secret": b""}, tmp_path, "l1.tar")

    report = unpack_layers([first, second], tmp_path / "root")

    assert not (tmp_path / "root" / "usr" / "secret").exists()
    assert not (tmp_path / "root" / "usr" / ".wh.secret").exists()
    assert report["whiteouts_honoured"] == 1


def test_an_opaque_whiteout_empties_the_directory_it_sits_in(tmp_path):
    first = _layer(
        {"var/cache": None, "var/cache/a": b"a\n", "var/cache/b": b"b\n"},
        tmp_path,
        "l0.tar",
    )
    second = _layer({"var/cache/.wh..wh..opq": b""}, tmp_path, "l1.tar")

    unpack_layers([first, second], tmp_path / "root")

    assert (tmp_path / "root" / "var" / "cache").is_dir()
    assert list((tmp_path / "root" / "var" / "cache").iterdir()) == []


def test_an_absolute_path_in_a_layer_is_refused(tmp_path):
    absolute = _layer({"/etc/shadow": b"no\n"}, tmp_path, "l0.tar")
    with pytest.raises(ImageRefused, match="absolute path"):
        unpack_layers([absolute], tmp_path / "root")


# --------------------------------------------------------------------------
# the one added file, and the image that is built from all of it
# --------------------------------------------------------------------------


def test_the_root_entry_every_layer_starts_with_is_not_an_escape(tmp_path):
    """``.`` is the first member of a real OCI layer, and it stopped C2's first boot.

    The check was written with ``lstrip("./")``, which takes a set of characters
    rather than a prefix: ``.`` became the empty string and was refused as an
    escape. The same call turned ``../x`` into ``x`` and ``/etc/shadow`` into
    ``etc/shadow``, so the two members it existed to stop were the two it let
    through. Both directions are held here.
    """
    layer = _layer({".": None, "./etc/hostname": b"guest\n"}, tmp_path, "l0.tar")

    report = unpack_layers([layer], tmp_path / "root")

    assert (tmp_path / "root" / "etc" / "hostname").read_bytes() == b"guest\n"
    assert report["entries_written"] == 1, "the root entry is skipped, not written"


@pytest.mark.parametrize(
    "escape", ["../x", "/etc/shadow", "a/../../b", "./../../y"]
)
def test_a_member_that_lands_outside_the_root_is_refused(tmp_path, escape):
    with pytest.raises(ImageRefused):
        unpack_layers(
            [_layer({escape: b"no\n"}, tmp_path, "bad.tar")], tmp_path / "root"
        )
    assert not (tmp_path / "x").exists()
    assert not (tmp_path / "b").exists()


def test_a_member_written_through_a_symlinked_parent_is_refused(tmp_path):
    """Neither member escapes on its own reading, and the pair of them does.

    ``etc`` as a link to ``/`` is a legal thing for a layer to contain. So is a
    file called ``etc/passwd``. Together they write to the host's own file, and
    the only moment the pair is visible is the one where the second is about to
    be extracted and the link already exists.
    """
    link = _special("symlink", "etc", "/", tmp_path, "l0.tar")
    through = _layer({"etc/passwd": b"pwned\n"}, tmp_path, "l1.tar")

    with pytest.raises(ImageRefused, match="symbolic link"):
        unpack_layers([link, through], tmp_path / "root")


def test_a_hardlink_pointing_out_of_the_image_is_refused(tmp_path):
    """A hardlink is a second name, and tar lets it name something outside.

    It cannot be used to write to the host — but it pulls a host file's contents
    into the filesystem the guest boots from, which is the same disclosure in
    the other direction and is not something the manifest describes.
    """
    escaping = _special("hardlink", "usr/x", "../../../etc/shadow", tmp_path, "l0.tar")
    with pytest.raises(ImageRefused, match="points outside"):
        unpack_layers([escaping], tmp_path / "root")


def test_a_narrow_directory_does_not_break_the_layer_it_is_in(tmp_path):
    """Its own children arrive after it, and its mode is in place by then.

    ``extractall`` defers directory modes to the end for exactly this reason,
    and cannot be used here because the whiteout and escape checks need each
    member in hand. So the mode is widened during the unpack and put back
    afterwards, and this is both halves: the children land, and the image's own
    mode is what survives.
    """
    narrow = io.BytesIO()
    with tarfile.open(fileobj=narrow, mode="w") as archive:
        directory = tarfile.TarInfo("var")
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o700
        archive.addfile(directory)
        child = tarfile.TarInfo("var/log")
        child.size = 4
        archive.addfile(child, io.BytesIO(b"log\n"))
    path = tmp_path / "l0.tar"
    path.write_bytes(narrow.getvalue())
    layer = {"digest": _digest(narrow.getvalue()), "path": path.as_posix()}

    report = unpack_layers([layer], tmp_path / "root")

    assert (tmp_path / "root" / "var" / "log").read_bytes() == b"log\n"
    assert (tmp_path / "root" / "var").stat().st_mode & 0o777 == 0o700
    assert report["directory_modes_restored"] == 1


def test_the_unpack_says_what_the_extraction_filter_changed(tmp_path):
    """So the artefact does not imply the tree is the image's own permissions."""
    layer = _layer({"a": b"a\n"}, tmp_path, "l0.tar")
    report = unpack_layers([layer], tmp_path / "root")

    assert "setuid" in report["what_the_filter_changed"]
    assert report["extraction_filter"] in {"tar", "none available"}


def test_the_added_init_is_recorded_in_full_rather_than_described(tmp_path):
    (tmp_path / "root").mkdir()
    record = add_guest_init(tmp_path / "root")

    assert record["path"] == GUEST_INIT_PATH
    assert record["text"] == GUEST_INIT
    assert record["sha256"] == hashlib.sha256(GUEST_INIT.encode()).hexdigest()
    assert (tmp_path / "root" / "gdpval-init").read_text() == GUEST_INIT


def test_the_init_opens_no_channel_the_policy_closed():
    """The guest's only way out is the work disk, and this is where that holds.

    ``network: none`` and the pinned-absent ``vsock`` are enforced by the
    launcher. They would still be enforced if this script tried — but a script
    that tried would mean the design had drifted, and the drift is worth
    catching here rather than in a packet capture.
    """
    forbidden = ("vsock", "ip ", "ifconfig", "curl", "wget", "nc ", "ssh")
    for word in forbidden:
        assert word not in GUEST_INIT, f"the guest init reaches for {word!r}"
    assert "/work/out/exit_status" in GUEST_INIT
    assert "/work/in/command.sh" in GUEST_INIT


def test_building_an_ext4_mounts_nothing_and_attaches_no_loop_device(tmp_path):
    """``mke2fs -d`` populates the image directly, which is the whole point.

    The alternative — mount, copy, unmount — needs privilege the jailed account
    does not have and hands a guest-written filesystem to the host kernel's ext4
    driver. Both are avoided, and this test is what stops somebody reaching for
    the easier one later.
    """
    argv = ext4_image_arguments(tmp_path / "x.ext4", size_mib=256, populate_from=tmp_path)

    assert argv[0] == "mke2fs"
    assert "-d" in argv and argv[argv.index("-d") + 1] == tmp_path.as_posix()
    assert argv[-1] == "65536", "256 MiB of 4096-byte blocks"
    assert "mount" not in argv
    assert not any(part.startswith("/dev/loop") for part in argv)


def test_an_ext4_with_nothing_to_populate_it_takes_no_source_directory(tmp_path):
    argv = ext4_image_arguments(tmp_path / "x.ext4", size_mib=16, populate_from=None)
    assert "-d" not in argv


def test_the_rootfs_is_sized_from_what_is_in_it(tmp_path):
    small = tmp_path / "small"
    (small / "a").parent.mkdir(parents=True, exist_ok=True)
    (small / "a").write_bytes(b"0" * 1024)
    large = tmp_path / "large"
    large.mkdir()
    (large / "a").write_bytes(b"0" * (400 * 1024 * 1024))

    assert rootfs_size_mib(small) == 512, "the floor, for an image smaller than it"
    assert rootfs_size_mib(large) > 512
