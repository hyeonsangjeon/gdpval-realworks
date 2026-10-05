#!/usr/bin/env python3
"""Require the existing synthetic owned-host case to prove real reparenting.

Read one bounded, temporary JUnit report; retain only a small JSON job-summary
receipt. This is CI platform evidence, never a study observation or launch grant.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET

CASE_CLASS = "tests.test_gpt54_time_budget_comparison"
CASE_NAME = "test_time_budget_observation_deadline_process_ownership_platform_contract"
PROPERTY = "time_budget_owned_host_platform"
JUNIT_LIMIT = 8 * 1024 * 1024
OUTCOME_LIMIT = 1024
RECEIPT_LIMIT = 4096
ROOT = Path(__file__).resolve().parents[2]


class PlatformEvidenceRefused(ValueError):
    """A stable safe reason, never XML, process output or an environment value."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise PlatformEvidenceRefused(reason)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "platform_outcome_malformed")
        result[key] = value
    return result


def extract_outcome(report: bytes) -> dict:
    _require(len(report) <= JUNIT_LIMIT, "junit_size_limit")
    _require(b"\x00" not in report and b"<!DOCTYPE" not in report.upper()
             and b"<!ENTITY" not in report.upper(),
             "junit_malformed")
    try:
        root = ET.fromstring(report)
    except (ET.ParseError, ValueError):
        raise PlatformEvidenceRefused("junit_malformed") from None
    _require(root.tag in {"testsuites", "testsuite"}, "junit_malformed")
    candidates = [case for case in root.iter("testcase")
                  if case.get("name") == CASE_NAME
                  or any(prop.get("name") == PROPERTY for prop in case.iter("property"))]
    _require(len(candidates) == 1, "platform_case_count")
    case = candidates[0]
    _require(case.get("classname") == CASE_CLASS and case.get("name") == CASE_NAME,
             "platform_case_identity")
    _require(not any(list(case.iter(tag)) for tag in ("skipped", "failure", "error")),
             "platform_case_not_completed")
    try:
        duration = float(case.attrib["time"])
    except (KeyError, TypeError, ValueError):
        raise PlatformEvidenceRefused("platform_case_not_completed") from None
    _require(math.isfinite(duration) and duration >= 0, "platform_case_not_completed")
    properties = [prop for prop in case.findall("./properties/property")
                  if prop.get("name") == PROPERTY]
    _require(len(properties) == 1
             and sum(prop.get("name") == PROPERTY for prop in root.iter("property")) == 1,
             "platform_property_count")
    value = properties[0].get("value", "")
    _require(len(value.encode("utf-8")) <= OUTCOME_LIMIT, "platform_outcome_malformed")
    try:
        outcome = json.loads(value, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError):
        raise PlatformEvidenceRefused("platform_outcome_malformed") from None
    _require(type(outcome) is dict, "platform_outcome_malformed")
    if outcome.get("platform_result") == "real_reparenting_confirmed":
        _require(set(outcome) == {"platform_result", "host_reusable"}
                 and outcome["host_reusable"] is True, "platform_outcome_malformed")
    else:
        _require(set(outcome) == {"platform_result", "host_reusable", "reason", "cause_type", "errno"}
                 and outcome["platform_result"] == "admission_refused"
                 and outcome["host_reusable"] is False
                 and outcome["reason"] == "time_budget_owned_process_host_required"
                 and type(outcome["cause_type"]) is str
                 and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", outcome["cause_type"]) is not None
                 and (outcome["errno"] is None or type(outcome["errno"]) is int
                      and 0 <= outcome["errno"] <= 4095), "platform_outcome_malformed")
    return outcome


def read_report(path: Path) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            _require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "junit_not_regular")
            report = stream.read(JUNIT_LIMIT + 1)
    except OSError:
        raise PlatformEvidenceRefused("junit_unavailable") from None
    _require(len(report) <= JUNIT_LIMIT, "junit_size_limit")
    return report


def checked_source(expected_sha: str) -> dict:
    _require(re.fullmatch(r"[0-9a-f]{40}", expected_sha) is not None, "source_anchor_invalid")
    environment = {"PATH": os.defpath, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
                   "GIT_CONFIG_GLOBAL": os.devnull, "GIT_NO_LAZY_FETCH": "1",
                   "GIT_ALLOW_PROTOCOL": "", "GIT_OPTIONAL_LOCKS": "0"}

    def git(*arguments):
        try:
            result = subprocess.run(
                ["/usr/bin/git", "--no-replace-objects", "-c", "core.fsmonitor=false",
                 "-c", "core.hooksPath=/dev/null", "-C", str(ROOT), *arguments],
                env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise PlatformEvidenceRefused("source_verification_failed") from None
        _require(result.returncode == 0, "source_verification_failed")
        try:
            return result.stdout.decode("ascii").strip()
        except UnicodeError:
            raise PlatformEvidenceRefused("source_verification_failed") from None

    head = git("rev-parse", "--verify", "HEAD^{commit}")
    _require(head == expected_sha, "source_anchor_mismatch")
    tree = git("rev-parse", "--verify", expected_sha + "^{tree}")
    _require(re.fullmatch(r"[0-9a-f]{40}", tree) is not None, "source_tree_invalid")
    git("diff", "--quiet", "--no-ext-diff", "--no-textconv", expected_sha, "--")
    _require(git("rev-parse", "--verify", "HEAD^{commit}") == head, "source_identity_changed")
    return {"commit": head, "tree": tree}


def ci_identity(args: argparse.Namespace) -> dict:
    _require(re.fullmatch(r"[1-9][0-9]{0,19}", args.run_id) is not None
             and re.fullmatch(r"[1-9][0-9]{0,6}", args.run_attempt) is not None
             and args.job == "comparison-contracts" and args.runner_os == "Linux"
             and args.runner_arch in {"X64", "ARM64"}
             and args.runner_environment == "github-hosted"
             and re.fullmatch(r"[A-Za-z0-9_. -]{1,128}", args.runner_name) is not None,
             "ci_identity_invalid")
    return {"run_id": args.run_id, "run_attempt": args.run_attempt, "job": args.job,
            "runner": {"os": args.runner_os, "arch": args.runner_arch,
                       "environment": args.runner_environment,
                       "name_sha256": hashlib.sha256(args.runner_name.encode("utf-8")).hexdigest()}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("junit", "summary", "expected-sha", "run-id", "run-attempt", "job", "test-outcome",
                 "runner-name", "runner-os", "runner-arch", "runner-environment"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    receipt = {"schema": "time_budget_owned_host_ci.v1", "synthetic": True,
               "model_free": True, "study_observation": False, "live_authorization": False,
               "gate_passed": False, "host_reusable": False}
    try:
        identity = ci_identity(args)
        source = checked_source(args.expected_sha)
        receipt["provenance"] = {"source": source, **identity}
        _require(args.test_outcome == "success", "comparison_step_not_successful")
        outcome = extract_outcome(read_report(Path(args.junit)))
        _require(checked_source(args.expected_sha) == source, "source_identity_changed")
        receipt["platform_outcome"] = outcome
        _require(outcome["platform_result"] == "real_reparenting_confirmed",
                 "platform_admission_refused")
        receipt.update(gate_passed=True, host_reusable=True)
    except PlatformEvidenceRefused as error:
        receipt["refusal_reason"] = str(error)
    payload = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    _require(len(payload.encode("utf-8")) <= RECEIPT_LIMIT, "receipt_size_limit")
    try:
        with open(args.summary, "a", encoding="utf-8") as summary:
            summary.write("```json\n" + payload + "\n```\n")
    except OSError:
        print("owned_host_ci_summary_unavailable", file=sys.stderr)
        return 1
    print(payload)
    return 0 if receipt["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
