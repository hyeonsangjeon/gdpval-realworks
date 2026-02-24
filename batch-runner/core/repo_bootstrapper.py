"""HuggingFace Repo Bootstrapper -- Step 0

Duplicates openai/gdpval into a user-owned SUBMISSION_REPO_ID on HuggingFace,
but **strips deliverable columns and excludes deliverable_files/** so only the
user's own experiment results are uploaded later.

Also generates ``step0_needs_files_manifest.json`` from the SOURCE dataset --
a task-level map that records which tasks require file output.

Lifecycle:
    1. Check if SUBMISSION_REPO_ID exists on HF -> abort if has content
    2. Download openai/gdpval -> temp dir
    3. Generate step0_needs_files_manifest.json (BEFORE stripping)
    4. Strip deliverable columns + remove deliverable_files/
    5. Upload cleaned content to SUBMISSION_REPO_ID
    6. Download submission repo to local snapshot
    7. Validate

Usage:
    from core.repo_bootstrapper import RepoBootstrapper

    bs = RepoBootstrapper(submission_repo_id="HyeonSang/exp001_smoke_baseline")
    bs.bootstrap()
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional, List

try:
    from huggingface_hub import HfApi, snapshot_download
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from core.config import (
    DATASET_ID,
    DEFAULT_LOCAL_PATH,
    EXPECTED_TASK_COUNT,
    WORKSPACE_DIR,
)

# -- Columns that belong to the submitter (must be cleared) ----------------
_SUBMITTER_COLUMNS_TEXT = ["deliverable_text"]
_SUBMITTER_COLUMNS_LIST = [
    "deliverable_files",
    "deliverable_file_urls",
    "deliverable_file_hf_uris",
]

# -- Critical columns for validation --------------------------------------
_CRITICAL_COLUMNS = {
    "rubric_json", "rubric_pretty",
    "task_id", "prompt", "sector", "occupation",
}


class RepoBootstrapper:
    """Bootstrap a submission HF dataset repo from openai/gdpval.

    Steps:
        0. Abort if repo already has content
        1. Download openai/gdpval to temp dir
        2. Generate step0_needs_files_manifest.json (from ORIGINAL data)
        3. Strip deliverable columns + remove deliverable_files/
        4. Upload to submission repo (clean)
        5. Download submission repo to local_path
        6. Validate
    """

    SOURCE_REPO = DATASET_ID  # "openai/gdpval"

    def __init__(
        self,
        submission_repo_id: str,
        local_path: Optional[str] = None,
        token: Optional[str] = None,
        private: bool = False,
    ):
        if not HF_HUB_AVAILABLE:
            raise ImportError("huggingface_hub is required.  pip install huggingface_hub")

        self.submission_repo_id = submission_repo_id
        self.local_path = Path(local_path) if local_path else DEFAULT_LOCAL_PATH
        self.token = token or os.getenv("HF_TOKEN")
        self.private = private
        self.api = HfApi(token=self.token)
        self.manifest_path = WORKSPACE_DIR / "step0_needs_files_manifest.json"

    # -- Public API --------------------------------------------------------

    def bootstrap(self, force: bool = False) -> Path:
        """Run full bootstrap pipeline.

        Returns:
            Path to validated local snapshot directory.
        """
        print(f"\n{'='*60}")
        print(f"Step 0: Bootstrap -- Preparing Submission Dataset")
        print(f"{'='*60}")
        print(f"   Source repo : {self.SOURCE_REPO}")
        print(f"   Target repo : {self.submission_repo_id}")
        print(f"   Local path  : {self.local_path}")

        if not self.token:
            raise ValueError("HF_TOKEN is required.\n   export HF_TOKEN=hf_xxx")

        # 1. Ensure remote repo (abort if exists with content)
        self._ensure_remote_repo()

        # 2. Download submission repo to local
        self._download_snapshot(force=force)

        # 3. Validate
        self._validate_snapshot()

        print(f"\n   Bootstrap complete!")
        print(f"      Local snapshot : {self.local_path}")
        print(f"      Manifest       : {self.manifest_path}")
        print(f"{'='*60}")
        return self.local_path

    # -- Remote Repo -------------------------------------------------------

    def _repo_exists(self) -> bool:
        try:
            self.api.repo_info(
                repo_id=self.submission_repo_id,
                repo_type="dataset",
                token=self.token,
            )
            return True
        except Exception:
            return False

    def _repo_has_content(self) -> bool:
        try:
            files = self.api.list_repo_files(
                repo_id=self.submission_repo_id,
                repo_type="dataset",
                token=self.token,
            )
            return any(f.startswith("data/") for f in files)
        except Exception:
            return False

    def _ensure_remote_repo(self) -> None:
        """Create submission repo from openai/gdpval with deliverables stripped."""
        if self._repo_exists():
            if self._repo_has_content():
                print(f"\n   Repo already exists with data: {self.submission_repo_id}")
                print(f"     To re-bootstrap, delete it first:")
                print(f"       huggingface-cli repo delete {self.submission_repo_id} --repo-type dataset")
                raise SystemExit(
                    f"Aborted: repo '{self.submission_repo_id}' already exists."
                )
            else:
                print(f"\n   Repo exists but is empty (partial bootstrap). Deleting ...")
                self.api.delete_repo(
                    repo_id=self.submission_repo_id,
                    repo_type="dataset",
                    token=self.token,
                )

        self._duplicate_stripped()

    def _duplicate_stripped(self) -> None:
        """Download source, strip deliverables, generate manifest, upload."""
        print(f"\n   Duplicating {self.SOURCE_REPO} -> {self.submission_repo_id}")
        print(f"      (deliverable columns cleared, deliverable_files/ excluded)")

        old_timeout = os.environ.get("HF_HUB_DOWNLOAD_TIMEOUT")
        os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = str(
            max(int(old_timeout or "0"), 300)
        )

        # 1. Create empty repo
        self.api.create_repo(
            repo_id=self.submission_repo_id,
            repo_type="dataset",
            private=self.private,
            exist_ok=True,
            token=self.token,
        )
        print(f"   Repo created: {self.submission_repo_id}")

        # 2. Download + strip + upload (with retry)
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    print(f"\n   Downloading {self.SOURCE_REPO} "
                          f"(attempt {attempt}/{max_retries}) ...")
                    snapshot_download(
                        repo_id=self.SOURCE_REPO,
                        repo_type="dataset",
                        local_dir=tmpdir,
                        token=self.token,
                    )
                    print(f"   Downloaded to temp dir")

                    # 3. Generate manifest BEFORE stripping
                    self._generate_manifest_from_dir(tmpdir)

                    # 4. Strip deliverable columns from parquet
                    self._strip_deliverables_in_dir(tmpdir)

                    # 5. Remove deliverable_files/ physical directory
                    deliverable_dir = Path(tmpdir) / "deliverable_files"
                    if deliverable_dir.exists():
                        shutil.rmtree(deliverable_dir)
                        print(f"   Removed deliverable_files/ from upload")

                    # 6. Upload to submission repo
                    print(f"\n   Uploading to {self.submission_repo_id} ...")
                    self.api.upload_folder(
                        folder_path=tmpdir,
                        repo_id=self.submission_repo_id,
                        repo_type="dataset",
                        token=self.token,
                        ignore_patterns=[".git*", ".cache*"],
                    )
                break  # success
            except Exception as e:
                if attempt == max_retries:
                    raise RuntimeError(
                        f"Failed to duplicate {self.SOURCE_REPO} after "
                        f"{max_retries} attempts: {e}"
                    ) from e
                wait = 30 * attempt
                print(f"   Attempt {attempt} failed: {e}")
                print(f"      Retrying in {wait}s ...")
                time.sleep(wait)

        # Restore timeout
        if old_timeout is None:
            os.environ.pop("HF_HUB_DOWNLOAD_TIMEOUT", None)
        else:
            os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = old_timeout

        print(f"   Repo duplicated (clean): {self.submission_repo_id}")

    # -- Strip deliverable columns -----------------------------------------

    def _strip_deliverables_in_dir(self, dir_path: str) -> None:
        """Strip deliverable columns from all parquet files in a directory."""
        if not PANDAS_AVAILABLE:
            print(f"   pandas not available -- skipping deliverable strip")
            return

        data_dir = Path(dir_path) / "data"
        if not data_dir.exists():
            return

        parquets = sorted(data_dir.glob("train-*.parquet"))
        for pq_path in parquets:
            df = pd.read_parquet(pq_path)
            changed = False

            for col in _SUBMITTER_COLUMNS_TEXT:
                if col in df.columns:
                    df[col] = ""
                    changed = True

            for col in _SUBMITTER_COLUMNS_LIST:
                if col in df.columns:
                    df[col] = [[] for _ in range(len(df))]
                    changed = True

            if changed:
                df.to_parquet(pq_path, index=False)

        print(f"   Stripped deliverable columns from {len(parquets)} parquet file(s)")

    # -- Generate step0_needs_files_manifest.json ---------------------------

    def _generate_manifest_from_dir(self, dir_path: str) -> None:
        """Generate step0_needs_files_manifest.json from SOURCE parquet (before strip).

        Records which task_ids have non-empty deliverable_files in the
        original openai/gdpval dataset -- meaning the task expects file output.
        """
        if not PANDAS_AVAILABLE:
            print(f"   pandas not available -- skipping manifest generation")
            return

        data_dir = Path(dir_path) / "data"
        if not data_dir.exists():
            return

        parquets = sorted(data_dir.glob("train-*.parquet"))
        if not parquets:
            return

        # Read all parquet shards
        dfs = [pd.read_parquet(p) for p in parquets]
        df = pd.concat(dfs, ignore_index=True)

        manifest = {
            "_description": (
                "Generated by Step 0 bootstrap from openai/gdpval. "
                "Records which tasks require file output."
            ),
            "_source": self.SOURCE_REPO,
            "_total_tasks": len(df),
            "tasks": {},
        }

        needs_count = 0
        text_only_count = 0

        for _, row in df.iterrows():
            task_id = row["task_id"]
            files = row.get("deliverable_files", [])
            if files is None:
                files = []
            if isinstance(files, str):
                files = [files] if files else []
            # numpy array -> list
            if hasattr(files, 'tolist'):
                files = files.tolist()

            has_files = len(files) > 0
            manifest["tasks"][task_id] = {
                "needs_files": has_files,
                "original_file_count": len(files),
                "original_files": list(files),
            }

            if has_files:
                needs_count += 1
            else:
                text_only_count += 1

        manifest["_summary"] = {
            "needs_files": needs_count,
            "text_only": text_only_count,
        }

        # Save to workspace dir (create dirs if needed)
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        print(f"   Generated step0_needs_files_manifest.json "
              f"(needs_files={needs_count}, text_only={text_only_count})")

    # -- Download snapshot -------------------------------------------------

    def _is_valid_local(self) -> bool:
        if not self.local_path.exists():
            return False
        data_dir = self.local_path / "data"
        if not data_dir.exists():
            return False
        return len(list(data_dir.glob("train-*.parquet"))) > 0

    def _download_snapshot(self, force: bool = False) -> None:
        """Download submission repo to local_path."""
        if self._is_valid_local() and not force:
            print(f"\n   Local snapshot already exists: {self.local_path}")
            return

        if force and self.local_path.exists():
            print(f"\n   Removing old local snapshot ...")
            # Preserve manifest if it exists
            manifest_backup = None
            if self.manifest_path.exists():
                manifest_backup = self.manifest_path.read_text()
            shutil.rmtree(self.local_path)
            if manifest_backup:
                self.local_path.mkdir(parents=True, exist_ok=True)
                self.manifest_path.write_text(manifest_backup)

        print(f"\n   Downloading {self.submission_repo_id} -> {self.local_path} ...")
        self.local_path.parent.mkdir(parents=True, exist_ok=True)

        # Increase per-file read timeout (default is too low for large reference files)
        os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")

        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                print(f"   Downloading snapshot (attempt {attempt}/{max_retries}) ...")
                snapshot_download(
                    repo_id=self.submission_repo_id,
                    repo_type="dataset",
                    local_dir=str(self.local_path),
                    token=self.token,
                )
                break  # success
            except Exception as e:
                if attempt == max_retries:
                    raise RuntimeError(
                        f"Failed to download {self.submission_repo_id} after "
                        f"{max_retries} attempts: {e}"
                    ) from e
                wait = 30 * attempt
                print(f"   Attempt {attempt} failed: {e}")
                print(f"      Retrying in {wait}s ... (already-downloaded files are skipped)")
                time.sleep(wait)

        # Create empty deliverable_files/ for later experiment outputs
        (self.local_path / "deliverable_files").mkdir(parents=True, exist_ok=True)

        print(f"   Local snapshot ready: {self.local_path}")

    # -- Validate ----------------------------------------------------------

    def _validate_snapshot(self) -> None:
        """Validate local snapshot integrity."""
        print(f"\n   Validating local snapshot ...")
        errors: List[str] = []

        # 1. Parquet files
        data_dir = self.local_path / "data"
        if not data_dir.exists():
            errors.append("data/ directory not found")
        else:
            parquets = sorted(data_dir.glob("train-*.parquet"))
            if not parquets:
                errors.append("No train-*.parquet files found in data/")
            elif PANDAS_AVAILABLE:
                df = pd.read_parquet(parquets[0])
                if len(df) != EXPECTED_TASK_COUNT:
                    errors.append(
                        f"Row count: expected {EXPECTED_TASK_COUNT}, got {len(df)}"
                    )
                missing = _CRITICAL_COLUMNS - set(df.columns)
                if missing:
                    errors.append(f"Missing critical columns: {missing}")

                # Verify deliverable columns are empty (not from source)
                if "deliverable_text" in df.columns:
                    non_empty = df["deliverable_text"].apply(
                        lambda x: bool(x) if isinstance(x, str) else False
                    ).sum()
                    if non_empty > 0:
                        errors.append(
                            f"deliverable_text should be empty but {non_empty} rows have content"
                        )

        # 2. reference_files/
        ref_dir = self.local_path / "reference_files"
        if not ref_dir.exists():
            errors.append("reference_files/ directory not found")

        # 3. Manifest
        if not self.manifest_path.exists():
            errors.append("step0_needs_files_manifest.json not found")

        if errors:
            err_str = "\n      ".join(errors)
            raise ValueError(f"Snapshot validation failed:\n      {err_str}")

        print(f"   Snapshot valid")
        print(f"   Deliverable columns: cleared")
        print(f"   Manifest: {self.manifest_path}")


# -- Standalone pre-upload validation --------------------------------------


def validate_pre_upload(
    local_path: Optional[str] = None,
    submission_repo_id: Optional[str] = None,
    expected_rows: Optional[int] = None,
) -> List[str]:
    """Pre-upload validation -- call before step6 upload.

    Uses step0_needs_files_manifest.json to check which tasks need files.
    Only tasks with needs_files=true are required to have deliverable_files.

    Args:
        expected_rows: Expected row count. If None, uses EXPECTED_TASK_COUNT (220).
                       Pass sample_size when running in compact/test mode so that
                       row count and deliverable_files checks cover only present tasks.

    Returns:
        List of error strings (empty = all good)
    """
    if not PANDAS_AVAILABLE:
        return ["pandas is required for validation"]

    root = Path(local_path) if local_path else DEFAULT_LOCAL_PATH
    errors: List[str] = []
    expected = expected_rows if expected_rows is not None else EXPECTED_TASK_COUNT
    compact_mode = expected != EXPECTED_TASK_COUNT

    # Find parquet
    data_dir = root / "data"
    parquets = sorted(data_dir.glob("train-*.parquet")) if data_dir.exists() else []
    if not parquets:
        errors.append("No train-*.parquet found")
        return errors

    df = pd.read_parquet(parquets[0])

    # 1. Row count
    if len(df) != expected:
        errors.append(f"Row count: expected {expected}, got {len(df)}")

    # 2. Column set
    for col in ("rubric_json", "rubric_pretty", "task_id", "sector",
                "occupation", "prompt", "deliverable_text", "deliverable_files"):
        if col not in df.columns:
            errors.append(f"Missing column: {col}")

    # 3. Manifest-based deliverable_files check
    #    compact_mode: only validate tasks present in parquet (others intentionally excluded)
    manifest_path = WORKSPACE_DIR / "step0_needs_files_manifest.json"
    if manifest_path.exists() and "deliverable_files" in df.columns:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        present_ids = set(df["task_id"]) if "task_id" in df.columns else set()

        for task_id, info in manifest.get("tasks", {}).items():
            if not info.get("needs_files"):
                continue  # text-only -- no file requirement

            if compact_mode and task_id not in present_ids:
                continue  # intentionally excluded in compact/test mode

            rows = df[df["task_id"] == task_id]
            if len(rows) == 0:
                errors.append(f"task {task_id}: missing from parquet")
                continue

            files = rows.iloc[0].get("deliverable_files")
            if files is None or (hasattr(files, '__len__') and len(files) == 0):
                errors.append(
                    f"task {task_id}: needs_files=true but deliverable_files is empty"
                )
    elif not manifest_path.exists():
        errors.append("needs_files_manifest.json not found -- cannot validate files")

    # 4. task_id unique count
    if "task_id" in df.columns:
        ids = set(df["task_id"])
        if len(ids) != expected:
            errors.append(
                f"Unique task_id count: expected {expected}, got {len(ids)}"
            )

    return errors
