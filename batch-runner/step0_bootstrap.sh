#!/bin/bash
# Step 0: Bootstrap submission dataset repo
#
# Duplicates openai/gdpval into your HF submission repo (if not exists)
# then downloads a local snapshot to data/gdpval-local.
#
# submission_repo_id는 experiment YAML의 data.source에서 자동으로 읽습니다.
#
# Usage:
#   export HF_TOKEN=hf_xxx
#   ./step0_bootstrap.sh <yaml_config_path>
#   ./step0_bootstrap.sh experiments/exp001_smoke_baseline.yaml
#
# This is idempotent — safe to run multiple times.

set -euo pipefail
cd "$(dirname "$0")"

YAML_CONFIG="${1:?Usage: ./step0_bootstrap.sh <yaml_config_path>}"

if [ ! -f "$YAML_CONFIG" ]; then
  echo "❌ YAML config not found: $YAML_CONFIG"
  exit 1
fi

REPO_ID=$(python3 -c "
import yaml, sys
with open('$YAML_CONFIG', 'r') as f:
    cfg = yaml.safe_load(f)
source = cfg.get('data', {}).get('source', '')
if not source:
    print('ERROR: data.source not found in YAML', file=sys.stderr)
    sys.exit(1)
print(source)
")

echo "ℹ️  Submission repo: $REPO_ID  (from $YAML_CONFIG)"

if [ -z "${HF_TOKEN:-}" ]; then
  echo "❌ HF_TOKEN not set."
  echo "   export HF_TOKEN=hf_xxx"
  exit 1
fi

echo "🔧 Step 0: Bootstrap Submission Repo"
echo "   Repo: $REPO_ID"
echo ""

export REPO_ID

python3 - <<'PYEOF'
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) or ".")
from core.repo_bootstrapper import RepoBootstrapper

repo_id = os.environ["REPO_ID"]
bs = RepoBootstrapper(submission_repo_id=repo_id)
bs.bootstrap()
PYEOF
