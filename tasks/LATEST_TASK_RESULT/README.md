# Latest task result

## GHCP Sol gate: pinned-SDK local CI partition verification

Scope: FREE-only validation of branch
`leader/ghcp-sol-gate-actions-20261024` at tested source HEAD
`4e61a4bb20de67995d0684e051f1d3416eacea69`, in
`/ai-work/copilot/_tmp_worktrees/ghcp-sol-gate-actions-20261024`.
No production code, workflow, assertion, marker or partition selection changed.
Only this result record and the corresponding changelog entry were updated.

### Concrete outcome

- Installed repository pins **openai-codex 0.147.0** and
  **openai-codex-cli-bin 0.147.0** in
  `/ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv`.
  Python is **3.10.12**, pytest **9.1.1**;
  `include-system-site-packages = false`. System Python and the user checkout
  were not modified. Missing system `ensurepip` was handled by running a
  downloaded pip 25.3 wheel against the venv, not by installing system packages.
  Core/renderer test dependencies were installed there; this was not a complete
  installation of every optional dependency in `requirements.txt`.
- Previously unverified partition check: **1 passed in 22.43s**.
  The unchanged backend workflow hash and exactly-once partition guards pass.
- Full backend `pytest` job's core test command:
  **3 failed, 13,373 passed, 57 skipped, 46 deselected, 1 warning in 3250.97s**.
  The exact workflow command, including every ignore and the integration marker
  filter, was retained. Local elapsed time exceeded the hosted job's 45-minute
  ceiling; this host does not establish hosted timing.
- The same job's repo-root script test command:
  **186 passed in 46.50s**.
- All three failures reproduced at exact branch point
  `6efe99cbd40bb839037e7a20711a734e0a4ce002`, with the same venv and inherited
  environment: **3 failed in 5.95s**. The failing tests and audio implementations
  have no diff against that branch point. No branch-caused failure was found;
  no baseline assertion or implementation was changed.

| Failing node (under `batch-runner/tests/`) | Same failure on HEAD and branch point |
|---|---|
| `test_codex_retention_budget_report.py::test_consolidated_budget_report_preserves_all_eight_observations` | Environment-presence assertion rejects inherited `GH_TOKEN`; no authentication was performed. |
| `test_gold_ceiling_contract.py::test_spec_accounts_for_the_archive_answer_the_run_could_not_read` | `KeyError: 'sample_rate'`; absent PyAV makes the probe return backend `none`. |
| `test_perception_audio.py::test_the_clip_is_re_encoded_to_the_rate_and_layout_that_is_sent` | `48000 != 16000`; absent PyAV makes the existing fallback retain raw audio. |

The baseline failures were left unchanged as requested. Missing PyAV also
accounts for several reported skips. Other skips include unavailable Ruby,
LibreOffice, dataset/private handoffs, Docker/sandbox and kernel capabilities.
No skipped private-input test was enabled or supplied with downloaded inputs.

### Exact verification commands

The venv's `bin` directory was prepended to `PATH` for all commands below.
The workflow's `pytest.ini` integration-deselection grep passed before the
full core command. Commands ran from the tested worktree unless noted.

```bash
cd batch-runner
python -m pytest -m "not integration" --tb=short -q -rs tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts
python -m pytest -m "not integration" --tb=short -q -rs --ignore=tests/test_gpt54_codex_grading_input.py --ignore=tests/test_gpt54_codex_input_capture.py --ignore=tests/test_gpt54_comparison_preflight.py --ignore=tests/test_gpt54_disposable_checkout.py --ignore=tests/test_gpt54_prepared_input_attestation.py --ignore=tests/test_gpt54_run_config_bundle.py --ignore=tests/test_gpt54_run_input_bundle.py --ignore=tests/test_gpt54_runtime_checkout.py --ignore=tests/test_gpt54_time_budget_comparison.py --ignore=tests/test_gpt54_v2_grading_input.py --ignore=tests/test_gpt54_v2_input_capture.py --ignore=tests/test_gpt54_workflow_gate.py --ignore=tests/test_gpt56_evidence_preflight_gate.py --ignore=tests/test_gpt56_foundry_evidence_intake.py --ignore=tests/test_gpt56_pilot_config_bundle.py --ignore=tests/test_gpt56_pilot_deployment_binding.py --ignore=tests/test_gpt56_pilot_identity_plan.py --ignore=tests/test_gpt56_pilot_input_bundle.py --ignore=tests/test_gpt56_pilot_input_capture.py --ignore=tests/test_gpt56_pilot_wire_receipt.py --ignore=tests/test_gpt56_sol_codex_pilot_preflight.py --ignore-glob='tests/test_codex_budget_pilot*.py' --ignore-glob='tests/test_time_budget_*.py'
cd ..
python -m pytest scripts/__tests__ -m "not integration" --tb=short -q -rs
```

Baseline-only reproduction, from the temporary detached branch-point
worktree's `batch-runner` directory (removed after verification):

```bash
python -m pytest -m "not integration" --tb=line -q -rs tests/test_codex_retention_budget_report.py::test_consolidated_budget_report_preserves_all_eight_observations tests/test_gold_ceiling_contract.py::test_spec_accounts_for_the_archive_answer_the_run_could_not_read tests/test_perception_audio.py::test_the_clip_is_re_encoded_to_the_rate_and_layout_that_is_sent
```

Logs remain outside the checkout under `/ai-work/copilot/_tmp/`, mode **0600**.
Environment-representation traceback lines were removed before hashing to
avoid retaining inherited credential values; failure messages/counts remain.

| Log | SHA-256 |
|---|---|
| `ghcp-sol-gate-partition-check.log` | `822c7ec067b84b38dc48a2e4b5237db1a04cdfb5223078688d3e9057472a991e` |
| `ghcp-sol-gate-ci-core.log` | `bdb82f30c8ac1ddaa7f7563b13a5ae1b34f5841d46ad1089a5bfd996b6777f96` |
| `ghcp-sol-gate-ci-scripts.log` | `1845bd7478109455bd5cec85dd8d070f46b9ed75ab963deff333ca699618f162` |
| `ghcp-sol-gate-ci-baseline.log` | `9beb579aef1f651ca36526b0bb09f94afbecd6b57c0c3c704a5a5f0f925f76fd` |

### Evidence boundary and remaining work

**Not locally green for every touched CI job.** The requested core partition
ran with three baseline/environment failures and host-dependent skips; the
other backend partitions and Pages validation job were not run in this step.
The SDK-dependent partition coverage gap is resolved, not the broader CI gate.
An initial attempt in the fresh venv failed collection for missing
`jsonschema`; installing declared core/renderer dependencies resolved it
before the reported partition and full-suite runs.

Prior evidence remains separate: **313 targeted checks** and **5/5 capture-shell
rehearsals** passed during the previous review, with workflow inventory **29 to
30** and no count/hash guard weakening. That review directly examined source
`f27cde892e144a242260e47a1c2b2e22e07abcf8` plus its corrective diff;
this step tests `4e61a4bb20de67995d0684e051f1d3416eacea69` and does not
claim a new specialist review or exact-head launch approval.

No model/GHCP call, GHCP authentication, private input download, push, PR,
workflow dispatch, paid execution or remote project change was performed.
Tests used synthetic/local fixtures, including local loopback SDK stubs.
Existing specialist-review and paid-run authorization blockers remain;
full CI and its required host capabilities still need separate evidence.
