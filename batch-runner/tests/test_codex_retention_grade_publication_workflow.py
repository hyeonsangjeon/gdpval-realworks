"""Execute the real publication shell; simulate only its external CLI processes.

This checks workflow wiring, not record validity or a live server observation.
The CLI's authority, receipt and terminal validators are not replaced or invoked.
"""

import json
import os
from pathlib import Path
import subprocess

import yaml


def test_retention_publication_workflow_reconciles_once_without_replay(tmp_path):
    repository = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((repository / ".github/workflows/grade-run.yml").read_bytes())
    live = workflow["jobs"]["pilot-live"]
    step = next(item for item in live["steps"] if item.get("name") ==
                "Retain validated private grade and accounting on the grading branch")
    script = step["run"]
    assert step == {
        "name": "Retain validated private grade and accounting on the grading branch",
        "if": "${{ always() && !cancelled() && steps.pilot_judge.outcome != 'skipped' && steps.pilot_claim.outcome == 'success' }}",
        "timeout-minutes": 5,
        "env": {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"},
        "run": script,
    }
    assert live["defaults"]["run"]["shell"] == "bash -e {0}"
    assert live["permissions"] == {"contents": "read", "id-token": "write"}
    assert live["needs"] == ["pilot-approve-paid"] and "environment" not in live
    assert "HF_TOKEN" not in live["env"]
    assert '-O "$RUNNER_TEMP/pilot-fixed-grade/publication-reserved.json"' in script
    assert script.count("--phase publish") == script.count("--phase reconcile") == 1

    # No executable is available through PATH. Bash builtins and this command
    # boundary are sufficient for the verbatim workflow body; no real Python,
    # service, credential, claim, judge or other external command can run.
    simulated_cli = r'''
python() {
  printf '%s\0' "$@" >> "$COMMAND_LOG"
  printf '\0' >> "$COMMAND_LOG"
  [[ "$1" == "batch-runner/codex_budget_pilot_grading.py" && "$2" == "--phase" ]] || return 98
  case "$3" in
    publish)
      printf '%s\n' "$SIMULATED_PUBLICATION"
      return "$SIMULATED_PUBLICATION_STATUS"
      ;;
    reconcile)
      printf '%s\n' "$SIMULATED_RECONCILIATION" > "$RUNNER_TEMP/pilot-fixed-grade/grade-server-observation.json"
      printf '%s\n' "$SIMULATED_RECONCILIATION"
      return "$SIMULATED_RECONCILIATION_STATUS"
      ;;
    *) return 99 ;;
  esac
}
'''
    retained = "retention/first-cell"
    legacy = "pilot/0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r1"
    cases = (
        ("acknowledged", retained, 0, "owned", 0),
        ("lost-ack", retained, 2, "owned", 0),
        ("pre-reservation", retained, 2, "missing", 0),
        ("reconcile-refused", retained, 2, "owned", 9),
        ("reconcile-ambiguous", retained, 23, "owned", 2),
        ("symlink-reservation", retained, 2, "symlink", 0),
        ("directory-reservation", retained, 2, "directory", 0),
        ("legacy-success", legacy, 0, "owned", 0),
        ("legacy-failure", legacy, 7, "owned", 0),
        ("lookalike", retained + "-other", 2, "owned", 0),
    )
    for label, selector, publication_status, reservation_kind, reconciliation_status in cases:
        runner_temp = tmp_path / (label + " private")
        root = runner_temp / "pilot-fixed-grade"
        root.mkdir(parents=True, mode=0o700)
        private_file = root / "private-deliverable.txt"
        private_bytes = b"synthetic private bytes must never be logged\n"
        private_file.write_bytes(private_bytes)
        reservation = root / "publication-reserved.json"
        if reservation_kind == "owned":
            reservation.write_bytes(b'{"synthetic_reservation":true}\n')
            assert reservation.stat().st_uid == os.geteuid()
        elif reservation_kind == "symlink":
            reservation.symlink_to(private_file)
        elif reservation_kind == "directory":
            reservation.mkdir()

        publication = {
            "stage": "retention_grade_publication" if selector == retained else "grade_publication",
            "outcome": "acknowledged" if publication_status == 0 else "unresolved",
            "reason": None if publication_status == 0 else "synthetic_publication_failure",
        }
        publication_json = json.dumps(publication, sort_keys=True)
        receipt = root / "publication-receipt.json"
        receipt_bytes = (publication_json + "\n").encode()
        if reservation_kind != "missing":
            receipt.write_bytes(receipt_bytes)
        observation = {
            "stage": "retention_grade_server_reconciliation",
            "outcome": "verified_server_state" if reconciliation_status == 0 else "unresolved",
            "reason": None if reconciliation_status == 0 else "synthetic_reconciliation_failure",
        }
        if reconciliation_status == 0:
            observation["writer_acknowledgment"] = "not_established"
        command_log = runner_temp / "commands.bin"
        inventory = set(runner_temp.rglob("*"))
        environment = {
            "PATH": str(runner_temp / "no-executables"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "RUNNER_TEMP": str(runner_temp), "GRADE_SELECTOR": selector,
            "GITHUB_SHA": "d" * 40,
            "PILOT_GRADE_PRODUCER_SOURCE_SHA": "e355faf9a6212175a288e8473968915ffb2408d0",
            "GRADE_TERMINAL": "de50ff0aa6037c0ef6e3b713da519359abd1d08d",
            "COMMAND_LOG": str(command_log), "SIMULATED_PUBLICATION": publication_json,
            "SIMULATED_PUBLICATION_STATUS": str(publication_status),
            "SIMULATED_RECONCILIATION": json.dumps(observation, sort_keys=True),
            "SIMULATED_RECONCILIATION_STATUS": str(reconciliation_status),
        }
        completed = subprocess.run(
            ["/bin/bash", "--noprofile", "--norc", "-e", "-c", simulated_cli + script],
            cwd=repository, env=environment, capture_output=True, text=True, timeout=10,
        )
        assert completed.returncode == publication_status, label
        assert completed.stderr == "", label
        chunks = command_log.read_bytes().split(b"\0\0")
        assert chunks[-1] == b""
        calls = [chunk.decode().split("\0") for chunk in chunks[:-1]]
        expected_publish = [
            "batch-runner/codex_budget_pilot_grading.py", "--phase", "publish",
            "--selector", selector, "--reviewed-source-sha", environment["GITHUB_SHA"],
            "--producer-source-sha", environment["PILOT_GRADE_PRODUCER_SOURCE_SHA"],
            "--terminal-revision", environment["GRADE_TERMINAL"], "--root", str(root),
        ]
        should_reconcile = selector == retained and publication_status != 0 and reservation_kind == "owned"
        expected_calls = [expected_publish]
        if should_reconcile:
            expected_calls.append([*expected_publish[:2], "reconcile", *expected_publish[3:]])
        assert calls == expected_calls, label
        safe_results = [json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")]
        assert safe_results == [publication] + ([observation] if should_reconcile else []), label
        observation_path = root / "grade-server-observation.json"
        if should_reconcile:
            assert json.loads(observation_path.read_bytes()) == observation
            assert f"retention_reconciliation_exit_code={reconciliation_status}\n" in completed.stdout
            if reconciliation_status == 0:
                assert safe_results[-1]["writer_acknowledgment"] == "not_established"
                assert safe_results[0]["outcome"] == "unresolved"
        else:
            assert not observation_path.exists()
            assert "retention_reconciliation_exit_code=" not in completed.stdout
        if selector == retained and publication_status != 0:
            assert f"retention_publication_exit_code={publication_status}\n" in completed.stdout
            assert ("retention_reconciliation=not_attempted_no_owned_reservation\n" in completed.stdout) == (not should_reconcile)
        else:
            assert completed.stdout == publication_json + "\n"
        if reservation_kind == "missing":
            assert not reservation.exists() and not receipt.exists()
        else:
            assert receipt.read_bytes() == receipt_bytes
        if reservation_kind == "symlink":
            assert reservation.is_symlink() and reservation.readlink() == private_file
        elif reservation_kind == "directory":
            assert reservation.is_dir()
        elif reservation_kind == "owned":
            assert reservation.read_bytes() == b'{"synthetic_reservation":true}\n'
        assert private_file.read_bytes() == private_bytes
        assert private_bytes.decode().strip() not in completed.stdout
        assert set(runner_temp.rglob("*")) == inventory | {command_log} | ({observation_path} if should_reconcile else set())
