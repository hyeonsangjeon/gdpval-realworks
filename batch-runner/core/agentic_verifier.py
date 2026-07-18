"""No-network verifier-container entrypoint for private artifact snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path

from core.artifact_verifier import verify_artifacts
from core.deliverable_contract import infer_deliverable_contract, validate_contract
from core.output_qa import run_output_qa


SNAPSHOT_ROOT = Path("/snapshot")
MAX_FILES = 64
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_SINGLE_BYTES = 256 * 1024 * 1024
MAX_DEPTH = 16
MAX_PATH_BYTES = 240


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_files() -> list[Path]:
    files: list[Path] = []
    total = 0
    for path in sorted(SNAPSHOT_ROOT.rglob("*")):
        relative = path.relative_to(SNAPSHOT_ROOT)
        if any(part.startswith(".") for part in relative.parts):
            continue
        encoded = relative.as_posix().encode("utf-8")
        if len(relative.parts) > MAX_DEPTH or len(encoded) > MAX_PATH_BYTES:
            raise ValueError("artifact_path_limit")
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError("artifact_type_or_link_violation")
        if metadata.st_size <= 0 or metadata.st_size > MAX_SINGLE_BYTES:
            raise ValueError("artifact_size_limit")
        total += metadata.st_size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("artifact_total_size_limit")
        files.append(path)
        if len(files) > MAX_FILES:
            raise ValueError("artifact_file_count_limit")
    return files


def verify(payload: dict) -> dict:
    if not isinstance(payload, dict) or not set(payload) <= {
        "task_prompt", "reference_hashes", "selected_deliverables"
    }:
        return {"ok": False, "error_type": "invalid_verifier_request"}
    task_prompt = payload.get("task_prompt")
    reference_hashes = set(payload.get("reference_hashes") or [])
    if not isinstance(task_prompt, str):
        return {"ok": False, "error_type": "invalid_verifier_request"}
    files = _strict_files()
    if not files:
        return {"ok": False, "error_type": "no_artifacts"}

    selected = payload.get("selected_deliverables")
    if selected is not None:
        if not isinstance(selected, list) or not selected:
            return {"ok": False, "error_type": "invalid_selected_deliverables"}
        by_name = {
            path.relative_to(SNAPSHOT_ROOT).as_posix(): path for path in files
        }
        normalized = []
        for value in selected:
            if not isinstance(value, str) or "\\" in value:
                return {"ok": False, "error_type": "invalid_selected_deliverables"}
            relative = Path(value)
            if (
                relative.is_absolute()
                or not relative.parts
                or relative.as_posix() != value
                or ".." in relative.parts
                or any(part.startswith(".") for part in relative.parts)
                or value not in by_name
                or value in normalized
            ):
                return {"ok": False, "error_type": "invalid_selected_deliverables"}
            normalized.append(value)
        files = [by_name[value] for value in normalized]

    copied_inputs = [path for path in files if _sha256(path) in reference_hashes]
    if copied_inputs:
        return {"ok": False, "error_type": "copied_input"}

    contract = infer_deliverable_contract(task_prompt, [])
    contract_report = validate_contract(contract, files)
    verification = verify_artifacts(files, contract=contract, workdir=SNAPSHOT_ROOT)
    output_qa = run_output_qa(
        files,
        contract=contract,
        config={
            "enabled": True,
            "render": True,
            "max_pages_per_artifact": 3,
            "blank_page_threshold": 0.999,
            "vision": {"enabled": False},
        },
        out_dir=Path("/verify-work/render"),
        task_text=task_prompt,
    )
    uncertain = any(report.openable is None for report in verification.artifacts)
    ok = (
        contract_report.ok
        and verification.ok
        and output_qa.ok
        and not uncertain
    )
    return {
        "ok": ok,
        "error_type": None if ok else "artifact_verification_failed",
        "data": {
            "artifact_count": len(files),
            "artifacts": [
                {
                    "path": path.relative_to(SNAPSHOT_ROOT).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                    "kind": report.kind,
                    "openable": report.openable,
                }
                for path, report in zip(files, verification.artifacts)
            ],
            "contract": contract_report.to_dict(),
            "blocking_error_count": (
                len(contract_report.blocking_errors)
                + len(verification.blocking_errors)
                + len(output_qa.blocking_errors)
                + int(uncertain)
            ),
            "warning_count": (
                len(contract_report.warnings)
                + len(verification.warnings)
                + len(output_qa.warnings)
            ),
        },
    }


def main() -> None:
    if os.geteuid() == 0:
        raise SystemExit("verifier refuses UID 0")
    try:
        for relative in (".home", ".tmp", ".cache", ".config"):
            (Path("/verify-work") / relative).mkdir(
                mode=0o700, parents=True, exist_ok=True
            )
        payload = json.loads(sys.stdin.buffer.read(131073))
        result = verify(payload)
        encoded = json.dumps(
            result, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        if len(encoded) > 32768:
            encoded = b'{"ok":false,"error_type":"verifier_result_too_large"}'
        sys.stdout.buffer.write(encoded)
    except Exception:
        sys.stdout.write('{"ok":false,"error_type":"verifier_internal_error"}')


if __name__ == "__main__":
    main()