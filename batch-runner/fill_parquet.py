#!/usr/bin/env python3
"""Fill deliverable_text and deliverable_files into parquet from experiment JSON.

Reads experiment result JSON (exp002.json etc.) and merges deliverable_text /
deliverable_files into the source parquet file, keyed by task_id.

Schema-preservation guarantee:
    The base parquet (from the duplicate of openai/gdpval) keeps ALL columns
    including rubric_json, rubric_pretty, and all reference metadata.
    Only three groups are overwritten:
        • deliverable_text
        • deliverable_files
        • deliverable_file_urls / deliverable_file_hf_uris (re-generated)

Usage (standalone):
    python fill_parquet.py --parquet data/gdpval-local/data/train-00000-of-00001.parquet \\
                           --json results/exp002.json \\
                           --output data/gdpval-local/data/train-00000-of-00001.parquet

    # With submission repo (regenerates deliverable_file_urls, hf_uris)
    python fill_parquet.py --parquet ... --json ... \\
                           --submission-repo HyeonSang/exp002_single_baseline

    # Dry-run (preview only, no write)
    python fill_parquet.py --parquet ... --json ... --dry-run

Can also be called from main.py as:
    from fill_parquet import fill_parquet
    stats = fill_parquet(parquet_path, json_path, output_path)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List

import pandas as pd

from core.inference_manifest import canonical_deliverable_uris


def _build_deliverable_uris(
    file_list: List[str],
    submission_repo_id: str,
) -> tuple:
    """Generate deliverable_file_urls and deliverable_file_hf_uris.

    Args:
        file_list: e.g. ["deliverable_files/task_1/report with spaces.xlsx"]
        submission_repo_id: e.g. "HyeonSang/exp002_single_baseline"

    Returns:
        (urls_list, hf_uris_list)
        Spaces and special chars in filenames are URL-encoded (e.g. ' ' → '%20').
    """
    return canonical_deliverable_uris(file_list, submission_repo_id)


def fill_parquet(
    parquet_path: str,
    json_path: str,
    output_path: Optional[str] = None,
    overwrite_existing: bool = False,
    dry_run: bool = False,
    submission_repo_id: Optional[str] = None,
    compact: bool = True,
    selected_task_ids: Optional[List[str]] = None,
    source_manifest_path: Optional[str] = None,
    source_root: Optional[str] = None,
) -> dict:
    """Merge experiment JSON results into parquet deliverable columns.

    Only three groups of columns are overwritten — everything else (rubric_json,
    rubric_pretty, reference metadata, etc.) is preserved from the base parquet.

    Args:
        parquet_path: Path to input parquet file
        json_path: Path to experiment result JSON (e.g., exp002.json)
        output_path: Path to output parquet. If None, overwrites input file.
        overwrite_existing: If True, overwrite already-filled deliverable_text.
                            If False (default), only fill empty rows.
        dry_run: If True, print stats but don't write.
        submission_repo_id: If set, regenerate deliverable_file_urls and
                            deliverable_file_hf_uris per this repo.
        selected_task_ids: Exact subset retained in compact mode. Failed
                   selected tasks remain so validation can represent
                   their outcome explicitly.

    Returns:
        Dict with merge statistics:
            filled_text: Number of deliverable_text fields filled
            filled_files: Number of deliverable_files fields filled
            skipped: Number of rows skipped (already filled)
            missing: Number of JSON tasks not found in parquet
            errors_with_text: Number of error tasks that had deliverable_text
    """
    # Load parquet (read-only source: gdpval-local)
    df = pd.read_parquet(parquet_path)
    print(f"📄 Parquet: {parquet_path} ({len(df)} rows)")

    if source_manifest_path:
        from core.repo_bootstrapper import validate_source_projection_rows

        source_errors = validate_source_projection_rows(
            df,
            Path(source_manifest_path),
            snapshot_root=Path(source_root) if source_root else None,
            require_complete=True,
        )
        if source_errors:
            raise ValueError(
                "Source parquet integrity validation failed:\n  - "
                + "\n  - ".join(source_errors)
            )

    # Snapshot reference columns from source parquet (never overwrite)
    _REF_COLS = ["reference_files", "reference_file_urls", "reference_file_hf_uris"]
    ref_snapshot = {
        col: df.set_index("task_id")[col].to_dict()
        for col in _REF_COLS
        if col in df.columns
    }

    # Ensure deliverable_text column exists (not in source gdpval parquet)
    if "deliverable_text" not in df.columns:
        df["deliverable_text"] = ""

    # Load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])
    experiment_id = data.get("experiment_id", "unknown")
    print(f"📊 JSON: {json_path} ({len(results)} results, experiment={experiment_id})")

    result_ids = [r["task_id"] for r in results]
    if len(result_ids) != len(set(result_ids)):
        raise ValueError("result task IDs must be unique")

    # Build lookup: task_id -> result dict
    result_map = {r["task_id"]: r for r in results}

    if selected_task_ids is not None:
        if len(selected_task_ids) != len(set(selected_task_ids)):
            raise ValueError("selected_task_ids must not contain duplicates")
        if len(result_ids) != len(selected_task_ids):
            raise ValueError(
                "result count does not match selected_task_ids: "
                f"results={len(result_ids)}, selected={len(selected_task_ids)}"
            )
        selected_set = set(selected_task_ids)
        missing_results = selected_set - set(result_map)
        unexpected_results = set(result_map) - selected_set
        if missing_results or unexpected_results:
            raise ValueError(
                "result task IDs do not match selected_task_ids: "
                f"missing={len(missing_results)}, unexpected={len(unexpected_results)}"
            )

    # Stats
    stats = {
        "filled_text": 0,
        "filled_files": 0,
        "skipped": 0,
        "missing": 0,
        "errors_with_text": 0,
        "total_json": len(results),
        "total_parquet": len(df),
    }

    # Count JSON tasks not in parquet
    parquet_ids = set(df["task_id"])
    missing_ids = set(result_map.keys()) - parquet_ids
    stats["missing"] = len(missing_ids)

    for column in (
        "deliverable_files",
        "deliverable_file_urls",
        "deliverable_file_hf_uris",
    ):
        if column not in df.columns:
            df[column] = [[] for _ in range(len(df))]

    if overwrite_existing:
        # Production rebuilds selected success/error rows from this run only.
        # The legacy False mode retains its documented fill-empty-only behavior.
        selected_indices = df.index[df["task_id"].isin(result_map)]
        for index in selected_indices:
            df.at[index, "deliverable_text"] = ""
            df.at[index, "deliverable_files"] = []
            df.at[index, "deliverable_file_urls"] = []
            df.at[index, "deliverable_file_hf_uris"] = []

    # Merge
    for idx, row in df.iterrows():
        task_id = row["task_id"]
        if task_id not in result_map:
            continue

        r = result_map[task_id]

        # --- deliverable_text ---
        current_text = row.get("deliverable_text", "")
        new_text = r.get("deliverable_text") or ""

        if new_text:
            has_existing = bool(current_text and str(current_text).strip())
            if has_existing and not overwrite_existing:
                stats["skipped"] += 1
            else:
                df.at[idx, "deliverable_text"] = new_text
                stats["filled_text"] += 1

            # Track error tasks that still have text
            if r.get("status") == "error":
                stats["errors_with_text"] += 1

        # --- deliverable_files ---
        new_files = r.get("deliverable_files") or []
        if new_files:
            # Ensure list type (parquet stores as numpy array)
            df.at[idx, "deliverable_files"] = new_files
            stats["filled_files"] += 1

            # --- Regenerate URI columns ---
            if submission_repo_id:
                urls, uris = _build_deliverable_uris(new_files, submission_repo_id)
            else:
                # submission_repo 없으면 로컬 경로 그대로 (빈 배열 방지)
                urls = new_files
                uris = new_files

            if "deliverable_file_urls" in df.columns:
                df.at[idx, "deliverable_file_urls"] = urls
            if "deliverable_file_hf_uris" in df.columns:
                df.at[idx, "deliverable_file_hf_uris"] = uris

    # Print summary
    print(f"\n{'='*50}")
    print(f"📈 Merge Summary (experiment: {experiment_id})")
    print(f"{'='*50}")
    print(f"  deliverable_text filled : {stats['filled_text']}/{stats['total_json']}")
    print(f"  deliverable_files filled: {stats['filled_files']}/{stats['total_json']}")
    print(f"  skipped (already filled): {stats['skipped']}")
    print(f"  missing in parquet      : {stats['missing']}")
    print(f"  errors with text        : {stats['errors_with_text']}")
    print(f"{'='*50}")

    # Compact mode: exact prepared subset when provided, legacy successes otherwise.
    if compact:
        if selected_task_ids is not None:
            parquet_index = df.set_index("task_id", drop=False)
            unknown_ids = [
                task_id for task_id in selected_task_ids
                if task_id not in parquet_index.index
            ]
            if unknown_ids:
                raise ValueError(
                    f"selected_task_ids missing from parquet: {', '.join(unknown_ids[:5])}"
                )
            df = parquet_index.loc[selected_task_ids].reset_index(drop=True).copy()
            print(f"📦 Compact mode: retained exact selected scope ({len(df)} rows)")
        else:
            filled_task_ids = [r["task_id"] for r in results
                              if r.get("status") == "success"]
            df = df[df["task_id"].isin(filled_task_ids)].copy()
            print(f"📦 Compact mode: extracted {len(df)} rows (successful tasks only)")
        stats["output_rows"] = len(df)
    else:
        print(f"📦 Full mode: keeping all {len(df)} rows")
        stats["output_rows"] = len(df)

    # Restore reference columns from source snapshot (read-only, must not be changed)
    for col, val_by_id in ref_snapshot.items():
        df[col] = df["task_id"].map(val_by_id)

    if source_manifest_path:
        from core.repo_bootstrapper import CANONICAL_TARGET_COLUMNS

        if set(df.columns) != set(CANONICAL_TARGET_COLUMNS):
            missing = sorted(set(CANONICAL_TARGET_COLUMNS) - set(df.columns))
            extra = sorted(set(df.columns) - set(CANONICAL_TARGET_COLUMNS))
            raise ValueError(
                f"output columns differ from canonical target schema: "
                f"missing={missing}, extra={extra}"
            )
        df = df[list(CANONICAL_TARGET_COLUMNS)]
    else:
        cols = [column for column in df.columns if column != "deliverable_text"]
        insert_pos = (
            cols.index("reference_file_hf_uris") + 1
            if "reference_file_hf_uris" in cols
            else len(cols)
        )
        cols.insert(insert_pos, "deliverable_text")
        df = df[cols]
    print(f"📋 Column order: {list(df.columns)}")

    if dry_run:
        print("\n⚠️  Dry-run mode: no file written")
    else:
        out = output_path or parquet_path
        Path(out).parent.mkdir(parents=True, exist_ok=True)

        df.to_parquet(out, index=False)
        print(f"\n✅ Parquet written to: {out} ({len(df)} rows)")

    return stats


_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_JSON = _SCRIPT_DIR / "workspace" / "step2_inference_results.json"
_DEFAULT_PARQUET = _SCRIPT_DIR.parent / "data" / "gdpval-local" / "data" / "train-00000-of-00001.parquet"
_DEFAULT_OUTPUT = _SCRIPT_DIR / "workspace" / "upload" / "data" / "train-00000-of-00001.parquet"


def main():
    parser = argparse.ArgumentParser(
        description="Fill deliverable_text/files in parquet from experiment JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--parquet",
        default=str(_DEFAULT_PARQUET),
        help=f"Path to input parquet file (default: {_DEFAULT_PARQUET})",
    )
    parser.add_argument(
        "--json",
        default=str(_DEFAULT_JSON),
        help=f"Path to experiment result JSON (default: {_DEFAULT_JSON})",
    )
    parser.add_argument(
        "--output",
        default=str(_DEFAULT_OUTPUT),
        help=f"Path to output parquet (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite already-filled deliverable_text (default: skip)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only, don't write output",
    )
    parser.add_argument(
        "--submission-repo",
        default=None,
        help="HF repo ID override. If omitted, reads 'source' from the JSON file.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Include all 220 rows (default: compact, only tasks with results)",
    )
    args = parser.parse_args()

    # Auto-detect submission_repo from JSON's "source" field if not provided
    submission_repo = args.submission_repo
    if not submission_repo:
        try:
            with open(args.json, "r", encoding="utf-8") as f:
                _data = json.load(f)
            submission_repo = _data.get("source") or None
            if submission_repo:
                print(f"ℹ️  submission_repo: {submission_repo}  (from JSON 'source')")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    stats = fill_parquet(
        parquet_path=args.parquet,
        json_path=args.json,
        output_path=args.output,
        overwrite_existing=args.overwrite,
        dry_run=args.dry_run,
        submission_repo_id=submission_repo,
        compact=not args.full,
    )

    # Exit code: 0 if filled anything, 1 if nothing to fill
    if stats["filled_text"] == 0 and stats["filled_files"] == 0:
        print("\n⚠️  Nothing was filled")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
