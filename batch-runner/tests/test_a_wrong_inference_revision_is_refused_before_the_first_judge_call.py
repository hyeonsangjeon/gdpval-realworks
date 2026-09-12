"""A mispinned `inference_revision` has to be refused while it is still free.

`grading_design.md` ends on a gap it leaves open on purpose: when the final
relay leg finishes step 7, a human has to pin the upload's commit SHA into the
grading config by hand, and green CI does not mean the SHA is right. Every
config test in the suite checks the pin's *shape* -- forty lowercase hex
characters -- because no offline test can know which commit step 7 will
produce. So the first thing that ever compares the pinned value against a real
one is `step8_grade.py` itself, at grading time.

That makes *where* the comparison sits a cost question rather than a style
one. `_validate_pinned_rerun_identity` raises and `main()` returns 1, so the
run stops either way; what the ordering decides is whether it stops before or
after the judge has been paid. The repository has been on the wrong side of
this distinction before -- `bind_run_to_ledger` returned a write-note with no
`status` and killed a run *after* its calls had been billed -- which is why
this is pinned by a test instead of trusted to stay put.

Today the order inside `main()` is:

    resolve_source_inference_identity   reads what the run recorded
    _validate_pinned_rerun_identity     compares the pin against it, or raises
    Grader(...)                         first construction of an Azure client
    grader.grade_task(...)              the only paid judge surface

Three properties are worth keeping, and the test asserts each one separately
so a failure says which:

* the comparison happens after the actual value is resolved -- comparing
  against a value you have not read yet cannot fail for the right reason;
* the comparison happens before any judge client exists at all;
* the comparison happens before every `grade_task` call, not merely the
  first one.

The ordering is read out of the AST rather than by grepping line numbers,
because a test keyed to line numbers would fail on every unrelated edit and
be silenced rather than read.

A fourth test covers the behaviour instead of the layout: a config whose
`rerun_identity` block disagrees with the resolved revision has to raise,
including when only the SHA disagrees and every other pinned field matches.
That is the exact shape of the mistake this is guarding -- the experiment id,
the task count, the ordered task ids and the rubric SHA are all knowable today
and will be right; the upload SHA is the one field that is copied by hand on
the day.

Nothing here contacts a provider, and nothing here reads the Hub.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import step8_grade

GRADER = Path(__file__).resolve().parents[1] / "step8_grade.py"

#: The call that reads what the inference run actually recorded.
RESOLVES = "resolve_source_inference_identity"
#: The call that compares the config's pin against it.
VALIDATES = "_validate_pinned_rerun_identity"
#: The first construction of anything holding an Azure client.
BUILDS_JUDGE = "Grader"
#: The only surface in this file that spends money.
SPENDS = "grade_task"


def _call_lines() -> dict[str, list[int]]:
    tree = ast.parse(GRADER.read_text(encoding="utf-8"))
    main = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        ),
        None,
    )
    assert main is not None, "step8_grade.py has no main() to read"

    found: dict[str, list[int]] = {}
    for node in ast.walk(main):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name in (RESOLVES, VALIDATES, BUILDS_JUDGE, SPENDS):
            found.setdefault(name, []).append(node.lineno)
    return {name: sorted(lines) for name, lines in found.items()}


CALLS = _call_lines()


def _require(name: str) -> list[int]:
    lines = CALLS.get(name)
    assert lines, (
        f"main() no longer calls {name}(). If it was renamed, rename it here "
        f"too -- if it was removed, the ordering this file pins is gone and "
        f"the removal is what needs review."
    )
    return lines


def test_the_pin_is_compared_only_after_the_actual_value_is_resolved():
    resolved = _require(RESOLVES)[0]
    validated = _require(VALIDATES)[0]
    assert resolved < validated, (
        f"{VALIDATES} runs at line {validated}, before {RESOLVES} at line "
        f"{resolved}. It would be comparing the pin against a value that has "
        f"not been read yet."
    )


def test_the_pin_is_compared_before_a_judge_client_is_ever_built():
    validated = _require(VALIDATES)[0]
    built = _require(BUILDS_JUDGE)[0]
    assert validated < built, (
        f"{BUILDS_JUDGE}(...) is constructed at line {built}, before the "
        f"pinned identity is checked at line {validated}. A mispinned "
        f"inference_revision is a free failure only while it happens before "
        f"the judge exists."
    )


def test_the_pin_is_compared_before_every_paid_call_not_just_the_first():
    validated = _require(VALIDATES)[0]
    spends = _require(SPENDS)
    too_early = [line for line in spends if line < validated]
    assert not too_early, (
        f"{SPENDS}(...) is reached at {too_early} before the pinned identity "
        f"is checked at line {validated}. Whatever those calls spend is spent "
        f"whether or not the config was grading the right upload."
    )


def test_a_config_whose_only_wrong_field_is_the_sha_still_raises():
    """Every other pinned field is knowable today. This one is typed by hand."""
    task_ids = ["aaaa", "bbbb", "cccc"]
    pinned = {
        "rerun_identity": {
            "experiment_id": "exp035_codex_foundry_full220",
            "expected_task_count": len(task_ids),
            "rubric_commit_sha": "11e7900cdcac61bc4daf59e65feb238acda98fbf",
            "inference_revision": "a" * 40,
            "task_ids": list(task_ids),
        }
    }

    # The control: everything agrees, so nothing is raised.
    step8_grade._validate_pinned_rerun_identity(
        pinned,
        experiment_id="exp035_codex_foundry_full220",
        task_ids=list(task_ids),
        rubric_commit_sha="11e7900cdcac61bc4daf59e65feb238acda98fbf",
        inference_revision="a" * 40,
    )

    with pytest.raises(ValueError, match="inference_revision"):
        step8_grade._validate_pinned_rerun_identity(
            pinned,
            experiment_id="exp035_codex_foundry_full220",
            task_ids=list(task_ids),
            rubric_commit_sha="11e7900cdcac61bc4daf59e65feb238acda98fbf",
            inference_revision="b" * 40,
        )


def test_a_config_with_no_rerun_identity_is_not_checked_at_all():
    """Absence is a silent pass, so a pinned config may not lose the block.

    This is not a defect to fix here -- six of the fourteen grading configs
    legitimately have no `rerun_identity` -- but it does mean the guard above
    protects exp035 only for as long as the block is present. Deleting it
    disables all five comparisons (experiment id, task count, rubric SHA,
    inference revision, ordered task ids) without failing anything.
    """
    step8_grade._validate_pinned_rerun_identity(
        {},
        experiment_id="anything",
        task_ids=["x"],
        rubric_commit_sha="deadbeef" * 5,
        inference_revision="c" * 40,
    )
