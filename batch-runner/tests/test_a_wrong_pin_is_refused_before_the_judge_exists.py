"""A grading config that pins the wrong inference revision must cost nothing.

``rerun_identity.inference_revision`` is already checked twice, and both checks
have tests. ``validate_grading_config`` rejects anything that is not 40 lowercase
hex, so a placeholder never loads; ``_validate_pinned_rerun_identity`` rejects a
well-formed sha that does not match the revision the grader actually resolved
from the inference results it downloaded, which is what catches a sha that was
copied from the wrong run.

What nothing checked is *where in ``main()`` the second one sits*. It is the
position, not the comparison, that decides whether a wrong pin is a free mistake
or a paid one: the same ``ValueError`` raised after the first judge call is an
invoice, and the judge on the sol_max path is deliberately unpriced, so that
invoice could not even be stated in dollars afterwards. Today the check runs
immediately after task filtering, several hundred lines before the ``Grader``
is constructed and further still before the first ``grade_task``, so a mismatch
returns ``1`` having asked nothing.

The comparison also has to come *after* the value it is compared against.
``resolve_source_inference_identity`` is what reads the revision the downloaded
inference actually carries, and the pin is checked against its result. That
ordering is asserted on its own below, because the two ends can move
independently and the failure should say which one did.

This matters right now for a config that does not exist yet. exp035's grading
config cannot pin a real ``inference_revision`` until the final relay leg runs
step 7 and uploads the filled parquet -- the round is mid-relay, intermediate
legs skip steps 3 through 7, and there is no sha to write. The rule is to leave
it unwritten rather than guess one. This test is what makes the opposite
mistake cheap if it is ever made anyway: a guessed sha is refused before the
judge exists, for zero calls. If the check ever drifts below the ``Grader``,
that stops being true silently, which is the failure this file exists to catch.
"""

import ast
from pathlib import Path

import pytest

STEP8 = Path(__file__).resolve().parents[1] / "step8_grade.py"

#: The call that compares the config's pinned identity against what the
#: downloaded inference actually says about itself.
PIN_CHECK = "_validate_pinned_rerun_identity"

#: The call that reads what the downloaded inference says about itself. The pin
#: is compared against its result, so the check is meaningless above this line.
RESOLVES = "resolve_source_inference_identity"

#: Constructing this is the first thing in ``main()`` that can reach a paid
#: model. ``Grader._classify`` is an attribute read on the class and appears
#: earlier in the file, outside ``main()``; only a call whose callee is the
#: bare name counts as building one.
JUDGE_BUILD = "Grader"

#: The call that actually spends. Kept separate from the construction so that
#: moving one without the other still fails here.
JUDGE_CALL = "grade_task"


def _main_body() -> ast.FunctionDef:
    tree = ast.parse(STEP8.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("step8_grade.py has no module-level main()")


def _lines_of(kind: str) -> list[int]:
    """Line numbers inside ``main()`` where one landmark occurs."""
    lines = []
    for node in ast.walk(_main_body()):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if kind in (PIN_CHECK, JUDGE_BUILD, RESOLVES):
            if isinstance(func, ast.Name) and func.id == kind:
                lines.append(node.lineno)
        elif isinstance(func, ast.Attribute) and func.attr == kind:
            lines.append(node.lineno)
    return sorted(lines)


@pytest.mark.parametrize("landmark", [RESOLVES, PIN_CHECK, JUDGE_BUILD, JUDGE_CALL])
def test_main_still_contains_the_landmark_the_ordering_is_measured_between(
    landmark: str,
):
    """Without this, a rename would make the ordering test vacuously true.

    An ``ast`` search that finds nothing returns an empty list, and ``min()``
    of an empty list is the kind of failure that gets "fixed" by adding a
    default. Each landmark is asserted present on its own so that the failure
    names which one moved.
    """
    assert _lines_of(landmark), (
        f"main() no longer calls {landmark!r}. The ordering guarantee below is "
        "measured between this and the pinned-identity check, so it cannot be "
        "checked until this is pointed at whatever replaced it."
    )


def test_the_pin_is_compared_only_after_the_value_it_is_compared_against():
    """Running the check too early makes it fail for the wrong reason.

    ``_validate_pinned_rerun_identity`` is handed the resolved revision as an
    argument. Moving it above ``resolve_source_inference_identity`` therefore
    does not produce a comparison against a stale value -- it produces an
    ``UnboundLocalError``, or a comparison against whatever unrelated thing that
    name held. The run still stops for free, so this is not a cost assertion
    like the one below; what it protects is the diagnosis. An operator who typed
    the wrong sha should be told that, not handed a traceback from a different
    part of the file.
    """
    resolved = min(_lines_of(RESOLVES))
    pin_check = min(_lines_of(PIN_CHECK))

    assert resolved < pin_check, (
        f"main() checks the pinned identity at line {pin_check}, before "
        f"{RESOLVES} has read the actual revision at line {resolved}. The "
        "comparison would not be against the downloaded inference at all."
    )


def test_a_wrong_pin_is_refused_before_any_judge_is_built():
    """The refusal has to happen while the run is still free.

    ``_validate_pinned_rerun_identity`` raising is already covered for all four
    pinned fields, including ``inference_revision``. What is asserted here is
    only that ``main()`` reaches it first -- before it builds a ``Grader`` and
    before it asks one to grade anything.
    """
    pin_check = min(_lines_of(PIN_CHECK))
    judge_build = min(_lines_of(JUDGE_BUILD))
    judge_call = min(_lines_of(JUDGE_CALL))

    assert pin_check < judge_build, (
        f"step8_grade.main() builds a Grader at line {judge_build} but does "
        f"not check the pinned rerun identity until line {pin_check}. A config "
        "pinning the wrong inference_revision would be refused after the judge "
        "exists rather than before it."
    )
    assert pin_check < judge_call, (
        f"step8_grade.main() calls grade_task at line {judge_call} before "
        f"checking the pinned rerun identity at line {pin_check}. A wrong pin "
        "would be paid for and then rejected."
    )


def test_the_pin_check_is_not_reached_only_on_some_paths():
    """Running early is worth nothing if it can be skipped.

    The test above compares line numbers, which answers "before the judge?"
    but not "at all?". Wrapping the call in ``if args.strict:`` or
    ``if not args.resume:`` would keep every line number where it is and still
    leave the default path unchecked, so a guessed sha would reach the judge
    on the ordinary invocation and be caught only on the one nobody uses.

    ``try``/``except`` is not a branch in this sense -- it is the shape the
    call already has, and it re-raises as ``return 1`` rather than skipping.
    A conditional, a loop, or a ``match`` arm is.
    """
    skippable = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Match)
    body = _main_body()

    def enclosing(node: ast.AST, ancestry: tuple) -> list[str]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name) and func.id == PIN_CHECK:
                    return [type(a).__name__ for a in ancestry]
            deeper = enclosing(
                child,
                ancestry + (child,) if isinstance(child, skippable) else ancestry,
            )
            if deeper:
                return deeper
        return []

    branches = enclosing(body, ())

    assert branches == [], (
        f"main() reaches {PIN_CHECK} only inside {branches}. The pinned "
        "identity would go unchecked on any path that skips that branch, so a "
        "guessed inference_revision could reach the judge on the default "
        "invocation no matter how early the call is written."
    )
