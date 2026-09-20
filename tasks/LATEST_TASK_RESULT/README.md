# Latest substantive task result

## PROJECT5-GPT56-PILOT-DISPATCH-GRADING-IDENTITY

The active Foundry GPT-5.6 Sol Codex pilot now has a canonical offline dispatch
and grading identity compiler, publisher and verifier. Explicit preflight
consumption of a verified bundle can satisfy exactly
`pilot_dispatch_and_grading_identity_not_wired`. This is a local contract
check, not dispatch, grading, external identity approval or launch authority.
The sole targeted selector reported `115 passed in 22.87s`, exit 0.

Both `launch_allowed` and `full_220_allowed` stay false, as do the manifest's
`launch_enabled` and `full_220_enabled`. No real evidence was acquired and no
pilot was deployed or executed.

### Scope and outcome

`gpt56_pilot_identity_plan.py` exposes `compile_pilot_identity`,
`publish_pilot_identity` and `verify_pilot_identity`, plus a small offline CLI.
The immutable canonical plan binds the exact
`gpt56_sol_foundry_codex_pilot5_v1` run, `codex_foundry` condition, Azure route,
Sol-not-Fast, Max and the 1M context request. Dispatch and grading carry the same
five task IDs in the same order, prompt hashes and per-task reference paths and
hashes. The document also binds the dataset revision/parquet hash, source-pin
map, one repeat and one logical attempt. Fresh sessions, no relay or resume,
no automatic escalation, and existing timeout, retry, cap, result and receipt
declarations are preserved.
Native caps remain null; the three infrastructure retries are after the initial
attempt, not a three-attempt total.

The grader identity uses the actual step8 config validator, source-hash closure,
ordered-task digest and prompt-version helper without constructing a grader.
It records the template path/raw digest, historical grader source SHA, current
template-source hash, rubric revision, actual tool prompt/version, judge
model/effort, grade schema/version and receipt contract. The exp035 template's
historical 220-task `rerun_identity` is not copied or modified. The pilot scope
has one pass per task, null future inference repository/revision,
`reuse_baseline_rerun_identity: false` and `runnable_config: false`. No runnable
experiment/grading config, argv or launch command is emitted.

Optional evidence linkage calls the real `verify_foundry_evidence`. It includes
only the ready-bundle SHA256, caller-reviewed source SHA and sealed intake
evaluation time. Each verification still uses the caller's explicit current UTC
`as_of` for freshness. No-evidence linkage stays null; linked plans cannot
downgrade to null. Raw claims, resource identities and local host paths are not
copied into the plan or report.

The publisher verifies inputs before reserving an absent destination outside
the source/evidence trees. It reuses held-parent and atomic no-clobber primitives
to publish a sibling reservation, `foundry-pilot-identity-plan.json`, then
`foundry-pilot-identity-ready.json` last. It rechecks current sources, optional
evidence, plan bytes and reservation before ready publication. Verification
recompiles the recipes and requires all three canonical byte sequences to match.
Links, traversal, drift, extra members, collisions and partial reuse are refused.
Failures retain their reservation/partial tree; nothing is automatically deleted
or overwritten.

Preflight activation is explicit through `identity_bundle` or
`--identity-bundle`. Absent/null input keeps the existing plan-only and
evidence-only paths. A verified identity alone clears exactly one blocker and
leaves eight. With both evidence and identity gates accepted, three remain:

- `live_identity_and_input_bytes_unverified`
- `native_sandbox_and_result_bundle_host_unverified`
- `actual_pilot_deployment_not_prepared`

Identity failure keeps its blocker, including late report-construction errors.
Independently verified evidence can still satisfy its own five requirements.
Reports add only the plan digest, approved evidence linkage, closed blocker
transition and `offline_dispatch_grading_identity` boundary. CLI refusals are
static and do not echo untrusted values. The preflight still exits 2.

The active manifest now pins 37 sources. The newly sealed plan has a new digest;
previously sealed evidence is stale and has no compatibility exception. The
no-bundle byte-compatibility check applies to the same active plan, not an
obsolete digest. The fixed task cohort, model, effort, context request, grader
template, runtime defaults and historical Copilot contract are unchanged.

### Immutable base and review boundary

The clean development worktree started at immutable main
`ed6c64f0afb90b0b3a6a9e4719e44184384296ec` on branch
`b/gpt56-pilot-dispatch-grading-identity-20260920`. The preserved checkout
`wip/local-main-preserved-20260719` was not used for work or edited.

Reviewed implementation HEAD: `0e472bd021bdc868819fc51ac3e0edc5e3a17a4c`.
`first-reviewer` returned APPROVE with no BLOCK, MAJOR or MINOR findings and no
second-review escalation. It confirmed the compiler/preflight Git-object hashes
match the YAML pins. This approval covers the seven-file code/config/test/spec
diff, not a live run or future CI result. This completion record and
`CHANGELOG.md` follow validation and are outside that implementation boundary.
No implementation or test correction followed the passing selector.

The existing Git author and committer,
`hyeonsangjeon <wingnut0310@gmail.com>`, were preserved without changing Git
configuration. No attribution trailers, hook bypass, history rewrite, forced
push or forbidden Git cleanup was used.

### Exact validation evidence

Exactly one targeted pytest invocation ran:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt56_pilot_identity_plan.py
```

It collected 115 cases and reported `115 passed in 22.87s`, exit 0, with Python
`3.10.12` and pytest `9.1.1`. No test was removed, skipped or marked xfail.
The #631 and #632 selectors were not rerun. No broad/full suite or manual
workflow was run.

Coverage includes canonical plan/marker/reservation bytes; exact five-task
dispatch/grading equality; Sol/Max/1M and fixed controls; the real step8
validator/source hash; absent/null compatibility; actual evidence verification
and later-time linkage; closed blocker transitions; contract/task/grader/source
drift; missing/extra/noncanonical/link/path/collision cases; forged matching
markers; partial reuse; write failures; held-parent replacement; drift before
ready publication; static refusals and false launch flags. Transient catalog
and same-version prompt mutations are refused even when original bytes are
restored. Late report failures cannot remove the identity blocker.

Module-scoped seeds share only immutable bytes. Every case receives fresh
single-link files, and a regression confirms mutations cannot reach another
case or seed. No validator verdict is cached. The real validators and source
hash helpers still read current files; only YAML parsing is cached by exact
bytes with defensive copies. Fixtures prohibit subprocess, network, provider
auth, model/client/grader construction and the grader entrypoint.

`git diff --check` and `git diff --cached --check` passed before the
implementation commit. This is offline unit evidence, not a workflow, Azure
capability, actual input consumption or paid-run result. Automatic CI remains
separate evidence.

### Changed files

- `batch-runner/gpt56_pilot_identity_plan.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/tests/test_gpt56_pilot_identity_plan.py`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/tests/test_gpt56_foundry_evidence_intake.py`
- `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The two older test files only update the exact source count from 30 to 37.
Their selectors were not run.

### Skills and roles

The full supplied/filesystem skill catalog and repository agent catalog were
inspected once. `experiment-design` was applied before planning or config edits.
It kept this intervention limited to offline identity, preserved all experiment
variables and distinguished synthetic fixtures from observed Foundry behavior.

`llm-systems-engineer` provided read-only design and implementation audits.
`grading-engineer` checked the existing step8/grader contract after the
consolidated grading specification and stable baseline were read. Its scope was
read-only; no production grader behavior changed. The audits identified consumed
catalog/prompt snapshots that needed direct pin checks and a late report-failure
ordering issue. Both were fixed before the sole selector, with regressions.
`first-reviewer` supplied the separate immutable review boundary above.

`im-not-ai-en` was applied to the English specification, changelog, completion
record and PR wording, preserving hashes, commands, counts and evidence limits.
UI/animation skills do not apply to this backend contract. `extreme-reasoner`
does not apply because no workflow, `core/qa.py` or HF upload file changed.

### Evidence boundary and remaining work

This unit closes only offline dispatch/grading artifact identity. A verified
plan does not authenticate external Foundry evidence, prove its historical
grader Git source, supply inference publication identity or consumed input/wire
bytes, or authorize a launch. The current template-source hash is not a future
materialized grader/runtime identity.

Remaining work includes actual Foundry evidence acquisition and independent
review; live inference identity and input/wire binding; runtime/grader config
materialization; native sandbox/result-bundle hosting; actual pilot deployment
and execution; runtime enforcement of native caps; and usage/tariff receipt
integration. No evidence has been accepted outside synthetic fixtures in this
task. The nine default blockers remain unless callers explicitly supply verified
bundles, and both launch flags always remain false.

No Azure/API/CLI, credential/OIDC, deployment, provider/model/client, inference,
grading, download, workflow dispatch or paid execution occurred. Production
runtime/grader defaults, workflows, `core/qa.py`, HF upload and historical
ledger/evidence bytes were not changed. Project updates and merge decisions
remain with the leader. This record stops at pre-merge facts and contains no
carrying-PR merge SHA, time or state.
