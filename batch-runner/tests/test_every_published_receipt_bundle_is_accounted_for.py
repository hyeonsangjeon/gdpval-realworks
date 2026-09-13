"""Every published receipt bundle, discovered rather than listed.

The audio gap went unnoticed for months partly because nothing checked the
whole corpus at once. Individual suites pin individual runs -- the nine exp035
shards have their own file -- but a bundle can be added to ``data/grades`` and
be watched by nothing. This file takes the opposite approach: it asks git what
is committed and checks whatever comes back.

That shape is deliberate. A test carrying a fixed count has one failure mode
worth naming, which is that adding evidence turns it red and the cheapest way
to green is to edit the number down until it matches. Nothing here has a number
to edit. The corpus is discovered, every discovered bundle must be verified,
and the only count asserted is a floor that new evidence can never violate.

The exact inventory as of 2026-09-13 -- 42 bundles, 87,244 settled calls -- is
recorded in ``docs/run_records/`` beside the derived repair, where a figure
that moves is a fact to explain rather than a test to fix.

No model is called. Nothing is written. Every file is read as committed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER_ROOT.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from scripts.verify_cost_ledger import verify  # noqa: E402

#: The corpus only grows. This floor is what the tree held when the audio
#: repair landed; it exists so a glob that silently matches nothing cannot
#: pass every assertion below by iterating over an empty list.
KNOWN_BUNDLE_FLOOR = 42

#: Spelled out rather than imported from the verifier. A test that reads the
#: list off the thing it is checking would keep agreeing with it after the
#: list itself went wrong.
AUDIO_KEYS = ("audio_input_tokens", "audio_output_tokens")


def _committed_ledgers() -> list[Path]:
    """Ask git, not the filesystem.

    Published means committed. A working tree can hold a half-finished bundle
    or a leftover from an aborted merge, and either would be verified here as
    though someone had published it.
    """
    listed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "data/grades/**.cost_ledger.jsonl"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [REPO_ROOT / rel for rel in sorted(listed)]


def _grade_for(ledger: Path) -> Path:
    return Path(str(ledger)[: -len(".cost_ledger.jsonl")] + ".json")


def _ledger_audio(ledger: Path) -> dict[str, int]:
    """What the durable evidence measured, read straight off the rows."""
    totals = {key: 0 for key in AUDIO_KEYS}
    with ledger.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("record_type", "call") != "call" or row.get("state") != "settled":
                continue
            for key in AUDIO_KEYS:
                totals[key] += int(row.get(key) or 0)
    return totals


@pytest.fixture(scope="module")
def corpus():
    """Verify every committed bundle once; 87k rows is too much to redo per test."""
    ledgers = _committed_ledgers()
    if not ledgers:
        pytest.skip("this checkout carries no committed cost ledgers")

    bundles = []
    for ledger in ledgers:
        grade = _grade_for(ledger)
        if not grade.is_file():
            bundles.append({"ledger": ledger, "grade": grade, "paired": False})
            continue
        findings, context = verify(grade)
        bundles.append(
            {
                "ledger": ledger,
                "grade": grade,
                "paired": True,
                "findings": {f.check: f for f in findings},
                "context": context,
                "audio": _ledger_audio(ledger),
            }
        )
    return bundles


def _name(bundle) -> str:
    return str(bundle["ledger"].relative_to(REPO_ROOT))


# ---------------------------------------------------------------------------
# 1. 발견된 것은 하나도 건너뛰지 않는다
# ---------------------------------------------------------------------------


def test_the_corpus_only_grows(corpus):
    assert len(corpus) >= KNOWN_BUNDLE_FLOOR, (
        f"{len(corpus)} bundles found, fewer than the {KNOWN_BUNDLE_FLOOR} "
        "committed when this was written -- evidence was removed, or the "
        "discovery pattern stopped matching"
    )


def test_every_ledger_has_the_grade_it_belongs_to(corpus):
    """A sidecar with no grade file is unreachable evidence, not evidence."""
    orphaned = [_name(b) for b in corpus if not b["paired"]]
    assert orphaned == []


def test_every_discovered_bundle_was_actually_verified(corpus):
    """Guards the guard: a bundle cannot be skipped into passing."""
    unverified = [_name(b) for b in corpus if "findings" not in b]
    assert unverified == []
    assert all(b["findings"] for b in corpus), "a bundle produced no findings at all"


# ---------------------------------------------------------------------------
# 2. 이 수리가 실제로 주장하는 것 -- 담지 못하는 토큰 종류가 없다
# ---------------------------------------------------------------------------


def test_no_published_bundle_carries_a_token_kind_the_receipt_cannot_express(corpus):
    """The repair's claim, asserted over the whole corpus rather than two shards.

    Before ``cost-receipt-v1`` declared the audio fields, two bundles failed
    here because the receipt had nowhere to put what the ledger measured. It
    now has somewhere, so every bundle passes -- including the two, whose gap
    did not vanish but moved to a check that can describe it exactly.
    """
    failed = {
        _name(b): b["findings"]["usage_containment"].detail
        for b in corpus
        if not b["findings"]["usage_containment"].ok
    }
    assert failed == {}


def test_every_bundle_agrees_on_which_kinds_a_receipt_can_hold(corpus):
    """One contract, not one per run."""
    declared = {
        tuple(b["findings"]["usage_containment"].data.get("receipt_keys", ()))
        for b in corpus
        if b["findings"]["usage_containment"].data.get("receipt_keys")
    }
    assert len(declared) == 1, f"bundles disagree about the receipt contract: {declared}"
    assert set(AUDIO_KEYS) <= set(next(iter(declared)))


# ---------------------------------------------------------------------------
# 3. 측정된 오디오는 진술되거나 신고된다. 조용히 사라지지 않는다
# ---------------------------------------------------------------------------


def test_measured_audio_is_never_silently_absent_from_a_receipt(corpus):
    """The property the whole repair exists to hold, checked corpus-wide.

    For every bundle whose ledger measured audio, the published receipt must
    either state the same number -- written by the repaired serializer -- or be
    reported as disagreeing with the ledger, because it was written before the
    contract had a field for it. What must never happen is the third case: a
    receipt silent about audio the ledger measured, and a checker calling that
    fine.
    """
    unaccounted = []
    examined = 0
    for bundle in corpus:
        measured = {k: v for k, v in bundle["audio"].items() if v}
        if not measured:
            continue
        examined += 1
        receipt = (
            json.loads(bundle["grade"].read_text(encoding="utf-8"))
            .get("summary", {})
            .get("grading_cost", {})
            .get("usage", {})
        )
        reconciles = bundle["findings"]["usage_reconciles"]
        for key, value in measured.items():
            if receipt.get(key) == value:
                continue  # stated outright
            if not reconciles.ok and key in (reconciles.data or {}):
                continue  # reported as a gap, by name
            unaccounted.append(
                {"bundle": _name(bundle), "kind": key, "ledger": value,
                 "receipt": receipt.get(key), "reconciles_ok": reconciles.ok}
            )
    assert examined, (
        "no committed ledger measured any audio, which cannot be true while the "
        "exp035 shards are in the tree -- the row filter or the column name "
        "stopped matching, and this test was about to pass over an empty list"
    )
    assert unaccounted == []


def test_the_bundles_that_disagree_about_audio_are_exactly_those_that_sent_it(corpus):
    """Derived from the evidence, so a new audio run joins this set by itself."""
    sent_audio = {_name(b) for b in corpus if any(b["audio"].values())}
    disagree = set()
    for bundle in corpus:
        finding = bundle["findings"]["usage_reconciles"]
        if not finding.ok and any(key in (finding.data or {}) for key in AUDIO_KEYS):
            disagree.add(_name(bundle))
    assert disagree <= sent_audio, (
        "a bundle disputes audio it never sent, so the disagreement is in the "
        f"checker rather than the evidence: {sorted(disagree - sent_audio)}"
    )
    assert sent_audio, "no bundle carries audio at all -- see the guard above"


def test_no_receipt_claims_audio_its_ledger_never_measured(corpus):
    """The opposite error, which no check would otherwise be looking for."""
    invented = []
    for bundle in corpus:
        receipt = (
            json.loads(bundle["grade"].read_text(encoding="utf-8"))
            .get("summary", {})
            .get("grading_cost", {})
            .get("usage", {})
        )
        for key in AUDIO_KEYS:
            claimed = receipt.get(key)
            if claimed and not bundle["audio"][key]:
                invented.append({"bundle": _name(bundle), "kind": key, "claimed": claimed})
    assert invented == []


# ---------------------------------------------------------------------------
# 4. 점수·개수·비용·신원은 이 수리가 건드리는 것이 아니다
# ---------------------------------------------------------------------------


def test_scores_counts_costs_and_identity_are_read_back_not_recomputed(corpus):
    """What the repair must not have moved, checked against the files themselves.

    The audio work touched the usage block and the checks that read it. Nothing
    else was meant to move, and the way to keep that true is to make the
    verifier's own reported figures answerable to the files rather than to each
    other: the settled-row count against the ledger, the task count, mean score,
    cost and grader fingerprint against the grade.

    A snapshot of yesterday's verdicts would say the same thing once and then
    need editing every time evidence is added. This says it about whatever is
    in the tree today, so a future change that quietly shifts a score or a
    denominator is caught on the run that introduces it.
    """
    drift = []
    for bundle in corpus:
        grade = json.loads(bundle["grade"].read_text(encoding="utf-8"))
        summary = grade.get("summary") or {}
        settled = sum(
            1
            for line in bundle["ledger"].read_text(encoding="utf-8").splitlines()
            if line.strip()
            and json.loads(line).get("record_type", "call") == "call"
            and json.loads(line).get("state") == "settled"
        )
        expected = {
            "settled_rows": settled,
            "grader_source_hash": grade.get("grader_source_hash"),
            "receipt_estimated_cost_usd": (summary.get("grading_cost") or {}).get(
                "estimated_cost_usd"
            ),
            "task_count": summary.get("task_count", summary.get("total_tasks")),
            "mean_score": summary.get("mean_score", summary.get("average_score")),
        }
        actual = {
            "settled_rows": bundle["context"].get("settled_rows"),
            "grader_source_hash": bundle["context"].get("grader_source_hash"),
            "receipt_estimated_cost_usd": bundle["context"].get(
                "receipt_estimated_cost_usd"
            ),
            "task_count": bundle["context"]["quality"].get("task_count"),
            "mean_score": bundle["context"]["quality"].get("mean_score"),
        }
        if expected != actual:
            drift.append({"bundle": _name(bundle), "files_say": expected, "verifier_says": actual})
    assert drift == []
