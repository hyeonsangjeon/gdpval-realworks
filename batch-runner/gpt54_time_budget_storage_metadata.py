"""Two fixed, read-only HF metadata operations; never study admission.

The credential stays in one Actions step. Only the allowlisted envelope may
leave it. Existing source, bounded-transport and private-target checks are
reused without entering a historical campaign's compiler or claim path.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from urllib.parse import parse_qs

import codex_budget_pilot_output as storage
from codex_ci_input_intake import _hf_environment
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_run_config_bundle import _held_parents, _root
from gpt54_time_budget_comparison import _reviewed_source
from gpt54_v2_grading_input import _object, _read_bytes

HELPER = "batch-runner/gpt54_time_budget_storage_metadata.py"
WORKFLOW = ".github/workflows/gpt54-time-budget-storage-metadata.yml"
REPOSITORY = "hyeonsangjeon/gdpval-realworks"
OWNER = "hyeonsangjeon"
JOB = "metadata"
FORMAT = "gpt54-time-budget-storage-metadata-v1"
BASENAME = "time-budget-storage-metadata.json"
TARGET = "HyeonSang/gdpval-codex-budget-pilot-ci-20260923"
TARGET_SHA256 = "a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44"
PREFIX = ("time-budget/gpt54_sandboxv2_codex_time_budget_v1/"
          "gpt54_time_budget_v1_v2_r1/02aa1805-c658-4069-8a6a-02dec146063a")
SECONDS = 60
SOURCE_ROLES = {HELPER, WORKFLOW, "batch-runner/requirements.txt", "batch-runner/requirements-renderer.txt"} | {
    "batch-runner/" + name + ".py" for name in (
        "codex_budget_pilot_output", "codex_budget_pilot", "codex_budget_pilot_ci",
        "codex_ci_input_intake", "codex_ci_input_bundle", "gpt54_codex_input_capture",
        "gpt54_comparison_preflight", "gpt54_disposable_checkout", "gpt54_prepared_input_attestation",
        "gpt54_run_config_bundle", "gpt54_run_input_bundle", "gpt54_time_budget_comparison",
        "gpt54_v2_grading_input",
    )
}


class MetadataRefused(ValueError):
    """A fixed refusal code, never a raw transport message or private object."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise MetadataRefused(reason)


@contextmanager
def checked_source(*, runtime_root: Path, reviewed_source_sha: str, reviewed_source_tree: str):
    """Validate actual Actions identity and held source bytes before credentials."""
    _require(storage._hash(reviewed_source_sha, 40) and storage._hash(reviewed_source_tree, 40),
             "independent_reviewed_source_required")
    expected = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": OWNER, "GITHUB_TRIGGERING_ACTOR": OWNER,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": JOB, "GITHUB_SHA": reviewed_source_sha,
        "METADATA_WORKFLOW_SHA": reviewed_source_sha,
        "GITHUB_WORKFLOW_REF": REPOSITORY + "/" + WORKFLOW + "@refs/heads/main",
        "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
        "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
    }
    _require(all(os.environ.get(key) == value for key, value in expected.items()), "actions_context_refused")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    _require(re.fullmatch(r"[1-9][0-9]{0,19}", run_id) is not None, "run_identity_required")
    root = _root(runtime_root)
    _require(str(root) == os.environ.get("GITHUB_WORKSPACE") == str(runtime_root)
             and root.resolve() == root, "canonical_checkout_required")
    with _reviewed_source(root, reviewed_source_sha, SOURCE_ROLES) as (_, tree, identities):
        _require(tree == reviewed_source_tree, "reviewed_tree_mismatch")
        for name in SOURCE_ROLES:
            if name.endswith(".py"):
                module = sys.modules[__name__] if name == HELPER else sys.modules[Path(name).stem]
                _read_bytes(Path(module.__file__), **identities[name])
        yield {"source": {"sha": reviewed_source_sha, "tree": tree},
               "ci": {"run_id": run_id, "job": JOB, "attempt": 1}}


def validate_envelope(value: dict, identity: dict) -> None:
    """Only these exact nonsecret fields may be logged or retained in Actions."""
    _require(type(value) is dict and set(value) == {
        "format", "source", "ci", "timestamp_utc", "target_identity_sha256",
        "verified_private", "parent_commit", "prefix", "prefix_outcome",
    }, "envelope_schema")
    _require(value["format"] == FORMAT and value["source"] == identity["source"]
             and value["ci"] == identity["ci"] and type(value["ci"]["attempt"]) is int
             and value["target_identity_sha256"] == TARGET_SHA256 and value["prefix"] == PREFIX,
             "envelope_binding")
    stamp = value["timestamp_utc"]
    _require(type(stamp) is str and datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").strftime(
        "%Y-%m-%dT%H:%M:%SZ") == stamp, "envelope_timestamp")
    _require(value["verified_private"] is None or value["verified_private"] is True, "envelope_privacy")
    parent = value["parent_commit"]
    _require((parent is None and value["verified_private"] is None)
             or (storage._hash(parent, 40) and value["verified_private"] is True), "envelope_parent")
    _require(value["prefix_outcome"] in ("absent", "present", "refused")
             and (value["prefix_outcome"] == "refused" or parent is not None), "envelope_outcome")


def _metadata(identity: dict) -> dict:
    envelope = {"format": FORMAT, **identity, "timestamp_utc": datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"), "target_identity_sha256": TARGET_SHA256,
        "verified_private": None, "parent_commit": None, "prefix": PREFIX, "prefix_outcome": "refused"}
    try:
        _require(hashlib.sha256(TARGET.encode()).hexdigest() == TARGET_SHA256, "fixed_target_identity")
        token = os.environ.get("HF_TOKEN", "")
        _require(bool(token) and len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token),
                 "explicit_hf_token_required")
        with storage._time_bound(SECONDS) as deadline, _hf_environment(online=True):
            from huggingface_hub import constants
            from huggingface_hub.utils import _http

            # The job sets both before import; refuse a previously cached SDK
            # that could start telemetry outside this two-request boundary.
            _require(constants.HF_HUB_DISABLE_TELEMETRY, "sdk_telemetry_must_be_disabled")
            with storage._hf_client(token, deadline, response_bytes_limit=64 * 1024) as api:
                session = _http.get_session()
                session.follow_redirects = False
                attempts, parent = 0, None

                def request_guard(request):
                    nonlocal attempts
                    storage._remaining(deadline)
                    _require(request.url.scheme == "https" and request.url.host == "huggingface.co"
                             and request.url.port in (None, 443) and request.url.userinfo == b""
                             and request.headers.get("authorization") == "Bearer " + token,
                             "metadata_transport_target")
                    route = f"/api/datasets/{TARGET}"
                    if attempts == 0:
                        _require(request.method == "GET" and request.url.path == route + "/revision/main"
                                 and parse_qs(request.url.query.decode()) == {"expand": ["private", "sha"]}
                                 and not request.content, "head_metadata_only")
                    else:
                        # HF's paths-info POST reads metadata; no write route
                        # or body-download endpoint is permitted here.
                        _require(attempts == 1 and parent is not None and request.method == "POST"
                                 and request.url.path == route + "/paths-info/" + parent and not request.url.query
                                 and parse_qs(request.content.decode(), strict_parsing=True) == {
                                     "paths": [PREFIX], "expand": ["false"]}, "exact_prefix_metadata_only")
                    attempts += 1

                def response_guard(response):
                    _require(response.status_code == 200, "metadata_http_refused")
                    if attempts == 2:
                        # Read metadata only, through the existing byte/deadline
                        # bound. A 404, malformed list or unrelated path is not absence.
                        response.read()
                        rows = response.json()
                        _require(type(rows) is list and len(rows) <= 1, "prefix_metadata_schema")
                        for row in rows:
                            _require(type(row) is dict and row.get("path") == PREFIX
                                     and row.get("type") in ("directory", "file")
                                     and storage._hash(row.get("oid"), 40), "prefix_metadata_binding")
                            if row["type"] == "file":
                                _require(type(row.get("size")) is int and row["size"] >= 0,
                                         "prefix_file_metadata")

                session.event_hooks = {"request": [request_guard], "response": [response_guard]}
                # Request only privacy/head fields, not repository siblings or
                # unrelated paths. The existing validator still checks id/private/SHA.
                head = storage._metadata(SimpleNamespace(repo_info=partial(
                    api.repo_info, expand=["private", "sha"])), TARGET, "main", token, deadline)
                parent = head["sha"]
                envelope.update(verified_private=True, parent_commit=parent)
                found = api.get_paths_info(repo_id=TARGET, repo_type="dataset", revision=parent,
                                           paths=[PREFIX], expand=False, token=token)
                storage._remaining(deadline)
                _require(attempts == 2 and type(found) is list and len(found) <= 1
                         and all(item.path == PREFIX for item in found), "metadata_completion_required")
                envelope["prefix_outcome"] = "present" if found else "absent"
    except (Exception, KeyboardInterrupt):
        # No raw exception, status payload, URL, credential or private object.
        # Keep a verified first response if the second operation refused.
        envelope["prefix_outcome"] = "refused"
    validate_envelope(envelope, identity)
    return envelope


def inspect_metadata(**source) -> dict:
    with checked_source(**source) as identity:
        result = _metadata(identity)
    return result  # Final held-source rereads must succeed before publication.


def _destination() -> Path:
    value = os.environ.get("RUNNER_TEMP", "")
    _require(bool(value) and Path(value).is_absolute(), "runner_temp_required")
    root = _root(Path(value))
    _require(str(root) == value and root.resolve() == root, "canonical_runner_temp_required")
    return root / BASENAME


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise MetadataRefused("invalid_arguments")


def main(argv=None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("operation", choices=("validate-source", "inspect", "verify-envelope"))
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--reviewed-source-tree", required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    logging.disable(logging.CRITICAL)
    try:
        args = vars(parser.parse_args(argv))
        operation = args.pop("operation")
        destination = _destination()
        with _held_parents(destination.parent, (destination.name,)) as held:
            if operation == "inspect":
                _require(not destination.exists() and not destination.is_symlink(), "envelope_already_exists")
                envelope = inspect_metadata(**args)
                held()
                _write_no_clobber(destination, json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode())
                held()
                sys.stdout.write(json.dumps(envelope, sort_keys=True) + "\n")
                return 2 if envelope["prefix_outcome"] == "refused" else 0
            with checked_source(**args) as identity:
                if operation == "verify-envelope":
                    _require(destination.lstat().st_size <= 4096, "envelope_bytes_bound")
                    validate_envelope(json.loads(_read_bytes(destination), object_pairs_hook=_object), identity)
            held()
        return 0
    except (Exception, KeyboardInterrupt):
        sys.stdout.write("metadata_refused\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
