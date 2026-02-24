#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./step2_run_inference.sh                          # YAML defaults (mode + retries from execution:)
#   ./step2_run_inference.sh condition_b               # condition_b
#   ./step2_run_inference.sh condition_a --mode subprocess  # CLI override
#   ./step2_run_inference.sh condition_a --no-resume   # extra args

CONDITION="${1:-condition_a}"
EXTRA_ARGS="${@:2}"

cd "$(dirname "$0")"

echo "============================================================"
echo "🚀 Step 2: Run Inference"
echo "   Condition: $CONDITION"
echo "   (mode & max_retries from YAML execution: section)"
if [ -n "$EXTRA_ARGS" ]; then
echo "   CLI overrides: $EXTRA_ARGS"
fi
echo "============================================================"

python step2_run_inference.py --condition "$CONDITION" $EXTRA_ARGS
