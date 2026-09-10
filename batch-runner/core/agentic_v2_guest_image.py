"""The two images a guest boots from, and where each of them came from.

A Firecracker machine needs a ``vmlinux`` and a root filesystem. Neither is an
OCI image, so ``security/agentic-v2-supply-chain-policy.json`` — which is
written for OCI images, asks for ``oci_layout`` as evidence and names a
``dockerfile`` among its provenance subjects — does not reach either of them as
written. That is a statement about the shape of the artefacts, not about the
strength of the policy.

The answer that keeps the chain intact is to build the root filesystem *from*
the image the policy already governs, so that what boots is what was signed,
scanned and attested rather than a second filesystem assembled beside it. That
is what :func:`pull_image_by_digest` and :func:`unpack_layers` do: every blob is
checked against the digest that named it before a single byte of it is used,
and the layers are applied in the order the manifest lists them.

**The kernel has no such parent, and this module says so rather than implying
otherwise.** It comes from Firecracker's own CI bucket, pinned to
:data:`PINNED_GUEST_KERNEL`. Three things about that source are recorded in the
data itself, because each of them is the kind of fact that quietly disappears
when only a hash is written down:

*Upstream publishes no checksum and no signature for these files.* The
getting-started guide's verification step prints filenames. The bucket's ETag
for this object is a multipart tag and is not a hash of the content. So the
digest this module enforces is one **we** computed on download. It proves the
file did not change between that download and this boot. It does not mean
anybody vouched for it, and :func:`fetch_pinned_kernel` returns
``vouched_for_by_upstream: False`` so that no caller can print a hash beside the
word "verified" and leave a reader to assume a signature was checked.

*The bucket listing that would find this key is fetched over plain ``http``.*
So the key is pinned here in full rather than discovered, which also stops
``sort -V | tail -1`` from changing the guest kernel underneath the containment
tests without anything saying so.

*Its validated support window has already lapsed.* Firecracker's
``docs/kernel-policy.md`` at v1.13.1 validates two guest kernels; 6.1's minimum
end-of-support date is 2026-09-02. The other, 5.10, expired in 2024. This is
recorded as lapsed rather than pinned in silence.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

A_MEBIBYTE = 1024 * 1024

PINNED_GUEST_KERNEL: dict[str, Any] = {
    "url": (
        "https://s3.amazonaws.com/spec.ccfc.min/"
        "firecracker-ci/v1.13/x86_64/vmlinux-6.1.141"
    ),
    "bucket": "spec.ccfc.min",
    "key": "firecracker-ci/v1.13/x86_64/vmlinux-6.1.141",
    "version": "6.1.141",
    "size_bytes": 41865904,
    "published": "2025-08-12",
    "validated_by": "firecracker docs/kernel-policy.md at tag v1.13.1",
    "minimum_end_of_support": "2026-09-02",
    "support_window_has_lapsed": True,
    "upstream_publishes_a_checksum": False,
    "upstream_publishes_a_signature": False,
}
"""One exact object, not the discovery upstream's guide performs.

``size_bytes`` is checked on download. It is a shape check and nothing more —
a wrong file of the right length would pass it — which is why the digest is
what gets recorded and enforced afterwards.
"""

GUEST_INIT_PATH = "/gdpval-init"

GUEST_INIT = """#!/bin/sh
# PID 1 in the guest. There is no console: the launcher passes --daemonize,
# which points Firecracker's standard descriptors at /dev/null, so everything
# this script has to say it says on the work disk.
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PATH
mount -t proc proc /proc 2>/dev/null
mount -t sysfs sys /sys 2>/dev/null
mount -t devtmpfs dev /dev 2>/dev/null
mkdir -p /work
mount -t ext4 /dev/vdb /work
mkdir -p /work/out
uname -r > /work/out/guest_kernel 2>/dev/null
id -u > /work/out/guest_uid 2>/dev/null
sh /work/in/command.sh > /work/out/stdout 2> /work/out/stderr
echo $? > /work/out/exit_status
echo done > /work/out/init_reached_the_end
sync
umount /work 2>/dev/null
sync
# Reset through the i8042 controller, which is what boot_args' reboot=k selects
# and what makes Firecracker exit rather than sit on a halted guest.
reboot -f 2>/dev/null
echo b > /proc/sysrq-trigger 2>/dev/null
while true; do sleep 1; done
"""
"""The one file added to the image's own layers, recorded in full in the artefact.

It is deliberately dull. Anything clever here would be a second thing to
distrust when a boot produces nothing, and a boot producing nothing is the
failure mode this stage has to be able to tell apart from a boot that worked.
"""

_MANIFEST_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)

_INDEX_TYPES = frozenset(
    {
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
    }
)

_EXTRACTION_FILTER: dict[str, str] = (
    {"filter": "tar"} if hasattr(tarfile, "data_filter") else {}
)
"""CPython's own extraction filter, where the running interpreter has one.

``tar`` rather than ``data``: ``data`` refuses device nodes and absolute
symbolic-link targets, and a root filesystem legitimately contains both, so it
would reject images this is meant to boot. ``tar`` blocks what is dangerous —
absolute paths, traversal, and a destination that escapes *after* symbolic links
are followed — and that last one is the same defence :func:`_refuse_symlinked_parents`
implements, kept as well because the filter is absent on older interpreters.

Presence is detected through :data:`tarfile.data_filter` rather than a version
comparison: the ``filter`` parameter arrived in 3.12 and was backported into
security releases of four earlier branches, so the version number does not
answer the question and the attribute does.
"""


class ImageRefused(RuntimeError):
    """An image or kernel was not what its digest said it would be."""


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _http_get(url: str, headers: Mapping[str, str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers=dict(headers or {}))
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
        return response.read()


def fetch_pinned_kernel(
    destination: str | Path,
    *,
    fetch: Callable[[str, Mapping[str, str] | None], bytes] = _http_get,
    pinned: Mapping[str, Any] = PINNED_GUEST_KERNEL,
) -> dict[str, Any]:
    """Download the one pinned kernel and describe it, disclaimers included.

    Returns the digest it computed rather than comparing against one, because on
    a first download there is nothing to compare against — that is the whole
    content of ``upstream_publishes_a_checksum: False``. A caller that has a
    previous digest should compare, and :func:`require_same_kernel` is how.
    """
    destination = Path(destination)
    body = fetch(str(pinned["url"]), None)
    if len(body) != pinned["size_bytes"]:
        raise ImageRefused(
            f"the pinned kernel object is {pinned['size_bytes']} bytes and "
            f"{len(body)} arrived; the key names one exact object and this is "
            "not it"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)
    return {
        "path": destination.as_posix(),
        "sha256": hashlib.sha256(body).hexdigest(),
        "size_bytes": len(body),
        "source": {k: v for k, v in pinned.items() if k != "url"},
        "url": pinned["url"],
        "vouched_for_by_upstream": False,
        "what_the_digest_means": (
            "computed here on download, not published by upstream. It shows the "
            "file did not change between that download and this boot. It is not "
            "a signature and nothing upstream attests to it."
        ),
    }


def require_same_kernel(reading: Mapping[str, Any], expected_sha256: str) -> None:
    if reading["sha256"] != expected_sha256:
        raise ImageRefused(
            "the pinned kernel key now returns a different file: expected "
            f"{expected_sha256}, got {reading['sha256']}. The key is a moving "
            "target upstream and this is what pinning it is for"
        )


def anonymous_pull_token(
    repository: str,
    *,
    registry: str = "ghcr.io",
    fetch: Callable[[str, Mapping[str, str] | None], bytes] = _http_get,
) -> str:
    """A read-only token for a public repository. Issues no credential.

    ``ghcr.io/v2/`` answers 401 to an unauthenticated request even for public
    content, which reads like a permission problem and is not one: the registry
    is asking for a token it will hand out to anybody. Nothing here is stored,
    and nothing here belongs to an account.
    """
    url = (
        f"https://{registry}/token"
        f"?scope=repository:{repository}:pull&service={registry}"
    )
    return str(json.loads(fetch(url, None))["token"])


def pull_image_by_digest(
    repository: str,
    digest: str,
    destination: str | Path,
    *,
    registry: str = "ghcr.io",
    platform: str = "linux/amd64",
    token: str | None = None,
    fetch: Callable[[str, Mapping[str, str] | None], bytes] = _http_get,
) -> dict[str, Any]:
    """Fetch one image by digest and lay it out, checking every blob it takes.

    The digest may name a multi-architecture index, which is what
    ``parent.lock.json`` pins. An index digest is exact, but it does not say
    which of its children was used, so the child's digest is returned separately
    and belongs in the artefact beside it.
    """
    destination = Path(destination)
    (destination / "blobs" / "sha256").mkdir(parents=True, exist_ok=True)
    if token is None:
        token = anonymous_pull_token(repository, registry=registry, fetch=fetch)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": ",".join(_MANIFEST_TYPES),
    }

    def _manifest(reference: str) -> tuple[dict[str, Any], bytes]:
        body = fetch(
            f"https://{registry}/v2/{repository}/manifests/{reference}", headers
        )
        if reference.startswith("sha256:") and _sha256_bytes(body) != reference:
            raise ImageRefused(
                f"the registry returned a manifest whose content is not "
                f"{reference}; a digest that does not match is the one thing "
                "pinning by digest is supposed to make impossible"
            )
        return json.loads(body), body

    index_digest = None
    manifest, raw = _manifest(digest)
    if manifest.get("mediaType") in _INDEX_TYPES:
        index_digest = digest
        wanted_os, _, wanted_arch = platform.partition("/")
        children = [
            child
            for child in manifest.get("manifests", [])
            if (child.get("platform") or {}).get("architecture") == wanted_arch
            and (child.get("platform") or {}).get("os") == wanted_os
        ]
        if len(children) != 1:
            raise ImageRefused(
                f"the index names {len(children)} manifests for {platform}; "
                "one is needed and picking among several is a choice this "
                "should not be making silently"
            )
        digest = str(children[0]["digest"])
        manifest, raw = _manifest(digest)

    layers = []
    for layer in manifest.get("layers", []):
        blob_digest = str(layer["digest"])
        body = fetch(
            f"https://{registry}/v2/{repository}/blobs/{blob_digest}", headers
        )
        if _sha256_bytes(body) != blob_digest:
            raise ImageRefused(
                f"layer {blob_digest} does not hash to its own name; nothing "
                "from this image is used"
            )
        path = destination / "blobs" / "sha256" / blob_digest.split(":", 1)[1]
        path.write_bytes(body)
        layers.append(
            {
                "digest": blob_digest,
                "media_type": str(layer.get("mediaType", "")),
                "size_bytes": len(body),
                "path": path.as_posix(),
            }
        )
    if not layers:
        raise ImageRefused("the manifest lists no layers, so there is no rootfs")

    return {
        "repository": f"{registry}/{repository}",
        "pinned_digest": index_digest or digest,
        "pinned_digest_is_an_index": index_digest is not None,
        "manifest_digest": digest,
        "platform": platform,
        "layers": layers,
        "layer_count": len(layers),
        "credential_used": "none — anonymous pull token for a public repository",
    }


def _remove(path: Path) -> None:
    """Delete a path whatever it is, without following a symlink to a directory."""
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _inside_the_root(name: str, digest: str) -> str | None:
    """Where a tar member lands under the root, or ``None`` for the root itself.

    The first version of this stripped ``"./"`` off the front with
    :meth:`str.lstrip`, which was wrong in both directions and refused the real
    image on its first entry. ``lstrip`` takes a *set of characters*, so it ate
    every leading dot and slash: ``"."`` — the root entry every OCI layer starts
    with — became the empty string and was refused as an escape, while
    ``"../x"`` became ``"x"`` and ``"/etc/shadow"`` became ``"etc/shadow"``, so
    the two members the check exists to stop were the two it let through.

    :func:`os.path.normpath` is the right tool: it collapses the traversal
    first, so what is compared against ``".."`` is where the member actually
    lands rather than how it spelled itself.
    """
    if name.startswith("/") or os.path.isabs(name):
        raise ImageRefused(
            f"layer {digest} contains the absolute path {name!r}"
        )
    landing = os.path.normpath(name)
    if landing in (".", ""):
        return None
    if landing == ".." or landing.startswith(".." + os.sep):
        raise ImageRefused(
            f"layer {digest} contains {name!r}, which points outside the "
            "filesystem it describes"
        )
    return landing


def _refuse_symlinked_parents(into: Path, landing: str, digest: str) -> None:
    """Refuse a member whose parent directory is a symbolic link.

    An image can name ``etc`` as a link to ``/`` and then write ``etc/passwd``.
    Neither member escapes on its own reading, and the second one lands on the
    host's own file. Checking the parents at the moment of extraction catches it
    because the link has to exist by then for the trick to work.
    """
    current = into
    for part in Path(landing).parent.parts:
        current = current / part
        if current.is_symlink():
            raise ImageRefused(
                f"layer {digest} writes through {current.as_posix()}, which an "
                "earlier entry made a symbolic link, so the write leaves the "
                "filesystem being assembled"
            )


def unpack_layers(
    layers: Sequence[Mapping[str, Any]], into: str | Path
) -> dict[str, Any]:
    """Apply verified layers in order, honouring whiteouts, refusing escapes.

    A layer entry named ``.wh.<name>`` deletes ``<name>`` from what earlier
    layers put there, and ``.wh..wh..opq`` empties the directory it sits in.
    Skipping either would leave files in the guest that the image says are not
    in it — including, in the worst case, a file a later layer replaced for a
    reason.

    Members whose names climb out of the destination are refused rather than
    filtered, because a layer that contains one is not an image this should be
    unpacking at all.
    """
    into = Path(into)
    into.mkdir(parents=True, exist_ok=True)
    applied: list[str] = []
    directory_modes: dict[Path, int] = {}
    whiteouts = 0
    entries = 0
    for layer in layers:
        digest = str(layer["digest"])
        with tarfile.open(layer["path"], "r:*") as archive:
            for member in archive:
                landing = _inside_the_root(member.name, digest)
                if landing is None:
                    continue
                if member.islnk():
                    _inside_the_root(member.linkname, digest)
                base = os.path.basename(landing)
                if base == ".wh..wh..opq":
                    directory = into / os.path.dirname(landing)
                    if directory.is_dir() and not directory.is_symlink():
                        for child in directory.iterdir():
                            _remove(child)
                    whiteouts += 1
                    continue
                if base.startswith(".wh."):
                    _remove(into / os.path.dirname(landing) / base[len(".wh.") :])
                    whiteouts += 1
                    continue
                _refuse_symlinked_parents(into, landing, digest)
                target = into / landing
                if member.isdir() and target.is_dir() and not target.is_symlink():
                    pass
                elif target.is_symlink() or target.exists():
                    _remove(target)
                try:
                    archive.extract(member, into, set_attrs=True, **_EXTRACTION_FILTER)
                except tarfile.TarError as refused:
                    # Covers the filter's own refusals, which subclass this, and
                    # a corrupt archive. Both mean the same thing here: what
                    # came back is not the filesystem the manifest described.
                    raise ImageRefused(
                        f"layer {digest} would not extract {member.name!r}: {refused}"
                    ) from refused
                if member.isdir() and not target.is_symlink():
                    _hold_open_until_the_end(target, directory_modes)
                entries += 1
        applied.append(digest)
    restored = _restore_directory_modes(directory_modes)
    return {
        "root": into.as_posix(),
        "layers_applied_in_order": applied,
        "entries_written": entries,
        "whiteouts_honoured": whiteouts,
        "directory_modes_restored": restored,
        "extraction_filter": _EXTRACTION_FILTER.get("filter", "none available"),
        "what_the_filter_changed": (
            "the tar filter clears setuid, setgid and sticky bits. Nothing in "
            "this guest depends on them: it boots one process as root and has "
            "no second user to escalate from. Recorded because it means the "
            "unpacked tree is not byte-for-byte the image's own permissions."
        ),
    }


def _hold_open_until_the_end(directory: Path, remember: dict[Path, int]) -> None:
    """Give a freshly-extracted directory the bits needed to descend into it.

    A layer can name a directory ``0o750`` or narrower, and later entries in the
    same layer land underneath it. Extracting members one at a time — which is
    what the whiteout and escape checks above require — means that mode is in
    place before its children arrive, and the extraction of the next child then
    fails on a permission error that reads like a corrupt archive.

    :meth:`tarfile.TarFile.extractall` solves this by applying directory modes
    only after everything is written. This does the same thing, split in two so
    the recorded mode is the one the image asked for rather than the one that
    made the unpack possible.
    """
    mode = directory.stat().st_mode & 0o7777
    remember.setdefault(directory, mode)
    if mode & 0o700 != 0o700:
        directory.chmod(mode | 0o700)


def _restore_directory_modes(remembered: Mapping[Path, int]) -> int:
    """Put the image's own directory modes back, deepest first."""
    for directory in sorted(remembered, key=lambda path: len(path.parts), reverse=True):
        if directory.is_dir() and not directory.is_symlink():
            directory.chmod(remembered[directory])
    return len(remembered)


def add_guest_init(root: str | Path, *, text: str = GUEST_INIT) -> dict[str, Any]:
    """The one file that is not the image's, written where the artefact says."""
    path = Path(root) / GUEST_INIT_PATH.lstrip("/")
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return {
        "path": GUEST_INIT_PATH,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "bytes": len(text.encode("utf-8")),
        "text": text,
        "why": (
            "the rootfs is read-only and the image has no init that would run "
            "one command and stop, so exactly one file is added and its whole "
            "text is recorded here rather than described"
        ),
    }


def _directory_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            total += path.stat().st_size
    return total


def ext4_image_arguments(
    image: str | Path, *, size_mib: int, populate_from: str | Path | None
) -> list[str]:
    """``mke2fs`` arguments, built where a test can read them.

    ``-d`` populates the image from a directory without mounting anything, so no
    loop device is attached and no mount is performed. ``-F`` is needed because
    the target is a regular file rather than a block device.
    """
    argv = ["mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096"]
    if populate_from is not None:
        argv += ["-d", Path(populate_from).as_posix()]
    argv += [Path(image).as_posix(), f"{size_mib * 256}"]
    return argv


def build_ext4(
    image: str | Path,
    *,
    size_mib: int,
    populate_from: str | Path | None = None,
    run: Callable[[Sequence[str]], Any] = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    image = Path(image)
    image.parent.mkdir(parents=True, exist_ok=True)
    argv = ext4_image_arguments(image, size_mib=size_mib, populate_from=populate_from)
    runner = run or (
        lambda command: subprocess.run(  # noqa: S603
            list(command), check=True, capture_output=True, text=True, timeout=1800
        )
    )
    runner(argv)
    return {
        "path": image.as_posix(),
        "size_mib": size_mib,
        "sha256": sha256_file(image) if image.exists() else None,
        "argv": argv,
        "populated_from": (
            Path(populate_from).as_posix() if populate_from is not None else None
        ),
    }


def rootfs_size_mib(root: str | Path, *, headroom: float = 1.35, floor: int = 512) -> int:
    """How large the rootfs image has to be, with room for ext4's own overhead.

    Sized from what is actually there rather than from a constant, because the
    image this builds from is pinned by digest but is not the same size forever,
    and an image one block too small fails at ``mke2fs`` in a way that reads
    like a broken layer.
    """
    used_mib = _directory_bytes(Path(root)) // A_MEBIBYTE
    return max(floor, int(used_mib * headroom) + 128)


def read_file_out_of_ext4(
    image: str | Path,
    inside: str,
    *,
    run: Callable[[Sequence[str]], Any] = None,  # type: ignore[assignment]
) -> str | None:
    """Take one file out of an ext4 image without mounting it.

    ``debugfs`` walks the filesystem structures directly. That matters twice
    over: mounting would need privilege the jailed account does not have, and it
    would also mean trusting the guest's filesystem to the host kernel's ext4
    driver, which is a larger attack surface than reading it with a userspace
    tool.
    """
    runner = run or (
        lambda command: subprocess.run(  # noqa: S603
            list(command), check=False, capture_output=True, text=True, timeout=300
        )
    )
    result = runner(["debugfs", "-R", f"cat {inside}", Path(image).as_posix()])
    output = getattr(result, "stdout", "") or ""
    stderr = getattr(result, "stderr", "") or ""
    if "File not found" in stderr or getattr(result, "returncode", 0) not in (0, None):
        return None
    return output


def files_out_of_work_disk(
    image: str | Path, names: Iterable[str], **kwargs: Any
) -> dict[str, str | None]:
    return {name: read_file_out_of_ext4(image, name, **kwargs) for name in names}
