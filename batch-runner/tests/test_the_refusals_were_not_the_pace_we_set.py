"""What refused exp034's calls, and what a refusal actually cost.

Four things were named as possible causes of the refusals in run 34540053904:
the number of requests we sent, the size of the prompts we reserved tokens for,
the throughput of the deployment, and the spacing between calls. Three of them
are ruled out by the run's own record. This file pins that, so the answer
cannot quietly drift back into a guess before the 220-task run is read.

**The basis, before any conclusion.** Two files that know nothing about each
other are used together: the Actions log, which names the start of every task
and every retry it announced, and the cost ledger the run uploaded, which has
one row per Codex turn. Reconstructing turns from the log gives 59; the ledger
holds 59; and the per-task counts agree for all thirty tasks. That agreement is
what makes it legitimate to lay one on the other, and it is asserted first
below. If it ever fails, nothing else in this file means anything.

**Call spacing — no.** The five tasks that exhausted their retries each waited
60, then 120, then 240 seconds between attempts, 420 seconds of deliberate
idleness, and were refused on every one. Waiting longer is not the lever.

**Request volume — no.** The pipeline runs one task at a time; the task start
times in the log are strictly increasing, so two requests were never in flight
together. And task 6 burned four attempts over eleven minutes against the
refusal while task 7, immediately after it, succeeded on a clean first attempt.
A deployment with no capacity for us would not have taken task 7.

**Token reservation — no, and if anything the reverse.** The largest turn in
the whole run, 847,817 tokens, is a turn that *succeeded*. The refused turns
sit at ordinary sizes. Shrinking prompts would not have helped and is not
proposed.

**What is left is not inferred — the provider names it.** Every exhausted
refusal came back reading ``Your requests to gpt-5.4 for gpt-5.4 in eastus2
have exceeded rate limit.`` That is a ceiling belonging to a deployment in a
region, which is where the three eliminations were already pointing. It does
not say whose traffic filled it; nothing in this run can say that.

**What the analysis found that nobody asked for: a refused turn is not a free
turn.** Twenty-nine turns ended in a rate-limit retry, and every one of them
settled with real token counts — 3,817,205 tokens, 39.3% of everything the run
spent, on work that was then thrown away and started over. This is the number
that matters for reading the 220-task run: its token total is not its progress.

**The blind spot, stated rather than hidden.** One ledger row is one Codex
turn, and the SDK reports no per-request breakdown inside a turn. The rows say
so themselves, and ``core.codex_cost`` attaches
:data:`~core.cost_receipts.REASON_CALL_REACHABILITY_UNKNOWN` to every Codex
settlement for exactly that reason. So nothing here can rule out a burst of
requests *inside* one turn hitting a per-minute ceiling. What remains after the
three eliminations is deployment throughput, seen through that limit — which is
why the conclusion is "not our pacing" and not "we know the exact mechanism".

Nothing here contacts a provider or reads anything outside ``fixtures/``.
"""

import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from core.cost_receipts import REASON_CALL_REACHABILITY_UNKNOWN

FIXTURE = Path(__file__).parent / "fixtures" / "run_record"
TIMELINE = FIXTURE / "exp034_inference_timeline.txt"
LEDGER = FIXTURE / "exp034_turn_ledger.json"

ANSI = re.compile(r"\x1b\[[0-9;]*m")
START = re.compile(
    r"^(?P<ts>\S+Z)\s+\[(?P<n>\d+)/30\]\s+(?P<task>[0-9a-f-]{36})\s+"
    r"\([^)]*\)\.\.\.\s*(?P<tail>.*)$"
)
RETRY = re.compile(
    r"^(?P<ts>\S+Z)\s+⏳\s+(?P<kind>\S+)\s+—\s+attempt\s+\d/\d\s+"
    r"in\s+(?P<wait>\d+)s\.\.\.\s*(?P<tail>.*)$"
)
SUCCEEDED = re.compile(r"✓\s+\(\d+ms")
FAILED = re.compile(r"✗\s+(?P<why>.*?),\s+mem=")


def _stamp(text: str) -> dt.datetime:
    """Actions stamps seven fractional digits; the stdlib parser takes six."""
    base, _, frac = text.rstrip("Z").partition(".")
    return dt.datetime.fromisoformat(f"{base}.{frac[:6]:0<6}+00:00")


@pytest.fixture(scope="module")
def tasks() -> list[dict]:
    """The thirty tasks, as the log reports them."""
    parsed: list[dict] = []
    current: dict | None = None
    for raw in TIMELINE.read_text(encoding="utf-8").splitlines():
        line = ANSI.sub("", raw)
        if "\t" in line:  # the "batch-run<TAB>Step 2a: ...<TAB>" prefix Actions adds
            line = line.rsplit("\t", 1)[-1]
        line = line.strip()

        opening = START.match(line)
        if opening:
            current = {
                "n": int(opening.group("n")),
                "task_id": opening.group("task"),
                "started": _stamp(opening.group("ts")),
                "waits": [],
                "retry_kinds": [],
                "outcome": None,
                "why": None,
                "why_text": None,
            }
            parsed.append(current)
            tail = opening.group("tail")
        else:
            again = RETRY.match(line)
            if not again or current is None:
                continue
            current["waits"].append(int(again.group("wait")))
            current["retry_kinds"].append(again.group("kind"))
            tail = again.group("tail")

        if SUCCEEDED.search(tail):
            current["outcome"] = "ok"
            continue
        stopped = FAILED.search(tail)
        if stopped:
            why = stopped.group("why")
            current["outcome"] = "fail"
            current["why_text"] = why
            current["why"] = (
                "rate" if "exceeded rate limit" in why
                else "content" if "content_filter" in why
                else "other"
            )
    return parsed


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    """One row per Codex turn, as the ledger recorded them."""
    return json.loads(LEDGER.read_text(encoding="utf-8"))["rows"]


def _tokens(row: dict) -> int:
    return (row["input_tokens"] or 0) + (row["output_tokens"] or 0)


# ── the basis ────────────────────────────────────────────────────────────────


def test_the_two_records_agree_on_how_many_turns_each_task_took(tasks, rows):
    """Everything below lays the ledger on the log. This is why that is allowed.

    A turn is a task's first attempt plus one for each retry the log announced.
    The ledger, written by different code at a different moment, should hold
    exactly that many rows for the same task.
    """
    assert len(tasks) == 30
    assert all(task["outcome"] for task in tasks), "every task should reach an outcome"

    from_log = Counter()
    for task in tasks:
        from_log[task["task_id"]] = 1 + len(task["waits"])
    from_ledger = Counter(row["task_id"] for row in rows)

    assert sum(from_log.values()) == 59
    assert from_log == from_ledger


# ── call spacing ─────────────────────────────────────────────────────────────


def test_every_exhausted_task_had_already_waited_the_full_backoff(tasks):
    """Refused after 420 seconds of idleness. Waiting more is not the lever."""
    exhausted = [t for t in tasks if t["why"] == "rate"]
    assert len(exhausted) == 5

    for task in exhausted:
        assert task["waits"] == [60, 120, 240], task["task_id"]
        assert set(task["retry_kinds"]) == {"rate_limited"}, task["task_id"]
        assert sum(task["waits"]) == 420


# ── request volume ───────────────────────────────────────────────────────────


def test_the_pipeline_never_had_two_tasks_in_flight(tasks):
    """Strictly increasing starts: nothing here sent concurrent requests."""
    starts = [task["started"] for task in tasks]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)


def test_a_task_succeeded_on_its_first_attempt_right_after_one_was_refused(tasks):
    """A deployment with nothing left for us would have refused this one too."""
    by_position = {task["n"]: task for task in tasks}
    refused = next(t for t in tasks if t["why"] == "rate")
    assert refused["n"] == 6

    after = by_position[refused["n"] + 1]
    assert after["outcome"] == "ok"
    assert after["waits"] == [], "it needed no retry at all"


# ── token reservation ────────────────────────────────────────────────────────


def test_the_largest_turn_of_the_whole_run_was_not_refused(tasks, rows):
    """Biggest turn in the run succeeded, so size is not what was refused."""
    largest = max(rows, key=_tokens)
    assert _tokens(largest) == 847_817

    owner = next(t for t in tasks if t["task_id"] == largest["task_id"])
    assert owner["outcome"] == "ok"
    assert owner["waits"] == [], "and it was never retried"

    refused_turns = [row for row in rows if row["retry_kind"] == "infrastructure"]
    biggest_refused = max(_tokens(row) for row in refused_turns)
    assert biggest_refused < _tokens(largest)


# ── what a refusal cost ──────────────────────────────────────────────────────


def test_a_refused_turn_still_burned_tokens(rows):
    """39.3% of the run's tokens bought work that was then thrown away.

    This is the correction that matters when reading the 220-task run: its
    token total is not a measure of how much of it got done.
    """
    thrown_away = [row for row in rows if row["retry_kind"] == "infrastructure"]
    assert len(thrown_away) == 29
    assert all(row["state"] == "settled" for row in thrown_away)
    assert all(_tokens(row) > 0 for row in thrown_away), "a retried turn still ran"

    wasted = sum(_tokens(row) for row in thrown_away)
    total = sum(_tokens(row) for row in rows)
    assert wasted == 3_817_205
    assert total == 9_705_200
    assert 0.39 < wasted / total < 0.40


def test_a_turn_that_never_reported_usage_claims_nothing_instead_of_zero(rows):
    """Six turns raised before any usage came back. They stay unmeasured.

    ``reserved`` does not mean the task failed — four of the six belong to
    tasks that went on to succeed. It means this turn's cost is unknown, and
    the ledger says so rather than writing a convenient zero.
    """
    unreported = [row for row in rows if row["state"] == "reserved"]
    assert len(unreported) == 6
    for row in unreported:
        assert row["input_tokens"] is None
        assert row["output_tokens"] is None


def test_no_row_carries_a_dollar_amount(rows):
    """This deployment has no entry in the price table, so USD stays absent.

    Absent is the honest reading. The run is not free and must never be
    reported as ``$0`` on the strength of a missing table row.
    """
    assert all(row["model_cost_usd"] is None for row in rows)


# ── what is left ─────────────────────────────────────────────────────────────


def test_the_provider_named_the_deployment_it_was_refusing(tasks):
    """The fourth candidate is not an inference of ours. It is what came back.

    Three causes are eliminated above by our own behaviour. The remaining one
    is stated by the refusal itself, naming a deployment and a region. What it
    does not say — and what nothing in this run can say — is whether the
    traffic filling that ceiling was ours or came from elsewhere sharing the
    same deployment. Both readings survive; "we should have gone slower" does
    not, because we did and it was refused anyway.
    """
    exhausted = [t for t in tasks if t["why"] == "rate"]
    assert len(exhausted) == 5

    for task in exhausted:
        assert task["why_text"].endswith(
            "Your requests to gpt-5.4 for gpt-5.4 in eastus2 have exceeded rate limit."
        ), task["task_id"]


def test_the_content_stops_are_kept_as_failures(tasks):
    """Three tasks the model stopped on. They stay failed, and stay counted.

    A content stop is the benchmark recording what the model did, so it is not
    retried — the filter is not an infrastructure condition — and the task is
    not reworded, resampled or dropped to lift the success rate. Two of the
    three reached a second attempt only because their first was rate-refused;
    the stop came on that second attempt, from the model.
    """
    stopped = [t for t in tasks if t["why"] == "content"]
    assert len(stopped) == 3

    for task in stopped:
        assert task["outcome"] == "fail"
        assert "reason: content_filter" in task["why_text"]
        # never retried *for* the content stop
        assert set(task["retry_kinds"]) <= {"rate_limited"}
        assert len(task["waits"]) <= 1, "a content stop does not buy another attempt"

    assert sum(1 for t in stopped if t["waits"]) == 2
    assert sum(1 for t in stopped if not t["waits"]) == 1


# ── the limit of all of the above ────────────────────────────────────────────


def test_the_record_still_says_it_cannot_see_inside_a_turn(rows):
    """The eliminations above are bounded by this, and it is not dropped."""
    assert {row["note"] for row in rows} == {
        "one Codex turn; the model requests inside it are not individually reported"
    }
    for row in rows:
        if row["state"] == "settled":
            assert REASON_CALL_REACHABILITY_UNKNOWN in row["missing_reasons"]
