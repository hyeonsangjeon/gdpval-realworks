# Latest task result

## Task4 time-budget guard alignment

Scope: repair the two stale guards reported in PR #786's backend CI run
`40015357524`, job `120625917401`, after baseline
`88d757fd9ed3b3f23dac700246b13d64f901712c`. Work is confined to the designated
`task4-control-reader-publish-20261023` worktree on
`leader/task4-control-reader-20261023`.

Update only the owned-host comparison inventory expectation from 12 to 13 and
the retention guard's exact workflow hash (after removing its one retention
option) to
`58ecfccbacc6a887780b821692d07b8e03bf6eac120b703ffdf1d9bab600a3a4`.
Uniqueness, exact reconstruction, retention behavior and all other assertions
remain intact. No workflow or production code changed.

Verification: searched tests for the old hash, `== 12` and backend workflow
hash references. In `batch-runner`, ran `python3 -m pytest -m "not integration"
-q tests/test_time_budget_owned_host_ci.py
tests/test_time_budget_tmp_path_retention.py
tests/test_a_test_file_nobody_runs_is_not_a_test.py
tests/test_ghcp_vm_gate_contract.py`: **172 passed in 42.21s**.
The first run reported **171 passed, 1 failed** because the partition guard's
child collection lacked `openai_codex`. The passing rerun used temporary
worktree-local installations of repository-pinned `openai-codex==0.147.0`
and `openai-codex-cli-bin==0.147.0` on `PYTHONPATH`.

Reviewed head SHA: no review gate or reviewed head supplied for this test-only
follow-up; the baseline is not review approval.
Remaining work: new PR CI and owner review. No merge, manual workflow dispatch,
experiment run, model/grader call or private Task4 read was performed. Records
stop at pre-merge facts.
