"""CI evidence from inert wire fixtures, explicitly not a live/model receipt."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ghcp_ahp_probe import save_json
from ghcp_ahp_wire_capture import analyze


def fixture(scenario):
    result = subprocess.run(["node", str(Path(__file__).with_name("ghcp_ahp_wire_observer_fixture.cjs")), scenario],
                            capture_output=True, check=True, text=True, timeout=20,
                            env={"PATH": "/usr/bin:/bin:/usr/local/bin"})
    return analyze(json.loads(result.stdout), synthetic=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    save_json(args.output, {"synthetic": True, "model_calls": 0, "session_create_requests": 0,
                           "admission_allowed": False,
                           "cases": {case: fixture(case) for case in ("match", "missing", "mismatch_model", "mismatch_effort", "model_free")}})
