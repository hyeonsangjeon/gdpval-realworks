"""Synthetic usage and owned files only; no runtime, billing API or model."""

import copy
import json
import os
import socket
import subprocess
import threading

import pytest

import ghcp_ahp_client as client
import ghcp_ahp_offline_fixture as fixtures
import ghcp_ahp_output_collection as output
import ghcp_ahp_token_ledger as ledger
import ghcp_sol_offline_rehearsal as rehearsal

TASK = fixtures.TASK_IDS[0]
CANARY = "SYNTHETIC_LEDGER_SECRET_NOT_REAL_123456789"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("token ledger fixture attempted real runtime/network")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)


def config(task="10000", total="50000", timeout=1200):
    return {"task_credits": task, "five_task_credits": total, "usage_timeout_seconds": timeout}


def usage(inp=12, out=2, cache=0, cumulative=None):
    return fixtures.usage_action(input_tokens=inp, output_tokens=out, cache_read_tokens=cache,
                                 cumulative=cumulative)["usage"]


def new_ledger(tmp_path, *, budget=None, profile=output.PROFILES[0], ids=(TASK,)):
    return ledger.TokenLedger(tmp_path / "token-ledger.json", config() if budget is None else budget,
                              ids, profile=profile, synthetic=True)


def bound(tmp_path, profile=output.PROFILES[0], *, budget=None, no_budget=False, real_clock=False):
    state, spool = tmp_path / "state", tmp_path / "capture"
    state.mkdir(mode=0o700)
    (state / "workspace").mkdir(mode=0o700)
    (state / "tmp").mkdir(mode=0o700)
    temp = state / "tmp/vscode-agent-codex-sandbox-fixture"
    temp.mkdir(mode=0o700)
    spool.mkdir(mode=0o700)
    (state / "workspace/input.txt").write_text("SYNTHETIC input\n")
    clock = fixtures.Clock()
    collection = output.OutputCollection(state, temp, spool / "output", profile=profile, synthetic=True, clock=clock)
    port = fixtures.Port(fixtures.first_turn_records(TASK), output_collection=collection)
    book = None if no_budget else new_ledger(tmp_path, budget=budget, profile=profile)
    kwargs = {} if real_clock else {"clock": clock}
    session = client.BudgetedSessionClient(port, "ahp-session:/fixture", "ahp-chat:/fixture",
        authenticated=True, output_collection=collection, token_ledger=book, task_id=TASK, credential=CANARY, **kwargs)
    return session, port, book, clock, collection


def event(session, seq, kind, **fields):
    return {"jsonrpc": "2.0", "method": "action", "params": {"channel": session.chat,
        "serverSeq": seq, "origin": None, "action": {"type": kind, "turnId": "turn1", **fields}}}


def start(session):
    assert session.send_turn("turn1", "SYNTHETIC, never a model prompt")
    assert session.accept(event(session, 1, "chat/turnStarted"))


@pytest.mark.parametrize("field", ["task_credits", "five_task_credits"])
@pytest.mark.parametrize("value", [None, "", "0", 0, -1, True, 1.5, "NaN", "Infinity", "-1", "1e3", " 1", "0.0000001"])
def test_invalid_caps_never_become_zero_or_a_default(field, value):
    value_config = config()
    value_config[field] = value
    with pytest.raises(client.Refused, match="^token_budget_invalid$"):
        ledger.Budget.parse(value_config)


@pytest.mark.parametrize("field", ["task_credits", "five_task_credits", "usage_timeout_seconds"])
def test_each_config_field_is_required(field):
    value = config()
    del value[field]
    with pytest.raises(client.Refused, match="^token_budget_invalid$"):
        ledger.Budget.parse(value)


@pytest.mark.parametrize("value", [None, 0, -1, 1201, True, 1.5, "10"])
def test_usage_timeout_is_explicit_and_bounded(value):
    with pytest.raises(client.Refused, match="^token_budget_invalid$"):
        ledger.Budget.parse(config(timeout=value))


def test_no_budget_and_price_overrides_refuse():
    with pytest.raises(client.Refused, match="^token_budget_required$"):
        ledger.Budget.parse(None)
    with pytest.raises(client.Refused, match="^token_budget_invalid$"):
        ledger.Budget.parse({**config(), "input_price": 0})


@pytest.mark.parametrize("profile", output.PROFILES)
def test_missing_budget_refuses_the_first_task_turn_with_zero_work(tmp_path, profile):
    session, port, _, _, collection = bound(tmp_path, profile, no_budget=True)
    assert session.send_turn("turn1", "MUST NOT BE SENT") is False
    assert session.reason == "token_budget_required" and session.status == "stopped"
    assert not any(row.get("params", {}).get("action", {}).get("type") == "chat/turnStarted" for row in port.sent)
    assert collection.events == output.EVENTS
    report = rehearsal.run_rehearsal(tmp_path / "pipeline", output_profile=profile)
    assert report["exit_status"] == 2 and report["reason_codes"] == ["token_budget_required"]
    assert report["tasks"] == [] and report["actual_calls"]["model_turns"] == 0


@pytest.mark.parametrize("inp,tier,expected", [(271999, "default", "244.7991"), (272000, "default", "244.8"),
                                              (272001, "long_context", "489.6018")])
def test_context_tier_uses_this_call_input_and_includes_exact_boundary(inp, tier, expected):
    value = ledger.price_usage(usage(inp, 0))
    assert value["tier"] == tier and value["estimated_credits"] == expected
    assert value["last"]["cacheWriteTokens"] is None
    assert value["cache_write_basis"] == "all_input_possible_write_surcharge"


def test_cumulative_crossing_does_not_reprice_prior_small_calls():
    first = ledger.price_usage(usage(272000, 0))
    second = ledger.price_usage(usage(272000, 0, cumulative=(544000, 0, 0)), first)
    assert first["tier"] == second["tier"] == "default"
    assert first["estimated_microcredits"] + second["estimated_microcredits"] == 489600000


@pytest.mark.parametrize("field", ["inputTokens", "outputTokens", "cacheReadTokens"])
@pytest.mark.parametrize("value", [None, True, -1, "12", 1.5, float("nan"), float("inf"), 2**53])
def test_malformed_token_counts_fail_without_pricing_as_zero(field, value):
    body = usage()
    body[field] = value
    with pytest.raises(client.Refused, match="^token_ledger_invalid_usage$"):
        ledger.price_usage(body)


@pytest.mark.parametrize("damage", ["missing_input", "missing_output", "missing_cache", "model", "meta", "totals",
    "two_models", "total_type", "negative_total", "cache_gt_input", "reasoning_gt_output", "direct_scope", "cache_write_type"])
def test_usage_shape_or_unpriced_scope_refuses(damage):
    body = usage()
    if damage.startswith("missing_"):
        del body[{"missing_input": "inputTokens", "missing_output": "outputTokens", "missing_cache": "cacheReadTokens"}[damage]]
    elif damage == "model": body["model"] = "gpt-5.3-codex"
    elif damage == "meta": body["_meta"] = None
    elif damage == "totals": del body["_meta"]["turnTokenTotals"]
    elif damage == "two_models": body["_meta"]["turnTokenTotals"] *= 2
    elif damage == "total_type": body["_meta"]["turnTokenTotals"][0]["inputTokens"] = True
    elif damage == "negative_total": body["_meta"]["turnTokenTotals"][0]["inputTokens"] = -1
    elif damage == "cache_gt_input": body["cacheReadTokens"] = 13
    elif damage == "reasoning_gt_output": body["_meta"]["reasoningOutputTokens"] = 3
    elif damage == "direct_scope": body["_meta"]["directTurnTokenTotals"] = []
    else: body["cacheWriteTokens"] = "0"
    with pytest.raises(client.Refused, match="^token_ledger_"):
        ledger.price_usage(body)


def test_reported_cache_read_and_write_remain_distinct_from_unknown():
    unknown = ledger.price_usage(usage(100, 20, 40))
    explicit = usage(100, 20, 40)
    explicit["cacheWriteTokens"] = 0
    zero = ledger.price_usage(explicit)
    assert unknown["estimated_credits"] == "0.1156" and zero["estimated_credits"] == "0.0656"
    assert unknown["last"]["cacheWriteTokens"] is None and zero["last"]["cacheWriteTokens"] == 0
    explicit["cacheWriteTokens"] = 60
    assert ledger.price_usage(explicit)["estimated_credits"] == "0.0956"


def test_single_response_envelope_and_reasoning_are_not_double_counted():
    body = usage(1000000, 128000)
    body["_meta"]["reasoningOutputTokens"] = 128000
    priced = ledger.price_usage(body)
    assert priced["reported_component_microcredits"] == 1184000000
    assert priced["cache_write_reserve_microcredits"] == 1000000000
    assert priced["estimated_credits"] == "2184" and priced["token_envelope_exceeded"] is False


@pytest.mark.parametrize("inp,out", [(1000001, 1), (12, 128001)])
def test_reported_envelope_excess_is_priced_and_stops_not_dropped(tmp_path, inp, out):
    book = new_ledger(tmp_path)
    book.admit(TASK, "turn1", 0)
    assert book.observe(TASK, "turn1", 1, usage(inp, out), 1) == "token_ledger_token_envelope_exceeded"
    record = json.loads(book.path.read_text())
    assert record["tasks"][TASK]["usage_events"][0]["pricing"]["token_envelope_exceeded"] is True
    assert record["tasks"][TASK]["known_estimated_microcredits"] > 0


def test_duplicate_totals_do_not_charge_twice_but_identical_new_calls_do(tmp_path):
    book = new_ledger(tmp_path)
    book.admit(TASK, "turn1", 0)
    book.observe(TASK, "turn1", 1, usage(), 1)
    book.observe(TASK, "turn1", 2, usage(), 2)
    book.observe(TASK, "turn1", 3, usage(cumulative=(24, 4, 0)), 3)
    record = book.verify()["tasks"][TASK]
    assert [row["pricing"]["duplicate"] for row in record["usage_events"]] == [False, True, False]
    assert record["known_estimated_credits"] == "0.0296"


@pytest.mark.parametrize("damage", ["gap", "regress", "changed_duplicate"])
def test_lost_or_ambiguous_usage_cannot_be_priced_from_an_average(tmp_path, damage):
    book = new_ledger(tmp_path)
    book.admit(TASK, "turn1", 0)
    book.observe(TASK, "turn1", 1, usage(), 1)
    body = usage(cumulative={"gap": (36, 6, 0), "regress": (6, 1, 0), "changed_duplicate": (12, 2, 0)}[damage])
    if damage == "changed_duplicate": body["inputTokens"] = 13
    with pytest.raises(client.Refused, match="^token_ledger_"):
        book.observe(TASK, "turn1", 2, body, 2)
    assert book.snapshot()["unknown_usage"] is True
    assert book.snapshot()["known_estimated_credits"] == "0.0148"  # Known part, never fabricated complete usage.


@pytest.mark.parametrize("profile", output.PROFILES)
def test_normal_five_has_one_shared_explicit_budget_and_separate_sealed_ledgers(tmp_path, profile):
    report = rehearsal.run_rehearsal(tmp_path / "five", output_profile=profile, token_budget=fixtures.budget_config())
    assert report["exit_status"] == 0 and report["fixture_pipeline_passed"] is True
    assert report["token_ledger"]["known_estimated_credits"] == "0.074"
    assert len(report["token_ledger"]["tasks"]) == 5
    for row in report["tasks"]:
        record = json.loads((tmp_path / "five/tasks" / row["task_id"] / "capture/token-ledger.json").read_text())
        assert record == row["token_ledger"] and record["known_estimated_credits"] == "0.0148"
        assert record["output_profile"] == profile and record["billing_complete"] is False
        assert record["execution_allowed"] is False and record["soft_guard"] is True


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("scope", ["task", "five"])
def test_exact_credit_threshold_stops_and_never_admits_another_request(tmp_path, profile, scope):
    budget = config("0.0148" if scope == "task" else "10", "0.0296" if scope == "five" else "50")
    report = rehearsal.run_rehearsal(tmp_path / "five", output_profile=profile, token_budget=budget)
    assert report["exit_status"] == 2
    statuses = [row["status"] for row in report["tasks"]]
    assert statuses == (["stopped"] * 5 if scope == "task" else ["completed"] + ["stopped"] * 4)
    stopped = report["tasks"][0 if scope == "task" else 1]
    assert stopped["reason_codes"] == ["token_ledger_task_limit" if scope == "task" else "token_ledger_five_task_limit"]
    assert stopped["counts"]["admitted_or_observed_turns"] == 1
    assert all(row["counts"]["admitted_or_observed_turns"] == 0
               for row in report["tasks"][(1 if scope == "task" else 2):])
    if scope == "five":
        assert all(row["counts"]["admitted_or_observed_turns"] == 0 and row["token_ledger"]["known_estimated_credits"] is None
                   for row in report["tasks"][2:])
        assert report["token_ledger"]["known_estimated_credits"] == "0.0296"
    assert all(value == 0 for value in report["actual_calls"].values())


@pytest.mark.parametrize("profile", output.PROFILES)
def test_interrupt_precedes_collect_seal_cleanup_and_capture_is_preserved(tmp_path, profile, monkeypatch):
    session, port, book, _, collection = bound(tmp_path, profile, budget=config(task="0.0148"))
    start(session)
    port.write_output("answer.txt", b"SYNTHETIC retained output", write=lambda path, raw: path.write_bytes(raw))
    original = port.send
    def send(message, timeout):
        if message.get("params", {}).get("action", {}).get("type") == "chat/turnCancelled":
            assert session.status == "stopped" and collection.phase == "bound"
            assert session.send_turn("turn2", "MUST NOT BE SENT") is False
        if message.get("method") == "disposeSession":
            assert collection.phase == "sealed"
        return original(message, timeout)
    monkeypatch.setattr(port, "send", send)
    assert session.accept(event(session, 2, "chat/usage", usage=usage())) is False
    capture = session.capture(tmp_path / "capture.json")
    assert port.operations == ["write", "interrupt", "hold", "dispose", "terminate"]
    assert collection.events == output.EVENTS and not collection.job_tmpdir.exists() and not collection.workspace.exists()
    assert capture["generated_files"][0]["content"] == "SYNTHETIC retained output"
    assert capture["token_ledger"] == book.task_receipt(TASK)
    assert capture["reason_codes"] == ["token_ledger_task_limit"]


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("damage", ["missing", "malformed"])
def test_unknown_usage_stops_its_turn_and_blocks_unpriced_following_tasks(tmp_path, profile, damage):
    fixture = fixtures.fixed_five()
    task = fixture["tasks"][0]
    if damage == "missing":
        task["steps"] = [step for step in task["steps"] if step.get("action", {}).get("type") not in {"chat/usage", "chat/turnComplete"}]
        task["steps"].append({"kind": "advance", "seconds": 5})
    else:
        task["steps"][2]["action"]["usage"]["inputTokens"] = CANARY
    report = rehearsal.run_rehearsal(tmp_path / "five", fixture=fixture, output_profile=profile, token_budget=config(timeout=5))
    assert report["exit_status"] == 2 and report["token_ledger"]["unknown_usage"] is True
    assert report["token_ledger"]["known_estimated_credits"] is None
    assert all(row["status"] == "stopped" for row in report["tasks"])
    assert all(row["counts"]["admitted_or_observed_turns"] == 0 for row in report["tasks"][1:])
    assert CANARY not in (tmp_path / "five/token-ledger.json").read_text()
    capture = rehearsal.validate_capture(tmp_path / "five/tasks" / TASK, TASK)
    assert capture["cleanup"]["cancel_attempts"] == capture["cleanup"]["dispose_attempts"] == 1
    assert capture["token_ledger"]["known_estimated_credits"] is None


def test_missing_usage_at_turn_completion_cannot_become_success(tmp_path):
    session, _, book, _, _ = bound(tmp_path)
    start(session)
    assert session.accept(event(session, 2, "chat/turnComplete", duration=1)) is False
    assert session.reason == "token_ledger_usage_missing" and session.status == "stopped"
    assert book.snapshot()["known_estimated_credits"] is None


def test_duplicate_or_zero_reports_cannot_keep_a_silent_turn_alive(tmp_path):
    book = new_ledger(tmp_path, budget=config(timeout=5))
    book.admit(TASK, "turn1", 0)
    assert book.observe(TASK, "turn1", 1, usage(0, 0), 4) is None
    assert book.check(TASK, 5) == "token_ledger_usage_missing"
    assert book.snapshot()["known_estimated_credits"] is None


def test_independent_usage_watchdog_interrupts_silent_receive(tmp_path):
    session, port, _, _, _ = bound(tmp_path, budget=config(timeout=1), real_clock=True)
    unblocked = threading.Event()
    entered = threading.Event()
    original = port.terminate
    def receive(timeout):
        entered.set()
        assert unblocked.wait(4), "usage watchdog did not interrupt/terminate"
        raise TimeoutError
    def terminate(timeout):
        try:
            return original(timeout)
        finally:
            unblocked.set()
    port.receive, port.terminate = receive, terminate
    assert session.send_turn("turn1", "SYNTHETIC")
    session.run()
    assert entered.is_set() and unblocked.is_set() and session.reason == "token_ledger_usage_missing"
    assert port.operations.index("interrupt") < port.operations.index("hold") < port.operations.index("terminate")


@pytest.mark.parametrize("damage", ["delete", "bytes", "replace", "hardlink", "symlink", "permissions"])
def test_journal_loss_or_tamper_fails_closed_before_more_work(tmp_path, damage):
    session, _, book, _, _ = bound(tmp_path)
    start(session)
    assert session.accept(event(session, 2, "chat/usage", usage=usage()))
    if damage == "delete": book.path.unlink()
    elif damage == "bytes": book.path.write_bytes(book.path.read_bytes() + b" ")
    elif damage == "replace":
        other = tmp_path / "replacement"
        other.write_bytes(book.path.read_bytes())
        os.replace(other, book.path)
    elif damage == "hardlink": os.link(book.path, tmp_path / "alias")
    elif damage == "permissions": book.path.chmod(0o666)
    else:
        original = tmp_path / "target"
        book.path.rename(original)
        book.path.symlink_to(original)
    assert session.tick() is False and session.reason == "token_ledger_persistence_refused"
    assert session.send_turn("turn2", "MUST NOT BE SENT") is False
    with pytest.raises((client.Refused, OSError)):
        session.capture(tmp_path / "capture.json")


@pytest.mark.parametrize("field", ["known_estimated_credits", "known_estimated_microcredits", "tariff", "soft_guard", "execution_allowed"])
def test_forged_receipt_total_or_price_is_rejected(field, tmp_path):
    book = new_ledger(tmp_path)
    book.admit(TASK, "turn1", 0)
    book.observe(TASK, "turn1", 1, usage(), 1)
    value = book.task_receipt(TASK)
    value[field] = {"known_estimated_credits": "0", "known_estimated_microcredits": 0,
                    "tariff": {}, "soft_guard": False, "execution_allowed": True}[field]
    with pytest.raises(client.Refused, match="^token_ledger_receipt_refused$"):
        ledger.verify_task_receipt(value)


def test_same_journal_cannot_be_reopened_reset_or_used_for_parallel_tasks(tmp_path):
    ids = fixtures.TASK_IDS[:2]
    book = new_ledger(tmp_path, ids=ids)
    with pytest.raises(client.Refused, match="^token_ledger_path_refused$"):
        new_ledger(tmp_path, ids=ids)
    book.admit(ids[0], "turn1", 0)
    with pytest.raises(client.Refused, match="^token_ledger_concurrent_task_refused$"):
        book.admit(ids[1], "turn1", 0)


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("failure", ["interrupt", "dispose", "terminate_false", "terminate_exception"])
def test_failed_runtime_stop_latches_unknown_usage_and_refuses_remaining_tasks(tmp_path, profile, failure, monkeypatch):
    original_send, original_terminate = fixtures.Port.send, fixtures.Port.terminate
    affected = []

    def send(port, message, timeout):
        if not affected:
            affected.append(port)
        original_send(port, message, timeout)
        action = message.get("params", {}).get("action", {}).get("type")
        if port is affected[0] and ((failure == "interrupt" and action == "chat/turnCancelled")
                or (failure == "dispose" and message.get("method") == "disposeSession")):
            raise OSError("SYNTHETIC stop transport failure")

    def terminate(port, timeout):
        original_terminate(port, timeout)
        if port is affected[0] and failure == "terminate_exception":
            raise OSError("SYNTHETIC terminate failure")
        return port is not affected[0] or failure != "terminate_false"

    monkeypatch.setattr(fixtures.Port, "send", send)
    monkeypatch.setattr(fixtures.Port, "terminate", terminate)
    report = rehearsal.run_rehearsal(tmp_path / "five", output_profile=profile,
                                    token_budget=config(task="0.0148"))
    assert report["exit_status"] == 2
    assert report["token_ledger"]["unknown_usage"] is True
    assert report["token_ledger"]["known_estimated_credits"] == "0.0148"
    assert all(row["counts"]["admitted_or_observed_turns"] == 0 for row in report["tasks"][1:])
    first = report["tasks"][0]
    expected = "token_ledger_interrupt_unconfirmed" if failure == "interrupt" else "token_ledger_cleanup_unconfirmed"
    if failure.startswith("terminate_"):
        assert first["status"] == "capture_refused" and first["reason_codes"] == ["capture_host_not_stopped"]
    else:
        assert first["reason_codes"] == [expected]
    assert expected in report["token_ledger"]["tasks"][TASK]["issues"]
    assert report["token_ledger"]["tasks"][TASK]["stopped_reason"] == expected
    assert all(value == 0 for value in report["actual_calls"].values())


@pytest.mark.parametrize("profile", output.PROFILES)
def test_failed_dispose_cannot_leave_a_completed_task_or_known_aggregate(tmp_path, profile, monkeypatch):
    session, port, book, _, collection = bound(tmp_path, profile)
    start(session)
    assert session.accept(event(session, 2, "chat/usage", usage=usage()))
    assert session.accept(event(session, 3, "chat/turnComplete", duration=1))
    original = port.send

    def send(message, timeout):
        original(message, timeout)
        if message.get("method") == "disposeSession":
            raise OSError(CANARY)

    monkeypatch.setattr(port, "send", send)
    session.finish()
    assert session.status == "stopped" and session.reason == "token_ledger_cleanup_unconfirmed"
    assert book.verify()["unknown_usage"] is True
    assert book.task_receipt(TASK)["known_estimated_credits"] == "0.0148"
    assert collection.events == output.EVENTS
    assert CANARY not in json.dumps(session.cleanup)


@pytest.mark.parametrize("profile", output.PROFILES)
def test_simultaneous_task_admissions_share_one_locked_aggregate(tmp_path, profile):
    book = new_ledger(tmp_path, ids=fixtures.TASK_IDS, profile=profile)
    barrier = threading.Barrier(5)
    outcomes = {}

    def admit(task):
        barrier.wait(timeout=5)
        try:
            book.admit(task, "turn1", 0)
            outcomes[task] = "admitted"
        except client.Refused as error:
            outcomes[task] = str(error)

    workers = [threading.Thread(target=admit, args=(task,)) for task in fixtures.TASK_IDS]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert not worker.is_alive()
    assert list(outcomes.values()).count("admitted") == 1
    assert list(outcomes.values()).count("token_ledger_concurrent_task_refused") == 4
    record = book.verify()
    assert sum(len(task["admitted_turns"]) for task in record["tasks"].values()) == 1
    assert record["known_estimated_credits"] is None and not record["unknown_usage"]


@pytest.mark.parametrize("profile", output.PROFILES)
def test_concurrent_replay_refuses_without_double_charge_or_budget_reset(tmp_path, profile):
    book = new_ledger(tmp_path, ids=fixtures.TASK_IDS, profile=profile)
    book.admit(TASK, "turn1", 0)
    barrier, outcomes = threading.Barrier(2), []

    def observe():
        barrier.wait(timeout=5)
        try:
            outcomes.append(book.observe(TASK, "turn1", 1, usage(), 1))
        except client.Refused as error:
            outcomes.append(str(error))

    workers = [threading.Thread(target=observe) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert not worker.is_alive()
    assert outcomes.count(None) == outcomes.count("token_ledger_sequence_refused") == 1
    record = book.verify()
    assert record["unknown_usage"] is True and record["known_estimated_credits"] == "0.0148"
    assert len(record["tasks"][TASK]["usage_events"]) == 1
    book.end_task(TASK, "token_ledger_sequence_refused")
    with pytest.raises(client.Refused, match="^token_ledger_sequence_refused$"):
        book.admit(fixtures.TASK_IDS[1], "turn1", 2)


@pytest.mark.parametrize("inp,tier,expected", [(272000, "default", "10.88"), (272001, "long_context", "21.76008")])
def test_cached_input_still_selects_the_tier_without_becoming_uncached_or_written(inp, tier, expected):
    body = usage(inp, 0, inp)
    body["cacheWriteTokens"] = 0
    priced = ledger.price_usage(body)
    assert priced["tier"] == tier and priced["estimated_credits"] == expected
    assert priced["cache_write_reserve_microcredits"] == 0
    assert priced["last"]["cacheReadTokens"] == inp and priced["last"]["cacheWriteTokens"] == 0


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("scenario", ["normal", "task_limit", "five_task_limit", "usage_missing", "usage_malformed"])
def test_leader_proposal_five_task_rehearsals_preserve_stop_collection_and_seal(tmp_path, profile, scenario, monkeypatch):
    ports, trace = [], []
    original_send, original_collect = fixtures.Port.send, output.OutputCollection.collect_and_seal
    original_terminate = fixtures.Port.terminate

    def send(port, message, timeout):
        if port not in ports:
            ports.append(port)
        if message.get("params", {}).get("action", {}).get("type") == "chat/turnCancelled":
            trace.append((port, "interrupt"))
        if message.get("method") == "disposeSession":
            assert port.output_collection.phase == "sealed"
            trace.append((port, "dispose"))
        return original_send(port, message, timeout)

    def collect(collection, port, safe):
        trace.append((port, "collect"))
        result = original_collect(collection, port, safe)
        assert collection.phase == "sealed"
        trace.append((port, "seal"))
        return result

    def terminate(port, timeout):
        trace.append((port, "terminate"))
        return original_terminate(port, timeout)

    monkeypatch.setattr(fixtures.Port, "send", send)
    monkeypatch.setattr(fixtures.Port, "terminate", terminate)
    monkeypatch.setattr(output.OutputCollection, "collect_and_seal", collect)
    root = tmp_path / "five"
    report = rehearsal.run_rehearsal(root, fixture=fixtures.budget_scenario(scenario), output_profile=profile,
                                    token_budget=config("2200", "11000", 120))
    expected_total = {"normal": "0.074", "task_limit": "2201", "five_task_limit": "11001",
                      "usage_missing": None, "usage_malformed": None}[scenario]
    expected_stop = {"normal": None, "task_limit": "token_ledger_task_limit",
                     "five_task_limit": "token_ledger_five_task_limit", "usage_missing": "token_ledger_usage_missing",
                     "usage_malformed": "token_ledger_invalid_usage"}[scenario]
    stop_index = None if scenario == "normal" else (4 if scenario == "five_task_limit" else 0)
    assert report["exit_status"] == (0 if stop_index is None else 2)
    assert report["fixture_pipeline_passed"] is (stop_index is None)
    assert report["token_budget"] == config("2200", "11000", 120)
    assert report["token_ledger"]["known_estimated_credits"] == expected_total
    assert report["token_ledger"]["global_stop_reason"] == expected_stop
    assert report["token_ledger"]["unknown_usage"] is scenario.startswith("usage_")
    assert len(ports) == len(report["tasks"]) == 5
    for index, (port, row) in enumerate(zip(ports, report["tasks"], strict=True)):
        expected_trace = ["collect", "seal", "dispose", "terminate"]
        if index == stop_index:
            expected_trace.insert(0, "interrupt")
        assert [operation for owner, operation in trace if owner is port] == expected_trace
        assert port.output_collection.events == output.EVENTS
        capture = rehearsal.validate_capture(root / "tasks" / row["task_id"], row["task_id"])
        assert capture["cleanup"]["host_terminated"] is True and not capture["cleanup"]["control_errors"]
        assert not port.output_collection.workspace.exists() and not port.output_collection.job_tmpdir.exists()
        if stop_index is not None and index >= stop_index:
            assert row["status"] == "stopped" and row["reason_codes"] == [expected_stop]
        else:
            assert row["status"] == "completed"
        if stop_index is not None and index > stop_index:
            assert row["counts"]["admitted_or_observed_turns"] == 0
            assert row["token_ledger"]["known_estimated_credits"] is None
            assert capture["generated_files"] == []
        else:
            assert row["counts"]["admitted_or_observed_turns"] == 1
            assert len(capture["generated_files"]) == 1
            assert capture["generated_files"][0]["path"] == "answer.txt"
        assert not any(event["direction"] == "client_work" and event["after_stop"]
                       for event in capture["transcript"]["wire"])
    assert report["synthetic"] is True and report["execution_allowed"] is False
    assert not report["gate5_passed"] and not report["ready_for_grading"]
    assert all(value == 0 for value in report["actual_calls"].values())


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("damage", ["profile", "synthetic"])
def test_policy_profiles_cannot_share_a_mismatched_budget_binding(tmp_path, profile, damage):
    session, port, book, _, _ = bound(tmp_path, profile)
    if damage == "profile":
        book.profile = next(item for item in output.PROFILES if item != profile)
    else:
        book.synthetic = False
    assert not session.send_turn("turn1", "MUST NOT BE SENT")
    assert session.reason == "token_ledger_binding_refused"
    assert not any(row.get("params", {}).get("action", {}).get("type") == "chat/turnStarted" for row in port.sent)


def test_late_usage_reprices_a_closed_turn_and_revokes_success_on_limit(tmp_path):
    session, _, book, _, _ = bound(tmp_path, budget=config(task="0.0296"))
    start(session)
    assert session.accept(event(session, 2, "chat/usage", usage=usage()))
    assert session.accept(event(session, 3, "chat/turnComplete", duration=1))
    session.finish()
    assert session.status == "completed"
    assert session.accept(event(session, 4, "chat/usage", usage=usage(cumulative=(24, 4, 0)))) is False
    assert session.status == "stopped" and session.reason == "token_ledger_task_limit"
    assert book.task_receipt(TASK)["known_estimated_credits"] == "0.0296"
    assert book.task_receipt(TASK)["stopped_reason"] == "token_ledger_task_limit"
    assert session.cleanup["dispose_attempts"] == 1


def test_progress_timeout_is_not_refreshed_by_duplicate_reports(tmp_path):
    book = new_ledger(tmp_path, budget=config(timeout=5))
    book.admit(TASK, "turn1", 0)
    book.observe(TASK, "turn1", 1, usage(), 1)
    book.observe(TASK, "turn1", 2, usage(), 5)
    assert book.check(TASK, 6) == "token_ledger_usage_missing"


def test_clock_regression_refuses_instead_of_extending_deadline(tmp_path):
    book = new_ledger(tmp_path, budget=config(timeout=5))
    book.admit(TASK, "turn1", 10)
    assert book.check(TASK, 9) == "token_ledger_clock_refused"


@pytest.mark.parametrize("profile", output.PROFILES)
def test_resumed_history_cannot_reset_an_unknown_prior_cost(tmp_path, profile):
    session, _, book, _, _ = bound(tmp_path, profile)
    snapshot = {"resource": session.chat, "fromSeq": 1, "state": {"turns": [{"id": "prior"}]}}
    assert session.accept({"jsonrpc": "2.0", "id": 1, "result": {"snapshot": snapshot}}) is False
    assert session.reason == "token_ledger_resumed_history_refused"
    assert book.snapshot()["unknown_usage"] is True and book.snapshot()["known_estimated_credits"] is None
    assert not session.send_turn("turn1", "MUST NOT BE SENT")


def test_unadmitted_server_turn_is_interrupted_and_not_priced_as_zero(tmp_path):
    session, _, book, _, _ = bound(tmp_path)
    assert session.accept(event(session, 1, "chat/turnStarted")) is False
    assert session.reason == "token_ledger_unadmitted_turn"
    assert session.cleanup["cancel_attempts"] == 1
    assert book.snapshot()["unknown_usage"] is True and book.snapshot()["known_estimated_credits"] is None


def test_completed_receipt_must_be_below_its_task_threshold(tmp_path):
    book = new_ledger(tmp_path)
    book.admit(TASK, "turn1", 0)
    book.observe(TASK, "turn1", 1, usage(), 1)
    value = book.task_receipt(TASK)
    value.update(stopped_reason="completed", closed=True, completed_turns=["turn1"])
    value["budget"]["task_credits"] = "0.0148"
    with pytest.raises(client.Refused, match="^token_ledger_receipt_refused$"):
        ledger.verify_task_receipt(value)


def test_failed_atomic_journal_write_prevents_dispatch(tmp_path, monkeypatch):
    session, port, _, _, _ = bound(tmp_path)
    def fail_replace(*args, **kwargs):
        raise OSError(CANARY)
    monkeypatch.setattr(ledger.os, "replace", fail_replace)
    assert session.send_turn("turn1", "MUST NOT BE SENT") is False
    assert session.reason == "token_ledger_persistence_refused"
    assert not any(row.get("params", {}).get("action", {}).get("type") == "chat/turnStarted" for row in port.sent)
    assert CANARY not in json.dumps(session.cleanup)


@pytest.mark.parametrize("profile", output.PROFILES)
def test_usage_guard_does_not_replace_first_turn_attestation(tmp_path, profile):
    fixture = fixtures.fixed_five()
    fixture["tasks"][0]["first_turn_records"][4]["value"]["response"]["model"] = "gpt-5.3-codex"
    result = rehearsal.run_rehearsal(tmp_path / "five", fixture=fixture, output_profile=profile,
                                      token_budget=fixtures.budget_config())
    assert result["exit_status"] == 2 and result["tasks"][0]["reason_codes"] == ["first_turn_attestation_refused"]
    assert result["tasks"][0]["token_ledger"]["known_estimated_credits"] == "0.0148"
    assert all(row["status"] == "completed" for row in result["tasks"][1:])


@pytest.mark.parametrize("profile", output.PROFILES)
def test_rehashed_false_ledger_cannot_reach_grader_contract(tmp_path, profile):
    import hashlib
    root = tmp_path / "five"
    assert rehearsal.run_rehearsal(root, output_profile=profile, token_budget=fixtures.budget_config())["exit_status"] == 0
    capture_root = root / "tasks" / TASK / "capture"
    record = json.loads((capture_root / "capture.json").read_text())
    for name in ("client-capture.json", "token-ledger.json"):
        value = json.loads((capture_root / name).read_text())
        target = value["token_ledger"] if name == "client-capture.json" else value
        target["known_estimated_credits"] = "0"
        raw = json.dumps(value).encode()
        (capture_root / name).write_bytes(raw)
        record["files"][name] = {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}
    (capture_root / "capture.json").write_text(json.dumps(record))
    with pytest.raises(client.Refused, match="^token_ledger_receipt_refused$"):
        rehearsal.validate_capture(root / "tasks" / TASK, TASK)


def test_cli_without_budget_is_a_refusal_not_a_demo_default(tmp_path, capsys):
    assert rehearsal.main(["--output", str(tmp_path / "missing")]) == 2
    assert json.loads(capsys.readouterr().out)["reason_codes"] == ["token_budget_required"]


@pytest.mark.parametrize("damage", ["sequence_bool", "sequence_negative", "divergent_replay", "reordered"])
def test_usage_envelope_failure_also_closes_aggregate_admission(tmp_path, damage):
    session, _, book, _, _ = bound(tmp_path)
    start(session)
    assert session.accept(event(session, 3, "chat/usage", usage=usage()))
    sequence = {"sequence_bool": True, "sequence_negative": -1, "divergent_replay": 3, "reordered": 2}[damage]
    bad = event(session, sequence, "chat/usage", usage=usage(cumulative=(24, 4, 0)))
    assert session.accept(bad) is False
    assert book.snapshot()["global_stop_reason"] == "token_ledger_stream_integrity_refused"
    assert book.snapshot()["unknown_usage"] is True
    assert book.snapshot()["known_estimated_credits"] == "0.0148"
    assert session.send_turn("turn2", "MUST NOT BE SENT") is False


def test_late_envelope_error_revokes_both_client_and_ledger_completion(tmp_path):
    session, _, book, _, _ = bound(tmp_path)
    start(session)
    assert session.accept(event(session, 2, "chat/usage", usage=usage()))
    assert session.accept(event(session, 3, "chat/turnComplete", duration=1))
    session.finish()
    assert session.status == "completed"
    assert session.accept(event(session, True, "chat/usage", usage=usage())) is False
    assert session.status == "stopped" and session.reason == "invalid_server_sequence"
    assert book.verify()["tasks"][TASK]["stopped_reason"] == "invalid_server_sequence"
    assert book.snapshot()["unknown_usage"] is True


def test_memory_only_state_change_is_not_a_persisted_receipt(tmp_path):
    book = new_ledger(tmp_path)
    book.tasks[TASK]["stopped_reason"] = "forged_unpersisted_state"
    with pytest.raises(client.Refused, match="^token_ledger_unpersisted_state$"):
        book.verify()
