#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "============================================================"
echo "🔍 Step 5: Validate Dataset"
echo "============================================================"

python step5_validate.py "$@"
