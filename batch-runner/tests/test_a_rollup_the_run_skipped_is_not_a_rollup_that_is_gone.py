"""A roll-up the run skipped is not a roll-up that is gone.

``step6_report.py`` reads ``file_generation`` from ``validate_stats.json``,
which only step 5 writes, and ``batch-run.yml`` skips step 5 on an ``&&`` of
four terms. Any one of them leaves the published report carrying nulls, and a
null there means "not counted" — the distinction already held on the reading
side by ``scripts/__tests__/file-generation-denominator.test.mjs``.

What was missing is that the count is still recoverable. Step 4's own gate does
not include ``dry_run``, so a dry run's artifact keeps the upload-staging
parquet; the manifest and the prepared scope are in the same artifact. That is
every input step 5 reads. ``recover_file_rollup.py`` points step 5's own
``validate()`` at an unpacked artifact and gets the number back, offline, with
no model call and nothing spent.

Measured, not argued: exp034 (run ``34540053904``, dispatched ``dry_run=true``)
publishes ``needs_files_total: null``. Recovered from its artifact it is 28
required, 22 produced, 6 failed — and all 8 rows with no file are exactly the 8
tasks that errored, so every task that finished produced its deliverable. The
shortfall is 5 rate limits and 3 content filters, not a file-generation defect.
A reader looking at ``null`` cannot tell those two apart, which is the whole
reason to recover it rather than leave it.

These tests hold the two things that would quietly undo that:

  * the recovered figure must not be able to overwrite a measured one, or
    replace itself on a re-run — a reconstruction and a measurement are not
    the same kind of evidence and the report has to keep saying which it has;
  * the four skip reasons the tool offers must stay the four the workflow
    actually has, so an operator cannot be forced to mislabel why a run was
    skipped, and a fifth cannot appear with no name to give it.

The end-to-end recovery is not re-run here: it needs the 431 MB artifact, and
the manifest carries digest checks that a synthetic fixture could only satisfy
by reimplementing them, which would test the fixture. It was run for real
against ``34540053904`` and reproduced 28/22/6.

Nothing here calls a model, signs in to a cloud account, or spends anything.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
BATCH_RUN = REPOSITORY_ROOT / ".github" / "workflows" / "batch-run.yml"

sys.path.insert(0, str(BATCH_RUNNER_ROOT))

import recover_file_rollup  # noqa: E402

# What a recovery produces, shaped as step 5 writes it.
RECOVERED = {
    "needs_files_total": 28,
    "files_succeeded": 22,
    "files_failed": 6,
    "files_absent": 0,
    "dummy_files_created": 0,
    "dummy_task_ids": [],
    "absent_task_ids": [],
    "policy_caveat": None,
}

PROVENANCE = {
    "recovered_at": "2026-09-11T10:52:51+00:00",
    "source_run_id": "34540053904",
    "step5_skipped_by": "dry_run",
}


def _report(tmp_path: Path, file_generation: dict) -> Path:
    path = tmp_path / "report_data.json"
    path.write_text(
        json.dumps({"meta": {"experiment_id": "expNNN"}, "file_generation": file_generation}),
        encoding="utf-8",
    )
    return path


# ── The recovered figure cannot displace a measured one ───────────────────


def test_a_report_that_counted_its_files_is_not_overwritten(tmp_path):
    """21 of this repository's runs carry a real denominator. None is a candidate."""
    path = _report(tmp_path, {"needs_files_total": 185, "files_succeeded": 180})
    before = path.read_text(encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        recover_file_rollup.annotate(path, RECOVERED, PROVENANCE)

    assert "185" in str(exc.value), "the refusal does not say what it is protecting"
    assert path.read_text(encoding="utf-8") == before, "the report was written anyway"


def test_a_recovered_rollup_does_not_silently_replace_itself(tmp_path):
    """A second run would rewrite the provenance, and the first would be gone."""
    path = _report(tmp_path, {"needs_files_total": None})
    recover_file_rollup.annotate(path, RECOVERED, PROVENANCE)
    first = json.loads(path.read_text(encoding="utf-8"))["file_generation_recovered"]

    with pytest.raises(SystemExit):
        recover_file_rollup.annotate(
            path, {**RECOVERED, "files_succeeded": 999}, {**PROVENANCE, "source_run_id": "x"}
        )

    again = json.loads(path.read_text(encoding="utf-8"))["file_generation_recovered"]
    assert again == first, "the second attempt overwrote the first"


def test_the_null_stays_null_and_the_recovery_says_where_it_came_from(tmp_path):
    """The run goes on recording that it recorded nothing."""
    path = _report(tmp_path, {"needs_files_total": None, "files_succeeded": None})
    recover_file_rollup.annotate(path, RECOVERED, PROVENANCE)
    report = json.loads(path.read_text(encoding="utf-8"))

    assert report["file_generation"]["needs_files_total"] is None
    assert report["file_generation"]["files_succeeded"] is None

    got = report["file_generation_recovered"]
    assert got["needs_files_total"] == 28 and got["files_succeeded"] == 22
    # Without the run ID and the reason, the figure is a number with no account
    # of why it had to be reconstructed — the thing that made exp034's null
    # read as a pipeline defect in the first place.
    assert got["provenance"]["source_run_id"] == "34540053904"
    assert got["provenance"]["step5_skipped_by"] == "dry_run"


# ── The reasons offered are the reasons the workflow has ──────────────────


def test_every_skip_reason_names_a_condition_that_is_really_on_step_5():
    """A reason the workflow no longer has would be a mislabel on a real report."""
    workflow = BATCH_RUN.read_text(encoding="utf-8")
    at = workflow.index("- name: 'Step 5: Validate dataset'")
    start = workflow.index("if:", at)
    gate = workflow[start : workflow.index("\n", start)]

    expressions = {
        "dry_run": "inputs.dry_run != true",
        "smoke_test": "steps.check_smoke_test.outputs.is_smoke_test != 'true'",
        "relay_handover": "steps.check_relay.outputs.needs_relay != 'true'",
        "step2a_failed": "steps.step2a.outcome == 'success'",
    }
    assert set(expressions) == set(recover_file_rollup.SKIP_REASONS), (
        "the tool's reasons and this test's expressions have drifted apart"
    )
    for reason, expression in expressions.items():
        assert expression in gate, f"step 5 no longer skips on {reason}: {gate}"

    # The count as well as the members: a fifth condition would be a fifth way
    # to lose a roll-up, and `--skipped-by` would have no honest value for it.
    terms = gate.removeprefix("if:").split("&&")
    assert len(terms) == len(expressions), (
        f"step 5 gained or lost a condition, so a run can now miss its roll-up "
        f"for a reason this tool cannot name: {gate}"
    )


def test_an_unpacked_artifact_is_recognised_by_what_step_5_reads(tmp_path):
    """Failing here beats failing inside step 5 with a path nobody chose."""
    with pytest.raises(SystemExit) as exc:
        recover_file_rollup.recover(tmp_path)

    message = str(exc.value)
    for needed in ("upload/data", "step0_needs_files_manifest.json", "step1_tasks_prepared.json"):
        assert needed in message, f"the error does not say {needed} is missing"
