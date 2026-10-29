"""Credential-free execution-host admission and hash-bound runner receipts.

Reuse GHCP's allowlisted labels plus actual OS-release check. GitHub-hosted
execution is pinned to Ubuntu 24.04; an explicitly approved Azure VM keeps its
separate admission rule. Sandbox readiness must also pass in the calling job.
Labels/DMI are operational evidence, not cryptographic host attestation.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
from pathlib import Path

REFUSED = "execution_environment_refused"
CHANGED = "execution_environment_changed"
STOPS = frozenset({REFUSED, CHANGED})
UBUNTU_IMAGES = {"24.04": "ubuntu24"}
AZURE_UBUNTU_VERSIONS = frozenset({"22.04", "24.04"})
ARCHITECTURES = {"x86_64": "X64", "aarch64": "ARM64"}


def _text(value, pattern=r"[A-Za-z0-9 _./:-]{1,128}"):
    return value if type(value) is str and re.fullmatch(pattern, value) else None


def _azure_dmi():
    try:
        vendor = Path("/sys/class/dmi/id/sys_vendor").read_text().strip()
        vm_id = Path("/sys/class/dmi/id/product_uuid").read_text().strip().lower()
    except OSError:
        return None
    return vm_id if vendor == "Microsoft Corporation" and re.fullmatch(r"[0-9a-f-]{36}", vm_id) else None


def observe():
    value = {key: None for key in (
        "github_actions", "runner_environment", "runner_name", "runner_os", "runner_arch",
        "image_os", "image_version", "run_id", "run_attempt", "os_id", "os_version_id",
        "platform_system", "platform_machine", "azure_vm_id", "azure_vm_approval_sha256")}
    value.update(github_hosted=False, approved_azure_vm=False, eligible_for_execution=False,
                 local_use_policy="dry_run_and_development_only",
                 evidence_boundary="observed_metadata_not_cryptographic_host_attestation")
    try:
        for field, name in (
            ("github_actions", "GITHUB_ACTIONS"), ("runner_environment", "RUNNER_ENVIRONMENT"),
            ("runner_name", "RUNNER_NAME"), ("runner_os", "RUNNER_OS"), ("runner_arch", "RUNNER_ARCH"),
            ("image_os", "ImageOS"),
        ):
            value[field] = _text(os.environ.get(name))
        value["image_version"] = _text(os.environ.get("ImageVersion"), r"[0-9]{8}\.[0-9]+(?:\.[0-9]+)?")
        value["run_id"] = _text(os.environ.get("GITHUB_RUN_ID"), r"[1-9][0-9]{0,19}")
        value["run_attempt"] = _text(os.environ.get("GITHUB_RUN_ATTEMPT"), r"[1-9][0-9]{0,5}")
        release = platform.freedesktop_os_release()
        value["os_id"] = _text(release.get("ID"))
        value["os_version_id"] = _text(release.get("VERSION_ID"))
        value["platform_system"] = _text(platform.system())
        value["platform_machine"] = _text(platform.machine())
        ubuntu = (value["platform_system"] == "Linux" and value["os_id"] == "ubuntu"
                  and value["os_version_id"] in AZURE_UBUNTU_VERSIONS
                  and value["platform_machine"] in ARCHITECTURES)
        value["github_hosted"] = bool(value["github_actions"] == "true"
                                       and value["runner_environment"] == "github-hosted")
        hosted = bool(ubuntu and value["os_version_id"] in UBUNTU_IMAGES
                      and value["github_hosted"] and value["runner_os"] == "Linux"
                      and value["runner_arch"] == ARCHITECTURES[value["platform_machine"]]
                      and value["image_os"] == UBUNTU_IMAGES[value["os_version_id"]]
                      and value["image_version"] and value["runner_name"]
                      and value["run_id"] and value["run_attempt"])
        # No default VM approval; do not query Azure/IMDS or inspect credentials.
        if os.environ.get("NATIVE_AZURE_VM_APPROVAL") == "owner-approved":
            value["azure_vm_approval_sha256"] = _text(os.environ.get("NATIVE_AZURE_VM_APPROVAL_SHA256"), r"[0-9a-f]{64}")
            value["azure_vm_id"] = _text(os.environ.get("NATIVE_AZURE_VM_ID"), r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
            value["approved_azure_vm"] = bool(ubuntu and value["github_actions"] != "true"
                and value["runner_environment"] is None and value["azure_vm_approval_sha256"]
                and value["azure_vm_id"] and _azure_dmi() == value["azure_vm_id"])
        value["eligible_for_execution"] = hosted or value["approved_azure_vm"]
    except Exception:
        value["eligible_for_execution"] = False
    return value


class ExecutionEnvironmentRefused(RuntimeError):
    def __init__(self, code, observation):
        self.code = code
        self.observation = observation
        super().__init__(code)


def require_execution(expected=None):
    current = observe()
    if not current["eligible_for_execution"]:
        raise ExecutionEnvironmentRefused(REFUSED, current)
    if expected is not None and current != expected:
        raise ExecutionEnvironmentRefused(CHANGED, current)
    return current


def receipt(stage, observation=None):
    if stage not in {"diagnostic", "inference", "grading"}:
        raise ValueError("runner_receipt_stage_refused")
    body = {"schema_version": "native-runner-evidence-v1", "stage": stage,
            "observation": observe() if observation is None else observation}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {**body, "sha256": hashlib.sha256(raw).hexdigest()}


def validate_receipt(value):
    if type(value) is not dict or set(value) != {"schema_version", "stage", "observation", "sha256"}:
        raise ValueError("runner_receipt_refused")
    observed = value["observation"]
    template = observe()
    bool_fields = {"github_hosted", "approved_azure_vm", "eligible_for_execution"}
    if (type(observed) is not dict or observed.keys() != template.keys()
            or value != receipt(value["stage"], observed)
            or any(type(observed[key]) is not bool for key in bool_fields)
            or any(item is not None and _text(item) != item
                   for key, item in observed.items() if key not in bool_fields)):
        raise ValueError("runner_receipt_refused")


class GradingEnvironmentStopped(BaseException):
    """Must not be converted to judge_error or a smaller score denominator."""
    def __init__(self, error):
        self.code = error.code
        self.runner_evidence = receipt("grading", error.observation)
        super().__init__(self.code)


class GuardedGradingClient:
    """Guard each grader/perception/retry request, even without a cost recorder."""
    def __init__(self, inner, observation=None):
        self._inner = inner
        self._observation = observe() if observation is None else observation

    def _invoke(self, call, kwargs):
        try:
            require_execution(self._observation)
        except ExecutionEnvironmentRefused as error:
            raise GradingEnvironmentStopped(error) from None
        return call(**kwargs)

    def __getattr__(self, name):
        inner = getattr(self._inner, name)
        if name == "responses":
            return _Endpoint(inner, self)
        if name == "chat":
            return _Chat(inner, self)
        if name == "chat_complete":
            return lambda **kwargs: self._invoke(inner, kwargs)
        if name == "with_options":
            return lambda **kwargs: GuardedGradingClient(inner(**kwargs), self._observation)
        return inner


class _Endpoint:
    def __init__(self, inner, owner):
        self._inner, self._owner = inner, owner

    def __getattr__(self, name):
        method = getattr(self._inner, name)
        if name in {"create", "parse", "stream"}:
            return lambda **kwargs: self._owner._invoke(method, kwargs)
        return method


class _Chat:
    def __init__(self, inner, owner):
        self._inner, self._owner = inner, owner

    @property
    def completions(self):
        return _Endpoint(self._inner.completions, self._owner)
