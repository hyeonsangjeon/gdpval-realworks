#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:?Usage: $0 <config.yaml>}"

cd "$(dirname "$0")"

echo "============================================================"
echo "📦 Step 1: Prepare Tasks"
echo "============================================================"

python step1_prepare_tasks.py --config "$CONFIG"
