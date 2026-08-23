#!/usr/bin/env python3
"""Download inference outputs from HF submission dataset.

Downloads:
- step2_inference_results.json
- exact task-scoped deliverable_files directories

Usage:
  python scripts/download_inference_from_hf.py --experiment exp998_smoke_baseline_sample --output workspace/step2_inference_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
import tempfile
import time
import types
import uuid
from pathlib import Path

import pandas as pd
import yaml
from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from huggingface_hub.errors import (
    EntryNotFoundError,
    HfHubHTTPError,
    RemoteEntryNotFoundError,
    XetDownloadError,
)

BATCH_RUNNER_ROOT = Path(__file__).resolve().parent.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))
if "core" not in sys.modules:
    core_package = types.ModuleType("core")
    core_package.__path__ = [str(BATCH_RUNNER_ROOT / "core")]
    core_package.__package__ = "core"
    sys.modules["core"] = core_package

from core.inference_manifest import (  # noqa: E402
    canonicalize_inference_payload,
    validate_inference_provenance,
    validate_local_deliverables,
)


FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
FULL_LOWER_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _hf_token() -> str | None:
    """Resolve the HF auth token from the standard env vars.

    The workflow injects ``HF_TOKEN`` for the download step, but the
    huggingface_hub auto-pickup does not always fire, so we pass it
    explicitly. Without it the requests go out anonymous (low rate
    limit) and the sequential relay trips HTTP 429 on repeated chunks.
    """
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")


# ── hub transport resilience ────────────────────────────────────────────────
# Dispatching the nine R1 shards in quick succession put nine runners onto the
# same 629-file dataset at once, and five of them died on this step with HTTP
# 429 from the xet read-token endpoint. The token was present, so this is not
# the anonymous-rate case ``_hf_token`` warns about -- it is the hub throttling
# concurrent reads of one dataset. Nothing had been spent, since the download
# runs before any model call, but five paid shards had to be re-dispatched by
# hand.
#
# ``huggingface_hub`` does ship ``http_backoff``, with defaults that are exactly
# right (``max_retries=5``, ``retry_on_status_codes=(429, 500, 502, 503, 504)``),
# but ``file_download.py`` never calls it: ``hf_hub_download`` and
# ``snapshot_download`` issue their requests through a plain session, so one 429
# ends the step. The retry has to live here.
#
# Two halves, and both are load-bearing: the stagger stops the shards colliding
# in the first place, the backoff catches the collisions it does not prevent.

#: Worth another attempt. 429 is the one that actually bit us; a hub 5xx is the
#: same kind of transient and there is no reason to treat it differently.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_DEFAULT_MAX_RETRIES = 5.0
_DEFAULT_BACKOFF_SEC = 4.0
_DEFAULT_SHARD_STAGGER_SEC = 20.0
#: One wait never exceeds this, whoever asked for it -- including the hub via
#: ``Retry-After``. A runner that sleeps for an hour is a dead runner.
_MAX_WAIT_SEC = 120.0


def _env_number(name: str, default: float, *, maximum: float) -> float:
    """Read a non-negative override, falling back to ``default`` if unusable.

    These are environment knobs rather than constants because this file is one
    of the named inputs to ``grader_source_hash`` (see ``step8_grade.py``).
    Editing it to wait longer would change the hash, and shards graded either
    side of that edit disagree at merge time -- after the spend. An env var lets
    a campaign ride out a bad hub day without touching the graded identity.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if not value == value or value < 0:  # NaN or negative
        return default
    return min(value, maximum)


def _is_transient(exc: Exception) -> bool:
    """Default-deny: only shapes known to be worth another attempt retry.

    The filter that matters is on status, not on class. ``RemoteEntryNotFoundError``
    is itself an ``HfHubHTTPError``, so a class-level rule would retry the 404
    that ``_download_or_reconstruct_inference`` relies on to fall back to the
    parquet -- turning a prompt fallback into minutes of pointless waiting, and
    hiding an actually-missing sidecar behind a retry storm. Its status is 404,
    so it is excluded here and raised on the first attempt, as are 401/403.

    Bare transport failures (a reset connection mid-snapshot) are deliberately
    not covered: catching them means importing ``httpx``, which reaches this
    process only as a transitive dependency of ``huggingface_hub`` and is not
    pinned in ``requirements.txt``. They are also not what took the shards down.
    """
    if isinstance(exc, HfHubHTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return isinstance(status, int) and status in _RETRYABLE_STATUS
    if isinstance(exc, XetDownloadError):
        # Nothing to inspect: the xet backend raises this for storage-transport
        # failures only -- a file that is genuinely absent is an
        # ``EntryNotFoundError`` -- so there is nothing here another attempt
        # cannot fix.
        return True
    return False


def _retry_after_seconds(exc: Exception) -> float | None:
    """The hub's own instruction, when it sends one, in preference to ours."""
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers is None:
        return None
    try:
        raw = headers.get("Retry-After")
    except Exception:
        return None
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except ValueError:
        # ``Retry-After`` may also be an HTTP-date. Rather than parse one, fall
        # through to our own backoff, which is the safe direction to be wrong in.
        return None
    if not value == value or value < 0:
        return None
    return min(value, _MAX_WAIT_SEC)


def _with_hub_retry(what: str, call):
    """Run one hub call, retrying it through a rate limit or a hub 5xx."""
    max_retries = int(_env_number("HF_DOWNLOAD_MAX_RETRIES", _DEFAULT_MAX_RETRIES, maximum=10))
    base = _env_number("HF_DOWNLOAD_BACKOFF_SEC", _DEFAULT_BACKOFF_SEC, maximum=_MAX_WAIT_SEC)

    for attempt in range(max_retries + 1):
        try:
            return call()
        except Exception as exc:
            if attempt >= max_retries or not _is_transient(exc):
                raise
            delay = _retry_after_seconds(exc)
            if delay is None:
                delay = min(base * (2**attempt), _MAX_WAIT_SEC)
                # Jitter, because shards that collided once will otherwise
                # collide again on the same schedule.
                delay += random.uniform(0, delay / 2)
            print(
                f"{what}: {type(exc).__name__} -- retry "
                f"{attempt + 1}/{max_retries} in {delay:.1f}s",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(delay)

    raise RuntimeError("unreachable")


def _stagger_shard_start() -> None:
    """Spread a shard fan-out out in time before its first hub request.

    Derived from the shard index rather than randomised: the spread is then
    guaranteed rather than merely likely, it reproduces on a rerun, and shard 0
    -- the canary, which runs on its own -- waits for nothing. An unsharded run
    and a local run both fall straight through.
    """
    try:
        count = int(os.environ.get("GRADE_SHARD_COUNT", "") or "1")
        index = int(os.environ.get("GRADE_SHARD_INDEX", "") or "0")
    except ValueError:
        return
    if count <= 1 or not 0 < index < count:
        return
    stride = _env_number(
        "HF_DOWNLOAD_SHARD_STAGGER_SEC",
        _DEFAULT_SHARD_STAGGER_SEC,
        maximum=_MAX_WAIT_SEC,
    )
    delay = stride * index
    if delay <= 0:
        return
    print(
        f"Staggering shard {index} of {count} by {delay:.0f}s before the first "
        "hub request",
        flush=True,
    )
    time.sleep(delay)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download step2 inference outputs from HF")
    parser.add_argument("--experiment", required=True, help="Experiment yaml name without .yaml")
    parser.add_argument("--output", required=True, help="Local output path for step2_inference_results.json")
    parser.add_argument(
        "--revision",
        default="",
        help="HF dataset revision; blank resolves main once, full commit SHAs are used directly",
    )
    parser.add_argument(
        "--expected-leading-task-id",
        action="append",
        default=[],
        help=(
            "Expected leading task ID in source order; repeat to download only "
            "an exact leading cohort"
        ),
    )
    legacy_group = parser.add_mutually_exclusive_group()
    legacy_group.add_argument(
        "--grading-config",
        help=(
            "Grading config under grading_configs/ whose pinned identity may "
            "authorize one legacy revision without a provenance sidecar"
        ),
    )
    legacy_group.add_argument(
        "--allow-legacy-missing-provenance",
        action="store_true",
        help="Allow non-publishable analysis of revisions without a provenance sidecar",
    )
    return parser.parse_args()


def resolve_repo_id(experiment: str) -> str:
    exp_path = Path("experiments") / f"{experiment}.yaml"
    data = yaml.safe_load(exp_path.read_text(encoding="utf-8"))
    source = str((data or {}).get("data", {}).get("source", "")).strip()
    if not source:
        raise ValueError("data.source is missing in experiment yaml")
    if "/" not in source:
        raise ValueError("data.source must be owner/name")
    return source


def resolve_immutable_revision(repo_id: str, revision: str = "") -> str:
    requested = revision
    if FULL_SHA_RE.fullmatch(requested):
        return requested.lower()

    # Explicitly tokenised for the same reason ``_hf_token`` exists: the
    # auto-pickup does not always fire, and this is the first hub request the
    # step makes. Leaving it anonymous puts the lowest rate limit on the call
    # that is hardest to retry usefully.
    resolved = _with_hub_retry(
        "dataset_info",
        lambda: HfApi(token=_hf_token()).dataset_info(repo_id, revision=requested or "main").sha,
    )
    if not isinstance(resolved, str) or not FULL_SHA_RE.fullmatch(resolved):
        raise ValueError(f"HF dataset revision did not resolve to a full commit SHA: {repo_id}")
    return resolved.lower()


def _load_repository_grading_config(path_value: str) -> dict:
    relative = Path(path_value)
    if (
        relative.is_absolute()
        or relative.parent != Path("grading_configs")
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml", relative.name)
    ):
        raise ValueError(
            "--grading-config must name one YAML file under grading_configs/"
        )
    config_root = (BATCH_RUNNER_ROOT / "grading_configs").resolve()
    candidate = BATCH_RUNNER_ROOT / relative
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError("--grading-config must be a regular non-symlink file")
    resolved = candidate.resolve()
    if resolved.parent != config_root or resolved != candidate.absolute():
        raise ValueError("--grading-config must remain inside grading_configs/")
    try:
        config = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("--grading-config could not be loaded") from exc
    if not isinstance(config, dict):
        raise ValueError("--grading-config must contain a YAML object")
    return config


def resolve_legacy_missing_provenance_allowance(
    config: dict,
    *,
    experiment: str,
    requested_revision: str,
    resolved_revision: str,
) -> bool:
    identity = config.get("rerun_identity")
    if not isinstance(identity, dict):
        return False
    declaration = identity.get("allow_legacy_missing_provenance")
    if declaration is None:
        return False
    if type(declaration) is not bool:
        raise ValueError(
            "rerun_identity.allow_legacy_missing_provenance must be boolean"
        )
    if declaration is False:
        return False

    task_ids = identity.get("task_ids")
    expected_count = identity.get("expected_task_count")
    if (
        not isinstance(task_ids, list)
        or not task_ids
        or len(task_ids) != len(set(task_ids))
        or type(expected_count) is not int
        or expected_count != len(task_ids)
    ):
        raise ValueError(
            "legacy missing provenance allowance requires pinned task_ids"
        )
    if identity.get("experiment_id") != experiment:
        raise ValueError(
            "legacy missing provenance allowance experiment mismatch"
        )
    pinned_revision = identity.get("inference_revision")
    if (
        not isinstance(pinned_revision, str)
        or not FULL_LOWER_SHA_RE.fullmatch(pinned_revision)
    ):
        raise ValueError(
            "legacy missing provenance allowance requires a pinned lowercase SHA"
        )
    if requested_revision != pinned_revision:
        raise ValueError(
            "legacy missing provenance allowance requested revision mismatch"
        )
    if resolved_revision != pinned_revision:
        raise ValueError(
            "legacy missing provenance allowance resolved revision mismatch"
        )
    return True


def _coerce_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, tuple):
        return [str(item) for item in value if item is not None]
    if hasattr(value, "tolist"):
        return [str(item) for item in value.tolist() if item is not None]
    try:
        if pd.isna(value):
            return []
    except Exception:
        pass
    return [str(value)] if value else []


def _build_inference_from_parquet(parquet_path: str, experiment: str, repo_id: str) -> dict:
    df = pd.read_parquet(parquet_path)
    results = []
    for row in df.to_dict("records"):
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            continue
        deliverable_files = _coerce_list(row.get("deliverable_files"))
        deliverable_text = str(row.get("deliverable_text") or "")
        results.append(
            {
                "task_id": task_id,
                "status": "success" if deliverable_files or deliverable_text else "error",
                "deliverable_text": deliverable_text,
                "deliverable_files": deliverable_files,
            }
        )

    return {
        "experiment_id": experiment,
        "source": repo_id,
        "model": "",
        "completed_at": None,
        "results": results,
    }


def _canonicalize_inference_payload(payload: object, repo_id: str, revision: str) -> dict:
    normalized = canonicalize_inference_payload(payload)
    normalized["source_repo_id"] = repo_id
    normalized["source_revision"] = revision
    normalized.setdefault("source", repo_id)
    return normalized


def _attach_inference_provenance(
    payload: dict,
    *,
    experiment: str,
    repo_id: str,
    revision: str,
    allow_legacy_missing_provenance: bool = False,
) -> dict:
    task_ids = [row["task_id"] for row in payload["results"]]
    had_embedded_routes = bool(payload.get("azure_ai_routes"))
    try:
        provenance_file = _with_hub_retry(
            "inference_provenance.json",
            lambda: hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename="inference_provenance.json",
                revision=revision,
                token=_hf_token(),
            ),
        )
    except RemoteEntryNotFoundError as exc:
        if had_embedded_routes or not allow_legacy_missing_provenance:
            raise ValueError(
                "inference route provenance sidecar is missing"
            ) from exc
        normalized = dict(payload)
        normalized["azure_ai_routes"] = []
        normalized["azure_ai_provenance_status"] = "legacy-missing"
        return normalized

    provenance = json.loads(Path(provenance_file).read_text(encoding="utf-8"))
    verified = validate_inference_provenance(
        provenance,
        experiment_id=experiment,
        source_repo_id=repo_id,
        task_ids=task_ids,
        prepared_fingerprint=payload.get("prepared_fingerprint"),
        azure_ai_routes=(
            payload["azure_ai_routes"]
            if "azure_ai_routes" in payload
            else None
        ),
        execution_mode=payload.get("execution_mode"),
    )
    normalized = dict(payload)
    normalized["prepared_fingerprint"] = verified["prepared_fingerprint"]
    normalized["azure_ai_routes"] = verified["azure_ai_routes"]
    normalized["azure_ai_provenance_status"] = "verified-sidecar"
    return normalized


def _select_expected_leading_tasks(
    payload: dict, expected_task_ids: list[str]
) -> dict:
    if not expected_task_ids:
        return payload
    if len(expected_task_ids) != len(set(expected_task_ids)):
        raise ValueError("expected leading task IDs must be unique")
    results = payload["results"]
    actual_task_ids = [
        row["task_id"] for row in results[: len(expected_task_ids)]
    ]
    if actual_task_ids != expected_task_ids:
        raise ValueError(
            "expected leading task IDs do not match source order: "
            f"expected={expected_task_ids}, actual={actual_task_ids}"
        )
    selected = dict(payload)
    selected["results"] = results[: len(expected_task_ids)]
    return selected


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _download_or_reconstruct_inference(
    experiment: str,
    repo_id: str,
    revision: str,
    out: Path,
    *,
    allow_legacy_missing_provenance: bool = False,
) -> None:
    token = _hf_token()
    try:
        step2_file = _with_hub_retry(
            "step2_inference_results.json",
            lambda: hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename="step2_inference_results.json",
                revision=revision,
                token=token,
            ),
        )
        payload = json.loads(Path(step2_file).read_text(encoding="utf-8"))
    except (EntryNotFoundError, FileNotFoundError):
        parquet_file = _with_hub_retry(
            "train parquet",
            lambda: hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename="data/train-00000-of-00001.parquet",
                revision=revision,
                token=token,
            ),
        )
        payload = _build_inference_from_parquet(parquet_file, experiment, repo_id)

    canonical = _canonicalize_inference_payload(payload, repo_id, revision)
    canonical = _attach_inference_provenance(
        canonical,
        experiment=experiment,
        repo_id=repo_id,
        revision=revision,
        allow_legacy_missing_provenance=allow_legacy_missing_provenance,
    )
    _atomic_write_json(out, canonical)


def _remove_owned_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def _download_and_replace_deliverables(
    repo_id: str, revision: str, results: list[dict]
) -> None:
    destination = Path("workspace") / "upload" / "deliverable_files"
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent)
    )
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    backup_created = False

    try:
        allow_patterns = [
            f"deliverable_files/{row['task_id']}/**" for row in results
        ]
        # The 629-file read that five R1 shards died on. Retried as a whole
        # rather than per file: ``snapshot_download`` resumes from the local
        # cache, so a second attempt re-fetches only what the first did not get.
        _with_hub_retry(
            "deliverable_files snapshot",
            lambda: snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                local_dir=staging_root,
                allow_patterns=allow_patterns,
                revision=revision,
                token=_hf_token(),
            ),
        )
        staged_deliverables = staging_root / "deliverable_files"
        staged_deliverables.mkdir(parents=True, exist_ok=True)
        validate_local_deliverables(results, staging_root)

        if destination.exists() or destination.is_symlink():
            os.replace(destination, backup)
            backup_created = True
        try:
            os.replace(staged_deliverables, destination)
        except BaseException:
            if backup_created:
                _remove_owned_path(destination)
                os.replace(backup, destination)
                backup_created = False
            raise

        if backup_created:
            _remove_owned_path(backup)
            backup_created = False
    finally:
        _remove_owned_path(staging_root)


def main() -> int:
    args = parse_args()
    repo_id = resolve_repo_id(args.experiment)
    _stagger_shard_start()
    revision = resolve_immutable_revision(repo_id, args.revision)
    print(f"Resolved inference revision: {revision}")

    config_allowance = False
    if args.grading_config:
        grading_config = _load_repository_grading_config(args.grading_config)
        config_allowance = resolve_legacy_missing_provenance_allowance(
            grading_config,
            experiment=args.experiment,
            requested_revision=args.revision,
            resolved_revision=revision,
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    _download_or_reconstruct_inference(
        args.experiment,
        repo_id,
        revision,
        out,
        allow_legacy_missing_provenance=(
            args.allow_legacy_missing_provenance or config_allowance
        ),
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    canonical = _canonicalize_inference_payload(payload, repo_id, revision)
    selected = _select_expected_leading_tasks(
        canonical, args.expected_leading_task_id
    )
    _atomic_write_json(out, selected)
    _download_and_replace_deliverables(repo_id, revision, selected["results"])

    print(f"Downloaded inference from {repo_id} at {revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
