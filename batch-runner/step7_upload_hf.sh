#!/usr/bin/env bash
# Step 7: Upload dataset to HuggingFace Hub (openai/gdpval 구조와 동일)
#
# Usage:
#   HF_TOKEN=hf_xxx ./step7_upload_hf.sh            # 완전 자동 (220행 full 검증)
#   HF_TOKEN=hf_xxx ./step7_upload_hf.sh [repo_id]  # repo override
#   HF_TOKEN=hf_xxx ./step7_upload_hf.sh --test      # smoke test (parquet 실제 행 수로 검증)
#
# 업로드 대상: README.md, data/train-*.parquet, deliverable_files/**
# 제외 대상: .cache/, train/, dataset_dict.json 등 캐시 아티팩트
# reference_files/** 는 duplicate 된 베이스를 그대로 유지 (삭제/업로드 안 함)

set -euo pipefail
cd "$(dirname "$0")"

UPLOAD_DIR="workspace/upload"
FORCE_TEST=""

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --test) FORCE_TEST="1" ;;
        *)      REPO_ARG="$arg" ;;
    esac
done

# ── expected row count 결정 ──────────────────────────────────────────────
EXPECTED_ROWS=220
TEST_MODE_SOURCE=""

if [ -n "$FORCE_TEST" ]; then
    # --test: parquet의 실제 행 수를 읽어 검증 (smoke test용)
    EXPECTED_ROWS=$(python3 -c "
import pandas as pd, glob
parquets = sorted(glob.glob('${UPLOAD_DIR}/data/train-*.parquet'))
print(sum(len(pd.read_parquet(path)) for path in parquets) if parquets else 220)
" 2>/dev/null || echo 220)
    TEST_MODE_SOURCE="--test (rows=${EXPECTED_ROWS})"
fi

# repo_id 결정: 인자 > workspace/step2_inference_results.json의 "source" > 기본값
if [ -n "${REPO_ARG:-}" ]; then
  REPO_ID="$REPO_ARG"
  echo "ℹ️  Repo: $REPO_ID  (인자 지정)"
elif [ -f "workspace/step2_inference_results.json" ]; then
  REPO_ID=$(python3 -c "
import json, sys
d = json.load(open('workspace/step2_inference_results.json'))
src = d.get('source', '').strip()
if not src:
    print('hyeonsangjeon/gdpval-realwork-results')
else:
    print(src)
")
  echo "ℹ️  Repo: $REPO_ID  (step2_inference_results.json 'source'에서 읽음)"
else
  REPO_ID="hyeonsangjeon/gdpval-realwork-results"
  echo "ℹ️  Repo: $REPO_ID  (기본값)"
fi

if [ -z "${HF_TOKEN:-}" ]; then
  echo "❌ HF_TOKEN not set."
  echo "   export HF_TOKEN=hf_xxx"
  exit 1
fi

if [ ! -d "$UPLOAD_DIR" ]; then
  echo "❌ Upload directory not found: $UPLOAD_DIR"
  echo "   Run step2 (inference) and step4 (fill parquet) first."
  exit 1
fi

echo "🤗 HuggingFace Upload"
echo "   Repo:          $REPO_ID"
echo "   Source:        $UPLOAD_DIR"
if [ -n "$TEST_MODE_SOURCE" ]; then
  echo "   Mode:          Test — ${TEST_MODE_SOURCE}"
else
  echo "   Mode:          Full (220 rows)"
fi
echo ""

# ── Pre-upload validation ──────────────────────────────────────────────
echo "🔍 Pre-upload validation..."
export REPO_ID UPLOAD_DIR EXPECTED_ROWS

python3 - <<'VALIDATE_EOF'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or ".")
from core.repo_bootstrapper import validate_pre_upload
expected = int(os.environ.get("EXPECTED_ROWS", "220"))
errors = validate_pre_upload(
    local_path=os.environ["UPLOAD_DIR"],
    submission_repo_id=os.environ["REPO_ID"],
    expected_rows=expected,
)
if errors:
    print("❌ Pre-upload validation FAILED:")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)
print(f"✓ Pre-upload validation passed  (rows={expected})")
VALIDATE_EOF

# ── Upload ─────────────────────────────────────────────────────────────
python3 - <<'PYEOF'
import os
from pathlib import Path
from huggingface_hub import HfApi, create_repo

repo_id = os.environ["REPO_ID"]
data_dir = Path(os.environ["UPLOAD_DIR"])
token = os.environ["HF_TOKEN"]

api = HfApi(token=token)

# Create repo if not exists
try:
    create_repo(repo_id, repo_type="dataset", exist_ok=True, token=token)
    print(f"✓ Repository ready: {repo_id}")
except Exception as e:
    print(f"⚠️  Repo creation: {e}")

# Upload only what matches openai/gdpval structure
# reference_files/** is intentionally EXCLUDED — it comes from the
# duplicated openai/gdpval base and should never be re-uploaded.
INCLUDE = [
    "README.md",
    "data/train-*.parquet",
    "deliverable_files/**",
    "self_report.json",
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

# delete_patterns: wipe data/** and deliverable_files/** from remote FIRST
# so stale files from previous runs don't persist.
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
