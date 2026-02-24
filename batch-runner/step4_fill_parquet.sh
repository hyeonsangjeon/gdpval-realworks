#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python step4_fill_parquet.py "$@"
