#!/usr/bin/env python3
"""Step 4: Fill deliverable_text/files from experiment JSON into parquet.

Auto-detects full/compact mode from YAML data.filter.sample_size:
  sample_size: null  → --full  (전체 220행)
  sample_size: N     → compact (결과 있는 task만)

submission_repo_id는 workspace/step2_inference_results.json의 "source"에서 자동 읽음.

Usage:
  python step4_fill_parquet.py                         # 완전 자동
  python step4_fill_parquet.py --submission-repo HyeonSang/other-repo
  python step4_fill_parquet.py --full
  python step4_fill_parquet.py --compact
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from fill_parquet import fill_parquet

_SCRIPT_DIR = Path(__file__).resolve().parent
_PREPARED_JSON = _SCRIPT_DIR / "workspace" / "step1_tasks_prepared.json"
_INFERENCE_JSON = _SCRIPT_DIR / "workspace" / "step2_inference_results.json"
_DEFAULT_PARQUET = _SCRIPT_DIR.parent / "data" / "gdpval-local" / "data" / "train-00000-of-00001.parquet"
_DEFAULT_OUTPUT = _SCRIPT_DIR / "workspace" / "upload" / "data" / "train-00000-of-00001.parquet"


def _detect_compact(mode_override: str) -> tuple[bool, str]:
    """Return (compact: bool, source_description: str).

    Priority: CLI override > step1_tasks_prepared.json YAML > default (compact)
    """
    if mode_override == "full":
        return False, "강제 override (--full)"
    if mode_override == "compact":
        return True, "강제 override (--compact)"

    if _PREPARED_JSON.exists():
        try:
            prepared = json.loads(_PREPARED_JSON.read_text())
            config_path = prepared.get("config_path")
            if config_path and Path(config_path).exists():
                with open(config_path) as f:
                    cfg = yaml.safe_load(f)
                sample_size = cfg.get("data", {}).get("filter", {}).get("sample_size")
                if sample_size is None:
                    return False, "자동 (sample_size: null → full)"
                else:
                    return True, f"자동 (sample_size: {sample_size} → compact)"
        except Exception:
            pass

    return True, "기본값 (step1_tasks_prepared.json 없음 → compact)"


def _detect_submission_repo(override: str | None) -> str | None:
    """Return submission repo ID: CLI override > inference JSON 'source' field."""
    if override:
        return override
    if _INFERENCE_JSON.exists():
        try:
            data = json.loads(_INFERENCE_JSON.read_text())
            src = data.get("source", "").strip()
            if src:
                return src
        except Exception:
            pass
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fill deliverable columns in parquet from experiment JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--full", action="store_true", help="Include all rows")
    mode_group.add_argument("--compact", action="store_true", help="Include only tasks with results")
    parser.add_argument(
        "--submission-repo",
        default=None,
        help="HF repo ID override (default: auto from step2 JSON 'source')",
    )
    args = parser.parse_args()

    mode_override = "full" if args.full else ("compact" if args.compact else "")
    compact, mode_source = _detect_compact(mode_override)
    submission_repo = _detect_submission_repo(args.submission_repo)

    print("============================================================")
    print("📦 Step 4: Fill Parquet")
    print(f"   JSON:   {_INFERENCE_JSON}")
    print(f"   Input:  {_DEFAULT_PARQUET}  (read-only)")
    print(f"   Output: {_DEFAULT_OUTPUT}")
    print(f"   Mode:   {'Full (all rows)' if not compact else 'Compact (tasks with results only)'}  — {mode_source}")
    if submission_repo:
        src_label = "(override)" if args.submission_repo else "(from JSON 'source')"
        print(f"   Repo:   {submission_repo}  {src_label}")
    else:
        print("   Repo:   (not set — local paths used)")
    print("============================================================")

    _DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    stats = fill_parquet(
        parquet_path=str(_DEFAULT_PARQUET),
        json_path=str(_INFERENCE_JSON),
        output_path=str(_DEFAULT_OUTPUT),
        overwrite_existing=True,
        submission_repo_id=submission_repo,
        compact=compact,
    )

    if stats["filled_text"] == 0 and stats["filled_files"] == 0:
        print("\n⚠️  Nothing was filled")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
