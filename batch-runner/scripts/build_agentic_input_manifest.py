#!/usr/bin/env python3
"""Build exact approved input identities on the dedicated compute runner."""

import argparse
import json
import sys
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_input_manifest import build_input_manifest  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-manifest", required=True)
    parser.add_argument("--dataset-root", required=True)
    parser.add_argument("--staging-parent", required=True)
    parser.add_argument("--provider-classification", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    selection = json.loads(
        Path(args.selection_manifest).read_text(encoding="utf-8")
    )
    manifest = build_input_manifest(
        selection_manifest=selection,
        dataset_root=args.dataset_root,
        staging_parent=args.staging_parent,
        provider_classification=args.provider_classification,
    )
    Path(args.output).write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()