"""exp035's grading config must differ from exp003's only on the inference side.

`exp035_codex_foundry_full220_v2_sol_max.yaml` opens by claiming that its
judge, rubric, grader, tpm_guard, prompt and output blocks are "copied unchanged
from regrade_exp003_v2_sol_max_score_excluded -- verified block-by-block, not
asserted". That was true when it was written, and it was verified by hand. A
comment cannot keep it true, and everything the pair is for rests on it.

Both configs grade the same fixed 220-task corpus against the same rubric
revision. The difference the pair is supposed to isolate is on the inference
side -- execution harness, model, deployment. Any judge-side difference between
them lands in the same score gap and is indistinguishable from it afterwards,
because a grade records what it was run with but not what the *other* grade was
run with. There is no post-hoc way to subtract it back out.

The realistic way this breaks is not malice. exp035's grading is slow by
construction: `max_concurrent: 1` with 500 ms between calls, across 6,717
rubric items. Raising the concurrency of *one* of the two configs to finish
sooner is an obvious, well-meant edit, and it is exactly the edit that silently
ends the comparison. So is adding a judge option to one file while leaving the
other alone, or bumping one `prompt.version`.

## What the six blocks decide

| block | decides |
|---|---|
| `judge` | which model answers, on which deployment and API version, with what reasoning effort, token ceiling, seed and temperature, and how a critical item is defined |
| `rubric` | which rubric revision the items come from |
| `prompt` | which template the question is asked with, and its version |
| `grader` | how the answer is counted: evidence rules, retry allowance, truncation |
| `tpm_guard` | whether an item gets asked at all, via pacing and 429 retry budget |
| `output` | how the result file names the identity it was produced under |

`tpm_guard` is the one that needs stating precisely: pacing does not change what
the judge says about an item it answers. What it changes is whether an item
exhausts its retries and is recorded as an error instead of a score. That is
enough to move a total, so it belongs on the fixed side.

## What this test does not claim

Block equality does **not** make the pair a ranking. Three inference-side axes
move at once -- harness, model and deployment -- so a gap between the two grades
is a difference between two configurations and cannot be attributed to any one
of them. `docs/run_records/grading_design.md` says so, and holding the judge
fixed does not upgrade that. This file only guarantees that the *judge* is not a
fourth moving axis.

It also proves nothing about the grades already on disk. A config edited after a
grade ran leaves that grade's own recorded identity intact; this test protects
the next grade, not the last one.
"""

from pathlib import Path

import pytest
import yaml

GRADING_CONFIGS = Path(__file__).resolve().parents[1] / "grading_configs"

#: The grade this round is compared against. Its inference predates the
#: provenance sidecar and ran on a different harness entirely; the judge side is
#: what the two have in common.
REFERENCE = "regrade_exp003_v2_sol_max_score_excluded.yaml"

#: The grade of the Codex + Foundry round on the same fixed corpus.
SUBJECT = "exp035_codex_foundry_full220_v2_sol_max.yaml"

#: Everything that decides what the judge is asked, how its answer is counted,
#: and whether it is asked at all. These must be identical in both files.
FIXED_BLOCKS = (
    "schema_version",
    "judge",
    "rubric",
    "prompt",
    "grader",
    "tpm_guard",
    "output",
)

#: The blocks that are supposed to differ. `rerun_identity` is where the
#: inference side lives -- experiment id, inference revision, and the pinned
#: task order, which is the same 220 ids in a different sequence.
MOVING_BLOCKS = ("config_name", "description", "rerun_identity")


def _load(name: str) -> dict:
    path = GRADING_CONFIGS / name
    assert path.is_file(), (
        f"{name} is missing. If it was renamed, update this file rather than "
        "deleting it -- the comparison it guards is still the one being run."
    )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{name} did not parse to a mapping"
    return data


@pytest.fixture(scope="module")
def pair() -> tuple[dict, dict]:
    return _load(REFERENCE), _load(SUBJECT)


def test_the_two_configs_declare_the_same_set_of_blocks(pair) -> None:
    """A key present in one file and absent from the other is already a drift.

    Checked separately from the value comparison because the two failures want
    different fixes: a missing key is usually a half-applied edit, while a
    changed value is usually a deliberate one that forgot its twin.
    """
    reference, subject = pair
    only_reference = sorted(set(reference) - set(subject))
    only_subject = sorted(set(subject) - set(reference))
    assert not only_reference and not only_subject, (
        f"{REFERENCE} and {SUBJECT} no longer describe the same shape: "
        f"only in the reference {only_reference}, only in the subject "
        f"{only_subject}. Apply the change to both, or record in both "
        "descriptions that the judge side has diverged and the score gap is no "
        "longer attributable to the inference side alone."
    )


@pytest.mark.parametrize("block", FIXED_BLOCKS)
def test_a_judge_side_block_is_identical_in_both_configs(block: str, pair) -> None:
    """The fixed axis. Compared parsed, so comments and layout are free to differ.

    Parsed rather than textual on purpose: the two files carry different
    comments above the same values, and requiring byte equality would make the
    honest documentation of *why* a value is what it is into a test failure.
    What must match is what the loader sees.
    """
    reference, subject = pair
    assert block in reference and block in subject, (
        f"{block} is not present in both configs; see the shape test above"
    )
    assert reference[block] == subject[block], (
        f"`{block}` differs between {REFERENCE} and {SUBJECT}.\n"
        f"  reference: {reference[block]!r}\n"
        f"  subject:   {subject[block]!r}\n"
        "Both files grade the same 220 tasks, and the pair exists to isolate "
        "the inference side. A judge-side difference lands in the same score "
        "gap and cannot be separated from it afterwards. If the change is "
        "wanted, make it in both files; if it is wanted in only one, the two "
        "grades stop being comparable and both descriptions have to say so."
    )


@pytest.mark.parametrize("block", MOVING_BLOCKS)
def test_an_inference_side_block_actually_differs(block: str, pair) -> None:
    """The moving axis, asserted so the test above cannot pass by duplication.

    Without this, a config accidentally copied over its reference wholesale
    would satisfy every equality check in this file while grading the wrong
    round under the wrong identity.
    """
    reference, subject = pair
    assert reference.get(block) != subject.get(block), (
        f"`{block}` is identical in {REFERENCE} and {SUBJECT}. These grade "
        "different rounds, so this block cannot legitimately match."
    )


def test_the_pair_pins_one_rubric_revision_in_two_places(pair) -> None:
    """`rubric.revision` and `rerun_identity.rubric_commit_sha` must agree.

    The rubric revision is written twice per file: once in the shared `rubric`
    block that the loader fetches from, and once in `rerun_identity` where the
    grade records what it claims to have used. The equality test above holds the
    first across the pair; nothing holds the second, and a grade that fetches
    one revision while recording another is worse than one that fails.
    """
    for name, config in ((REFERENCE, pair[0]), (SUBJECT, pair[1])):
        fetched = config["rubric"]["revision"]
        recorded = config["rerun_identity"]["rubric_commit_sha"]
        assert fetched == recorded, (
            f"{name} fetches rubric revision {fetched} but records "
            f"{recorded} as the one it used."
        )
