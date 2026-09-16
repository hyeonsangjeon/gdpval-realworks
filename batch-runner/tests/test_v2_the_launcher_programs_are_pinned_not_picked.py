"""The two programs that launch the guest arrive by pin, not by discovery.

Nothing in this repository installed firecracker or jailer until now; they were
put on ``gdpval-devhost-vm`` by hand, which is why nobody had to decide what
"install firecracker" means. Doing it inside a job forces the decision, and the
easy version of it is wrong: fetching whatever release is newest would move the
binaries under a launcher whose every flag was read from **v1.13.1**, including
the pid filename it waits on.

So the tag is pinned in full, the published digest is checked, and the digest
actually seen is recorded. These tests hold the three things that make that
worth doing -- that a different file is refused rather than installed, that the
archive not being laid out as expected is a sentence rather than a ``KeyError``,
and that the names the programs land under are the names the first boot looks
for. They also hold the two honesties: that the checksum is a transfer check
and not provenance, and that the fetch is over a channel that cannot be
rewritten in transit.

Every test here injects the transport. Nothing reaches the network.
"""

from __future__ import annotations

import hashlib
import io
import sys
import tarfile
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_firecracker_release import (  # noqa: E402
    PINNED_FIRECRACKER_RELEASE,
    PROGRAMS,
    ReleaseRefused,
    fetch_release,
    unpack_programs,
)

from scripts import install_pinned_firecracker as installer  # noqa: E402

FIRST_BOOT = BATCH_RUNNER_ROOT / "scripts" / "run_agentic_c2_first_boot.py"


def an_archive(
    at: Path,
    members: dict[str, bytes | tuple[bytes, int]],
    *,
    directory: str = "release-v1.13.1-x86_64",
) -> Path:
    """Write a tarball shaped the way upstream ships one.

    A member is either bytes, which lands runnable the way a program does, or a
    ``(bytes, mode)`` pair for the things shipped beside a program that are not
    one.
    """
    with tarfile.open(at, "w:gz") as archive:
        for name, entry in members.items():
            payload, mode = entry if isinstance(entry, tuple) else (entry, 0o755)
            info = tarfile.TarInfo(f"{directory}/{name}" if directory else name)
            info.size = len(payload)
            info.mode = mode
            archive.addfile(info, io.BytesIO(payload))
    return at


def the_usual_archive(at: Path) -> Path:
    """What v1.13.1 actually contains, in the shape it contains it.

    Every program is shipped twice -- the binary, and its detached debug
    symbols under the same name with ``.debug`` on the end and without the
    executable bit. Leaving the symbols out of this fixture is what let an
    installer that could not tell the two apart pass every test here and then
    refuse the real release on a runner.
    """
    return an_archive(
        at,
        {
            "firecracker-v1.13.1-x86_64": b"the launcher",
            "firecracker-v1.13.1-x86_64.debug": (b"where the launcher hurts", 0o644),
            "jailer-v1.13.1-x86_64": b"the thing that confines it",
            "jailer-v1.13.1-x86_64.debug": (b"where it hurts", 0o644),
            "seccompiler-bin-v1.13.1-x86_64": b"not asked for",
            "SHA256SUMS": (b"not asked for either", 0o644),
        },
    )


def a_transport(payloads: dict[str, bytes]):
    """An opener that answers from a dict, so no test reaches the network."""

    def open_it(url: str) -> io.BytesIO:
        if url not in payloads:
            raise AssertionError(f"nothing asked for {url}")
        return io.BytesIO(payloads[url])

    return open_it


def a_release_on_the_wire(tarball: bytes, *, digest: str | None = None) -> dict:
    said = digest if digest is not None else hashlib.sha256(tarball).hexdigest()
    return {
        str(PINNED_FIRECRACKER_RELEASE["url"]): tarball,
        str(PINNED_FIRECRACKER_RELEASE["checksum_url"]): (
            f"{said}  {PINNED_FIRECRACKER_RELEASE['asset']}\n".encode()
        ),
    }


# ── the pin itself ────────────────────────────────────────────────────────


def test_one_tag_is_named_everywhere_the_release_is_addressed() -> None:
    """A tag that agrees with itself in two places and not the third installs
    the asset of one release checked against the digest of another."""
    tag = str(PINNED_FIRECRACKER_RELEASE["tag"])

    assert tag == "v1.13.1", (
        "every launcher flag was read from this tag; moving it is a change to "
        "the launcher, not a version bump"
    )
    for field in ("asset", "url", "checksum_url"):
        assert tag in str(PINNED_FIRECRACKER_RELEASE[field]), field


def test_the_digest_is_not_called_provenance() -> None:
    """It comes from the same release by the same host, and upstream signs
    nothing, so the record says which of the two it is."""
    assert PINNED_FIRECRACKER_RELEASE["upstream_publishes_a_checksum"] is True
    assert PINNED_FIRECRACKER_RELEASE["checksum_comes_from_the_same_release"] is True
    assert PINNED_FIRECRACKER_RELEASE["upstream_publishes_a_signature"] is False


def test_the_names_are_the_ones_the_first_boot_looks_for() -> None:
    """``shutil.which`` answers to a name, and the release ships neither of them.

    The archive suffixes both programs with the tag and the architecture. If the
    installer kept those names, ``read_the_host`` would find nothing and the
    boot would refuse for a reason that reads like a missing package.
    """
    source = FIRST_BOOT.read_text(encoding="utf-8")

    for program in PROGRAMS:
        assert f'shutil.which("{program}")' in source, (
            f"{program} is installed under that name because that is the name "
            "run_agentic_c2_first_boot.py asks the path for"
        )


# ── fetching ──────────────────────────────────────────────────────────────


def test_a_download_that_matches_the_published_digest_is_kept(tmp_path: Path) -> None:
    tarball = the_usual_archive(tmp_path / "source.tgz").read_bytes()

    record = fetch_release(
        tmp_path / "into", opener=a_transport(a_release_on_the_wire(tarball))
    )

    assert record["sha256"] == hashlib.sha256(tarball).hexdigest()
    assert record["checksum_matched_the_published_one"] is True
    assert record["size_bytes"] == len(tarball)
    assert record["tag"] == PINNED_FIRECRACKER_RELEASE["tag"]
    assert Path(record["path"]).read_bytes() == tarball


def test_the_record_says_what_the_match_does_not_mean(tmp_path: Path) -> None:
    """Whoever reads the report should not have to know this to know it."""
    tarball = the_usual_archive(tmp_path / "source.tgz").read_bytes()

    record = fetch_release(
        tmp_path / "into", opener=a_transport(a_release_on_the_wire(tarball))
    )

    assert "provenance" in record["what_that_does_not_mean"]
    assert "no signature" in record["what_that_does_not_mean"]


def test_a_different_file_is_refused_rather_than_installed(tmp_path: Path) -> None:
    tarball = the_usual_archive(tmp_path / "source.tgz").read_bytes()
    lie = "0" * 64

    with pytest.raises(ReleaseRefused) as refusal:
        fetch_release(
            tmp_path / "into",
            opener=a_transport(a_release_on_the_wire(tarball, digest=lie)),
        )

    said = str(refusal.value)
    assert hashlib.sha256(tarball).hexdigest() in said
    assert lie in said, "both digests, so a reader can tell which one moved"


def test_a_checksum_file_with_nothing_in_it_is_refused(tmp_path: Path) -> None:
    """An empty answer is not agreement; it is nothing to compare against."""
    tarball = the_usual_archive(tmp_path / "source.tgz").read_bytes()
    wire = a_release_on_the_wire(tarball)
    wire[str(PINNED_FIRECRACKER_RELEASE["checksum_url"])] = b"   \n"

    with pytest.raises(ReleaseRefused, match="carried no digest"):
        fetch_release(tmp_path / "into", opener=a_transport(wire))


def test_the_digest_is_read_out_of_the_sha256sum_layout(tmp_path: Path) -> None:
    """Upstream publishes ``<digest>  <filename>``, not a bare digest."""
    tarball = the_usual_archive(tmp_path / "source.tgz").read_bytes()
    seen = hashlib.sha256(tarball).hexdigest()
    wire = a_release_on_the_wire(tarball)
    wire[str(PINNED_FIRECRACKER_RELEASE["checksum_url"])] = (
        f"{seen.upper()}  release/{PINNED_FIRECRACKER_RELEASE['asset']}\n".encode()
    )

    record = fetch_release(tmp_path / "into", opener=a_transport(wire))

    assert record["sha256"] == seen


def test_the_programs_are_not_fetched_over_a_channel_that_can_be_rewritten(
    tmp_path: Path,
) -> None:
    """A digest check confirms whatever arrived, including what was substituted."""
    elsewhere = dict(PINNED_FIRECRACKER_RELEASE)
    elsewhere["url"] = "http://releases.example/firecracker-v1.13.1-x86_64.tgz"

    with pytest.raises(ReleaseRefused, match="is not https"):
        fetch_release(
            tmp_path / "into",
            release=elsewhere,
            opener=a_transport({str(elsewhere["url"]): b"anything"}),
        )


# ── unpacking ─────────────────────────────────────────────────────────────


def test_both_programs_land_under_the_names_that_will_be_looked_up(
    tmp_path: Path,
) -> None:
    tarball = the_usual_archive(tmp_path / "source.tgz")

    installed = unpack_programs(tarball, tmp_path / "bin")

    assert set(installed) == set(PROGRAMS)
    assert (tmp_path / "bin" / "firecracker").read_bytes() == b"the launcher"
    assert (tmp_path / "bin" / "jailer").read_bytes() == b"the thing that confines it"
    for program in PROGRAMS:
        assert installed[program]["came_from"].endswith(f"{program}-v1.13.1-x86_64")


def test_what_was_installed_is_recorded_by_digest(tmp_path: Path) -> None:
    """The tarball's digest says nothing about which member came out of it."""
    tarball = the_usual_archive(tmp_path / "source.tgz")

    installed = unpack_programs(tarball, tmp_path / "bin")

    assert installed["firecracker"]["sha256"] == hashlib.sha256(
        b"the launcher"
    ).hexdigest()
    assert installed["jailer"]["size_bytes"] == len(b"the thing that confines it")


def test_the_programs_are_left_runnable(tmp_path: Path) -> None:
    """A tar member's mode is upstream's to change, and the jailer is exec'd."""
    tarball = the_usual_archive(tmp_path / "source.tgz")

    unpack_programs(tarball, tmp_path / "bin")

    for program in PROGRAMS:
        assert (tmp_path / "bin" / program).stat().st_mode & 0o111


def test_an_archive_missing_a_program_is_a_sentence_not_a_keyerror(
    tmp_path: Path,
) -> None:
    tarball = an_archive(
        tmp_path / "source.tgz", {"firecracker-v1.13.1-x86_64": b"alone"}
    )

    with pytest.raises(ReleaseRefused, match="looking for one runnable jailer"):
        unpack_programs(tarball, tmp_path / "bin")


def test_an_archive_offering_two_of_a_program_is_refused(tmp_path: Path) -> None:
    """Which one it meant is not a question an installer should answer."""
    tarball = an_archive(
        tmp_path / "source.tgz",
        {
            "firecracker-v1.13.1-x86_64": b"one",
            "firecracker-v1.13.1-x86_64-debug": b"two",
            "jailer-v1.13.1-x86_64": b"the other program",
        },
    )

    with pytest.raises(ReleaseRefused, match="looking for one runnable firecracker"):
        unpack_programs(tarball, tmp_path / "bin")


def test_the_symbols_shipped_beside_a_program_are_not_mistaken_for_it(
    tmp_path: Path,
) -> None:
    """The failure this test exists for was observed, not imagined.

    Run 35082237811 refused v1.13.1 on a GitHub runner -- the release laid out
    exactly as upstream publishes it -- because the prefix ``firecracker-``
    matched both the binary and its ``.debug`` symbols and two is not one. The
    programs are told apart by the executable bit rather than by the suffix,
    because the suffix is the part upstream is free to change again.
    """
    tarball = an_archive(
        tmp_path / "source.tgz",
        {
            "firecracker-v1.13.1-x86_64": b"the launcher",
            "firecracker-v1.13.1-x86_64.debug": (b"symbols", 0o644),
            "jailer-v1.13.1-x86_64": b"the jailer",
            "jailer-v1.13.1-x86_64.debug": (b"symbols too", 0o644),
        },
    )

    found = unpack_programs(tarball, tmp_path / "bin")

    assert found["firecracker"]["came_from"].endswith("firecracker-v1.13.1-x86_64")
    assert found["jailer"]["came_from"].endswith("jailer-v1.13.1-x86_64")
    assert (tmp_path / "bin" / "firecracker").read_bytes() == b"the launcher"
    assert (tmp_path / "bin" / "jailer").read_bytes() == b"the jailer"


def test_the_digest_recorded_is_the_programs_and_not_the_symbols(
    tmp_path: Path,
) -> None:
    """Taking the wrong member of the pair would still produce a digest.

    Both files are real and both hash to something, so a record that named the
    symbols would look exactly as complete as one that named the binary. The
    check is that the digest is of what will actually be exec'd.
    """
    tarball = the_usual_archive(tmp_path / "source.tgz")

    found = unpack_programs(tarball, tmp_path / "bin")

    for program, payload in (
        ("firecracker", b"the launcher"),
        ("jailer", b"the thing that confines it"),
    ):
        assert found[program]["sha256"] == hashlib.sha256(payload).hexdigest()
        assert found[program]["size_bytes"] == len(payload)


def test_a_program_shipped_without_the_executable_bit_is_refused_and_named(
    tmp_path: Path,
) -> None:
    """The mode is upstream's to change too, so this has to fail readably.

    If a later release stops marking the binary runnable, the prefix still
    matches and the mode filter then finds nothing. Reporting only the empty
    list would send whoever reads it looking for a member that is right there.
    """
    tarball = an_archive(
        tmp_path / "source.tgz",
        {
            "firecracker-v1.13.1-x86_64": (b"not marked runnable", 0o644),
            "jailer-v1.13.1-x86_64": b"the other program",
        },
    )

    with pytest.raises(ReleaseRefused) as refusal:
        unpack_programs(tarball, tmp_path / "bin")

    said = str(refusal.value)
    assert "looking for one runnable firecracker" in said
    assert "not runnable, so not considered" in said
    assert "firecracker-v1.13.1-x86_64" in said


def test_a_member_name_cannot_choose_where_it_is_written(tmp_path: Path) -> None:
    """Members are found by name and written to a path this code builds.

    ``extractall`` would honour ``../`` in a member name and write outside the
    directory it was given. Nothing here passes a member name to the filesystem,
    so a hostile archive lands where an honest one does, and the digest check
    above is what decides whether it should have arrived at all.
    """
    tarball = an_archive(
        tmp_path / "source.tgz",
        {"firecracker-x": b"escapes", "jailer-x": b"escapes too"},
        directory="../../..",
    )
    bin_dir = tmp_path / "bin"

    unpack_programs(tarball, bin_dir)

    assert sorted(path.name for path in bin_dir.iterdir()) == ["firecracker", "jailer"]
    assert not (tmp_path.parent / "firecracker").exists()


# ── the script that runs the two of them on a runner ──────────────────────


def test_the_script_lays_both_programs_out_and_says_what_is_missing(
    tmp_path: Path,
) -> None:
    """Being on disk is not being on the program search path, and the record
    says so rather than letting the caller assume the install finished."""
    tarball = the_usual_archive(tmp_path / "source.tgz").read_bytes()
    into = tmp_path / "fc"

    record = installer.install(
        into,
        work=tmp_path / "download",
        opener=a_transport(a_release_on_the_wire(tarball)),
    )

    assert sorted(record["installed"]) == ["firecracker", "jailer"]
    for program in PROGRAMS:
        assert (into / program).is_file()
    assert "shutil.which" in record["what_is_still_needed"]
    assert record["release"]["tag"] == PINNED_FIRECRACKER_RELEASE["tag"]


def test_the_report_names_both_digests(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The one upstream published and the one each program actually has. A
    report that prints only the first is a report that would look identical if
    the archive had been laid out differently inside."""
    tarball = the_usual_archive(tmp_path / "source.tgz").read_bytes()

    record = installer.install(
        tmp_path / "fc",
        work=tmp_path / "download",
        opener=a_transport(a_release_on_the_wire(tarball)),
    )
    installer.report(record)

    printed = capsys.readouterr().out
    assert record["release"]["sha256"] in printed
    for program in PROGRAMS:
        assert record["installed"][program]["sha256"] in printed


def test_a_refused_release_exits_nonzero_and_says_nothing_was_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The next step is ``sudo install`` from this directory. If it runs anyway
    it copies whatever is there, which on a refusal is either nothing or half a
    release -- so the exit code has to be the thing that stops it."""

    def refuse(*_args, **_kwargs):
        raise ReleaseRefused("the published digest names a different file")

    monkeypatch.setattr(installer, "install", refuse)

    code = installer.main(["--into", (tmp_path / "fc").as_posix()])

    assert code == 1
    stderr = capsys.readouterr().err
    assert "nothing was installed" in stderr
    assert str(PINNED_FIRECRACKER_RELEASE["tag"]) in stderr
