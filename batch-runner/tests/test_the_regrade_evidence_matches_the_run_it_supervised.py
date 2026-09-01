"""The supervision record has to agree with the run it supervised.

`314-full-185-regrade-evidence.md` is a hand-written account of how the 185-task
regrade was run. Its headline numbers were typed by a person reading artifacts,
which is the one class of claim that goes stale with every other check still
green -- the same reason stage 3's report pins its own typed digests.

So each figure the document states is recomputed here from the committed grade
payload rather than compared against a constant. A constant would only prove the
document agrees with this file.

Two of the checks are pointed the other way round, at source rather than at data.
The document records two defects it deliberately did not fix, because both sites
feed the grader source hash and editing either would produce a fingerprint that
this evidence is not pinned to. A test that merely restated the defect would go
green forever. These assert that the defect is *still there*, so that whoever
eventually fixes it is told, in the same commit, that a published document now
describes code that no longer exists.
"""

import json
from pathlib import Path
import re

import pytest

from tests.test_full_gold_corpus_report_quotes_its_run import (
    _stage_three_grade_files,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = (
    REPO_ROOT / "tasks/rebuilding_grading_task/314-full-185-regrade-evidence.md"
)
COMPANION_PATH = (
    REPO_ROOT / "tasks/rebuilding_grading_task/PR3_FULL_GOLD_CORPUS.md"
)
STEP8_PATH = REPO_ROOT / "batch-runner/step8_grade.py"
NARRATIVE_PATH = REPO_ROOT / "batch-runner/core/narrative_analyzer.py"

#: The fingerprint the eleven shards carried and the document is about. Taken
#: from the document itself so that a document about a different run cannot
#: quietly pass by inheriting this file's constant.
FINGERPRINT_RE = re.compile(r"`(79c2f503[0-9a-f]*)…?`")


@pytest.fixture(scope="module")
def evidence() -> str:
    assert EVIDENCE_PATH.is_file(), (
        f"{EVIDENCE_PATH.relative_to(REPO_ROOT)} is missing. Everything below "
        "checks that document against the run, so its absence is the failure."
    )
    return EVIDENCE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def payload() -> dict:
    files = _stage_three_grade_files()
    assert len(files) == 1, (
        "the supervision record has to be about exactly one finished run, and "
        f"{len(files)} committed payloads claim to be it: {files}"
    )
    return json.loads(files[0].read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ledger() -> list[dict]:
    files = _stage_three_grade_files()
    # The ledger is the grade file's own name with `.json` swapped for
    # `.cost_ledger.jsonl`. Not `with_suffix` -- the name ends `__v2.2.json`
    # and pathlib reads `.2` as the suffix of the stem.
    path = files[0].with_name(files[0].name[: -len(".json")] + ".cost_ledger.jsonl")
    assert path.is_file(), (
        f"{path.name} is not in the repository. Section 8-5 records that this "
        "file was missing once already because the publish step staged the "
        "grade and not its ledger; #327 closed that. Its absence now is that "
        "defect returning, and section 7's token reconciliation cannot run."
    )
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _stated(evidence: str, pattern: str) -> str:
    """The one substring the document states for `pattern`, or a clear failure."""
    found = re.findall(pattern, evidence)
    assert found, f"the document no longer states a value for /{pattern}/"
    assert len(set(found)) == 1, (
        f"the document states more than one value for /{pattern}/: "
        f"{sorted(set(found))}. Two numbers for one fact is the drift this "
        "file exists to catch."
    )
    return found[0]


# ── The document is about the run it names ─────────────────────────────────


def test_the_document_is_about_the_fingerprint_it_names(evidence, payload):
    """A supervision record of the wrong run is worse than none."""
    stated = FINGERPRINT_RE.search(evidence)
    assert stated, (
        "the document no longer names the grader source hash it supervised. "
        "Without it nothing below distinguishes this run from any other."
    )
    actual = payload["grader_source_hash"]
    assert actual.startswith(stated.group(1)), (
        f"the document supervises {stated.group(1)}… but the committed run was "
        f"graded by {actual[:16]}…. One of the two is about a different grader."
    )


def test_the_run_finished_and_nothing_errored(payload):
    """Section 0 rests on this: 185 graded, 0 in error."""
    tasks = payload["tasks"]
    assert len(tasks) == payload["expected_task_count"] == 185
    assert [t for t in tasks if t.get("error")] == []
    assert len({t["task_id"] for t in tasks}) == 185, (
        "a task id appears twice in the merged payload, which is exactly what "
        "section 6's 22 mechanical checks exist to prevent"
    )


# ── Section 0's table, recomputed ──────────────────────────────────────────


def test_the_headline_numbers_are_the_runs_numbers(evidence, payload):
    tasks = payload["tasks"]
    pcts = sorted(t["pct"] for t in tasks)
    mid = len(pcts) // 2
    median = pcts[mid] if len(pcts) % 2 else (pcts[mid - 1] + pcts[mid]) / 2

    computed = {
        "평균": f"{sum(pcts) / len(pcts):.2f}",
        "중앙값": f"{median:.2f}",
        "산업": str(len({t["sector"] for t in tasks})),
        "직업": str(len({t["occupation"] for t in tasks})),
        "50퍼밑": str(sum(1 for p in pcts if p < 50.0)),
        "치명적결함": str(sum(1 for t in tasks if t.get("critical_fail"))),
    }
    cost = payload["summary"]["cost"]
    total_calls = cost["total_judge_calls"]
    assert total_calls == (
        cost["total_main_judge_calls"] + cost["total_perception_calls"]
    ), (
        "the run's own call total no longer decomposes into main judging plus "
        "perception, so the document's single call figure would hide a third "
        "category it never mentions"
    )

    assert _stated(evidence, r"평균 \| \*\*([\d.]+)%") == computed["평균"], (
        f"the run's mean is {computed['평균']}% and the headline table says "
        "something else"
    )
    assert _stated(evidence, r"중앙값 \| \*\*([\d.]+)%") == computed["중앙값"], (
        f"the run's median is {computed['중앙값']}% and the headline table says "
        "something else"
    )
    assert f"{computed['산업']}개 산업" in evidence
    assert f"{computed['직업']}개 직업" in evidence
    assert f"**{computed['치명적결함']}개" in evidence, (
        f"{computed['치명적결함']} tasks carry critical_fail; the document's "
        "headline claim about that count no longer matches"
    )
    assert f"{total_calls:,}" in evidence, (
        f"the run made {total_calls:,} model calls while grading and the "
        "document does not state that figure"
    )


def test_the_document_does_not_call_the_ceiling_a_model_score(evidence):
    """The single most consequential thing the document must not get wrong."""
    assert "정답지의 성적" in evidence
    assert "어떤 모델의 성적이 아니다" in evidence


# ── Section 7: the bill says unpriced, never zero ──────────────────────────


def test_the_bill_is_unpriced_and_the_document_never_renders_it_as_zero(
    evidence, payload
):
    cost = payload["summary"]["cost"]
    assert cost["estimated_cost_usd"] is None
    assert cost["pricing_complete"] is False
    for model in cost["unpriced_models"]:
        assert model in evidence, (
            f"{model} has no price and the document does not name it as "
            "unpriced. A reader cannot tell which half of the bill is missing."
        )

    # The document has to be able to *talk about* "$0" -- section 7 exists to
    # say the run was not free, and 8-5's hazard is literally that a reader
    # gets "$0.00". So the rule is not "the string never appears": it is that
    # every dollar amount is quoted or in a code span, named as a rendering
    # being warned against, never written as this document's own figure. The
    # moment a bare one appears in prose, the document is stating a price for
    # a run that has none.
    prose = re.sub(r"`[^`]*`", "", evidence)
    prose = re.sub(r'"[^"\n]*"', "", prose)
    bare = re.findall(r"\$\s*[\d.,]+", prose)
    assert not bare, (
        f"the document states {bare} as a plain figure. This run is unpriced: "
        "two of its models are absent from the price table, so any dollar "
        "amount here is a claim the artifacts do not support."
    )


def test_the_zero_dot_zero_receipt_hazard_is_still_real(evidence, payload):
    """Section 9's second limitation, asserted against the receipts.

    Every task's receipt carries a literal 0.0 in three money fields while the
    only markers of 'unknown' sit in two neighbouring fields. If that is ever
    fixed -- nulls instead of zeros -- this goes red, and the limitation
    section that describes it has to be rewritten rather than left standing.
    """
    zero_fields = ("known_cost_usd", "model_cost_usd", "runtime_cost_usd")
    receipts = [t.get("grading_cost") or {} for t in payload["tasks"]]
    assert len(receipts) == 185

    for field in zero_fields:
        values = {r.get(field) for r in receipts}
        assert values == {0.0}, (
            f"{field} is no longer a flat 0.0 across all 185 receipts "
            f"(found {sorted(values, key=repr)}). Section 9 records that it is, "
            "and that the only things saying 'unknown' are status and "
            "estimated_cost_usd. Update the document with the fix."
        )
    assert {r.get("status") for r in receipts} == {"partial"}
    assert {r.get("estimated_cost_usd") for r in receipts} == {None}


def test_the_ledger_and_the_summary_agree_on_every_token_column(
    evidence, payload, ledger
):
    """Section 7 claims all four token columns reconcile. They have to."""
    assert len(ledger) == 22528

    summary_usage = payload["summary"]["grading_cost"]["usage"]
    cost = payload["summary"]["cost"]
    pairs = (
        ("input_tokens", cost["total_input_tokens"]),
        ("output_tokens", cost["total_output_tokens"]),
        ("cached_input_tokens", cost["total_cached_tokens"]),
        ("reasoning_tokens", summary_usage["reasoning_tokens"]),
    )
    for column, expected in pairs:
        summed = sum(row.get(column) or 0 for row in ledger)
        assert summed == expected, (
            f"the ledger's {column} sums to {summed:,} but the published "
            f"summary says {expected:,}. Section 7 states the two agree, which "
            "is what makes the summary a second reading rather than a copy."
        )
        assert f"{expected:,}" in evidence, (
            f"{column} totals {expected:,} and the document does not say so"
        )


def test_the_two_hour_totals_are_two_scopes_of_the_same_seconds(
    evidence, payload
):
    """Section 7 reconciles its 43.0h against the companion report's 42.9h."""
    cost = payload["summary"]["cost"]
    narrower = cost["total_judge_latency_sec"]
    wider = narrower + cost["total_render_latency_sec"]

    assert f"{narrower:,.0f}초" in evidence, (
        f"the companion report's narrower total is {narrower:,.0f}s and this "
        "document no longer quotes it, so the two look like they disagree"
    )
    assert f"{wider:,.0f}초" in evidence, (
        f"this document's own total is {wider:,.0f}s and it no longer says so"
    )
    assert f"{wider / 3600:.1f}시간" in evidence
    assert f"{cost['total_render_latency_sec']:,.0f}초" in evidence, (
        "the difference between the two totals is the render time, and the "
        "document has to name it for the reconciliation to be checkable"
    )


# ── The two defects the document deliberately left in place ────────────────


def test_perfect_count_still_counts_something_other_than_full_marks():
    """Section 8-6, asserted against the code rather than restated.

    The document records that `perfect_count` counts >= 99% and `zero_count`
    counts <= 1%, while the narrative prompt hands a model "(100%)" and "(0%)".
    Both sites feed the grader source hash, so the document says plainly that
    it is being recorded and not fixed while the queue is frozen.

    When someone does fix it, this test goes red -- which is the point. The
    published document describes the defect in the present tense.
    """
    step8 = STEP8_PATH.read_text(encoding="utf-8")
    assert re.search(r"perfect\s*=\s*sum\(1 for x in pcts if x >= 99\.0\)", step8), (
        "step8_grade.py no longer computes perfect_count as '>= 99.0'. If it "
        "now counts full marks, section 8-6 of "
        "314-full-185-regrade-evidence.md is describing code that is gone and "
        "must be updated in the same change."
    )
    assert re.search(r"zero\s*=\s*sum\(1 for x in pcts if x <= 1\.0\)", step8), (
        "step8_grade.py no longer computes zero_count as '<= 1.0'; section 8-6 "
        "needs updating with this change."
    )

    narrative = NARRATIVE_PATH.read_text(encoding="utf-8")
    assert "Perfect tasks (100%)" in narrative and "Zero tasks (0%)" in narrative, (
        "narrative_analyzer.py no longer mislabels those two counts to the "
        "model. That is the fix section 8-6 asks for -- update the document."
    )


def test_the_document_states_the_count_the_code_actually_produces(
    evidence, payload
):
    """8-6 is only a finding if both numbers are stated and they differ."""
    tasks = payload["tasks"]
    exactly_full = sum(1 for t in tasks if t["pct"] == 100.0)
    at_least_99 = sum(1 for t in tasks if t["pct"] >= 99.0)
    reported = payload["summary"]["openai_compat"]["perfect_count"]

    assert reported == at_least_99, (
        "perfect_count no longer equals the >= 99% population, so 8-6's "
        "explanation of where the number comes from is wrong"
    )
    assert exactly_full != reported, (
        "this run no longer distinguishes full marks from >= 99%, so 8-6 has "
        "no evidence in it and should be re-examined rather than left standing"
    )
    assert f"**{exactly_full}개**" in evidence, (
        f"exactly {exactly_full} task scored full marks and the document does "
        "not say so"
    )
    assert f"`perfect_count`는 **{reported}**" in evidence, (
        f"the file reports perfect_count={reported}; the document has to quote "
        "that number for the contrast to mean anything"
    )


# ── The pair of documents stays a pair ─────────────────────────────────────


def test_every_cross_reference_resolves(evidence):
    """The document defers to its companion rather than restating it."""
    targets = set(re.findall(r"\]\(([A-Za-z0-9_./-]+\.md)\)", evidence))
    assert targets, (
        "the document no longer points at its companion anywhere. Section 1 "
        "hands the result analysis to PR3_FULL_GOLD_CORPUS.md; if that link is "
        "gone the reader has no way to reach it."
    )
    for target in targets:
        resolved = (EVIDENCE_PATH.parent / target).resolve()
        assert resolved.is_file(), (
            f"{target} is linked from the evidence document but is not in the "
            "repository"
        )
    assert COMPANION_PATH.name in targets


def test_the_document_is_committed_and_not_ignored():
    """`tasks/rebuilding_grading_task/` is an opt-in allowlist.

    A new file there is silently un-addable until it is named in .gitignore.
    The document existing on disk is not evidence that it is in the repository.
    """
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    relative = EVIDENCE_PATH.relative_to(REPO_ROOT).as_posix()
    assert f"!{relative}" in gitignore, (
        f"{relative} is not named in .gitignore, so it is covered by the "
        "directory's blanket ignore and `git add` will silently skip it."
    )
