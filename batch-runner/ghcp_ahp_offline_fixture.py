"""Inert response scripts, not a host, authentication result or model evidence.

Keep the response literals separate from the real attestation's expectations:
changing a request must never manufacture a corresponding observed value.
"""

import copy
import os
import shutil

from ghcp_sol_actions_gate import TASK_IDS


def budget_config():
    """Explicit SMALL synthetic test input, never a production/owner default."""
    return {"task_credits": "10", "five_task_credits": "50", "usage_timeout_seconds": 1200}


def usage_action(turn_id="turn1", *, input_tokens=12, output_tokens=2, cache_read_tokens=0, cumulative=None):
    # Literal observed-model fixture, deliberately independent of request defaults.
    total = cumulative if cumulative is not None else (input_tokens, output_tokens, cache_read_tokens)
    return {"type": "chat/usage", "turnId": turn_id, "usage": {
        "model": "@provider=vscode-proxy:gpt-5.6-sol", "inputTokens": input_tokens,
        "outputTokens": output_tokens, "cacheReadTokens": cache_read_tokens,
        "_meta": {"turnTokenTotals": [{"model": "@provider=vscode-proxy:gpt-5.6-sol",
            "inputTokens": total[0], "outputTokens": total[1], "cachedTokens": total[2]}]}}}


def first_turn_records(task_id):
    native = {"process": f"fixture-{task_id}", "stream": "ipc-1", "synthetic": True}
    http = {"process": f"fixture-{task_id}", "stream": "http-1", "synthetic": True}
    thread = f"fixture-thread-{task_id}"
    return [
        {**native, "kind": "ipc_request", "value": {"id": 13, "method": "turn/start",
            "params": {"threadId": thread}}},
        {**native, "kind": "ipc_response", "value": {"id": 13, "result": {"turn": {"id": "turn1"}}}},
        {**http, "kind": "capi_request", "value": {"model": "gpt-5.6-sol", "reasoning": {"effort": "max"}}},
        {**http, "kind": "capi_headers", "status": 200},
        {**http, "kind": "capi_event", "event": "response.completed", "value": {
            "type": "response.completed", "response": {"id": f"fixture-response-{task_id}",
                "status": "completed", "model": "gpt-5.6-sol", "reasoning": {"effort": "max"},
                "output": [{"type": "message"}]}}},
        {**http, "kind": "capi_end"},
        {**native, "kind": "ipc_response", "value": {"method": "thread/tokenUsage/updated", "params": {
            "threadId": thread, "turnId": "turn1", "tokenUsage": {"modelContextWindow": 1000000}}}},
    ]


def turn_steps(turn_id="turn1", *, text="SYNTHETIC answer; no benchmark task was solved.\n", tools=True):
    steps = [
        {"kind": "begin", "turn_id": turn_id, "text": "SYNTHETIC fixture input; never send to a model."},
        {"kind": "event", "action": {"type": "chat/turnStarted", "turnId": turn_id}},
        {"kind": "event", "action": usage_action(turn_id)},
    ]
    if tools:
        steps += [
            {"kind": "event", "action": {"type": "chat/toolCallReady", "turnId": turn_id,
                "toolCallId": "tool-" + turn_id, "toolInput": "fixture: write answer.txt (not executed)"}},
            {"kind": "write", "path": "answer.txt", "content": text},
            {"kind": "event", "action": {"type": "chat/toolCallComplete", "turnId": turn_id,
                "toolCallId": "tool-" + turn_id, "result": {"content": [
                    {"type": "fileEdit", "path": "answer.txt"}]}}},
        ]
    return steps + [
        {"kind": "event", "action": {"type": "chat/delta", "turnId": turn_id, "partId": "answer", "content": text}},
        {"kind": "advance", "seconds": 1},
        {"kind": "event", "action": {"type": "chat/turnComplete", "turnId": turn_id, "duration": 1000}},
    ]


def fixed_five():
    """The frozen cohort's IDs, but deliberately NOT its real prompts/answers."""
    return {"schema": "ghcp-fixed-five-offline-fixture-v1", "synthetic": True, "model_free": True,
            "execution_allowed": False, "limits": {"turns": 64, "tool_calls": 32, "seconds": 1200},
            "tasks": [{"task_id": task_id,
                "inputs": {"reference_files/input.txt": f"SYNTHETIC reference for {task_id}\n"},
                "first_turn_records": first_turn_records(task_id),
                "steps": turn_steps(text=f"SYNTHETIC deliverable for {task_id}; not a task answer.\n")}
                for task_id in TASK_IDS]}


def budget_scenario(name):
    """Inert review scenarios for an EXPLICIT 2200/11000/120 proposal input.

    Does not provide a production budget default or imply owner approval.
    Every token count/response below is fabricated, never native usage evidence.
    """
    if name not in {"normal", "task_limit", "five_task_limit", "usage_missing", "usage_malformed"}:
        raise ValueError("unknown synthetic budget scenario")
    fixture = fixed_five()
    for index, task in enumerate(fixture["tasks"]):
        steps = task["steps"]
        ordinary = steps.pop(2)  # Write the owned output BEFORE the stop event.
        reports = [ordinary]
        if name == "five_task_limit" or (name == "task_limit" and index == 0):
            # 2184 + 15 = 2199 for completed tasks; the stopped task reports
            # 2184 + 17 = 2201 (task cap), or +21 = 2205 (sum 11001).
            final_output = 6000 if name == "five_task_limit" and index == 4 else 3000
            if name == "task_limit":
                final_output = 4000
            reports = [{"kind": "event", "action": usage_action(input_tokens=1_000_000, output_tokens=128000)},
                       {"kind": "event", "action": usage_action(input_tokens=10000, output_tokens=final_output,
                            cumulative=(1010000, 128000 + final_output, 0))}]
        elif index == 0 and name == "usage_missing":
            reports = []
            steps[:] = [step for step in steps if step["kind"] != "advance"
                        and step.get("action", {}).get("type") != "chat/turnComplete"]
            steps.append({"kind": "advance", "seconds": 120})
        elif index == 0 and name == "usage_malformed":
            ordinary["action"]["usage"]["inputTokens"] = "SYNTHETIC invalid token count"
        steps[5:5] = reports
    return fixture


class Clock:
    value = 0.0

    def __call__(self):
        return self.value


class Port:
    """Memory-only transport. No concrete live transport or host is imported."""

    def __init__(self, records, *, output_collection=None):
        self.records = copy.deepcopy(records)
        self.observed_records = []
        self.sent = []
        self.terminated = False
        self.output_collection = output_collection
        self.outputs_held = False
        self.operations = []

    def hold_outputs(self, *, binding, timeout):
        from ghcp_ahp_probe import Refused
        if self.output_collection is None or binding != self.output_collection.binding or self.outputs_held:
            raise Refused("output_hold_refused")
        self.outputs_held = True
        self.operations.append("hold")
        return {"binding": binding, "writers_stopped": True, "cleanup_held": True, "synthetic": True}

    def write_output(self, name, raw, *, write):
        from ghcp_ahp_probe import Refused
        if self.output_collection is None or self.outputs_held or self.terminated:
            raise Refused("output_fixture_write_after_hold")
        self.operations.append("write")
        write(self.output_collection.paths[self.output_collection.source] / name, raw)

    def _cleanup_admitted(self):
        from ghcp_ahp_probe import Refused
        if self.output_collection is not None and self.output_collection.phase not in {"sealed", "refused"}:
            raise Refused("output_fixture_cleanup_before_seal")

    def first_turn_evidence(self):
        self.observed_records = copy.deepcopy(self.records)
        return copy.deepcopy(self.observed_records)

    def send(self, message, timeout):
        if message.get("params", {}).get("action", {}).get("type") == "chat/turnCancelled":
            self.operations.append("interrupt")
        if message.get("method") == "disposeSession":
            self._cleanup_admitted()
            self.operations.append("dispose")
        self.sent.append(copy.deepcopy(message))

    def terminate(self, timeout):
        self._cleanup_admitted()
        self.operations.append("terminate")
        if self.output_collection is not None and os.path.lexists(self.output_collection.job_tmpdir):
            # Simulate the pinned child's close callback, NOT a native process.
            # This exact fresh fixture directory is the only recursive target.
            shutil.rmtree(self.output_collection.job_tmpdir)
        self.terminated = True
        return True  # Simulated cleanup only; there never was a native process.
