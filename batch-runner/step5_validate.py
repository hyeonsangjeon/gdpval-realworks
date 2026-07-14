#!/usr/bin/env python3
"""Step 5: Validate — Pre-upload validation of the dataset.

Checks that the local snapshot is ready for HuggingFace upload:
    1. Exact prepared task scope (220 rows for full runs, selected IDs for subsets)
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


def _load_expected_task_scope() -> dict:
    """Load prepared scope, defaulting to the legacy 220-task benchmark."""
    prepared_path = WORKSPACE_DIR / "step1_tasks_prepared.json"
    if not prepared_path.exists():
        return {"mode": "full", "expected_count": 220, "task_ids": None}
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    scope = prepared.get("task_scope") or {}
    mode = scope.get("mode", "full")
    if mode == "full":
        return {"mode": "full", "expected_count": 220, "task_ids": None}
    task_ids = scope.get("task_ids")
    if not isinstance(task_ids, list) or not task_ids:
        raise ValueError("prepared subset task_scope must contain non-empty task_ids")
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("prepared subset task_scope contains duplicate task IDs")
    expected_count = scope.get("expected_count", len(task_ids))
    if expected_count != len(task_ids):
        raise ValueError("prepared task_scope expected_count does not match task_ids")
    return {"mode": mode, "expected_count": expected_count, "task_ids": task_ids}


def _task_scope_errors(actual_task_ids: list[str], scope: dict) -> list[str]:
    """Return row-count and identity errors for full or subset submissions."""
    expected_count = int(scope["expected_count"])
    errors = []
    if len(actual_task_ids) != expected_count:
        errors.append(
            f"Row count: {len(actual_task_ids)} "
            f"(expected {expected_count} for {scope['mode']})"
        )
    expected_ids = scope.get("task_ids")
    if expected_ids is not None:
        actual_set = set(actual_task_ids)
        expected_set = set(expected_ids)
        missing = expected_set - actual_set
        unexpected = actual_set - expected_set
        if missing or unexpected:
            errors.append(
                "Task scope mismatch: "
                f"missing={len(missing)}, unexpected={len(unexpected)}"
            )
    return errors


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
    try:
        task_scope = _load_expected_task_scope()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Invalid prepared task scope: {exc}")
        _print_result(errors, warnings)
        return False

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

    # Normalise list columns: ndarray / None / scalar → plain Python list
    _list_cols = [
        "deliverable_files", "deliverable_file_urls", "deliverable_file_hf_uris",
        "reference_files", "reference_file_urls", "reference_file_hf_uris",
    ]
    for _col in _list_cols:
        if _col in df.columns:
            df[_col] = df[_col].apply(_to_list)

    print(f"   Parquet files: {len(parquet_files)}")
    print(f"   Rows: {len(df)}")
    print(f"   Columns: {list(df.columns)}")

    # ── 1. Row count + selected task identity ──
    if "task_id" in df.columns:
        errors.extend(_task_scope_errors(df["task_id"].tolist(), task_scope))
    elif len(df) != task_scope["expected_count"]:
        errors.append(
            f"Row count: {len(df)} (expected {task_scope['expected_count']})"
        )

    # ── 2. Required columns ──
    required = {
        "task_id", "sector", "occupation", "prompt",
        "reference_files", "reference_file_urls", "reference_file_hf_uris",
        "deliverable_text", "deliverable_files",
    }
    missing = required - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: {missing}")

    # ── 3. task_id uniqueness ──
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

        # ── Policy snapshot caveat ───────────────────────────────────
        # success_rate semantics depend on the policy under which the
        # manifest was generated.  Surface a WARNING and a JSON caveat
        # when the snapshot is not the baseline ``deliverable_only`` so
        # downstream readers (step6, dashboards) cannot silently compare
        # numbers across policies.
        active_policy = (
            manifest.get("_summary", {}).get("active_policy")
            or "deliverable_only"
        )
        if active_policy != "deliverable_only":
            print(
                f"[WARN] step5_validate: manifest active_policy="
                f"{active_policy!r}. success_rate definition differs from "
                "baseline 'deliverable_only'.",
                file=sys.stderr,
            )
        file_gen_stats["policy_caveat"] = (
            active_policy if active_policy != "deliverable_only" else None
        )

        needs_files_missing = []
        needs_files_total = 0

        selected_scope = (
            set(task_scope["task_ids"])
            if task_scope.get("task_ids") is not None else None
        )
        for task_id, info in manifest.get("tasks", {}).items():
            if selected_scope is not None and task_id not in selected_scope:
                continue
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
