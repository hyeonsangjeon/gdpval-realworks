"""One task was solved and then graded. Both prices must recompute from main.

exp026c_cost_receipt_smoke solved task 83d10b06 and the #288 smoke graded that
same deliverable. Two halves of one measurement, and until this file landed only
one of them could be checked from a clone.

The grading half was always here: `step9` commits the grade JSON next to its
`cost_ledger.jsonl`, so `$0.753121` has been recomputable since the run. The
solving half was not, and not because anything crashed. batch-run.yml:943 puts
exactly one file in a result PR -- `report/report.md` -- and PR #287 carried it.
That PR was closed, not merged, because `aggregate-reports.mjs` truncated
`exp026c_cost_receipt_smoke` to `exp026` and collided it with
`exp026_sandbox_skills_multimodal`. PR #289 fixed the truncation six minutes
after the close and the report was never re-landed, so the one experiment whose
whole purpose was to produce a cost figure was the one experiment with no cost
figure on main. It read as "never measured" rather than "measured, $0.285513".

So this file binds both halves to their ledgers, and binds the prose that quotes
them to the same arithmetic:

* Both totals are recomputed from committed rows with `Decimal`, never floats.
  `model_cost_usd` is a decimal STRING on purpose -- summing the raw fields with
  `+` raises TypeError rather than drifting, which is the intended failure.

* The rounding mode is checked, not assumed. The solving ledger sums to exactly
  `0.2855125`, a midpoint. Production quantizes ROUND_HALF_UP
  (core/cost_receipts.py:530) and prints `0.285513`; Python's default rounding
  is HALF_EVEN and would print `0.285512`. A test that reached for `round()`
  would fail here, so the half-up result is asserted to differ from the
  half-even one and the receipt is required to match the former.

* Every ratio the smoke config states is recomputed from the two totals. That
  is not decoration: the config shipped "roughly 20x what solving did" for a
  measurement that came in at 2.64x, and nothing on main disagreed with it. A
  stated multiple that no committed number has to reproduce is how a wrong one
  survives a review.

* The report's `sha256 de78e70a37c3…` line has to resolve to the file sitting
  beside it. That line was a dangling reference for as long as the ledger was
  only a HuggingFace object and an expiring Actions artifact.

One check points at naming rather than at data. The dashboard keeps this run out
of its default view via `isSmokeExperimentId`, which matches /smoke/i against
`meta.experiment_name` -- not against the id. Rename the experiment to something
without "smoke" in it and a 1-task, 0%-success run joins the public leaderboard
beside 220-task experiments, with no other test objecting.
"""

import json
import hashlib
import re
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

#: The file batch-run.yml:943 declares as the only member of a result PR.
SOLVING_REPORT = (
    REPO_ROOT
    / "batch-runner/results/exp026c_cost_receipt_smoke/report/report.md"
)
SOLVING_LEDGER = SOLVING_REPORT.parent / "cost_ledger.jsonl"

SMOKE_CONFIG = (
    REPO_ROOT
    / "batch-runner/grading_configs/cost_smoke_exp026c_v2_gpt54.yaml"
)

#: Located by shape, not pinned: the diagnostic fork directory is named for a
#: scope hash, and the grade filename carries a grader fingerprint.
GRADING_GLOB = "data/grades/_diagnostic/*/exp026c_cost_receipt_smoke*__v2.2.json"

#: The single task both halves are about.
TASK_ID = "83d10b06-26d1-4636-a32c-23f92c57f30b"

CENTS_6 = Decimal("0.000001")
CENTS_4 = Decimal("0.0001")


def _rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _total(rows: list[dict]) -> Decimal:
    """Sum priced rows exactly. `model_cost_usd` is a string, deliberately."""
    return sum((Decimal(r["model_cost_usd"]) for r in rows), Decimal(0))


@pytest.fixture(scope="module")
def solving_rows() -> list[dict]:
    assert SOLVING_LEDGER.is_file(), (
        f"{SOLVING_LEDGER.relative_to(REPO_ROOT)} is missing. Without it the "
        "solving half of this measurement is only a HuggingFace object and an "
        "Actions artifact that expires, and nothing here can be recomputed."
    )
    return _rows(SOLVING_LEDGER)


@pytest.fixture(scope="module")
def grading_grade() -> dict:
    matches = sorted(REPO_ROOT.glob(GRADING_GLOB))
    assert len(matches) == 1, f"expected exactly one grade JSON, found {matches}"
    return json.loads(matches[0].read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def grading_rows(grading_grade: dict) -> list[dict]:
    matches = sorted(REPO_ROOT.glob(GRADING_GLOB))
    ledger = matches[0].with_name(grading_grade["cost_ledger"]["path"])
    assert ledger.is_file(), f"grade JSON names a ledger that is not here: {ledger}"
    return _rows(ledger)


@pytest.fixture(scope="module")
def config_text() -> str:
    return SMOKE_CONFIG.read_text(encoding="utf-8")


# ── the two totals ──────────────────────────────────────────────────────────


def test_solving_report_is_on_main_at_the_path_the_workflow_declares():
    """The file PR #287 carried and never landed."""
    assert SOLVING_REPORT.is_file(), (
        "batch-run.yml:943 sets add-paths to results/<exp>/report/report.md and "
        "calls it the only file in a result PR. For exp026c that PR was closed "
        "over an aggregator collision that PR #289 then fixed, which is why the "
        "one cost-receipt experiment had no cost figure on main."
    )
    assert "Problem-Solving Cost" in SOLVING_REPORT.read_text(encoding="utf-8")


def test_solving_total_recomputes_and_is_rounded_half_up(solving_rows):
    total = _total(solving_rows)
    assert total == Decimal("0.2855125"), f"solving ledger no longer sums to it: {total}"

    half_up = total.quantize(CENTS_6, rounding=ROUND_HALF_UP)
    half_even = total.quantize(CENTS_6, rounding=ROUND_HALF_EVEN)
    assert half_up == Decimal("0.285513")
    assert half_even == Decimal("0.285512")
    assert half_up != half_even, (
        "This total is an exact midpoint, which is the only reason the rounding "
        "mode is observable here. If it stops being one, this test stops "
        "guarding core/cost_receipts.py:530 and should be given a total that is."
    )

    printed = re.search(r"^\| Total \| \$([0-9.]+) \|$", SOLVING_REPORT.read_text(encoding="utf-8"), re.M)
    assert printed, "report.md no longer has a Total row"
    assert Decimal(printed.group(1)) == total.quantize(CENTS_4, rounding=ROUND_HALF_UP)


def test_grading_total_recomputes_to_the_receipt(grading_rows, grading_grade):
    total = _total(grading_rows)
    assert total == Decimal("0.7531210"), f"grading ledger no longer sums to it: {total}"

    receipt = grading_grade["summary"]["grading_cost"]
    assert receipt["status"] == "complete"
    assert Decimal(str(receipt["model_cost_usd"])) == total.quantize(
        CENTS_6, rounding=ROUND_HALF_UP
    )
    assert receipt["model_calls"] == len(grading_rows) == 84


def test_neither_half_stands_a_zero_in_for_an_unpriced_call(solving_rows, grading_rows):
    """`complete` has to mean every row was priced, not that gaps read $0."""
    for label, rows in (("solving", solving_rows), ("grading", grading_rows)):
        for row in rows:
            assert row["state"] == "settled", f"{label}: unsettled row {row.get('call_id')}"
            assert row["model_cost_usd"] is not None, f"{label}: null cost survived"
            assert not row.get("missing_reasons"), (
                f"{label}: {row.get('call_id')} carries {row.get('missing_reasons')} "
                "yet the receipt claims complete"
            )


def test_both_halves_are_about_the_same_one_task(solving_rows, grading_rows):
    assert {r["task_id"] for r in solving_rows} == {TASK_ID}
    assert {r["task_id"] for r in grading_rows} == {TASK_ID}


# ── the ledger the report points at ─────────────────────────────────────────


def test_report_cites_the_sha256_of_the_ledger_beside_it(solving_rows):
    cited = re.search(
        r"Cost ledger: `cost_ledger\.jsonl` \(sha256 `([0-9a-f]+)…?`\)",
        SOLVING_REPORT.read_text(encoding="utf-8"),
    )
    assert cited, "report.md no longer cites its ledger's sha256"
    actual = hashlib.sha256(SOLVING_LEDGER.read_bytes()).hexdigest()
    assert actual.startswith(cited.group(1)), (
        f"report.md cites {cited.group(1)}… but the committed ledger hashes to "
        f"{actual}. One of the two was replaced without the other."
    )


# ── the prose that quotes the numbers ───────────────────────────────────────


def test_every_multiple_the_config_states_recomputes(solving_rows, grading_rows, config_text):
    """The check that would have caught "roughly 20x"."""
    solving = _total(solving_rows).quantize(CENTS_6, rounding=ROUND_HALF_UP)
    grading = _total(grading_rows).quantize(CENTS_6, rounding=ROUND_HALF_UP)

    stated_ratio = re.search(r"([0-9.]+)x is \$([0-9.]+) / \$([0-9.]+)", config_text)
    assert stated_ratio, "the config no longer states the grading-to-solving multiple"
    claimed, numerator, denominator = stated_ratio.groups()
    assert Decimal(numerator) == grading
    assert Decimal(denominator) == solving
    assert Decimal(claimed) == (grading / solving).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # The other multiple in the file: how far under the pre-run ceiling it came.
    ceiling = re.search(r"~\$([0-9.]+) as the ceiling", config_text)
    under = re.search(r"\(~([0-9]+)x under\)", config_text)
    assert ceiling and under, "the config no longer states the ceiling it missed by"
    assert round(Decimal(ceiling.group(1)) / grading) == int(under.group(1))


def test_the_falsified_prediction_is_labelled_rather_than_deleted(config_text):
    assert "20x what solving" not in config_text, (
        "The 20x claim is contradicted by the run this config paid for; it must "
        "not be restated as fact."
    )
    assert "Everything above this line is the pre-run prediction" in config_text, (
        "The prediction is kept on purpose. A smoke that quietly rewrites its "
        "own forecast to match the result has stopped being a smoke."
    )


def test_the_name_that_keeps_this_run_off_the_public_leaderboard():
    """src/lib/officialExperimentScope.js matches /smoke/i on experiment_name."""
    title = SOLVING_REPORT.read_text(encoding="utf-8").splitlines()[0]
    assert re.search(r"smoke", title, re.I), (
        "The dashboard hides this run from its default view by matching /smoke/i "
        "against meta.experiment_name, not against the id. Drop the word and a "
        "1-task, 0%-success run joins the leaderboard beside 220-task ones."
    )
