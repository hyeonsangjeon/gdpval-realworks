#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "============================================================"
echo "📝 Step 3: Format Results"
echo "============================================================"

python step3_format_results.py
