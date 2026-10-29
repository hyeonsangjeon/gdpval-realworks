"""Observe the allowed GHCP execution host without credentials or subprocesses.

Runner environment plus the actual OS release is a fail-closed operational
check, not cryptographic attestation. Local/NAS use is development/dry-run only.
"""

from __future__ import annotations

import json
import os
import platform
import re

EXECUTION_TARGET = "GitHub-hosted Actions runner ubuntu-24.04"
REFUSAL = "execution_environment_refused"


def _os_release():
    return platform.freedesktop_os_release()


def _text(value, pattern=r"[A-Za-z0-9 _./:-]{1,128}"):
    return value if type(value) is str and re.fullmatch(pattern, value) else None


def observe():
    """Read only allowlisted nonsecret metadata; unknown values cannot admit."""
    record = {
        "github_actions": None,
        "runner_environment": None,
        "runner_name": None,
        "runner_os": None,
        "image_os": None,
        "image_version": None,
        "os_id": None,
        "os_version_id": None,
        "platform_system": None,
        "eligible_for_execution": False,
        "local_use_policy": "dry_run_and_development_only",
        "evidence_boundary": "observed_runner_metadata_not_cryptographic_attestation",
    }
    try:
        for field, name in (
            ("github_actions", "GITHUB_ACTIONS"),
            ("runner_environment", "RUNNER_ENVIRONMENT"),
            ("runner_name", "RUNNER_NAME"),
            ("runner_os", "RUNNER_OS"),
            ("image_os", "ImageOS"),
        ):
            record[field] = _text(os.environ.get(name))
        record["image_version"] = _text(os.environ.get("ImageVersion"), r"[0-9]{8}\.[0-9]+(?:\.[0-9]+)?")
        release = _os_release()
        record["os_id"] = _text(release.get("ID"))
        record["os_version_id"] = _text(release.get("VERSION_ID"))
        record["platform_system"] = _text(platform.system())
    except Exception:
        # No exception message, arbitrary environment dump, or permissive fallback.
        return record
    record["eligible_for_execution"] = bool(
        record["github_actions"] == "true"
        and record["runner_environment"] == "github-hosted"
        and record["runner_os"] == record["platform_system"] == "Linux"
        and record["image_os"] == "ubuntu24"
        and record["os_id"] == "ubuntu"
        and record["os_version_id"] == "24.04"
        and record["runner_name"] and record["image_version"]
    )
    return record


def main():
    record = observe()
    print(json.dumps(record, sort_keys=True, allow_nan=False))
    return 0 if record["eligible_for_execution"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
