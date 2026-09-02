"""Which tasks a repeat audio measurement has to buy, counted rather than chosen.

The repeat-variation card asks for a confidence interval on how often the
grader changes its mind about a *listening* criterion between two runs of the
same answers. The number quoted for that today is 38%, and it is not usable:
it is a difference between two smokes at different grader fingerprints, so it
measures the code change as much as the grader. An interval needs repeats at
one fingerprint, and the repeats that exist cannot supply them.

That is the first thing checked here, because it is what makes anything paid
worth dispatching. Three runs of ``gold_ceiling_30_v2_sol_max`` sit at one
fingerprint, and ``38889c3b`` -- a task with ten audio criteria -- is one of
their thirty. They still contain no audio: at that fingerprint the task routes
``{text: 23, formatting: 12}`` with zero perception calls, and on the merged
185 it routes ``{text: 15, formatting: 10, audio: 10}`` with six. The audio
routing landed after those runs were bought. ``analyze_repeat_variation.py``
already refuses to shape a run containing audio for exactly this reason.

The second is the cohort itself. On the merged 185-task run, 31 of 8,816 items
route AUDIO, and they belong to three tasks. This file derives that set from
the payload rather than trusting the config's copy of it, so a corpus or a
router that moves shows up here instead of in a run that quietly graded the
wrong three.

The third is a bound that does not read that run at all. Audio reaches the
listening path from inside a container -- one .zip and two .mp4 -- and only
seven of the 185 gold bundles carry a .mp4 or a .zip. The other 178 are .pdf,
.xlsx, .docx and friends, which cannot hold audio whatever their criteria say.
So the derived set can only be wrong by omitting one of four named .zip tasks,
which is small enough to check by hand and is checked below.

The same fact is why the pin cannot be derived from filenames.
``GRADER_AUDIO_EXTENSIONS`` matches nothing in this corpus: not one gold
deliverable is a bare .wav or .mp3, so an extension projection returns the
empty set. Only a run that probed the containers knows.

Nothing here calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from step8_grade import _ordered_task_ids_sha256  # noqa: E402
from core.media_types import GRADER_AUDIO_EXTENSIONS  # noqa: E402
from scripts import analyze_repeat_variation as rv  # noqa: E402

BATCH_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_ROOT.parent
GRADES_ROOT = REPO_ROOT / "data/grades"
CONFIG = BATCH_ROOT / "grading_configs/gold_audio_repeat_v2_sol_max.yaml"
FULL = BATCH_ROOT / "grading_configs/gold_ceiling_185_v2_sol_max.yaml"
MANIFEST = BATCH_ROOT / "experiments/gold_corpus/gold_deliverable_manifest.json"

#: The 185-task gold corpus, by the digest its payloads carry rather than by a
#: filename, which encodes config and grader hashes that keep moving.
CORPUS_FINGERPRINT = (
    "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
)

#: Containers a probe can find audio inside. Deliberately not
#: ``GRADER_AUDIO_EXTENSIONS`` -- see ``test_no_gold_deliverable_is_a_bare_audio_file``.
AUDIO_CAPABLE_CONTAINERS = frozenset({".mp4", ".zip"})

#: The four container-bearing tasks that did *not* route audio. Named so the
#: bound below is a list a reader can check rather than a count they must
#: trust.
CONTAINERS_WITHOUT_AUDIO = ("5e2b6aab", "0e386e32", "7de33b48", "4122f866")

#: What the merged run recorded, per task. Pinned so a payload that stops
#: producing these is caught as a changed measurement rather than absorbed.
AUDIO_ITEMS_PER_TASK = {
    "38889c3b-e3d4-49c8-816a-3cc8e5313aba": 10,
    "e222075d-5d62-4757-ae3c-e34b0846583b": 7,
    "75401f7c-396d-406d-b08e-938874ad1045": 14,
}
CORPUS_AUDIO_ITEMS = 31

# ── the 30-task repeat cohort, by the identity the analysis pins ─────────
THIRTY_TASK_DIGEST = next(
    value for label, _, value in rv.PINNED_FINGERPRINTS if label == "task list digest"
)
THIRTY_TASK_GRADER = next(
    value for label, _, value in rv.PINNED_FINGERPRINTS if label == "grader source digest"
)


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
def all_payloads() -> list[tuple[Path, dict]]:
    return _payloads()


@pytest.fixture(scope="module")
def merged_185(all_payloads) -> dict:
    """The one committed payload that is the whole gold corpus, finished."""
    found = [
        payload
        for path, payload in all_payloads
        if payload.get("expected_ordered_task_ids_sha256") == CORPUS_FINGERPRINT
        and payload.get("run_status") == "final"
        and not {"_shards", "_repeats", "_superseded"} & set(path.parts)
    ]
    assert len(found) == 1, (
        "the audio cohort is derived from exactly one graded run, and "
        f"{len(found)} committed payloads claim to be it. A cohort cannot be "
        "derived from an ambiguous record."
    )
    return found[0]


@pytest.fixture(scope="module")
def thirty_task_runs(all_payloads) -> list[dict]:
    """The three same-fingerprint repeats the interval work already owns."""
    return [
        payload
        for path, payload in all_payloads
        if payload.get("expected_ordered_task_ids_sha256") == THIRTY_TASK_DIGEST
        and payload.get("grader_source_hash") == THIRTY_TASK_GRADER
        and payload.get("run_status") in {"final", "diagnostic"}
        and "_shards" not in path.parts
    ]


@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gold_bundles() -> dict[str, list[str]]:
    """task_id -> the suffixes its gold deliverable bundle ships."""
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = document["tasks"] if "tasks" in document else document
    return {
        row["task_id"]: sorted(
            {Path(f["graded_path"]).suffix.lower() for f in row["files"]}
        )
        for row in rows
        if row.get("files")
    }


def _audio_counts(payload: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in payload["tasks"]:
        n = sum(
            1
            for item in task.get("items") or []
            if item.get("routing_modality") == rv.FORBIDDEN_MODALITY
        )
        if n:
            counts[task["task_id"]] = n
    return counts


# ── why anything has to be bought at all ─────────────────────────────────


def test_the_repeats_that_exist_hold_no_audio_despite_holding_an_audio_task(
    thirty_task_runs,
):
    """The premise. Without this, the cheap answer is to reuse what we own.

    ``38889c3b`` is in that cohort and carries ten audio criteria on the merged
    185, so the cohort looks like free audio repeat data. It is not: those runs
    predate the routing, and the task was graded there without a single
    perception call. A flip rate computed from them would be a flip rate for
    text criteria wearing an audio task's name.
    """
    assert len(thirty_task_runs) == rv.EXPECTED_RUN_COUNT, (
        f"expected {rv.EXPECTED_RUN_COUNT} committed runs at the 30-task "
        f"fingerprint, found {len(thirty_task_runs)}"
    )

    audio_task = "38889c3b-e3d4-49c8-816a-3cc8e5313aba"
    for run in thirty_task_runs:
        assert len(run["tasks"]) == rv.EXPECTED_TASK_COUNT
        held = {task["task_id"] for task in run["tasks"]}
        assert audio_task in held, (
            "the 30-task cohort no longer holds 38889c3b; the comparison this "
            "test draws its premise from has moved"
        )
        assert _audio_counts(run) == {}, (
            "an existing repeat run now carries audio-routed items. If that is "
            "real, the paid cohort below may be unnecessary -- check before "
            "dispatching it, and check FORBIDDEN_MODALITY too."
        )

        task = next(t for t in run["tasks"] if t["task_id"] == audio_task)
        assert task.get("perception_call_count") == 0, (
            "38889c3b called perception in a run whose items are all text and "
            "formatting; the two facts this premise rests on disagree"
        )


def test_the_analysis_still_refuses_to_fold_audio_into_those_intervals():
    """The machine-enforced half of the same point.

    ``shape_problems`` raises on any run containing an audio item, so a paid
    audio cohort cannot be handed to the 30-task analysis and averaged in. The
    refusal is exercised rather than read off the constant, because a constant
    with no reader is a comment.
    """
    assert rv.FORBIDDEN_MODALITY == "audio"

    def run(modality: str) -> dict:
        return {
            "_label": f"run carrying one {modality} item",
            "tasks": [
                {
                    "task_id": "38889c3b-e3d4-49c8-816a-3cc8e5313aba",
                    "items": [
                        {
                            "rubric_item_id": "c1",
                            "routing_modality": modality,
                            "verdict": "pass",
                            "awarded_score": 2,
                        }
                    ],
                }
            ],
        }

    # The control: the identical shape routed as text passes cleanly, so the
    # refusal below is about the modality and not about the stub.
    assert rv.shape_problems([run("text")] * 3) == []

    problems = rv.shape_problems([run("audio")] * 3)
    assert any(rv.FORBIDDEN_MODALITY in problem for problem in problems), (
        "the analysis accepted a run carrying audio items; audio flipping "
        f"can now be folded into intervals that never measured it: {problems}"
    )


# ── the cohort, derived from the run that probed ─────────────────────────


def test_the_pin_is_every_task_the_graded_run_listened_to(config, merged_185):
    """The coverage claim, derived rather than asserted.

    The config could name any three tasks and look purposeful. What makes the
    pin evidence is that it equals the set the merged run measured -- so if a
    fourth task ever routes audio, this fails and the cohort is widened before
    it is bought, rather than after three runs have measured two thirds of it.
    """
    measured = _audio_counts(merged_185)
    assert measured == AUDIO_ITEMS_PER_TASK, (
        "the graded run's audio population moved. Update the pin, the config "
        f"and this table together: {measured}"
    )
    assert sum(measured.values()) == CORPUS_AUDIO_ITEMS

    pinned = config["rerun_identity"]["task_ids"]
    assert set(pinned) == set(measured), (
        f"the cohort pins {sorted(pinned)} but the run listened to "
        f"{sorted(measured)}; change the config, not this assertion"
    )
    assert config["rerun_identity"]["expected_task_count"] == len(measured)
    assert len(pinned) == len(set(pinned)), "the pin repeats a task"


def test_the_pin_follows_canonical_corpus_order(config, merged_185):
    """A reordering is a refusal, so it may as well be caught for free.

    ``step8_grade.py`` refuses a pinned list that is not in canonical source
    order and compares the pinned list to the selected list by equality. That
    refusal arrives after the workflow has started; this one arrives in CI.
    """
    order = [task["task_id"] for task in merged_185["tasks"]]
    positions = [order.index(task_id) for task_id in config["rerun_identity"]["task_ids"]]
    assert positions == sorted(positions), (
        f"the pin is out of corpus order: positions {positions}"
    )


# ── a bound that does not read the graded run ────────────────────────────


def test_no_gold_deliverable_is_a_bare_audio_file(gold_bundles):
    """Why the pin cannot come from filenames, stated as the measurement.

    If any bundle shipped a .wav or .mp3 outright, a reader could reasonably
    propose deriving this cohort by extension and skipping the graded run. None
    does. Every audio criterion in this corpus is answered from inside a
    container, which only a probe opens.
    """
    matched = {
        task_id: suffixes
        for task_id, suffixes in gold_bundles.items()
        if set(suffixes) & GRADER_AUDIO_EXTENSIONS
    }
    assert matched == {}, (
        "a gold bundle now ships a bare audio file. An extension projection "
        f"would find it, which it could not before: {matched}"
    )


def test_only_seven_bundles_could_hold_audio_at_all(config, gold_bundles):
    """The bound. 178 of the 185 are ruled out without reading a grade.

    A .pdf or a .xlsx cannot hold audio whatever its criteria ask for, so the
    derived cohort can only be wrong by omitting one of the four .zip tasks
    that did not route audio. Those four are named, which is the point: the
    residual doubt is a list, not a probability.
    """
    assert len(gold_bundles) == 185

    candidates = {
        task_id
        for task_id, suffixes in gold_bundles.items()
        if set(suffixes) & AUDIO_CAPABLE_CONTAINERS
    }
    assert len(candidates) == 7, (
        f"the corpus now has {len(candidates)} container-bearing bundles, not "
        "7; the bound this test draws has moved and the four named exceptions "
        "below are no longer the whole residual"
    )

    pinned = set(config["rerun_identity"]["task_ids"])
    assert pinned <= candidates, (
        "the cohort pins a task whose bundle carries nothing audio can hide "
        f"in: {sorted(pinned - candidates)}"
    )

    remainder = sorted(task_id[:8] for task_id in candidates - pinned)
    assert remainder == sorted(CONTAINERS_WITHOUT_AUDIO), (
        f"the container-bearing tasks outside the cohort are now {remainder}; "
        "check each one's routing before widening or narrowing the pin"
    )


def test_the_pinned_containers_are_the_ones_the_argument_names(gold_bundles):
    """One .zip and two .mp4, as the config's description says."""
    shipped = collections.Counter(
        suffix
        for task_id in AUDIO_ITEMS_PER_TASK
        for suffix in gold_bundles[task_id]
        if suffix in AUDIO_CAPABLE_CONTAINERS
    )
    assert shipped == collections.Counter({".mp4": 2, ".zip": 1}), (
        f"the cohort's containers are now {dict(shipped)}; the config's "
        "description says one .zip and two .mp4"
    )


# ── and a repeat here cannot land on anybody else's evidence ─────────────


def test_the_cohort_forks_off_both_existing_measurements(config):
    """Where the paid runs will land, and what they cannot overwrite.

    A pinned list that is a proper subset makes the run diagnostic, which forks
    the output into ``_diagnostic/<scope_sha>/``. That digest is a function of
    the pin, so it differs from the 185-task run's and from the 30-task
    cohort's -- meaning repeats here cannot overwrite either, including when
    they fail.
    """
    scope = _ordered_task_ids_sha256(config["rerun_identity"]["task_ids"])
    assert scope not in {CORPUS_FINGERPRINT, THIRTY_TASK_DIGEST}, (
        "the audio cohort resolves to a directory an existing measurement "
        "already owns"
    )
    assert scope == (
        "b16d9b188a763fa9382d9b18df796b2f08cf284b47619195a2feba963149063c"
    ), (
        "the cohort's scope digest moved, so the pin moved. That is allowed, "
        "but any repeats already bought are under the old digest and are not "
        "repeats of this one."
    )


def test_runtime_semantics_are_the_full_runs(config):
    """Only the identity may differ, or the repeats measure the settings.

    The point of a repeat is that everything except the dice is held still. If
    this cohort graded with a different cap, effort or prompt than the corpus
    it is a cohort of, its flip rate would not describe the corpus.
    """
    full = yaml.safe_load(FULL.read_text(encoding="utf-8"))
    identity = {"config_name", "description", "rerun_identity"}

    moved = {key for key in set(config) | set(full) if config.get(key) != full.get(key)}
    assert moved == identity, (
        f"the audio cohort differs from the full run in {sorted(moved)}; only "
        f"{sorted(identity)} may differ"
    )

    moved_identity = {
        key
        for key in set(config["rerun_identity"]) | set(full["rerun_identity"])
        if config["rerun_identity"].get(key) != full["rerun_identity"].get(key)
    }
    assert moved_identity == {"expected_task_count", "task_ids"}, (
        "the cohort's rerun identity differs from the full run's in "
        f"{sorted(moved_identity)}; the rubric and inference revisions must "
        "be the same corpus"
    )
