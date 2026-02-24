#!/usr/bin/env python3
"""GDPVal Dataset Preparation Script

Downloads and manages the GDPVal Gold Subset dataset locally.

Usage:
    # Download dataset
    python prepare_dataset.py

    # Force re-download
    python prepare_dataset.py --force

    # Check snapshot info
    python prepare_dataset.py --info

    # Custom local path
    python prepare_dataset.py --path data/custom-path
"""

import sys
import shutil
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

import pyarrow.parquet as pq
import pyarrow as pa
from datasets import load_dataset
from huggingface_hub import snapshot_download
from core.config import (
    DATASET_ID,
    DEFAULT_LOCAL_PATH,
    SNAPSHOT_MARKERS,
)


@dataclass
class GDPValTask:
    """Represents a single task from GDPVal Gold Subset"""
    task_id: str
    occupation: str
    sector: str
    prompt: str
    reference_files: List[str]
    reference_file_urls: List[str]
    reference_file_hf_uris: List[str]
    deliverable_text: str
    deliverable_files: List[str]


class GDPValDataset:
    """GDPVal Gold Subset 데이터셋 관리자"""

    DATASET_ID = DATASET_ID
    DEFAULT_LOCAL_PATH = DEFAULT_LOCAL_PATH

    def __init__(self, local_path: Optional[str] = None, auto_download: bool = True):
        """
        Args:
            local_path: 로컬 스냅샷 경로 (기본값: <project_root>/data/gdpval-local)
            auto_download: True면 로컬 스냅샷 없을 때 자동 다운로드
        """
        self.local_path = Path(local_path) if local_path else self.DEFAULT_LOCAL_PATH
        self.auto_download = auto_download
        self._dataset = None

    def _is_valid_snapshot(self) -> bool:
        """Check if local path contains a valid HF dataset snapshot."""
        if not self.local_path.exists():
            return False
        return any(
            (self.local_path / marker).exists() for marker in SNAPSHOT_MARKERS
        )

    def download(self, force: bool = False) -> Path:
        """
        HuggingFace에서 데이터셋을 다운로드하여 로컬에 저장

        Args:
            force: True면 기존 스냅샷을 덮어씀

        Returns:
            Path: 저장된 로컬 경로
        """
        if self._is_valid_snapshot() and not force:
            print(f"✓ Snapshot already exists at: {self.local_path}")
            return self.local_path

        print(f"📥 Downloading GDPVal dataset from HuggingFace...")
        print(f"   Dataset: {self.DATASET_ID}")

        # Create parent directory
        self.local_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove old snapshot if force=True
        if force and self.local_path.exists():
            print(f"   Removing old snapshot...")
            shutil.rmtree(self.local_path)

        # Step 1: Download full repository snapshot (parquet + reference_files/)
        print(f"   Step 1/2: Downloading full repository (including reference_files)...")
        snapshot_download(
            repo_id=self.DATASET_ID,
            repo_type="dataset",
            local_dir=str(self.local_path),
        )

        # Step 2: Add deliverable columns and save Arrow + Parquet
        print(f"   Step 2/2: Adding deliverable columns (Arrow + Parquet)...")
        dataset = load_dataset(self.DATASET_ID)
        dataset = self._add_deliverable_columns(dataset)
        dataset.save_to_disk(str(self.local_path))

        # Overwrite parquet with 9-column version (for HF upload consistency)
        self._update_parquet(dataset)

        # Create deliverable_files/ directory for future outputs
        deliverable_dir = self.local_path / "deliverable_files"
        deliverable_dir.mkdir(parents=True, exist_ok=True)

        print(f"✓ Snapshot saved to: {self.local_path}")
        try:
            train = dataset['train']
            print(f"   Train split: {len(train)} tasks")
            if hasattr(train, 'column_names'):
                print(f"   Columns: {train.column_names}")
        except Exception:
            pass

        return self.local_path

    def load(self) -> List[GDPValTask]:
        """
        전체 220개 태스크 로드 (로컬 parquet 우선, 없으면 자동 다운로드)

        Returns:
            List[GDPValTask]: 220개 태스크 리스트
        """
        # Check if local snapshot exists
        if not self._is_valid_snapshot():
            if self.auto_download:
                print(f"⚠ Local snapshot not found at: {self.local_path}")
                self.download()
            else:
                raise FileNotFoundError(
                    f"Local snapshot not found at: {self.local_path}\n"
                    f"Run step0_bootstrap.sh first."
                )

        # Load from parquet files
        print(f"📂 Loading from local snapshot: {self.local_path}")
        data_dir = self.local_path / "data"
        parquet_files = sorted(data_dir.glob("train-*.parquet"))

        if not parquet_files:
            raise FileNotFoundError(
                f"No train-*.parquet files found in {data_dir}\n"
                f"Run step0_bootstrap.sh first."
            )

        tables = [pq.read_table(str(f)) for f in parquet_files]
        table = pa.concat_tables(tables)
        df = table.to_pandas()
        print(f"   Read {len(df)} rows from {len(parquet_files)} parquet file(s)")

        tasks = [
            self._parse_task(row)
            for _, row in df.iterrows()
        ]

        print(f"✓ Loaded {len(tasks)} tasks")

        return tasks

    def _parse_task(self, row) -> GDPValTask:
        """Parse a dataset/pandas row into a GDPValTask."""
        def _to_list(val):
            """Convert value to list, handling None/NaN/str/ndarray."""
            if val is None:
                return []
            if isinstance(val, (list, tuple)):
                return list(val)
            # numpy ndarray (parquet list columns become ndarray in pandas)
            try:
                import numpy as np
                if isinstance(val, np.ndarray):
                    return val.tolist()
            except ImportError:
                pass
            if isinstance(val, str):
                return [val] if val else []
            # numpy NaN or similar
            try:
                import math
                if math.isnan(val):
                    return []
            except (TypeError, ValueError):
                pass
            return []

        def _to_str(val):
            """Convert value to string, handling None/NaN."""
            if val is None:
                return ''
            if isinstance(val, str):
                return val
            try:
                import math
                if math.isnan(val):
                    return ''
            except (TypeError, ValueError):
                pass
            return str(val)

        return GDPValTask(
            task_id=str(row['task_id']),
            occupation=str(row['occupation']),
            sector=str(row['sector']),
            prompt=str(row['prompt']),
            reference_files=_to_list(row.get('reference_files', [])),
            reference_file_urls=_to_list(row.get('reference_file_urls', [])),
            reference_file_hf_uris=_to_list(row.get('reference_file_hf_uris', [])),
            deliverable_text=_to_str(row.get('deliverable_text', '')),
            deliverable_files=_to_list(row.get('deliverable_files', [])),
        )

    @staticmethod
    def _add_deliverable_columns(dataset):
        """Add deliverable_text and deliverable_files columns if missing.

        Args:
            dataset: A HuggingFace DatasetDict

        Returns:
            DatasetDict with deliverable columns added
        """
        from datasets import DatasetDict

        train = dataset["train"]
        if "deliverable_text" not in train.column_names:
            train = train.add_column("deliverable_text", [""] * len(train))
        if "deliverable_files" not in train.column_names:
            train = train.add_column("deliverable_files", [[] for _ in range(len(train))])
        return DatasetDict({"train": train})

    def _update_parquet(self, dataset):
        """Overwrite parquet file(s) with deliverable columns included.

        This ensures the parquet files under data/ match the Arrow format,
        so the entire gdpval-local/ directory can be uploaded to HF as-is.
        """
        data_dir = self.local_path / "data"
        if not data_dir.exists():
            return

        parquet_files = sorted(data_dir.glob("train-*.parquet"))
        if not parquet_files:
            return

        # Convert HF dataset to pandas and overwrite each parquet shard
        df = dataset["train"].to_pandas()
        for pq_path in parquet_files:
            df.to_parquet(str(pq_path), index=False)
            print(f"   Updated parquet: {pq_path.name} ({len(df.columns)} columns)")

    def get_info(self) -> dict:
        """
        로컬 스냅샷 정보 조회

        Returns:
            dict: 스냅샷 존재 여부, 경로, 크기 등
        """
        exists = self._is_valid_snapshot()
        size_mb = 0
        task_count = 0

        if exists:
            # Calculate directory size
            size_bytes = sum(
                f.stat().st_size
                for f in self.local_path.rglob('*')
                if f.is_file()
            )
            size_mb = size_bytes / (1024 * 1024)

            # Try to count tasks from parquet
            try:
                data_dir = self.local_path / "data"
                for pf in sorted(data_dir.glob("train-*.parquet")):
                    task_count += pq.read_table(str(pf)).num_rows
            except Exception:
                pass

        return {
            'exists': exists,
            'valid': exists,
            'path': str(self.local_path),
            'size_mb': round(size_mb, 2),
            'task_count': task_count,
            'dataset_id': self.DATASET_ID,
        }

    def print_info(self):
        """Print snapshot information in a readable format"""
        info = self.get_info()

        print("\n" + "="*60)
        print("GDPVal Dataset Snapshot Info")
        print("="*60)
        print(f"Dataset ID:    {info['dataset_id']}")
        print(f"Local Path:    {info['path']}")
        print(f"Exists:        {'✓ Yes' if info['exists'] else '✗ No'}")
        print(f"Valid:         {'✓ Yes' if info['valid'] else '✗ No'}")

        if info['exists']:
            print(f"Size:          {info['size_mb']:.2f} MB")
            print(f"Tasks:         {info['task_count']}")
        print("="*60 + "\n")

    # ─── Backward Compatibility Aliases ───────────────────────────────────

    def download_snapshot(self, force: bool = False) -> Path:
        """Alias for download() - backward compatibility"""
        return self.download(force=force)

    def get_snapshot_info(self) -> dict:
        """Alias for get_info() - backward compatibility"""
        return self.get_info()


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Prepare GDPVal dataset for local use",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download dataset
  python prepare_dataset.py

  # Force re-download
  python prepare_dataset.py --force

  # Check snapshot info
  python prepare_dataset.py --info

  # Custom local path
  python prepare_dataset.py --path data/custom-path
        """
    )
    parser.add_argument(
        '--path',
        type=str,
        default=None,
        help=f'Local snapshot path (default: {GDPValDataset.DEFAULT_LOCAL_PATH})'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-download even if snapshot exists'
    )
    parser.add_argument(
        '--info',
        action='store_true',
        help='Show snapshot info and exit'
    )

    args = parser.parse_args()

    # Create dataset manager
    dataset = GDPValDataset(local_path=args.path)

    # Show info and exit
    if args.info:
        dataset.print_info()
        return 0

    # Download dataset
    try:
        print("\n🚀 GDPVal Dataset Preparation\n")
        dataset.download(force=args.force)
        print("\n✓ Dataset preparation completed!")

        # Show final info
        dataset.print_info()

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
