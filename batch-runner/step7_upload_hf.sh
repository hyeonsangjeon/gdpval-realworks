#!/usr/bin/env bash
# Step 7: Upload dataset to HuggingFace Hub (openai/gdpval 구조와 동일)
#
# Usage:
#   HF_TOKEN=hf_xxx ./step7_upload_hf.sh            # prepared scope 검증 후 게시
#   HF_TOKEN=hf_xxx ./step7_upload_hf.sh [repo_id]  # repo override
#   HF_TOKEN=hf_xxx ./step7_upload_hf.sh --test      # smoke/subset prepared scope 게시
#
# 업로드 대상: README.md, data/train-*.parquet, deliverable_files/**,
#               inference_provenance.json, self_report.json
# 제외 대상: .cache/, train/, dataset_dict.json 등 캐시 아티팩트
# Step 0 validated HEAD를 CAS parent로 사용하며 reference_files/**는 그대로 유지

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

TEST_MODE_SOURCE=""

if [ -n "$FORCE_TEST" ]; then
  TEST_MODE_SOURCE="--test (validated prepared scope)"
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
export REPO_ID UPLOAD_DIR

python3 - <<'VALIDATE_EOF'
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or ".")
from pathlib import Path

from core.hf_publication import (
  clear_publication_receipt,
  load_publication_identity,
)
from core.narrative_analyzer import expected_narrative_publication_identity
from core.repo_bootstrapper import validate_pre_upload

clear_publication_receipt()
model, effort, fingerprint = expected_narrative_publication_identity()
identity = load_publication_identity(
  Path("workspace/step1_tasks_prepared.json"),
  Path("workspace/step2_inference_results.json"),
  expected_narrative_model=model,
  expected_narrative_reasoning_effort=effort,
  expected_narrative_runtime_fingerprint=fingerprint,
)
if identity.repo_id != os.environ["REPO_ID"]:
  raise SystemExit("publication repository differs from prepared identity")
workflow_experiment_id = os.environ.get("EXPERIMENT_ID")
if workflow_experiment_id and workflow_experiment_id != identity.experiment_id:
  raise SystemExit("publication experiment differs from prepared identity")
errors = validate_pre_upload(
  local_path=os.environ["UPLOAD_DIR"],
  submission_repo_id=os.environ["REPO_ID"],
  expected_rows=len(identity.ordered_task_ids),
  expected_task_ids=list(identity.ordered_task_ids),
  expected_submitter_rows=identity.submitter_rows(),
  expected_experiment_id=identity.experiment_id,
)
if errors:
    print("❌ Pre-upload validation FAILED:")
    for e in errors:
        print(f"   • {e}")
    sys.exit(1)
print(f"✓ Pre-upload validation passed  (rows={len(identity.ordered_task_ids)})")
VALIDATE_EOF

# ── Upload ─────────────────────────────────────────────────────────────
python3 - <<'PYEOF'
import os
from pathlib import Path

from core.config import DEFAULT_LOCAL_PATH
from core.hf_publication import (
  DELETE_PATTERNS,
  IGNORE_PATTERNS,
  INCLUDE_PATTERNS,
  load_publication_identity,
  publish_dataset_with_receipt,
)
from core.narrative_analyzer import expected_narrative_publication_identity
from core.repo_bootstrapper import (
  TARGET_HEAD_FILENAME,
  load_target_head_identity,
)

INCLUDE = [
  "README.md",
  "data/train-*.parquet",
  "deliverable_files/**",
  "inference_provenance.json",
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
DELETE = [
  "data/**",
  "deliverable_files/**",
  "inference_provenance.json",
  "self_report.json",
  "step2_inference_results.json",
]
if INCLUDE_PATTERNS != INCLUDE:
  raise SystemExit("publication allowlist contract changed")
if IGNORE_PATTERNS != IGNORE:
  raise SystemExit("publication ignore-list contract changed")
if DELETE_PATTERNS != DELETE:
  raise SystemExit("publication delete-list contract changed")

repo_id = os.environ["REPO_ID"]
data_dir = Path(os.environ["UPLOAD_DIR"])
token = os.environ["HF_TOKEN"]
model, effort, fingerprint = expected_narrative_publication_identity()
identity = load_publication_identity(
  Path("workspace/step1_tasks_prepared.json"),
  Path("workspace/step2_inference_results.json"),
  expected_narrative_model=model,
  expected_narrative_reasoning_effort=effort,
  expected_narrative_runtime_fingerprint=fingerprint,
)
if identity.repo_id != repo_id:
  raise SystemExit("publication repository differs from prepared identity")
expected_head = os.environ.get("EXPECTED_TARGET_HEAD", "")
if not expected_head:
  expected_head = load_target_head_identity(
    DEFAULT_LOCAL_PATH / TARGET_HEAD_FILENAME,
    repo_id,
  )

print(f"\n📤 Uploading files (with remote cleanup)...")
print(f"   Parent:  {expected_head}")
print(f"   Include: {INCLUDE_PATTERNS}")
print(f"   Delete (remote): {DELETE_PATTERNS}")
print(f"   Ignore:  {IGNORE_PATTERNS}")

publication = publish_dataset_with_receipt(
  repo_id,
  data_dir,
  token=token,
  expected_head=expected_head,
  identity=identity,
)

print(f"\n✅ Upload complete!")
print(f"   Verified revision: {publication.oid}")
print(f"   Publication plan: {publication.plan_sha256}")
if publication.reconciled:
  print("   Commit response was reconciled against the verified remote state.")
print(f"   https://huggingface.co/datasets/{repo_id}/tree/main")
PYEOF
