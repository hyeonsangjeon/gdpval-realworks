"""Pin hosted Ubuntu without changing workflow behavior or historical seals."""

import hashlib
from pathlib import Path
import re

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
# Before/after bytes at main 7c1f4c94067485be3170612258639d739d07d585.
# Every historical value remains checked; only these job runner lines differ.
RUNNER_PINS = {
    "agentic-v2-stage-a-probe.yml": (
        "59e5789b36ad130fea25e5d83db10497f5a91ba0d50de7ecef464fdcf275992d",
        "68d31832a47d126215d07705e24afb32ccf3ab1902ecd199fac5d32dfdfff1b4",
        ("free", "paid"),
    ),
    "agentic-v2-stage-run.yml": (
        "f02579edfa09ee9d3e9576cff25510c27f86bb1a9498f311f0bafd9ff4261ae1",
        "4ef1cea1b561d686480a9b2dadc737655bcd3a68e5ed1f39b9e70aaff22dafd2",
        ("free", "paid", "collect", "comparison-admission"),
    ),
    "backend-tests.yml": (
        "75e6db775426a8470d2757f2ae62fafc2a806f0f2684ed59925480956ad3ac65",
        "9ec98746110499a2f199e1322a8568effcd7c8b174e04b35661420e64a06af51",
        ("pytest", "comparison-contracts", "pilot-contracts", "budget-readout-contracts",
         "pilot-preflight-contracts", "pilot-external-receipt-contracts",
         "pilot-external-publication-contracts", "wire-contracts", "native-host-contracts"),
    ),
    "batch-run.yml": (
        "06519bc2abb0f69fe688cd864dadb536e907a433e2726c5bf60c1115c5c220bb",
        "a7b65f7d8f167cc0b13c940b90b84334dcfed876608696baedccf0a7b414a9cd",
        ("inspect-mode", "reject-agentic", "reject-unconfirmed-codex", "batch-run", "comparison-admission"),
    ),
    "build-sandbox-image.yml": (
        "8c79b85f0c692d3a5c5897bd8f2eafb82af44412687b31982cb00d4c5e6ab043",
        "234c1b269b582425f7b4f344f6dffb8a89f5ad0503afae256f359726597e9d16",
        ("build-sandbox-image", "hosted-containment-measurement"),
    ),
    "execution-envelope-preflight.yml": (
        "62cc8887244fe1cc7a7643c512a65b3b23f95d4f429bd1e2f15d9117b6672c49",
        "25cd47ce3b63bc38d0eea51f6c4e4c5eb519a7fe4c21557ec318086841d68dd7",
        ("advance-check",),
    ),
    "grader-hash-freeze.yml": (
        "306e59b7e97fabcfc78a4bee75f41ad0bd1342a3a4b727caf06d6c8dcd85ea0f",
        "2161be71ce5c24f5c0afcd09efcf1c1e3964d844c3ad916d5f6e420fb1e1ac7c",
        ("freeze-check",),
    ),
}
# batch-run.yml changed once more after the runner pins: the wait for a result
# PR's dispatched checks moved out of the batch job into its own job,
# result-pr-checks (owner decision 2026-11-14). Its bytes are reconstructed in
# two exact steps, that move first, then the runner lines, so every historical
# hash above is still checked.
RESULT_PR_JOB_PIN = (
    "a7b65f7d8f167cc0b13c940b90b84334dcfed876608696baedccf0a7b414a9cd",  # runner pins only
    "5f41e8ff0941a516a6f4ae9f46438687268ee94622a6adf37782200e797c9992",  # plus result-pr-checks
)
OUTPUTS = (
    "    # Read by result-pr-checks below. Both stay empty unless the last leg\n"
    "    # opened a result PR and dispatched its checks.\n"
    "    outputs:\n"
    "      result_pr_number: ${{ steps.dispatch_checks.outputs.pr_number }}\n"
    "      result_pr_head_sha: ${{ steps.dispatch_checks.outputs.pr_head_sha }}\n"
)
DISPATCH_ADDED = (
    ("      - name: Dispatch exact result PR validation\n        id: dispatch_checks\n",
     "      - name: Dispatch exact result PR validation\n"),
    ("          PR_BRANCH: ${{ steps.cpr.outputs.pull-request-branch }}\n"
     "          PR_NUMBER: ${{ steps.cpr.outputs.pull-request-number }}\n"
     "          PR_HEAD_SHA: ${{ steps.cpr.outputs.pull-request-head-sha }}\n"
     "        run: |\n",
     "          PR_BRANCH: ${{ steps.cpr.outputs.pull-request-branch }}\n"
     "          PR_HEAD_SHA: ${{ steps.cpr.outputs.pull-request-head-sha }}\n"
     "        run: |\n"),
    ("            --raw-field expected_sha=\"$PR_HEAD_SHA\"\n"
     "          # Handed to result-pr-checks, which waits for both in its own job.\n"
     "          echo \"pr_number=$PR_NUMBER\" >> \"$GITHUB_OUTPUT\"\n"
     "          echo \"pr_head_sha=$PR_HEAD_SHA\" >> \"$GITHUB_OUTPUT\"\n",
     "            --raw-field expected_sha=\"$PR_HEAD_SHA\"\n"),
)
JOB_START = "  # Waits for the result PR's dispatched checks in a job of its own. Inside the\n"
JOB_STEPS = "    steps:\n"
NEXT_JOB = "  comparison-admission:\n"
STEP_ENV = (
    ("        env:\n"
     "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"
     "          PR_NUMBER: ${{ needs.batch-run.outputs.result_pr_number }}\n"
     "          PR_HEAD_SHA: ${{ needs.batch-run.outputs.result_pr_head_sha }}\n"
     "          REQUIRED_WORKFLOWS: 'backend-tests.yml deploy.yml'\n"
     "          # Backend Tests' slowest job takes 34 to 49 minutes once it starts\n"
     "          # (median 43); 110 minutes leaves room for the queue.\n"
     "          WAIT_SECONDS: '6600'\n"),
    ("        if: success() && inputs.dry_run != true && steps.check_relay.outputs.needs_relay == 'false' && steps.step2a.outcome == 'success'\n"
     "        env:\n"
     "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"
     "          PR_NUMBER: ${{ steps.cpr.outputs.pull-request-number }}\n"
     "          PR_HEAD_SHA: ${{ steps.cpr.outputs.pull-request-head-sha }}\n"
     "          REQUIRED_WORKFLOWS: 'backend-tests.yml deploy.yml'\n"
     "          WAIT_SECONDS: '1800'\n"),
)
SUMMARY = "      # ── Summary step ──\n"


def restore_pre_result_pr_job_bytes(data):
    """Undo exactly the result-pr-checks move, requiring both complete hashes."""
    before_hash, after_hash = RESULT_PR_JOB_PIN
    assert hashlib.sha256(data).hexdigest() == after_hash
    text = data.decode("utf-8")
    assert text.count(OUTPUTS) == 1
    text = text.replace(OUTPUTS, "")
    for new, old in DISPATCH_ADDED:
        assert text.count(new) == 1
        text = text.replace(new, old)
    start, end = text.index(JOB_START), text.index(NEXT_JOB)
    job = text[start:end]
    text = text[:start] + text[end:]
    assert job.count(JOB_STEPS) == 1 and job.endswith("\n\n")
    step = job.split(JOB_STEPS, 1)[1][:-1]
    new_env, old_env = STEP_ENV
    assert step.count(new_env) == 1
    step = step.replace(new_env, old_env)
    assert text.count(SUMMARY) == 1
    text = text.replace(SUMMARY, step + SUMMARY)
    restored = text.encode("utf-8")
    assert hashlib.sha256(restored).hexdigest() == before_hash
    return restored


# batch-run.yml changed a third time: the batch job now refuses a runner outside
# Azure at its first step and placement-reroll sends the same dispatch again
# (owner decision 2026-11-19). Undone in one exact step before the two above, so
# every historical hash is still checked.
PLACEMENT_GUARD_PIN = (
    "5f41e8ff0941a516a6f4ae9f46438687268ee94622a6adf37782200e797c9992",  # plus result-pr-checks
    "c10622a6ffcdc2fd676aa27de3d6ea85a9cc27308f85ed0a47a26185e534842e",  # plus the placement guard
)
# A successor to #810, not a replacement for its historical byte contract.
COMPARISON_INPUT_PROJECTION_PIN = (
    PLACEMENT_GUARD_PIN[1],
    "149d60e571ddbc6aae79ea78c76313a421e3805d1bbcf72e0d830253d377d718",
)
COMPARISON_INPUT_PROJECTION = '''          # Placement retries belong to ordinary batches, not this comparison.
          # Remove only the default counter; keep every old input and its type.
          COMPARISON_INPUTS="$(python3 -I - <<'PY'
          import json
          import os

          def unique_object(pairs):
              result = {}
              for key, value in pairs:
                  if key in result:
                      raise ValueError("duplicate comparison input")
                  result[key] = value
              return result

          values = json.loads(os.environ["COMPARISON_INPUTS"], object_pairs_hook=unique_object)
          if type(values) is not dict:
              raise SystemExit("comparison_placement_attempt_refused")
          placement = values.pop("placement_attempt", None)
          if not ((type(placement) is int and placement == 1) or
                  (type(placement) is str and placement == "1")):
              raise SystemExit("comparison_placement_attempt_refused")
          print(json.dumps(values, allow_nan=False))
          PY
          )"
'''


def restore_pre_comparison_input_projection_bytes(data):
    """Undo only the exact comparison adapter, preserving the #810 seal."""
    before_hash, after_hash = COMPARISON_INPUT_PROJECTION_PIN
    assert hashlib.sha256(data).hexdigest() == after_hash
    addition = COMPARISON_INPUT_PROJECTION.encode("utf-8")
    assert data.count(addition) == 1
    restored = data.replace(addition, b"", 1)
    assert hashlib.sha256(restored).hexdigest() == before_hash
    return restored


# Cut whole: the new job, up to the result-pr-checks comment, and the guard
# step, up to the checkout that used to be the batch job's first step.
PLACEMENT_CUTS = (
    ("  # Sends the dispatch again when batch-run refused its runner for being\n", JOB_START),
    ("      # GitHub now places ubuntu-24.04 jobs on AWS as well as on Azure\n",
     "      - name: Checkout\n"),
)
PLACEMENT_GUARDED = " && steps.placement.outcome == 'success'"
PLACEMENT_ADDED = (
    ("        default: ''\n"
     "      placement_attempt:\n"
     "        description: 'Internal, set by placement-reroll: which placement of this same dispatch this is, 1 to 20; it rises each time batch-run lands outside Azure and is sent again. Leave 1; each relay leg starts again at 1.'\n"
     "        required: false\n"
     "        type: number\n"
     "        default: 1\n"
     "\n"
     "permissions:\n",
     "        default: ''\n"
     "\n"
     "permissions:\n"),
    ("          # Raised only by placement-reroll below, once per placement outside\n"
     "          # Azure. Same shape as relay_run, its own ceiling.\n"
     "          PLACEMENT_ATTEMPT: ${{ inputs.placement_attempt }}\n", ""),
    ("          [[ \"$PLACEMENT_ATTEMPT\" =~ ^[1-9][0-9]?$ ]]\n"
     "          (( 10#$PLACEMENT_ATTEMPT <= 20 ))\n", ""),
    ("      # Read by placement-reroll below: azure, unknown or off-azure. Set by\n"
     "      # the first step, so it is there even when that step ends the job.\n"
     "      placement: ${{ steps.placement.outputs.verdict }}\n", ""),
    ("          # placement_attempt goes out as 1 rather than carried over: it counts\n"
     "          # the placements of one leg, and the next leg is a new request.\n", ""),
    ("            -f comparison_reviewed_source_sha=\"$COMPARISON_REVIEWED_SOURCE_SHA_INPUT\" \\\n"
     "            -f placement_attempt=1\n",
     "            -f comparison_reviewed_source_sha=\"$COMPARISON_REVIEWED_SOURCE_SHA_INPUT\"\n"),
)


def restore_pre_placement_guard_bytes(data):
    """Undo exactly the placement guard and its re-send job, requiring both hashes."""
    if hashlib.sha256(data).hexdigest() == COMPARISON_INPUT_PROJECTION_PIN[1]:
        data = restore_pre_comparison_input_projection_bytes(data)
    before_hash, after_hash = PLACEMENT_GUARD_PIN
    assert hashlib.sha256(data).hexdigest() == after_hash
    text = data.decode("utf-8")
    for start_marker, end_marker in PLACEMENT_CUTS:
        assert text.count(start_marker) == 1
        start = text.index(start_marker)
        text = text[:start] + text[text.index(end_marker, start):]
    assert text.count(PLACEMENT_GUARDED) == 3
    text = text.replace(PLACEMENT_GUARDED, "")
    for new, old in PLACEMENT_ADDED:
        assert text.count(new) == 1
        text = text.replace(new, old)
    restored = text.encode("utf-8")
    assert hashlib.sha256(restored).hexdigest() == before_hash
    return restored


# backend-tests.yml changed once after the runner pins: #808's GHCP AHP contract
# files and the offline rehearsal moved out of the core `pytest` job into
# ghcp-ahp-contracts, so the core job keeps its 45-minute margin (pre-merge
# review SF-1, 2026-11-28). Undone in one exact step before the runner lines,
# so both runner-pin hashes above are still checked unchanged.
GHCP_AHP_JOB_PIN = (
    "9ec98746110499a2f199e1322a8568effcd7c8b174e04b35661420e64a06af51",  # runner pins only
    "8a33a01879a1cf9742502a4ce21ef2a1a3550e2797fdb7b03e6fe2052d8905bb",  # plus ghcp-ahp-contracts
)
GHCP_AHP_JOB_START = "\n  # #808's GHCP AHP contract files and the offline rehearsal add about 3\n"
GHCP_AHP_CORE_IGNORES = (
    " --ignore-glob='tests/test_time_budget_*.py'"
    " --ignore-glob='tests/test_ghcp_ahp_*.py' --ignore=tests/test_ghcp_sol_offline_rehearsal.py\n",
    " --ignore-glob='tests/test_time_budget_*.py'\n",
)
GHCP_AHP_COMMENTS = (
    ("      # GPT-5.4/GPT-5.6, budget-pilot, time-budget and GHCP AHP contracts run in their family jobs;\n"
     "      # no additional tests are deselected across the eleven jobs. The partition\n",
     "      # GPT-5.4/GPT-5.6, budget-pilot and time-budget contracts run in their family jobs;\n"
     "      # no additional tests are deselected across the ten jobs. The partition\n"),
    ("  # ceiling. `pytest` remains the core check; all eleven job verdicts must be\n",
     "  # ceiling. `pytest` remains the core check; all ten job verdicts must be\n"),
)


def restore_pre_ghcp_ahp_job_bytes(data):
    """Undo exactly the GHCP AHP family job and its core ignores, requiring both hashes."""
    before_hash, after_hash = GHCP_AHP_JOB_PIN
    assert hashlib.sha256(data).hexdigest() == after_hash
    text = data.decode("utf-8")
    # The job is the file's last block; cut it whole, from its comment to EOF.
    assert text.count(GHCP_AHP_JOB_START) == 1
    start = text.index(GHCP_AHP_JOB_START)
    assert re.findall(r"^  ([A-Za-z0-9_-]+):$", text[start:], re.MULTILINE) == ["ghcp-ahp-contracts"]
    text = text[:start]
    for new, old in (GHCP_AHP_CORE_IGNORES, *GHCP_AHP_COMMENTS):
        assert text.count(new) == 1
        text = text.replace(new, old)
    restored = text.encode("utf-8")
    assert hashlib.sha256(restored).hexdigest() == before_hash
    return restored


PREVIOUS_BATCH_RUNNER = (
    "${{ needs.inspect-mode.outputs.uses_codex_foundry == 'true' "
    "&& 'ubuntu-24.04' || 'ubuntu-latest' }}"
)


def restore_pre_ubuntu_2404_runner_bytes(name, data):
    """Undo exactly the approved runner lines, requiring both complete hashes."""
    if name == "backend-tests.yml" and hashlib.sha256(data).hexdigest() == GHCP_AHP_JOB_PIN[1]:
        data = restore_pre_ghcp_ahp_job_bytes(data)
    if name == "batch-run.yml" and hashlib.sha256(data).hexdigest() in (
        PLACEMENT_GUARD_PIN[1], COMPARISON_INPUT_PROJECTION_PIN[1],
    ):
        data = restore_pre_placement_guard_bytes(data)
    if name == "batch-run.yml" and hashlib.sha256(data).hexdigest() == RESULT_PR_JOB_PIN[1]:
        data = restore_pre_result_pr_job_bytes(data)
    historical_hash, current_hash, changed_jobs = RUNNER_PINS[name]
    assert hashlib.sha256(data).hexdigest() == current_hash
    jobs = yaml.safe_load(data)["jobs"]
    assert all(jobs[job]["runs-on"] == "ubuntu-24.04" for job in changed_jobs)
    lines = data.decode("utf-8").splitlines(keepends=True)
    current_job = None
    restored = set()
    for index, line in enumerate(lines):
        match = re.fullmatch(r"  ([A-Za-z0-9_-]+):\n", line)
        if match:
            current_job = match[1]
        if current_job in changed_jobs and line.startswith("    runs-on:"):
            assert current_job not in restored
            assert line == "    runs-on: ubuntu-24.04\n"
            previous = (PREVIOUS_BATCH_RUNNER if name == "batch-run.yml" and current_job == "batch-run"
                        else "ubuntu-latest")
            lines[index] = f"    runs-on: {previous}\n"
            restored.add(current_job)
    assert restored == set(changed_jobs)
    historical = "".join(lines).encode("utf-8")
    assert hashlib.sha256(historical).hexdigest() == historical_hash
    return historical


@pytest.mark.parametrize("name", RUNNER_PINS)
def test_only_reviewed_runner_lines_change_and_historical_bytes_survive(name):
    current = (WORKFLOWS / name).read_bytes()
    historical = restore_pre_ubuntu_2404_runner_bytes(name, current)
    if name == "batch-run.yml":
        current = restore_pre_result_pr_job_bytes(restore_pre_placement_guard_bytes(current))
    if name == "backend-tests.yml":
        current = restore_pre_ghcp_ahp_job_bytes(current)
    before = yaml.safe_load(historical)
    after = yaml.safe_load(current)
    for job in RUNNER_PINS[name][2]:
        before["jobs"][job]["runs-on"] = "ubuntu-24.04"
    assert before == after


@pytest.mark.parametrize("name", RUNNER_PINS)
@pytest.mark.parametrize("mutation", ["floating", "other_release", "extra_byte", "old_bytes"])
def test_runner_reconstruction_rejects_unreviewed_bytes(name, mutation):
    data = (WORKFLOWS / name).read_bytes()
    if mutation == "floating":
        data = data.replace(b"    runs-on: ubuntu-24.04\n", b"    runs-on: ubuntu-latest\n", 1)
    elif mutation == "other_release":
        data = data.replace(b"    runs-on: ubuntu-24.04\n", b"    runs-on: ubuntu-26.04\n", 1)
    elif mutation == "extra_byte":
        data += b"\n"
    else:
        data = restore_pre_ubuntu_2404_runner_bytes(name, data)
    with pytest.raises(AssertionError):
        restore_pre_ubuntu_2404_runner_bytes(name, data)


def _assert_versioned_hosted_runner(name, job_name, job):
    runner = job.get("runs-on")
    if "uses" in job:
        assert runner is None  # Reusable workflows choose their own runner.
    elif isinstance(runner, list):
        assert (name, job_name) == ("agentic-sandbox-preflight.yml", "model-free-preflight")
        assert runner == ["self-hosted", "linux", "x64", "agentic-sandbox"]
    elif runner == "${{ matrix.runner }}":
        assert (name, job_name) == ("codex-sandbox-host-survey.yml", "survey")
        matrix = job["strategy"]["matrix"]
        assert set(matrix) == {"include"}
        assert {entry["runner"] for entry in matrix["include"]} == {"ubuntu-22.04", "ubuntu-24.04"}
    else:
        assert isinstance(runner, str) and re.fullmatch(r"ubuntu-\d{2}\.\d{2}", runner)


def test_all_hosted_ubuntu_runners_are_versioned_including_matrix_entries():
    paths = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert paths and sum(len(entry[2]) for entry in RUNNER_PINS.values()) == 24
    for path in paths:
        for job_name, job in yaml.safe_load(path.read_bytes())["jobs"].items():
            _assert_versioned_hosted_runner(path.name, job_name, job)


@pytest.mark.parametrize("runner", ["ubuntu", "ubuntu-latest", "linux", "${{ matrix.unknown }}"])
def test_floating_or_unresolved_hosted_runners_are_refused(runner):
    with pytest.raises(AssertionError):
        _assert_versioned_hosted_runner("new.yml", "new", {"runs-on": runner})


def test_python_pin_and_time_budget_control_runner_are_unchanged():
    jobs = yaml.safe_load((WORKFLOWS / "backend-tests.yml").read_bytes())["jobs"]
    assert jobs["time-budget-contracts"]["runs-on"] == "ubuntu-22.04"
    for job in jobs.values():
        setup = [step for step in job["steps"] if step.get("name") == "Setup Python"]
        assert len(setup) == 1 and setup[0]["with"]["python-version"] == "3.10.12"
    preflight = yaml.safe_load((WORKFLOWS / "execution-envelope-preflight.yml").read_bytes())
    setup = [step for step in preflight["jobs"]["advance-check"]["steps"]
             if step.get("name") == "Setup Python"]
    assert len(setup) == 1 and setup[0]["with"]["python-version"] == "3.10.12"


def test_the_result_pr_wait_is_the_only_change_after_the_runner_pins():
    current = restore_pre_placement_guard_bytes((WORKFLOWS / "batch-run.yml").read_bytes())
    pinned = restore_pre_result_pr_job_bytes(current)
    after, before = yaml.safe_load(current), yaml.safe_load(pinned)
    moved = after["jobs"].pop("result-pr-checks")["steps"]
    assert [step["name"] for step in moved] == ["Verify dispatched result PR checks"]
    del after["jobs"]["batch-run"]["outputs"]
    names = [step.get("name") for step in before["jobs"]["batch-run"]["steps"]]
    assert "Verify dispatched result PR checks" in names
    before["jobs"]["batch-run"]["steps"] = [
        step for step in before["jobs"]["batch-run"]["steps"] if step.get("name") != "Verify dispatched result PR checks"]
    for document in (after, before):
        (dispatch,) = [step for step in document["jobs"]["batch-run"]["steps"]
                       if step.get("name") == "Dispatch exact result PR validation"]
        dispatch.pop("id", None)
        dispatch["env"].pop("PR_NUMBER", None)
        dispatch["run"] = dispatch["run"].split("          # Handed to result-pr-checks")[0].split("# Handed to result-pr-checks")[0].rstrip("\n")
    assert after == before


@pytest.mark.parametrize("mutation", ["extra_byte", "already_restored"])
def test_the_result_pr_reconstruction_rejects_other_bytes(mutation):
    data = restore_pre_placement_guard_bytes((WORKFLOWS / "batch-run.yml").read_bytes())
    data = data + b"\n" if mutation == "extra_byte" else restore_pre_result_pr_job_bytes(data)
    with pytest.raises(AssertionError):
        restore_pre_result_pr_job_bytes(data)


def test_the_placement_guard_is_the_only_change_after_the_result_pr_job():
    current = restore_pre_comparison_input_projection_bytes((WORKFLOWS / "batch-run.yml").read_bytes())
    after = yaml.safe_load(current)
    before = yaml.safe_load(restore_pre_placement_guard_bytes(current))
    added = after[True]["workflow_dispatch"]["inputs"].pop("placement_attempt")
    assert {key: added[key] for key in ("required", "type", "default")} == {
        "required": False, "type": "number", "default": 1}
    reroll = after["jobs"].pop("placement-reroll")
    assert [step["name"] for step in reroll["steps"]] == ["Send the same dispatch again"]
    contract = after["jobs"]["inspect-mode"]["steps"][0]
    assert contract["env"].pop("PLACEMENT_ATTEMPT") == "${{ inputs.placement_attempt }}"
    check = '[[ "$PLACEMENT_ATTEMPT" =~ ^[1-9][0-9]?$ ]]\n(( 10#$PLACEMENT_ATTEMPT <= 20 ))\n'
    assert contract["run"].count(check) == 1
    contract["run"] = contract["run"].replace(check, "")
    batch = after["jobs"]["batch-run"]
    assert batch["outputs"].pop("placement") == "${{ steps.placement.outputs.verdict }}"
    guard = batch["steps"].pop(0)
    assert set(guard) == {"name", "id", "run"} and guard["id"] == "placement"
    guarded = [step for step in batch["steps"] if PLACEMENT_GUARDED in step.get("if", "")]
    assert [step["name"] for step in guarded] == [
        "Codex: preserve pre-call sandbox evidence", "Show summary", "Upload artifacts"]
    for step in guarded:
        step["if"] = step["if"].replace(PLACEMENT_GUARDED, "")
    (relay,) = [step for step in batch["steps"] if step.get("name") == "Retrigger relay run"]
    assert relay["run"].count(" \\\n  -f placement_attempt=1\n") == 1
    relay["run"] = relay["run"].replace(" \\\n  -f placement_attempt=1\n", "\n")
    assert after == before


@pytest.mark.parametrize("mutation", ["extra_byte", "already_restored"])
def test_the_placement_reconstruction_rejects_other_bytes(mutation):
    data = (WORKFLOWS / "batch-run.yml").read_bytes()
    data = data + b"\n" if mutation == "extra_byte" else restore_pre_placement_guard_bytes(data)
    with pytest.raises(AssertionError):
        restore_pre_placement_guard_bytes(data)


def test_the_ghcp_ahp_job_is_the_only_backend_change_after_the_runner_pins():
    current = (WORKFLOWS / "backend-tests.yml").read_bytes()
    after = yaml.safe_load(current)
    before = yaml.safe_load(restore_pre_ghcp_ahp_job_bytes(current))
    moved = after["jobs"].pop("ghcp-ahp-contracts")
    assert moved["runs-on"] == "ubuntu-24.04" and moved["timeout-minutes"] == 45
    assert [step["name"] for step in moved["steps"]][-1] == "Run GHCP AHP contracts"
    (core,) = [step for step in after["jobs"]["pytest"]["steps"] if step.get("name") == "Run tests"]
    new_ignores, old_ignores = GHCP_AHP_CORE_IGNORES
    assert core["run"].count(new_ignores) == 1
    core["run"] = core["run"].replace(new_ignores, old_ignores)
    assert after == before


@pytest.mark.parametrize("mutation", ["extra_byte", "already_restored", "core_ignores_dropped"])
def test_the_ghcp_ahp_job_reconstruction_rejects_other_bytes(mutation):
    data = (WORKFLOWS / "backend-tests.yml").read_bytes()
    if mutation == "extra_byte":
        data += b"\n"
    elif mutation == "already_restored":
        data = restore_pre_ghcp_ahp_job_bytes(data)
    else:
        new_ignores, old_ignores = GHCP_AHP_CORE_IGNORES
        data = data.replace(new_ignores.encode(), old_ignores.encode(), 1)
    with pytest.raises(AssertionError):
        restore_pre_ghcp_ahp_job_bytes(data)


@pytest.mark.parametrize("mutation", ["extra_byte", "already_restored"])
def test_the_comparison_input_reconstruction_rejects_other_bytes(mutation):
    data = (WORKFLOWS / "batch-run.yml").read_bytes()
    data = data + b"\n" if mutation == "extra_byte" else restore_pre_comparison_input_projection_bytes(data)
    with pytest.raises(AssertionError):
        restore_pre_comparison_input_projection_bytes(data)
