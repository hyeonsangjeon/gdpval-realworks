# Latest task result

## Task4 backend comparison-contract partition fix

Scope: fix PR #786's partition failure at baseline
`907a252483b74b841bd6987f7b25efe929a57e10`, only in the designated publication
worktree on `leader/task4-control-reader-20261023`.

The new `test_gpt54_time_budget_v2_task4_control_readout.py` made the comparison
inventory 13, but neither backend job list included it. Add it to
`comparison-contracts` and exclude it from core `pytest`; update the exact
inventory count, current workflow hash and historical reconstruction. The
partition and historical-baseline guards remain enforced. No reader code changed.

Verification: reproduced the exact `13 == 12` failure. Ran
`python3 -m pytest -m 'not integration' --tb=short -q -rs
tests/test_a_test_file_nobody_runs_is_not_a_test.py
tests/test_ghcp_vm_gate_contract.py tests/test_gpt54_*.py` in `batch-runner`:
**1592 passed, 1 failed, 74 errors** in 2011.31s. All unresolved nodes were
blocked by missing `openai_codex`; after installing the repository-pinned
`openai-codex==0.147.0` and CLI binary into a worktree-local test directory,
the same selection with `--lf --lfnf=none` and that directory on `PYTHONPATH`
reported **75 passed, 239 deselected** in 39.39s. Thus all **1667 selected
nodes** passed across the runs. The exact originally failing node also passed
separately after dependency restoration (**1 passed**, 31.70s).

Reviewed head SHA: none supplied for this CI-only fix; baseline above is not
claimed as review approval. The required workflow-review agent could not start
because its configured model was unavailable; no agent approval is claimed.
Remaining work: new PR CI and owner review. No merge, experiment run, workflow
dispatch, model/grader call or private Task4 read was performed. Records stop
at pre-merge facts.
