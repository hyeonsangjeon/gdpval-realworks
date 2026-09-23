# Latest task result

## PROJECT5-GRADING-SOURCE-REFUSAL-0629

### Result and live evidence boundary

Implemented a narrow source-preflight correction on a new branch from exact
main `02a9682747e371d8675d1d0afb63155f3c3bce82`. One focused offline selector
passed **28 tests in 29.37s** at
`13032a864a115c0150f944e18aa277a1e212e541`, exit 0. The correction addresses a
confirmed local Git ownership/trust incompatibility and adds closed error
stages. It does **not** establish the cause or side effects of the historical
live failure, current HF branch state, or readiness for paid execution.

The leader supplied this observation from run `35920355055`, job
`107382432896`, on the sealed source above:

- Plan succeeded at `21:09:59.868579 UTC`.
- Setup refused at `21:10:01.622976 UTC`, exit 2, with these reported fields:

  ```json
  {"outcome":"refused","reason":"grading_contract_refused","http_status":null,"grade_success":false,"inference_requested":false,"automatic_retry":false}
  ```

- Judge and grade publication were skipped. The generic refusal does not show
  which contract stage failed or whether a branch was created before receipt
  persistence failed. This task did not read, retry or reconcile that operation.

The grading-branch setup reservation remains **UNRESOLVED/CONSUMED**. The
leader's execution seal remains **BLOCKED_PRE_EXECUTION**, not replaced by this
branch or its tested SHA. Dataset setup `35881609256` and private bootstrap
`bfc7ae01ed14490817ceb7cb406adcb9bb95f557` remain valid and consumed; neither
setup may be replayed.

### Confirmed local mechanism and scoped correction

The reached path is `grade-run.yml`'s containerized `pilot-live` job, then
`codex_budget_pilot_grading.main`, `LocalTransport.require_source`, and
`gpt54_disposable_checkout._repository` / `_git`. The workflow installs an exact
global `safe.directory` entry. The helper deliberately uses
`GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_SYSTEM=/dev/null`, so that entry
cannot affect its commands.

A bounded pre-edit reproduction used real Git 2.34.1, synthetic temporary
repositories and Git's process-local `GIT_TEST_ASSUME_DIFFERENT_OWNER=1` switch.
It changed no filesystem ownership or real-repository permissions. Ordinary
Git with the exact isolated global allowance returned 0; the original hardened
helper returned 128 with a locally detected dubious-ownership refusal. An exact
command-local allowance returned 0; a foreign allowance remained refused at
128. The reproduction command exited 0. Raw stderr and temporary paths remain
private. This proves the compatibility mechanism locally, not that it was the
unreported stage in job `107382432896`.

`_git` now validates both the requested repository and code-defined
`TRUSTED_ROOT` with the existing root/path checks. Only equality permits one
command-local `-c safe.directory=<canonical checkout>`; the same canonical
repository is passed to `-C`. Symlink/traversal roots and wildcard/control-bearing
trusted paths are refused. No sibling, ancestor, common-directory, wildcard,
environment-selected or globally trusted path is added. The ownership test
switch exists only in test child processes, never production configuration.

The fixed Git executable, stripped environment, global/system isolation,
hooks/fsmonitor/attributes protections, filter/include/partial-clone refusals,
no-lazy-transport policy, timeout and captured/redacted errors remain intact.
Source SHA, clean worktree, object type, tree paths/modes, manifest and pinned
blob checks are unchanged. A synthetic shallow clean commit passes without
ancestor traversal. No workflow or fetch-depth change was justified or made.
`require_source` still does not call `require_pinned_runtime`; no Python,
dependency or runtime change was made.

The only source-pin adjustment is the checkout helper's SHA256 in
`batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`:

- Previous: `aaa7de1c54df7afc9f3e5b1bfadc831f6658a50d0895491359ff3e5ada11b24b`.
- Corrected helper: `de40ae571d66635f121d2ca538f30114125c2fbf12e679db854c4ae46d6b9862`.

The genuine compiler validates that coupling. No fixed-grader source/hash
closure, model, prompt, rubric, judge policy, grading branch, inference-main
isolation, budget or 30-cell order changed.

### Closed CLI diagnostics and mutation limits

The real CLI keeps refusal/exit 2 and emits only these new fixed local mappings:

| Boundary | `stage` | `reason` | `remote_mutation_possible` |
|---|---|---|---|
| Compile and validate reviewed source | `source_preflight` | `grading_source_preflight_refused` | `false` |
| Prepare private setup root and enter its lock | `branch_root` | `grading_root_refused` | `false` |
| Persist the final private setup receipt | `branch_receipt` | `grading_receipt_refused` | `true` |

For these local failures, HTTP status is null; grade success, inference request
and automatic retry remain false. The mutation flag describes **this invocation
only**: false does not prove an absent branch or unused reservation from an
earlier invocation; true is conservative, not proof of a mutation. Unrelated
outer failures retain their existing typed reason/HTTP context, or generic
`grading_contract_refused`, with stage and mutation possibility null. No raw Git
stderr, path, config value, token or arbitrary exception text is emitted.

Root/lock failure leaves any partial local state intact. Receipt failure after
a fake branch mutation preserves the real private local reservation and refuses
another invocation against that root before another fake session/mutation. The
test includes both an acknowledged fake creation and a lost fake response.
Neither case reconstructs the historical receipt or authorizes a live retry.

### Focused offline validation

Tested SHA: `13032a864a115c0150f944e18aa277a1e212e541`.
Selector: `batch-runner/tests/test_codex_budget_pilot_grading_source.py`.
Result: **28 passed in 29.37s**, exit 0. One invocation ran from `batch-runner/`:

```bash
timeout --signal=TERM --kill-after=5s 240s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -o junit_family=legacy -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/regression-results.xml tests/test_codex_budget_pilot_grading_source.py
```

The source compiler, preflight, object/blob/pin checks, real Git ownership
refusals, private file writes, locks and no-clobber checks are genuine. Tests
cover ordinary/shallow clean source; foreign trust, dirty/untracked source,
wrong commit, pin/manifest drift, tracked symlink and unsafe configuration/path
refusals; no-network plan; and exact closed CLI source/root/receipt/error output.
HF/token/runtime/inference/judge boundaries are blocked. Branch operations are
in-memory fakes. No old family, full suite, native-install check or live operation
ran. The JUnit report and reproduction diagnostics remain private; only the two
completion records change after this tested source snapshot.

### Review scope and remaining gates

The existing extreme-reasoner returned **APPROVE-WITH-CONDITIONS** before the
security/architecture behavior change. That decision covers the bounded design,
not approval of the resulting head. No new audit loop was started. English
reporting/copyediting guidance keeps the supplied CI refusal, locally reproduced
mechanism, synthetic branch tests and unresolved remote state separate.

Prior #668 review `5296511923` and all ten passing checks apply to
`d97d250cfc1a6f2f6ad485d9bb44a8fa58d79227`, not this correction. Historical
results remain **64 passed in 47.42s** at
`f352eb87af8c794a677629229884f37061342535` and **5 passed in 3.20s** at
`f210a789e2a0afa889fd5261858fcbc0b402327f`; neither selector was repeated.
Accepted-input run `35847871634` and consumed dataset setup `35881609256` remain
separate observations, not paid-cell results or grades. The prior local native
atomic-install `EINVAL` refusal and successful rename-test-double cases do not
establish actual CI grading-host capability.

Remaining: leader review/final exact-head CI; separately authorized, checked
read-only reconciliation of the unresolved grading branch; an explicit source
reseal and live gates; actual grading-host native installation; the first paid
cell with retained output, one fixed grade, and all 30 recorded outcomes. There
was no real HF credential/API/read/write, branch creation, setup replay, payload
transfer, workflow dispatch, grant change, Azure/model/grader operation or CI
query/wait in this task. The original reservation and blocked seal are unchanged.
