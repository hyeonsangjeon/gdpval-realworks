#!/usr/bin/env python3
"""Step 5: Validate — Pre-upload validation of the dataset.

Checks that the local snapshot is ready for HuggingFace upload:
  1. 220 rows in parquet
  2. All required columns present
  3. deliverable_files is list type
  4. deliverable_files paths exist locally
  5. deliverable_text fill rate
  6. needs_files tasks with no files  <- WARNING + creates dummy + updates parquet in-place
  7. No duplicate task_ids
  8. deliverable_files local existence check

Input:
  - data/gdpval-local/data/train-*.parquet
  - data/gdpval-local/deliverable_files/
  - workspace/step0_needs_files_manifest.json

Output:
  - Pass/fail with detailed report
  - workspace/validate_stats.json
      file generation statistics (needs_files_total, succeeded, failed, dummy count)
  - workspace/upload/deliverable_files/<task_id>/failed_to_generate.txt
      dummy placeholder for each task that needed files but produced none
  - workspace/upload/data/train-*.parquet  (updated in-place if dummies created)

Usage:
    python step5_validate.py
    python step5_validate.py --data-dir /path/to/data
"""

import argparse
import json
import sys
from pathlib import Path

from core.config import WORKSPACE_DIR, UPLOAD_DIR, DELIVERABLE_DIR, DEFAULT_LOCAL_PATH


# ── Helpers ────────────────────────────────────────────────────────────────


def _to_list(val) -> list:
    """Normalise ndarray / None / scalar to a plain Python list."""
    if val is None:
        return []
    try:
        import numpy as np
        if isinstance(val, np.ndarray):
            return val.tolist()
    except ImportError:
        pass
    if isinstance(val, list):
        return val
    if hasattr(val, '__iter__') and not isinstance(val, str):
        return list(val)
    return []


DUMMY_FILENAME = "failed_to_generate.txt"


def _create_dummy_file(task_id: str, error_summary: str = "") -> Path:
    """Create a placeholder file for a task that failed to produce deliverables.

    The placeholder signals to the grader that the task ran but the LLM
    failed to generate the required file, rather than the pipeline crashing.

    File location:
        workspace/upload/deliverable_files/<task_id>/failed_to_generate.txt

    Idempotent: if the file already exists, returns its path without overwriting.

    Returns:
        Path to the dummy file (created or pre-existing)
    """
    dummy_dir = DELIVERABLE_DIR / task_id
    dummy_dir.mkdir(parents=True, exist_ok=True)
    dummy_path = dummy_dir / DUMMY_FILENAME

    if dummy_path.exists():
        return dummy_path  # idempotent — skip if already created

    content_lines = [
        "This task failed to produce a deliverable file during inference.",
        "",
        f"task_id: {task_id}",
    ]
    if error_summary:
        content_lines.append(f"reason: {error_summary}")

    dummy_path.write_text("\n".join(content_lines), encoding="utf-8")
    return dummy_path


def _build_dummy_urls(task_id: str, submission_repo_id: str | None) -> dict:
    """Build all three deliverable column values for a dummy file.

    Returns:
        {
            "deliverable_files":         ["deliverable_files/<task_id>/failed_to_generate.txt"],
            "deliverable_file_urls":     ["https://huggingface.co/datasets/<repo>/resolve/main/..."],
            "deliverable_file_hf_uris":  ["hf://datasets/<repo>/deliverable_files/<task_id>/..."],
        }
    """
    rel_path = f"deliverable_files/{task_id}/{DUMMY_FILENAME}"

    if submission_repo_id:
        url = (
            f"https://huggingface.co/datasets/{submission_repo_id}"
            f"/resolve/main/{rel_path}"
        )
        hf_uri = f"hf://datasets/{submission_repo_id}/{rel_path}"
    else:
        url = ""
        hf_uri = ""

    return {
        "deliverable_files": [rel_path],
        "deliverable_file_urls": [url],
        "deliverable_file_hf_uris": [hf_uri],
    }


def _load_submission_repo_id() -> str | None:
    """Read submission repo ID from step2_inference_results.json 'source' field.

    Same logic as step4_fill_parquet.py._detect_submission_repo().
    Returns None if not available.
    """
    inference_json = WORKSPACE_DIR / "step2_inference_results.json"
    if inference_json.exists():
        try:
            data = json.loads(inference_json.read_text())
            src = data.get("source", "").strip()
            if src:
                return src
        except Exception:
            pass
    return None


def validate(data_dir: str = None) -> bool:
    """Validate dataset before HuggingFace upload.

    Validates the upload staging area (workspace/upload/) by default.
    """

    data_path = Path(data_dir) if data_dir else UPLOAD_DIR
    parquet_dir = data_path / "data"
    deliverable_dir = DELIVERABLE_DIR

    print(f"\n{'='*60}")
    print(f"🔍 Step 5: Validate Dataset (upload staging)")
    print(f"{'='*60}")
    print(f"   Upload dir: {data_path}")

    errors = []
    warnings = []

    # ── Load parquet ──
    try:
        import pyarrow.parquet as pq
        import pyarrow as pa
    except ImportError:
        print("❌ pyarrow not installed. pip install pyarrow")
        return False

    parquet_files = sorted(parquet_dir.glob("train-*.parquet"))
    if not parquet_files:
        errors.append(f"No train-*.parquet files found in {parquet_dir}")
        _print_result(errors, warnings)
        return False

    tables = [pq.read_table(f) for f in parquet_files]
    table = pa.concat_tables(tables)
    df = table.to_pandas()

    print(f"   Parquet files: {len(parquet_files)}")
    print(f"   Rows: {len(df)}")
    print(f"   Columns: {list(df.columns)}")

    # ── 1. Row count ──
    if len(df) != 220:
        errors.append(f"Row count: {len(df)} (expected 220)")

    # ── 2. Required columns ──
    required = {
        "task_id", "sector", "occupation", "prompt",
        "reference_files", "reference_file_urls", "reference_file_hf_uris",
        "deliverable_text", "deliverable_files",
    }
    missing = required - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {missing}")

    # ── 3. deliverable_files type ──
    if "deliverable_files" in df.columns:
        for idx in range(min(5, len(df))):
            val = df.iloc[idx]["deliverable_files"]
            if val is not None and not isinstance(val, (list, type(None))):
                errors.append(
                    f"deliverable_files is {type(val).__name__}, expected list"
                )
                break

    # ── 4. task_id uniqueness ──
    if "task_id" in df.columns:
        dupes = df["task_id"].duplicated().sum()
        if dupes > 0:
            errors.append(f"{dupes} duplicate task_id values")

    # ── 5. deliverable_text fill rate ──
    if "deliverable_text" in df.columns:
        filled = df["deliverable_text"].apply(
            lambda x: bool(x and str(x).strip()) if isinstance(x, str) else False
        ).sum()
        empty = len(df) - filled
        if filled == 0:
            warnings.append("All deliverable_text values are empty")
        elif empty > 0:
            pct = round(filled / len(df) * 100, 1)
            warnings.append(
                f"deliverable_text: {filled}/{len(df)} filled ({pct}%), "
                f"{empty} empty"
            )

    # ── 6. deliverable_files fill rate ──
    if "deliverable_files" in df.columns:
        files_filled = df["deliverable_files"].apply(
            lambda x: bool(x and len(x) > 0) if isinstance(x, list) else False
        ).sum()
        if files_filled == 0:
            warnings.append("All deliverable_files are empty")
        else:
            pct = round(files_filled / len(df) * 100, 1)
            warnings.append(
                f"deliverable_files: {files_filled}/{len(df)} have files ({pct}%)"
            )

    # ── 6. needs_files manifest cross-check + dummy creation + parquet update ──
    # Stats dict — written to validate_stats.json at the end
    file_gen_stats = {
        "needs_files_total": 0,
        "files_succeeded": 0,
        "files_failed": 0,
        "dummy_files_created": 0,
        "dummy_task_ids": [],
    }

    manifest_path = WORKSPACE_DIR / "step0_needs_files_manifest.json"
    parquet_updated = False  # track if parquet needs resaving

    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        needs_files_missing = []
        needs_files_total = 0

        for task_id, info in manifest.get("tasks", {}).items():
            if not info.get("needs_files"):
                continue
            needs_files_total += 1
            row = df[df["task_id"] == task_id]
            if len(row) == 0:
                continue
            files = _to_list(row.iloc[0]["deliverable_files"])
            if len(files) == 0:
                needs_files_missing.append(task_id)
            else:
                file_gen_stats["files_succeeded"] += 1

        file_gen_stats["needs_files_total"] = needs_files_total
        file_gen_stats["files_failed"] = len(needs_files_missing)

        if needs_files_missing:
            dummy_created = 0
            dummy_skipped = 0  # already existed from a previous run

            # Read submission_repo_id once — needed for URL/HF URI columns
            submission_repo_id = _load_submission_repo_id()
            if not submission_repo_id:
                print("   ⚠️  submission_repo_id not found — "
                      "deliverable_file_urls / hf_uris will be empty strings")

            for task_id in needs_files_missing:
                _create_dummy_file(task_id)
                dummy_cols = _build_dummy_urls(task_id, submission_repo_id)
                rel_path = dummy_cols["deliverable_files"][0]

                # Check if this task_id row already has the dummy recorded
                current_files = _to_list(df.loc[df["task_id"] == task_id, "deliverable_files"].iloc[0])
                if rel_path not in current_files:
                    idx = df.index[df["task_id"] == task_id][0]
                    # Update all three deliverable columns
                    df.at[idx, "deliverable_files"]        = dummy_cols["deliverable_files"]
                    df.at[idx, "deliverable_file_urls"]    = dummy_cols["deliverable_file_urls"]
                    df.at[idx, "deliverable_file_hf_uris"] = dummy_cols["deliverable_file_hf_uris"]
                    parquet_updated = True
                    dummy_created += 1
                    file_gen_stats["dummy_task_ids"].append(task_id)
                    print(f"   📄 Dummy created: {rel_path}")
                else:
                    dummy_skipped += 1

            file_gen_stats["dummy_files_created"] = dummy_created

            # Rewrite parquet in-place only when new dummies were added
            if parquet_updated:
                import pyarrow as pa
                import pyarrow.parquet as pq
                updated_table = pa.Table.from_pandas(df, preserve_index=False)
                pq.write_table(updated_table, parquet_files[0])
                print(f"   💾 Parquet updated: {parquet_files[0].name} "
                      f"({dummy_created} rows, 3 columns updated)")

            sample = needs_files_missing[:5]
            suffix = (
                f"... (+{len(needs_files_missing) - 5} more)"
                if len(needs_files_missing) > 5 else ""
            )
            msg = (
                f"{len(needs_files_missing)} file-required tasks had no files — "
                f"{dummy_created} dummy placeholders created"
            )
            if dummy_skipped:
                msg += f", {dummy_skipped} already existed (skipped)"
            msg += f": {sample}{suffix}"
            warnings.append(msg)
        else:
            warnings.append(
                f"All {needs_files_total} file-required tasks have deliverable files ✓"
            )
    else:
        warnings.append(
            "step0_needs_files_manifest.json not found — skipping file requirement check"
        )
        file_gen_stats = None

    # ── 8. deliverable_files local existence check ──
    if "deliverable_files" in df.columns:
        missing_files = 0
        checked = 0
        for _, row in df.iterrows():
            files = row.get("deliverable_files")
            if files is None or not hasattr(files, '__iter__') or (hasattr(files, '__len__') and len(files) == 0):
                continue
            for fpath in files:
                checked += 1
                full_path = UPLOAD_DIR / fpath
                if not full_path.exists():
                    missing_files += 1
        if missing_files > 0:
            warnings.append(
                f"{missing_files}/{checked} deliverable files not found on disk"
            )

    # ── Save validate stats for step6_report.py ──────────────────────────
    if file_gen_stats is not None:
        stats_path = WORKSPACE_DIR / "validate_stats.json"
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(file_gen_stats, f, indent=2, ensure_ascii=False)
        print(f"\n   📊 Stats saved → {stats_path.name}")
        print(f"      needs_files_total:   {file_gen_stats['needs_files_total']}")
        print(f"      files_succeeded:     {file_gen_stats['files_succeeded']}")
        print(f"      files_failed:        {file_gen_stats['files_failed']}")
        print(f"      dummy_files_created: {file_gen_stats['dummy_files_created']}")

    _print_result(errors, warnings)
    return len(errors) == 0


def _print_result(errors: list, warnings: list):
    """Print validation result."""
    print()
    if warnings:
        print("⚠️  Warnings:")
        for w in warnings:
            print(f"   - {w}")
        print()

    if errors:
        print("❌ Validation FAILED:")
        for e in errors:
            print(f"   - {e}")
    else:
        print("✅ Validation PASSED")

    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Step 5: Validate dataset")
    parser.add_argument("--data-dir", default=None, help="Dataset directory path")
    args = parser.parse_args()

    ok = validate(data_dir=args.data_dir)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
