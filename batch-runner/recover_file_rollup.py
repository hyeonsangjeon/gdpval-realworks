#!/usr/bin/env python3
"""Recover a file-generation roll-up the run itself never recorded.

`step6_report.py` reads `file_generation` from `workspace/validate_stats.json`,
which only step 5 writes, and `batch-run.yml` skips step 5 on four independent
conditions (`inputs.dry_run`, `sample_size <= 3`, a relay handover, and a
failed step 2a). Any of them leaves the roll-up `null` in the published report
— which means "not counted", never "0%".

The count is not lost when that happens. Step 4 runs on a dry run, so the run's
artifact still holds the upload-staging parquet, the needs-files manifest and
the prepared task scope: everything step 5 reads. So the number can be produced
afterwards, offline, from the artifact alone, with no model call and no cost.

This does not re-run the pipeline and does not re-do step 5's job. It calls
step 5's own `validate()` against an unpacked artifact, so the counting rule
here cannot drift from the counting rule in a run that was not skipped.

What it will not do:

  * It will not overwrite `file_generation`. A run that recorded nothing must
    go on saying it recorded nothing; the recovered figure lands beside it as
    `file_generation_recovered`, carrying where it came from. Erasing the
    difference between "measured during the run" and "reconstructed later"
    would make the two look like the same kind of evidence.
  * It will not touch a report whose roll-up is already populated. That would
    be overwriting a measurement with a reconstruction.

Input:
  - an unpacked run artifact containing workspace/upload/data/train-*.parquet,
    workspace/step0_needs_files_manifest.json, workspace/step1_tasks_prepared.json

Output:
  - <workspace>/validate_stats.json, exactly as step 5 writes it
  - optionally, `file_generation_recovered` merged into a report_data.json

Usage:
    python recover_file_rollup.py --workspace /tmp/artifact/workspace \\
        --run-id 34540053904 --skipped-by dry_run

    python recover_file_rollup.py --workspace /tmp/artifact/workspace \\
        --run-id 34540053904 --skipped-by dry_run \\
        --report results/exp034_codex_foundry_trial30/report/report_data.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# The four conditions on the `if:` of `Step 5: Validate dataset`. Naming which
# one fired is required rather than optional: a recovered figure whose absence
# is unexplained invites the reading that the pipeline was broken, and for
# exp034 that reading was wrong — every task that finished produced its file.
SKIP_REASONS = {
    "dry_run": "inputs.dry_run != true — no upload, so no validation",
    "smoke_test": "sample_size <= 3",
    "relay_handover": "this leg handed over to the next instead of finishing",
    "step2a_failed": "inference did not succeed, so there was nothing to count",
}


def _load_step5(workspace: Path):
    """step 5, pointed at an artifact instead of this checkout's workspace.

    `core.config.WORKSPACE_DIR` is a module constant with no environment
    override, and step 5 binds it at import. Rebinding it on the imported
    module — rather than copying step 5's counting into this file — is what
    keeps one counting rule instead of two that agree until they don't.
    """
    sys.path.insert(0, str(Path(__file__).parent))
    import step5_validate

    step5_validate.WORKSPACE_DIR = workspace
    step5_validate.UPLOAD_DIR = workspace / "upload"
    return step5_validate


def recover(workspace: Path) -> dict:
    """Run step 5's counting against `workspace` and return its stats."""
    missing = [
        name
        for name in (
            "upload/data",
            "step0_needs_files_manifest.json",
            "step1_tasks_prepared.json",
        )
        if not (workspace / name).exists()
    ]
    if missing:
        raise SystemExit(
            f"❌ {workspace} is not an unpacked run artifact — missing: "
            + ", ".join(missing)
        )

    step5 = _load_step5(workspace)
    step5.validate()

    stats_path = workspace / "validate_stats.json"
    if not stats_path.exists():
        # step 5 writes nothing when the manifest check could not run. Saying
        # so beats writing a roll-up of nulls that reads like a measurement.
        raise SystemExit(
            "❌ step 5 ran but produced no stats — the manifest check did not "
            "execute, so there is no roll-up to recover"
        )
    return json.loads(stats_path.read_text(encoding="utf-8"))


def annotate(report_path: Path, stats: dict, provenance: dict) -> None:
    """Merge the recovered roll-up into a report, beside the null it explains."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    published = report.get("file_generation") or {}

    if published.get("needs_files_total") is not None:
        raise SystemExit(
            f"❌ {report_path.name} already records "
            f"needs_files_total={published['needs_files_total']} — refusing to "
            "replace a measurement taken during the run with one reconstructed "
            "afterwards"
        )
    if "file_generation_recovered" in report:
        raise SystemExit(
            f"❌ {report_path.name} already carries a recovered roll-up; delete "
            "it by hand if it is genuinely wrong, so the replacement is a "
            "deliberate act and not a re-run"
        )

    report["file_generation_recovered"] = {**stats, "provenance": provenance}
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\n   📎 Merged into {report_path.name} as file_generation_recovered")
    print(f"      file_generation stays null — the run still records what it recorded")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recover a file-generation roll-up from a run artifact"
    )
    parser.add_argument(
        "--workspace", required=True, help="unpacked artifact's workspace/ directory"
    )
    parser.add_argument(
        "--run-id", required=True, help="the GitHub Actions run the artifact came from"
    )
    parser.add_argument(
        "--skipped-by",
        required=True,
        choices=sorted(SKIP_REASONS),
        help="which of step 5's four gates fired",
    )
    parser.add_argument(
        "--report", help="report_data.json to annotate; omit to only print the stats"
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    stats = recover(workspace)

    # The run ID is the provenance. The unpacked path is not: it names a
    # directory on whichever machine ran this, which no later reader can
    # resolve and which does not belong in a published report.
    provenance = {
        "recovered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_run_id": args.run_id,
        "step5_skipped_by": args.skipped_by,
        "step5_skipped_because": SKIP_REASONS[args.skipped_by],
        "tool": Path(__file__).name,
    }

    if args.report:
        annotate(Path(args.report), stats, provenance)
    else:
        print("\n" + json.dumps({**stats, "provenance": provenance}, indent=2))


if __name__ == "__main__":
    main()
