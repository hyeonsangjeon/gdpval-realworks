"""Compile generated Python, then irreversibly apply its syscall sandbox."""

from __future__ import annotations

import ctypes
import errno
import os
import platform
import sys


MAX_SOURCE_BYTES = 131072
PR_SET_NO_NEW_PRIVS = 38
SCMP_ACT_ALLOW = 0x7FFF0000
SCMP_ACT_ERRNO = 0x00050000
SCMP_FLTATR_CTL_TSYNC = 4
SCMP_CMP_MASKED_EQ = 7
CLONE_THREAD = 0x00010000

DENIED_SYSCALLS = (
    "execve", "execveat", "fork", "vfork", "clone3",
    "socket", "socketpair", "connect", "bind", "listen", "accept", "accept4",
    "mount", "umount2", "pivot_root", "chroot", "setns", "unshare",
    "ptrace", "process_vm_readv", "process_vm_writev",
    "kill", "tkill", "tgkill", "pidfd_send_signal",
    "add_key", "request_key", "keyctl", "bpf", "perf_event_open",
    "userfaultfd", "io_uring_setup", "io_uring_enter", "io_uring_register",
    "kexec_load", "finit_module", "init_module", "delete_module",
    "open_by_handle_at", "name_to_handle_at",
)


class ScmpArgCmp(ctypes.Structure):
    _fields_ = [
        ("arg", ctypes.c_uint),
        ("op", ctypes.c_uint),
        ("datum_a", ctypes.c_uint64),
        ("datum_b", ctypes.c_uint64),
    ]


def _install_filter() -> None:
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("unsupported seccomp architecture")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")

    seccomp = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint,
    ]
    seccomp.seccomp_rule_add.restype = ctypes.c_int
    seccomp.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint,
        ctypes.POINTER(ScmpArgCmp),
    ]
    seccomp.seccomp_rule_add_array.restype = ctypes.c_int
    seccomp.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint32]
    seccomp.seccomp_attr_set.restype = ctypes.c_int
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_load.restype = ctypes.c_int

    context = seccomp.seccomp_init(SCMP_ACT_ALLOW)
    if not context:
        raise RuntimeError("seccomp_init failed")
    deny_action = SCMP_ACT_ERRNO | errno.EPERM
    try:
        if seccomp.seccomp_attr_set(context, SCMP_FLTATR_CTL_TSYNC, 1) != 0:
            raise RuntimeError("seccomp TSYNC unavailable")
        for name in DENIED_SYSCALLS:
            number = seccomp.seccomp_syscall_resolve_name(name.encode("ascii"))
            if number < 0:
                raise RuntimeError(f"required syscall is unknown: {name}")
            if seccomp.seccomp_rule_add(context, deny_action, number, 0) != 0:
                raise RuntimeError(f"failed to deny syscall: {name}")

        clone_number = seccomp.seccomp_syscall_resolve_name(b"clone")
        if clone_number >= 0:
            comparison = ScmpArgCmp(0, SCMP_CMP_MASKED_EQ, CLONE_THREAD, 0)
            if seccomp.seccomp_rule_add_array(
                context, deny_action, clone_number, 1, ctypes.byref(comparison)
            ) != 0:
                raise RuntimeError("failed to restrict clone")
        if seccomp.seccomp_load(context) != 0:
            raise RuntimeError("seccomp_load failed")
    finally:
        seccomp.seccomp_release(context)


def _verify_file_descriptors() -> None:
    descriptors = {
        descriptor: os.readlink(f"/proc/self/fd/{descriptor}")
        for descriptor in range(256)
        if os.path.lexists(f"/proc/self/fd/{descriptor}")
    }
    if set(descriptors) != {0, 1, 2}:
        raise RuntimeError("unexpected inherited file descriptor")
    if any("socket:" in target for target in descriptors.values()):
        raise RuntimeError("inherited socket")


def main() -> None:
    if os.geteuid() == 0:
        raise SystemExit("generated Python refuses UID 0")
    source = sys.stdin.buffer.read(MAX_SOURCE_BYTES + 1)
    if len(source) > MAX_SOURCE_BYTES:
        raise SystemExit("source_too_large")
    try:
        text = source.decode("utf-8", errors="strict")
        code = compile(text, "<agentic-generated>", "exec")
    except (UnicodeDecodeError, SyntaxError) as exc:
        print(f"compile_failed:{type(exc).__name__}:{exc}", file=sys.stderr)
        raise SystemExit(2)
    os.chdir("/work")
    _verify_file_descriptors()
    _install_filter()
    globals_dict = {
        "__name__": "__main__",
        "__file__": "<agentic-generated>",
        "__package__": None,
    }
    exec(code, globals_dict, globals_dict)


if __name__ == "__main__":
    main()