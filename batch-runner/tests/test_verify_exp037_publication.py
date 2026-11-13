"""Read immutable exp037 artifacts; mutate only copies in disposable test repos."""

import hashlib
import json
from pathlib import Path
import socket
import subprocess

import pytest

from scripts import verify_cost_ledger as ledger
from scripts import verify_published_grades as published
from .test_verify_published_grades import repo, publish, _git, OK_CMD
from .test_verify_cost_ledger import _call, _write, TASK

ROOT = Path(__file__).resolve().parents[2]
CHUNK = "bd684d64a20a8e6a0878a25c59148ce739ece4ef"
FINAL = "ebe98bfd2746"  # Resolved from local immutable Git objects, never fetched by a test.
BOT = "41898282+github-actions[bot]@users.noreply.github.com"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("publication unit test attempted a network connection")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


@pytest.fixture(scope="module")
def artifacts():
    def git(*args):
        return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30).stdout
    result = {}
    for label, revision in (("chunk", CHUNK), ("final", FINAL)):
        paths = git("ls-tree", "-r", "--name-only", revision, "data/grades").decode().splitlines()
        grade = next(path for path in paths if path.startswith("data/grades/exp037_sol_first25__") and path.endswith(".json"))
        sidecar = grade[:-5] + ".cost_ledger.jsonl"
        checkpoint = next((path for path in paths if path.startswith("data/grades/_progress/exp037_sol_first25__") and path.endswith(".json")), None)
        bodies = {path: git("show", f"{revision}:{path}") for path in (grade, sidecar, checkpoint) if path}
        result[label] = {"grade": grade, "sidecar": sidecar, "checkpoint": checkpoint, "bodies": bodies}
    return result


def place(root, artifact):
    for relative, body in artifact["bodies"].items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return root / artifact["grade"]


def change_json(path, mutate):
    value = json.loads(path.read_text())
    mutate(value)
    path.write_text(json.dumps(value))


def change_calls(root, artifact, mutate):
    path = root / artifact["sidecar"]
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    mutate(rows)
    raw = b"".join(json.dumps(row).encode() + b"\n" for row in rows)
    path.write_bytes(raw)
    # Rebind deliberately: a test of the arithmetic/IDs must not pass merely
    # because the outer sidecar hash caught the edited bytes first.
    change_json(root / artifact["grade"], lambda grade: grade["cost_ledger"].update(sha256=hashlib.sha256(raw).hexdigest()))


@pytest.mark.parametrize("label,total,completed,progress", [("chunk", 1627, 1568, 59), ("final", 2965, 2965, 0)])
def test_actual_refused_and_in_progress_calls_are_explicitly_accounted(tmp_path, artifacts, label, total, completed, progress):
    path = place(tmp_path, artifacts[label])
    findings, context = ledger.verify(path)
    assert all(finding.ok for finding in findings), [finding.as_dict() for finding in findings if not finding.ok]
    assert context["refused_rows"] == 22 and context["call_rows"] == total
    assert context["completed_task_call_rows"] == completed
    assert sum(row["calls"] for row in context["progress"]["data"]["checkpoints"]) == progress
    assert context["receipt_status"] == "partial" and context["receipt_estimated_cost_usd"] is None


@pytest.mark.parametrize("label", ["chunk", "final"])
def test_real_amount_tampering_still_fails(tmp_path, artifacts, label):
    path = place(tmp_path, artifacts[label])
    change_json(path, lambda grade: grade["summary"]["grading_cost"].update(model_cost_usd=1, known_cost_usd=1))
    findings, _ = ledger.verify(path)
    assert next(finding for finding in findings if finding.check == "cost_reconciles").ok is False


@pytest.mark.parametrize("mutation", ["missing_id", "missing_task_id", "duplicate_id", "remove_refusal", "invented_refusal_cost", "invented_refusal_tokens", "unknown_state"])
def test_rehashed_ledger_corruption_is_not_accepted(tmp_path, artifacts, mutation):
    artifact = artifacts["final"]
    path = place(tmp_path, artifact)
    def mutate(rows):
        refused = next(row for row in rows if row["state"] == "refused")
        if mutation == "missing_id": refused.pop("call_id")
        elif mutation == "missing_task_id": refused.pop("task_id")
        elif mutation == "duplicate_id": refused["call_id"] = next(row["call_id"] for row in rows if row is not refused)
        elif mutation == "remove_refusal": rows.remove(refused)
        elif mutation == "invented_refusal_cost": refused["model_cost_usd"] = "0"
        elif mutation == "invented_refusal_tokens": refused["input_tokens"] = 0
        elif mutation == "unknown_state": refused["state"] = "not_reported"
    change_calls(tmp_path, artifact, mutate)
    findings, _ = ledger.verify(path)
    assert next(finding for finding in findings if finding.check == "sidecar").ok is True
    assert any(not finding.ok for finding in findings)


@pytest.mark.parametrize("mutation", ["calls", "tokens", "source", "task_id", "rubric_item_id", "missing_file", "unknown_usage"])
def test_progress_is_verified_not_exempted(tmp_path, artifacts, mutation):
    artifact = artifacts["chunk"]
    path = place(tmp_path, artifact)
    checkpoint_path = tmp_path / artifact["checkpoint"]
    if mutation == "missing_file":
        checkpoint_path.unlink()
    elif mutation == "unknown_usage":
        task_id = json.loads(checkpoint_path.read_text())["task_id"]
        def mutate(rows):
            row = next(row for row in rows if row["task_id"] == task_id)
            row["missing_reasons"] = ["usage_incomplete"]
        change_calls(tmp_path, artifact, mutate)
    else:
        def mutate(checkpoint):
            if mutation == "calls": checkpoint["completed_items"][0]["judge_call_count"] += 1
            elif mutation == "tokens": checkpoint["completed_items"][0]["judge_input_tokens"] += 1
            elif mutation == "source": checkpoint["grader_source_hash"] = "a" * 64
            elif mutation == "task_id": checkpoint["task_id"] = "different-task"
            elif mutation == "rubric_item_id": checkpoint["completed_items"][0].pop("rubric_item_id")
        change_json(checkpoint_path, mutate)
    findings, _ = ledger.verify(path)
    assert any(not finding.ok and finding.check in {"progress_coverage", "task_coverage"} for finding in findings)


def test_legacy_or_task_call_counts_cannot_drop_the_refusals(tmp_path, artifacts):
    path = place(tmp_path, artifacts["final"])
    change_json(path, lambda grade: grade["summary"]["cost"].update(total_judge_calls=2943))
    findings, _ = ledger.verify(path)
    assert next(finding for finding in findings if finding.check == "legacy_counters").ok is False


def test_an_unknown_task_cannot_be_hidden_by_rebinding_the_sidecar(tmp_path, artifacts):
    artifact = artifacts["final"]
    path = place(tmp_path, artifact)
    change_calls(tmp_path, artifact, lambda rows: rows[0].update(task_id="unowned-task"))
    findings, _ = ledger.verify(path)
    coverage = next(finding for finding in findings if finding.check == "task_coverage")
    assert coverage.ok is False and coverage.data["unowned_call_tasks"] == ["unowned-task"]


@pytest.mark.parametrize("reported,ok", [(None, True), ("0.02", False)])
def test_optional_legacy_task_price_is_not_invented_but_a_wrong_price_fails(tmp_path, reported, ok):
    receipt = {"model_calls": 1}
    if reported is not None:
        receipt["known_cost_usd"] = reported
    path = _write(tmp_path, [_call("c1")], results=[{
        "task_id": TASK, "judge_call_count": 1, "perception_call_count": 0, "grading_cost": receipt,
    }])
    findings, _ = ledger.verify(path)
    assert next(finding for finding in findings if finding.check == "task_coverage").ok is ok


def test_checkpoint_is_reported_as_progress_not_as_a_grade(repo, artifacts):
    place(repo, artifacts["chunk"])
    sha = publish(repo, "fixture: partial chunk")
    findings, context = published.verify(repo, [sha], aggregate_cmd=OK_CMD)
    assert all(finding.ok for finding in findings), [finding.as_dict() for finding in findings if not finding.ok]
    assert context["published_grade_files"] == [artifacts["chunk"]["grade"]]
    assert context["published_progress_files"] == [artifacts["chunk"]["checkpoint"]]


def finish_chunk(repo, artifacts, *, mutation=None, bot=True):
    partial, final = artifacts["chunk"], artifacts["final"]
    place(repo, partial)
    publish(repo, "fixture: partial chunk")
    place(repo, final)
    checkpoint = repo / partial["checkpoint"]
    checkpoint.unlink()
    if mutation:
        change_json(repo / final["grade"], mutation)
    _git(repo, "add", "-A")
    # Identity overrides apply only to this disposable fixture repository;
    # the user's worktree Git identity and branch are never changed.
    args = ["-c", "user.name=github-actions[bot]", "-c", f"user.email={BOT}"] if bot else []
    _git(repo, *args, "commit", "-m", "fixture: finished checkpoint task")
    _git(repo, "push", "origin", "main")
    return _git(repo, "rev-parse", "HEAD")


def test_exact_producer_cleanup_is_allowed_and_reported(repo, artifacts):
    sha = finish_chunk(repo, artifacts)
    findings, context = published.verify(repo, [sha], aggregate_cmd=OK_CMD)
    assert all(finding.ok for finding in findings), [finding.as_dict() for finding in findings if not finding.ok]
    assert context["deleted_grade_files"] == []
    assert context["cleaned_checkpoint_files"] == [artifacts["chunk"]["checkpoint"]]
    assert any(finding.check == "checkpoint_cleanup" and finding.ok for finding in findings)


@pytest.mark.parametrize("mutation", ["item_id", "calls", "normalized_flag", "evidence", "source"])
def test_checkpoint_cleanup_does_not_hide_changed_finished_items(repo, artifacts, mutation):
    task_id = json.loads(artifacts["chunk"]["bodies"][artifacts["chunk"]["checkpoint"]])["task_id"]
    def mutate(grade):
        item = next(task for task in grade["tasks"] if task["task_id"] == task_id)["items"][0]
        if mutation == "item_id": item["rubric_item_id"] = "wrong-id"
        elif mutation == "calls": item["judge_call_count"] += 1
        elif mutation == "normalized_flag": item["model_did_right"] = not item["model_did_right"]
        elif mutation == "evidence": item["evidence"] = "changed retained evidence"
        elif mutation == "source": grade["grader_source_hash"] = "a" * 64
    sha = finish_chunk(repo, artifacts, mutation=mutate)
    findings, context = published.verify(repo, [sha], aggregate_cmd=OK_CMD)
    assert any(finding.check == "no_deletions" and not finding.ok for finding in findings)
    assert context["cleaned_checkpoint_files"] == []


def test_non_workflow_checkpoint_deletion_is_not_exempt(repo, artifacts):
    sha = finish_chunk(repo, artifacts, bot=False)
    findings, _ = published.verify(repo, [sha], aggregate_cmd=OK_CMD)
    assert any(finding.check == "no_deletions" and not finding.ok for finding in findings)


@pytest.mark.parametrize("kind", ["checkpoint_only", "ledger", "grade", "unrelated_progress"])
def test_other_deletions_still_fail(repo, artifacts, kind):
    artifact = artifacts["chunk"]
    place(repo, artifact)
    if kind == "unrelated_progress":
        stray = repo / "data/grades/_progress/not-a-checkpoint.json"
        stray.write_text('{"task_id": "foreign"}')
    publish(repo, "fixture: seed")
    target = {"checkpoint_only": artifact["checkpoint"], "ledger": artifact["sidecar"],
              "grade": artifact["grade"], "unrelated_progress": "data/grades/_progress/not-a-checkpoint.json"}[kind]
    (repo / target).unlink()
    _git(repo, "add", "-A")
    _git(repo, "-c", f"user.email={BOT}", "commit", "-m", "fixture: deletion")
    _git(repo, "push", "origin", "main")
    sha = _git(repo, "rev-parse", "HEAD")
    findings, _ = published.verify(repo, [sha], aggregate_cmd=OK_CMD)
    assert any(finding.check == "no_deletions" and not finding.ok for finding in findings)


def test_only_sidecar_edit_still_checks_its_owner_grade(repo, artifacts):
    artifact = artifacts["final"]
    place(repo, artifact)
    publish(repo, "fixture: final")
    path = repo / artifact["sidecar"]
    path.write_bytes(path.read_bytes() + b"\n")
    sha = publish(repo, "fixture: sidecar-only edit")
    findings, context = published.verify(repo, [sha], aggregate_cmd=OK_CMD)
    assert context["published_grade_files"] == [artifact["grade"]]
    assert any(finding.check == "ledger" and not finding.ok for finding in findings)
