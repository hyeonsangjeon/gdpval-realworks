# Latest task result

## PROJECT5-RUNTIME-SOURCE-INDEPENDENCE-0730

### Result and live evidence boundary

Corrected the eager external-source lookup on the existing #669 branch,
starting at `2b64888cb422d7a5a9d0df847a063b8a84002b95`. One targeted offline
selector passed **12 tests in 17.92s** at
`3790e4d370f25700ea7a18d46233575135e4191b`, exit 0. Main remains the supplied
`02a9682747e371d8675d1d0afb63155f3c3bce82`; no integration or reseal was made.

The leader reported comparison CI `35926036972`, job `107401241366`, on the
starting head: **6 failed, 939 passed in 1294.77s**. The eager `_root(TRUSTED_ROOT)`
call introduced an external-source dependency into every runtime Git command.
It preempted the six tests that deliberately make the old compiler unavailable
after preparation. The new selector restores their original provider-boundary
and post-validation HEAD-move assertions without editing those tests. The
initial **28 passed in 29.37s** at
`13032a864a115c0150f944e18aa277a1e212e541` remains separate evidence; it did not
establish runtime independence. Neither the 28-case family nor the 945-case
comparison run or full suite was repeated, and CI was not queried.

This repair does **not** establish the cause or side effects of the original
live grading setup failure, current HF branch state, or paid-execution readiness.

The leader supplied this observation from run `35920355055`, job
`107382432896`, on sealed source `02a9682747e371d8675d1d0afb63155f3c3bce82`:

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

### Runtime independence and historical ownership mechanism

The supplied runtime contract is unchanged: once preparation has completed,
runtime lineage uses only the selected checkout's reviewed HEAD/tree, config,
input and receipt bindings. It must not call the external-source verifier or
require the old compiler directory to exist. The corrected `_git` validates
the actual command repository with `_root`, then uses `Path(TRUSTED_ROOT)` only
for lexical comparison. On mismatch it performs no `stat`, `resolve`, open,
existence check or `_root` call against the unrelated path and adds no trust
allowance. On exact equality it validates that trusted path before adding the
single exact `safe.directory` option. There is no fallback trust on failure.

All six runtime test nodes and their assertions remain byte-for-byte unchanged.
The r1/r2 cases reach the expected synthetic `ProviderBoundary`; the two
`head_moves` cases reach the injected move after real bundle validation and
then refuse at the intended lineage gate. The directly affected new trust test
also refuses foreign ownership with existing, missing and aliased comparison
roots. The unsafe-path test now selects its unsafe path as the command
repository; its no-Git assertion remains. No missing external directory was
created and no runtime fixture was redirected to the original compiler.

The original ownership reproduction remains a separate historical observation:

The grading entry's source-check path is `grade-run.yml`'s containerized `pilot-live` job, then
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

Only exact lexical equality followed by trusted-path validation permits one
command-local `-c safe.directory=<canonical checkout>`; the same validated
command repository is passed to `-C`. Selected symlink/traversal roots and
wildcard/control-bearing trusted paths remain refused. No sibling, ancestor,
common-directory, wildcard, environment-selected or globally trusted path is
added. The ownership test switch exists only in test child processes, never
production configuration.

The fixed Git executable, stripped environment, global/system isolation,
hooks/fsmonitor/attributes protections, filter/include/partial-clone refusals,
no-lazy-transport policy, timeout and captured/redacted errors remain intact.
Source SHA, clean worktree, object type, tree paths/modes, manifest and pinned
blob checks are unchanged. The prior 28-case selector covered a synthetic
shallow clean commit without ancestor traversal; that case was not rerun.
No workflow or fetch-depth change was justified or made.
`require_source` still does not call `require_pinned_runtime`; no Python,
dependency or runtime-configuration change was made.

The only source-pin adjustment is the checkout helper's SHA256 in
`batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`:

- Previous #669 helper: `de40ae571d66635f121d2ca538f30114125c2fbf12e679db854c4ae46d6b9862`.
- Corrected helper: `0dbbab8911e1cba106745087aed471dca0a8b7f904058b4958df1e07864bb885`.

The genuine compiler validates that coupling. No fixed-grader source/hash
closure, model, prompt, rubric, judge policy, grading branch, inference-main
isolation, budget or 30-cell order changed.

### Unchanged CLI diagnostics and mutation limits

The source/root/receipt diagnostics introduced in the initial correction are
unchanged. Their original 28-case evidence is not a new CLI rerun. The real CLI
keeps refusal/exit 2 and these fixed local mappings:

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
initial selector included both an acknowledged fake creation and a lost fake response.
Neither case reconstructs the historical receipt or authorizes a live retry.

### Focused offline validation

Tested SHA: `3790e4d370f25700ea7a18d46233575135e4191b`.
Result: **12 passed in 17.92s**, exit 0. One invocation from `batch-runner/`
selected only the six reported runtime nodes and six directly affected
exact-trust/foreign-owner/unsafe-path cases. The private JUnit destination was
required to be absent before running:

```bash
timeout --signal=TERM --kill-after=5s 300s env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3.10 -m pytest -q -o addopts= -o junit_family=legacy -p no:cacheprovider --tb=short --junitxml=<private-test-evidence>/runtime-independence-results.xml \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-r1]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-r1]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-r2]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-r2]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[codex-head_moves]' \
  'tests/test_gpt54_runtime_checkout.py::test_runtime_checkout_lineage_precedes_both_providers[sandbox_v2-head_moves]' \
  tests/test_codex_budget_pilot_grading_source.py::test_real_git_global_trust_is_ignored_but_exact_command_trust_works \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[symlink]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[traversal]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[wildcard]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[newline]' \
  'tests/test_codex_budget_pilot_grading_source.py::test_unsafe_trusted_root_never_reaches_git[control]'
```

Compiler and source-pin checks, temporary Git, preparation/runtime lineage,
bundle/receipt validation, repeated HEAD checks and path/ownership refusals are
real. Input fixtures and provider boundaries are synthetic. The four r1/r2
passes mean the intended intercepted provider boundary was reached, not that
auth or a model was called. Both head-movement tests prove the deliberately
changed HEAD is refused after the real validation hook, not before it.
No HF, model, grader, branch mutation, full-suite, native-install or live test
ran. The JUnit report remains private; only the two completion records change
after this tested source snapshot.

### Review scope and remaining gates

The same extreme-reasoner returned **APPROVE-WITH-CONDITIONS** before this
bounded Git-trust correction, clarifying the existing decision: validate an
actual command repository, but do not validate an unrelated compiler path merely
to select a trust allowance or require it to exist at runtime.
That memo covers the design, not approval of the resulting head. No new audit
loop was started. English reporting/copyediting guidance keeps the initial
28-pass result, supplied six CI failures, new 12-pass selector and original
unresolved live refusal separate. No current-head approval is claimed.

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
