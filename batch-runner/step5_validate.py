#!/usr/bin/env python3
"""Step 5: Validate — Pre-upload validation of the dataset.

Checks that the local snapshot is ready for HuggingFace upload:
  1. 220 rows in parquet
  2. All required columns present
  3. deliverable_files is list type
  4. deliverable_files paths exist locally
  5. needs_files tasks have files
  6. No duplicate task_ids
  7. deliverable_text fill rate

Input:
  - data/gdpval-local/data/train-*.parquet
  - data/gdpval-local/deliverable_files/
  - workspace/step0_needs_files_manifest.json

Output:
  - Pass/fail with detailed report

Usage:
    python step5_validate.py
    python step5_validate.py --data-dir /path/to/data
"""

import argparse
import json
import sys
from pathlib import Path

from core.config import WORKSPACE_DIR, UPLOAD_DIR, DELIVERABLE_DIR, DEFAULT_LOCAL_PATH


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

    # ── 7. needs_files manifest cross-check ──
    manifest_path = WORKSPACE_DIR / "step0_needs_files_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        needs_files_missing = []
        for task_id, info in manifest.get("tasks", {}).items():
            if not info.get("needs_files"):
                continue
            row = df[df["task_id"] == task_id]
            if len(row) == 0:
                continue
            files = row.iloc[0].get("deliverable_files")
            if not files or (isinstance(files, list) and len(files) == 0):
                needs_files_missing.append(task_id)

        if needs_files_missing:
            sample = needs_files_missing[:5]
            suffix = f"... (+{len(needs_files_missing)-5} more)" if len(needs_files_missing) > 5 else ""
            warnings.append(
                f"{len(needs_files_missing)} tasks need files but have empty "
                f"deliverable_files: {sample}{suffix}"
            )
    else:
        warnings.append("step0_needs_files_manifest.json not found — skipping file requirement check")

    # ── 8. deliverable_files local existence check ──
    if "deliverable_files" in df.columns:
        missing_files = 0
        checked = 0
        for _, row in df.iterrows():
            files = row.get("deliverable_files")
            if not files or not isinstance(files, list):
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
