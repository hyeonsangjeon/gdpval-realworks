"""Fail-closed entrypoint for the unconnected Phase 1B candidate image."""

import json
import sys


def main() -> None:
    print(json.dumps({
        "error": "agentic_v2_phase1b_candidate_not_activated",
        "foundation_only": True,
        "production_activation": "disabled",
    }, sort_keys=True, separators=(",", ":")), file=sys.stderr)
    raise SystemExit(78)


if __name__ == "__main__":
    main()