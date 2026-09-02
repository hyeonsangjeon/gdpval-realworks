"""What a task really spends on pictures, counted from a run that happened.

``judge.perception.visual.call_cap_per_task`` was 72 and nothing said why. The
number was not idle. On the 185-task gold run, task ``a73fbc98`` planned 102
renders, was refused, and 34 of its 63 rubric items were never attempted -- no
perception call, no tool call, no render against any of them. Its published
76.74% is 33 points out of the 43 that got graded, from a rubric worth 87.

That refusal is the one the cap has to answer to, because it happened on a
grader that had already been given a way out of it.
``Grader._relax_to_fit_visual_budget`` re-plans a task without the
no-text-layer escalation and grades it on the smaller plan rather than
dropping it, and it returns the strict plans unchanged when relaxing frees
nothing. The merged run's ``grader_source_hash`` is the tree of ``e82bc66``,
the commit that introduced it, and not one of ``a73fbc98``'s items comes back
``visual_budget_downgraded``. The way out was tried and there was none: every
render that task wanted was wanted by a criterion naming something visual.
**102 is a demand nothing in this repository can reduce.**

The older, larger figure is deliberately *not* the basis. At grader
``955be41e`` the same corpus refused task ``43dc9778`` at 134 renders and
dropped it whole -- ``all_items_score_excluded``, 0.0%, a 67-item task leaving
a 185-task corpus without the corpus looking any smaller. But 134 was never a
real demand, and what fixed it was not a bigger budget: ``058d4f8`` narrowed
the escalation so that one unreadable file stops sending a whole task to
pictures, and on the next generation that task plans 68, scores 92.23% and
excludes nothing. A cap sized to clear 134 would have bought that task nothing
and paid twice for it. Sized at 112 it still catches that shape of demand if
it ever returns.

So: the largest irreducible demand the current grader produces, 102, plus what
one further visual item can add, which the run records as ``visual_file_cap``
10. **112.**

What this file is not: a projection. ``test_track2_visual_inventory.py``
counts what criteria ask for by their wording, which is a useful thing to hold
steady and a bad thing to set a budget from: it cannot see the no-text-layer
escalation at all, so the two heaviest renderers on this very run, at 68 and 59,
both project as 2 there. Every number below comes out of a graded run's own
record.

Nothing here calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import json
import math
import re
import statistics
from pathlib import Path

import pytest
import yaml

from core.tool_calling_judge import resolve_visual_file_cap


REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER = Path(__file__).resolve().parents[1]
GRADES_ROOT = REPO_ROOT / "data/grades"
CONFIG_DIR = BATCH_RUNNER / "grading_configs"
README = CONFIG_DIR / "README.md"

#: The 185-task gold corpus, by the fingerprint its payloads carry. Named
#: rather than pattern-matched on filenames, which encode a config hash that
#: this very change moves.
CORPUS_FINGERPRINT = (
    "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
)

BUDGET_EVIDENCE = re.compile(
    r"task_visual_budget_exceeded:required_calls=(\d+),cap=(\d+)"
)

# The two tasks the argument turns on. Eight characters is how the run logs and
# the relaxation docstring both spell them. "Reducible" means a code change
# reduced it -- 058d4f8 did -- not that the grader reduces it at runtime.
REDUCIBLE_TASK = "43dc9778"
IRREDUCIBLE_TASK = "a73fbc98"

# ── measured on the merged 185-task run ──────────────────────────────
# Pinned, not re-derived, for the same reason the inventory's totals are: a
# payload that stops producing these means someone re-graded the corpus, and
# the cap below was argued from the old one.
TASKS_GRADED = 185
TASKS_NEEDING_A_RENDER = 131
MEDIAN_RENDERS_WHEN_NEEDED = 2
P90_RENDERS_WHEN_NEEDED = 13  # nearest-rank, ceil(0.9 * n)
CORPUS_RENDER_TOTAL = 670
BUSIEST_TASK_RENDERS = 68

#: The grader this run used. This digest is the tree of ``e82bc66``, the commit
#: that added ``_relax_to_fit_visual_budget`` -- which is what makes the refusal
#: below evidence of an irreducible demand rather than of a missing feature.
#: Recheck with ``git archive e82bc66`` and ``compute_grader_source_hash``.
GRADER_WITH_A_WAY_OUT = (
    "79c2f5035c4aa826355134dd87cdb8fbc320e5a1cc5fde0d8ecf91957f4eabc6"
)

# ── the two demands, as the runs recorded them ───────────────────────
REDUCIBLE_DEMAND = 134
IRREDUCIBLE_DEMAND = 102
CAP_IN_FORCE_ON_THE_RUN = 72


def _payloads() -> list[tuple[Path, dict]]:
    out = []
    for path in sorted(GRADES_ROOT.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(payload, dict) and "tasks" in payload:
            out.append((path, payload))
    return out


@pytest.fixture(scope="module")
def merged_run() -> dict:
    """The one committed payload that is this corpus, finished."""
    found = [
        payload
        for path, payload in _payloads()
        if payload.get("expected_ordered_task_ids_sha256") == CORPUS_FINGERPRINT
        and payload.get("run_status") == "final"
        and "_shards" not in path.parts
        and "_repeats" not in path.parts
        and "_superseded" not in path.parts
    ]
    assert len(found) == 1, (
        "the visual task cap is argued from exactly one graded run, and "
        f"{len(found)} committed payloads claim to be it. A cap cannot be "
        "argued from an ambiguous record."
    )
    return found[0]


def _task(payload: dict, prefix: str) -> dict:
    matches = [t for t in payload["tasks"] if t["task_id"].startswith(prefix)]
    assert len(matches) == 1, f"{prefix} matched {len(matches)} tasks"
    return matches[0]


def _item_refusal(item: dict) -> tuple[int, int] | None:
    match = BUDGET_EVIDENCE.search(str(item.get("evidence") or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _budget_refusals(task: dict) -> list[tuple[int, int]]:
    found = (_item_refusal(item) for item in task.get("items") or [])
    return [refusal for refusal in found if refusal is not None]


def _shard_holds(payload: dict, prefix: str) -> bool:
    return any(
        t["task_id"].startswith(prefix) for t in payload.get("tasks") or []
    )


# ── what the corpus actually spends ──────────────────────────────────

def test_the_render_volume_this_cap_is_set_against(merged_run):
    """The distribution, so the cap is set against a shape and not a worry.

    Most tasks want a handful. The tail is where a task cap earns its keep,
    and the tail on this corpus is short and steep: nine tenths of the tasks
    that render at all stay inside 13.
    """
    renders = [int(t.get("render_call_count") or 0) for t in merged_run["tasks"]]
    needed = sorted(n for n in renders if n)

    assert len(renders) == TASKS_GRADED
    assert len(needed) == TASKS_NEEDING_A_RENDER
    assert statistics.median(needed) == MEDIAN_RENDERS_WHEN_NEEDED
    assert needed[math.ceil(0.9 * len(needed)) - 1] == P90_RENDERS_WHEN_NEEDED
    assert sum(renders) == CORPUS_RENDER_TOTAL
    assert max(renders) == BUSIEST_TASK_RENDERS


def test_the_cap_the_run_was_graded_under_is_in_its_own_provenance(merged_run):
    """72 is read off the run, not remembered — and so is the grader.

    Both demands below are only meaningful against the cap that refused them,
    and the payload carries it, so nothing here has to trust a config file that
    has since changed. The grader digest matters for the same reason and one
    more: it is what says the refused task had a way out and did not take it.
    """
    visual = merged_run["judge"]["perception"]["visual"]

    assert visual["call_cap_per_task"] == CAP_IN_FORCE_ON_THE_RUN
    assert merged_run["grader_source_hash"] == GRADER_WITH_A_WAY_OUT


# ── the half a code change fixed ─────────────────────────────────────

def test_the_reducible_task_was_dropped_whole_at_the_earlier_grader():
    """134 against 72, and a 67-item task left the corpus at 0.0%.

    This is the shape of the loss that made both later fixes necessary, and it
    is worth keeping in a test because it is invisible in any summary: the task
    is not scored zero, it is dropped, and a corpus of 184 looks like a corpus.
    """
    shards = [
        (path, payload)
        for path, payload in _payloads()
        if "_shards" in path.parts and _shard_holds(payload, REDUCIBLE_TASK)
    ]
    assert shards, "no committed shard holds the reducible task"

    dropped = [
        (path, _task(payload, REDUCIBLE_TASK))
        for path, payload in shards
        if _budget_refusals(_task(payload, REDUCIBLE_TASK))
    ]
    assert len(dropped) == 1, (
        "exactly one committed shard should still show this task refused; "
        f"found {[str(p) for p, _ in dropped]}"
    )
    _, task = dropped[0]

    assert _budget_refusals(task) == [
        (REDUCIBLE_DEMAND, CAP_IN_FORCE_ON_THE_RUN)
    ] * len(task["items"])
    assert task["error"] == "all_items_score_excluded"
    assert task["pct"] == 0.0
    assert int(task.get("render_call_count") or 0) == 0


def test_the_reducible_task_now_grades_inside_the_same_cap(merged_run):
    """68 renders, nothing excluded, 92.23% — at the same cap of 72.

    Nothing about the budget changed between the two runs. ``058d4f8`` narrowed
    the no-text-layer escalation so that one unreadable file stops sending a
    whole task to pictures, and the demand fell from 134 to 68 on its own.

    The point is not that the task is fine. It is that its 134 was never a real
    demand: the same verdicts were reachable on half of it, so a cap sized to
    clear 134 would have bought nothing and paid twice.
    """
    task = _task(merged_run, REDUCIBLE_TASK)

    assert _budget_refusals(task) == []
    assert task["error"] is None
    assert sum(1 for i in task["items"] if i.get("score_excluded")) == 0
    assert int(task["render_call_count"]) == BUSIEST_TASK_RENDERS
    assert task["pct"] == 92.23


# ── the half that is still open, and is what 112 is for ──────────────

def test_the_irreducible_task_lost_a_majority_of_its_rubric(merged_run):
    """102 against 72, on the grader that has a way out, and it did not help.

    Every one of the 34 refused items has the marks of an item that was never
    attempted -- no perception call, no tool call, no render -- so this is not
    a judge that looked and could not tell. It is 34 questions nobody asked.
    """
    task = _task(merged_run, IRREDUCIBLE_TASK)
    refused = [i for i in task["items"] if _item_refusal(i)]

    assert _budget_refusals(task) == [
        (IRREDUCIBLE_DEMAND, CAP_IN_FORCE_ON_THE_RUN)
    ] * 34
    assert len(task["items"]) == 63
    for item in refused:
        assert item["verdict"] == "judge_error"
        assert item["score_excluded"] is True
        assert item["perception_called"] is False
        assert list(item.get("tools_used") or []) == []
        assert int(item.get("render_call_count") or 0) == 0

    assert int(task["render_call_count"]) == 0

    # And the way out was tried. `_relax_to_fit_visual_budget` marks every item
    # it gives up pictures for; none of the 63 is marked, which is the
    # signature of its `relaxed_demand >= strict_demand` return -- relaxing
    # freed nothing. Without this line the refusal would be equally consistent
    # with a grader that had no way out at all.
    assert not [i for i in task["items"] if i.get("visual_budget_downgraded")]


def test_the_published_score_of_that_task_covers_half_its_rubric(merged_run):
    """76.74% is 33 of 43 points, out of a rubric worth 87.

    The cap did not lower this task's score; it shrank what the score is
    about. Which of those two a headline percentage is reporting is a live
    question on its own card, and this test deliberately does not answer it.
    It pins the gap so that raising the cap can be seen to close it.
    """
    task = _task(merged_run, IRREDUCIBLE_TASK)
    rubric_worth = sum(float(i.get("max_score") or 0) for i in task["items"])

    assert task["pct"] == 76.74
    assert (task["total_awarded"], task["total_max"]) == (33.0, 43)
    assert rubric_worth == 87.0
    assert task["total_max"] < rubric_worth / 2


# ── where 112 comes from ─────────────────────────────────────────────

def _configured_cap(name: str) -> int:
    config = yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8"))
    return config["judge"]["perception"]["visual"]["call_cap_per_task"]


def test_the_cap_clears_the_demand_no_relaxation_can_reduce(merged_run):
    """112 = 102 + one more item's worth of files, both read, neither typed.

    The headroom is ``visual_file_cap``, which the run records as 10: it is
    the most a single further visual item can add, so a task one item heavier
    than the heaviest measured still fits.
    """
    headroom = resolve_visual_file_cap(merged_run["judge"])

    assert headroom == 10
    assert _configured_cap("default_v2.yaml") == IRREDUCIBLE_DEMAND + headroom


def test_the_cap_still_catches_the_demand_the_narrowing_removed():
    """Deliberately below 134, and this is the reason to resist rounding up.

    134 is not a demand the current grader produces -- ``058d4f8`` took that
    task to 68 -- so this is not a live saving. It is a guard on the shape of
    demand that produced it. A single unreadable file sending a whole task to
    pictures is a mistake that can be reintroduced, and at a cap of 134 or more
    the benchmark would quietly pay for it instead of refusing and saying so.
    """
    assert _configured_cap("default_v2.yaml") < REDUCIBLE_DEMAND


def test_the_way_out_of_the_budget_has_never_had_to_fire():
    """Relaxation is a backstop, and no committed run has needed it.

    Worth pinning because it is the assumption every figure in this file rests
    on: the render counts here are strict plans, not relaxed ones. The first
    payload with a downgraded item is a payload whose totals mean something
    different, and this test is where that should be noticed.
    """
    marked = [
        (str(path.relative_to(REPO_ROOT)), task["task_id"][:8])
        for path, payload in _payloads()
        for task in payload.get("tasks") or []
        for item in task.get("items") or []
        if item.get("visual_budget_downgraded")
    ]
    carried = [
        1
        for _, payload in _payloads()
        for task in payload.get("tasks") or []
        for item in task.get("items") or []
        if "visual_budget_downgraded" in item
    ]

    assert carried, "no committed payload records the flag at all any more"
    assert not marked, marked


def test_every_grading_config_carries_the_same_visual_task_cap():
    """One cap, thirteen files.

    ``test_perception_caps_have_one_source.py`` guards the module-level
    fallback, which no committed config uses -- every one names its own. That
    leaves the configs free to disagree with each other, and a cap argued from
    one run has to be the cap the other runs use or the argument is about
    nothing.
    """
    caps = {
        path.name: _configured_cap(path.name)
        for path in sorted(CONFIG_DIR.glob("*.yaml"))
    }

    assert caps, "no grading configs found"
    assert set(caps.values()) == {IRREDUCIBLE_DEMAND + 10}, caps


# ── what raising it cannot do ────────────────────────────────────────

def test_no_published_exp003_figure_can_move_when_the_cap_rises():
    """The check behind repinning three exp003 config hashes.

    Raising a ceiling can only change a run that reached it. No committed
    exp003 payload holds a single budget refusal, so no exp003 item was ever
    turned away for want of task budget, and none can start being answered
    now. Same argument the audio cap's repin used, and rerunnable by hand:
    ``grep -rl task_visual_budget_exceeded data/grades/``.
    """
    refused = [
        str(path.relative_to(REPO_ROOT))
        for path, payload in _payloads()
        if any(_budget_refusals(t) for t in payload.get("tasks") or [])
    ]

    assert refused, "the evidence this cap is argued from has gone missing"
    assert not [p for p in refused if "exp003" in p], refused
    assert all("exp_gold_baseline" in p for p in refused), refused


def test_the_cap_change_adds_one_task_worth_of_renders_to_this_corpus(
    merged_run,
):
    """The bill, stated before it is paid rather than discovered after.

    One task of 185 starts rendering. It is a large single task and a small
    corpus-wide change, and both halves of that belong in the record.
    """
    task = _task(merged_run, IRREDUCIBLE_TASK)
    added = IRREDUCIBLE_DEMAND - int(task["render_call_count"] or 0)

    assert added == IRREDUCIBLE_DEMAND
    assert added / CORPUS_RENDER_TOTAL < 0.16


# ── the number and its basis stay in the same place ──────────────────

def test_the_readme_states_the_figures_it_sets_the_cap_from():
    """A cap with a counted basis nobody can find is a cap with none.

    The card this closes asks for the basis to be attached to the number, so
    the operator-facing document has to carry it, not only this file.
    """
    text = README.read_text(encoding="utf-8")

    for figure in (
        str(IRREDUCIBLE_DEMAND + 10),
        str(IRREDUCIBLE_DEMAND),
        str(REDUCIBLE_DEMAND),
        str(CORPUS_RENDER_TOTAL),
        str(BUSIEST_TASK_RENDERS),
        f"{TASKS_NEEDING_A_RENDER} of {TASKS_GRADED}",
    ):
        assert figure in text, f"{figure} is not in grading_configs/README.md"

    assert Path(__file__).name in text, (
        "the README should name the file that recomputes its figures, so a "
        "reader can check them instead of believing them"
    )
