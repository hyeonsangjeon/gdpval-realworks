"""Response-only first-turn attestation. Missing evidence closes the task.

No inference, authentication, process or retry is performed here. Config/model
catalog echoes never fill these fields. A verified report still cannot unlock
the separately disabled AHP paid adapter or patched-host execution.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

from ghcp_ahp_errors import Refused

EXPECTED = {"served_model": "gpt-5.6-sol", "reasoning_effort": "max",
            "context_window": 1_000_000, "web_search_used": False}
SOURCES = {"served_model": "capi.completed_response.model",
           "reasoning_effort": "capi.completed_response.reasoning.effort",
           "context_window": "native.thread/tokenUsage/updated.tokenUsage.modelContextWindow",
           "web_search_used": "capi.completed_response.output[*].type"}
NOT_REPORTED = "not_reported"


def same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def read_live_records(state):
    from ghcp_ahp_probe import strict_json
    from ghcp_ahp_wire_capture import MAX_BYTES
    directory = Path(state) / "wire"
    if not directory.is_dir() or any(p.is_symlink() for p in (directory, *directory.parents)):
        raise Refused("first_turn_capture_unavailable")
    files = sorted(directory.glob("wire-*.jsonl"))
    if not files or len(files) > 16:
        raise Refused("first_turn_capture_unavailable")
    rows, size = [], 0
    for file in files:
        if file.is_symlink() or not file.is_file() or not re.fullmatch(r"wire-[0-9]+\.jsonl", file.name):
            raise Refused("first_turn_capture_invalid")
        size += file.stat().st_size
        if size > MAX_BYTES:
            raise Refused("first_turn_capture_limit")
        text = file.read_text()
        if text and not text.endswith("\n"):
            raise Refused("first_turn_capture_incomplete")
        for index, line in enumerate(text.splitlines(), 1):
            row = strict_json(line)
            if type(row) is not dict or type(row.get("sequence")) is not int or row["sequence"] != index:
                raise Refused("first_turn_capture_invalid")
            rows.append({**row, "process": file.name})
    return rows


def assess(records):
    from ghcp_ahp_wire_capture import analyze
    observed = dict.fromkeys(EXPECTED, NOT_REPORTED)
    sources = dict.fromkeys(EXPECTED, NOT_REPORTED)
    reasons = []
    thread_id = turn_id = NOT_REPORTED
    final = []
    try:
        capture = analyze(records, synthetic=any(row.get("synthetic") is True for row in records))
        if capture["capture_errors"]:
            reasons.append("first_turn_capture_invalid")
        requests = [row for row in records if row.get("kind") == "ipc_request"
                    and row.get("value", {}).get("method") == "turn/start"]
        if len(requests) != 1:
            raise Refused("first_turn_identity_unverified")
        request = requests[0]
        thread_id = request["value"].get("params", {}).get("threadId", NOT_REPORTED)
        replies = [row["value"] for row in records if row.get("kind") == "ipc_response"
                   and row.get("process") == request.get("process") and row.get("stream") == request.get("stream")
                   and same(row.get("value", {}).get("id"), request["value"].get("id"))]
        if (len(replies) != 1 or "error" in replies[0] or type(thread_id) is not str
                or thread_id in {"", NOT_REPORTED}):
            raise Refused("first_turn_identity_unverified")
        turn_id = replies[0].get("result", {}).get("turn", {}).get("id", NOT_REPORTED)
        if type(turn_id) is not str or turn_id in {"", NOT_REPORTED}:
            raise Refused("first_turn_identity_unverified")
        contexts = [row["context_window"] for row in capture["native_context_reports"]
                    if row["thread_id"] == thread_id and row["turn_id"] == turn_id]
        if contexts and all(same(value, contexts[0]) for value in contexts):
            observed["context_window"], sources["context_window"] = contexts[0], SOURCES["context_window"]
        elif contexts:
            reasons.append("first_turn_context_conflict")
        if len(capture["capi_requests"]) != 1:
            raise Refused("first_turn_provider_request_count_refused")
        provider_stream = tuple(capture["capi_requests"][0]["stream"])
        for row in records:
            if (row.get("process", "fixture"), row.get("stream")) != provider_stream:
                continue
            value = row.get("value")
            if row.get("kind") == "capi_body" and type(value) is dict:
                final.append(value)
            if row.get("kind") == "capi_event" and row.get("event") in {"response.completed", "message"}:
                if type(value) is dict and value.get("type") == "response.completed":
                    final.append(value.get("response"))
        if len(final) != 1 or type(final[0]) is not dict or final[0].get("status") != "completed":
            raise Refused("first_turn_completed_response_unreported")
        response = final[0]
        observed["served_model"] = response.get("model", NOT_REPORTED)
        reasoning = response.get("reasoning")
        observed["reasoning_effort"] = reasoning.get("effort", NOT_REPORTED) if type(reasoning) is dict else NOT_REPORTED
        for key in ("served_model", "reasoning_effort"):
            if observed[key] != NOT_REPORTED:
                sources[key] = SOURCES[key]
        # A COMPLETE response's explicit output array is the reported tool-use
        # inventory, not a requested tool setting. Unknown item kinds refuse.
        output = response.get("output")
        if (type(output) is list and all(type(item) is dict and item.get("type") in
                {"message", "reasoning", "web_search_call"} for item in output)):
            observed["web_search_used"] = any(item["type"] == "web_search_call" for item in output)
            sources["web_search_used"] = SOURCES["web_search_used"]
        for report in capture["capi_response_reports"]:
            for key, name in (("served_model", "reported_model"), ("reasoning_effort", "reported_reasoning_effort")):
                if report[name] != NOT_REPORTED and not same(report[name], observed[key]):
                    reasons.append("first_turn_" + key + "_conflict")
    except (Refused, KeyError, TypeError, ValueError, AttributeError) as error:
        reasons.append(str(error) if isinstance(error, Refused) else "first_turn_capture_invalid")
    for key, expected in EXPECTED.items():
        if not same(observed[key], expected):
            missing = observed[key] is None or observed[key] == NOT_REPORTED
            reasons.append("first_turn_" + key + ("_not_reported" if missing else "_mismatch"))
    return {"schema": "ghcp-ahp-first-turn-attestation-v1", "requested": dict(EXPECTED),
            "observed": observed, "sources": sources, "thread_id": thread_id, "turn_id": turn_id,
            "completed_responses": len(final), "verified": not reasons,
            "reason_codes": list(dict.fromkeys(reasons)), "synthetic": any(row.get("synthetic") is True for row in records),
            "evidence_scope": "runtime_response_report_not_independent_model_attestation"}


def require_report(report):
    if (type(report) is not dict or report.get("schema") != "ghcp-ahp-first-turn-attestation-v1"
            or report.get("verified") is not True or report.get("reason_codes") != []
            or not same(report.get("requested"), EXPECTED) or not same(report.get("observed"), EXPECTED)
            or not same(report.get("sources"), SOURCES) or not same(report.get("completed_responses"), 1)
            or any(type(report.get(key)) is not str or report[key] in {"", NOT_REPORTED} for key in ("thread_id", "turn_id"))):
        raise Refused("first_turn_attestation_refused")
    return report
