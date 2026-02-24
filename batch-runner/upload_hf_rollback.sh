#!/usr/bin/env bash
# Rollback Upload: HuggingFace에 gdpval-local 원본 데이터를 직접 업로드 (실험 결과 없음)
#
# step4 없이 원본 상태로 되돌릴 때 사용.
#
# Usage:
#   export HF_TOKEN=hf_xxx
#   ./upload_hf_rollback.sh HyeonSang/exp001_smoke_baseline
#
# Upload target: README.md, data/train-*.parquet, deliverable_files/**
# Excluded: reference_files/** (from base duplicate), .cache/, etc.
# Mixing prevention: delete_patterns wipes data/** and deliverable_files/**
#   from remote first, then uploads current files in same commit.

set -euo pipefail
cd "$(dirname "$0")"

REPO_ID="${1:?Usage: $0 <hf_repo_id>  (e.g. HyeonSang/exp001_smoke_baseline)}"
DATA_DIR="../data/gdpval-local"

if [ -z "${HF_TOKEN:-}" ]; then
  echo "❌ HF_TOKEN not set."
  echo "   export HF_TOKEN=hf_xxx"
  exit 1
fi

if [ ! -d "$DATA_DIR" ]; then
  echo "❌ Data directory not found: $DATA_DIR"
  exit 1
fi

echo "============================================================"
echo "📤 Step 6: Upload to HuggingFace"
echo "   Repo:  $REPO_ID"
echo "   Local: $DATA_DIR"
echo "============================================================"

# ── 1. Run Step 5 validation ──
echo ""
echo "── Pre-upload validation ──"
python step5_validate.py --data-dir "$DATA_DIR"
if [ $? -ne 0 ]; then
    echo "❌ Validation failed. Aborting upload."
    exit 1
fi

# ── 2. Upload ──
echo ""
echo "── Uploading to HuggingFace ──"
export REPO_ID DATA_DIR

python3 - <<'PYEOF'
import os
from pathlib import Path
from huggingface_hub import HfApi, create_repo

repo_id = os.environ["REPO_ID"]
data_dir = Path(os.environ["DATA_DIR"])
token = os.environ["HF_TOKEN"]

api = HfApi(token=token)

# Create repo if not exists
try:
    create_repo(repo_id, repo_type="dataset", exist_ok=True, token=token)
    print(f"✓ Repository ready: {repo_id}")
except Exception as e:
    print(f"⚠️  Repo creation: {e}")

# Upload only what matches openai/gdpval structure
INCLUDE = [
    "README.md",
    "data/train-*.parquet",
    "deliverable_files/**",
]

IGNORE = [
    ".cache/**",
    "train/**",
    "dataset_dict.json",
    "*.arrow",
    "*.lock",
    "__pycache__/**",
    "state.json",
    "dataset_info.json",
]

# delete_patterns: wipe stale files from remote first
DELETE = [
    "data/**",
    "deliverable_files/**",
]

print(f"\n📤 Uploading files (with remote cleanup)...")
print(f"   Include: {INCLUDE}")
print(f"   Delete (remote): {DELETE}")
print(f"   Ignore:  {IGNORE}")

api.upload_folder(
    folder_path=str(data_dir),
    repo_id=repo_id,
    repo_type="dataset",
    allow_patterns=INCLUDE,
    ignore_patterns=IGNORE,
    delete_patterns=DELETE,
    commit_message="Update dataset with experiment results",
)

print(f"\n✅ Upload complete!")
print(f"   https://huggingface.co/datasets/{repo_id}/tree/main")
PYEOF
