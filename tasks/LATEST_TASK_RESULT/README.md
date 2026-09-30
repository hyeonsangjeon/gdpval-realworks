# Latest task result

## PROJECT5-RETENTION-INTAKE-EXISTING-CI-CREDENTIAL

The single focused offline invocation passed at
`a650e5ebb07c2902a3d06b519c351a891fe1fa69`: 2 collected, 2 passed in 2.40s,
exit 0, no skips. The existing first-cell workflow now has an explicit
`read_result` mode confined to its contents-read preparation job. This is
offline routing/parser evidence, not a CI dispatch, credential-access check,
successful retained-byte intake or grade. The earlier NAS refusal and consumed
producer success remain separate below.

### Source, review and fixed boundary

The new branch `b/codex-retention-ci-result-intake-20260930` starts from exact
reader/main `b3a2fb61c3e44bbdc58933ef1c79adcfb6f3fde7`, tree
`3f257f1d263512782a7eb4580476837f6c99edbd`. The leader supplied all 10 passing
checks at PR707 head `c787d5819eb52fa733bab4529d3a3c6dcbd9cb6a`,
[review 5366662713](https://github.com/hyeonsangjeon/gdpval-realworks/pull/707#pullrequestreview-5366662713).
That review covers the unchanged reader, not this new workflow delta.

A read-only extreme-reasoner CI/auth decision, `APPROVE-WITH-CONDITIONS`,
preceded workflow edits. Its conditions require a secret-free source/hash
preflight, the existing preparation-job HF secret only, fixed reader arguments,
private output capture, preserved failure exit status and exclusion from both
downstream jobs. The decision covers only this implementation, not dispatch or intake.

The workflow adds `read_result=false` and rejects a read combined with prepare,
observe or execute in the first source gate, before checkout or credentials.
Read-only mode skips the closed plan, historical-original transfer, serialization
and packet preparation. Approval and execution jobs explicitly exclude it, so
it cannot reach protected execution approval, token verification, sandbox setup,
Azure login, CAS/admission, a cell clock, model or grader. The same three jobs,
permissions, concurrency, protected environment and source/main/attempt/cell
gates remain. When `read_result=false`, existing mode bodies remain unchanged.

Before the read step receives its existing step-scoped `secrets.HF_TOKEN`, a
separate step requires clean checkout HEAD = reviewed source = dispatch SHA =
workflow SHA and checks both unchanged file SHA256 values:

- Reader: `df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196`.
- Terminal-verifier module: `8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c`.

The reader command removes `GITHUB_TOKEN`, `GH_TOKEN`, both Actions issuance
variables and `ACTIONS_RUNTIME_TOKEN` from its environment. The HF token stays
in the step environment, never argv. Existing offline defaults remain unchanged;
the reviewed HF session already scopes its authorized online reads.

A fresh mode-0700 parent under trusted `RUNNER_TEMP`, created with umask 077,
holds an absent payload child and separate receipt/stderr files. Owner and
no-symlink checks precede the read. The outer limit is 180 seconds; internal
120-second transfer, 30-second request and object/count/128 MiB aggregate limits
are unchanged. Only the reader's safe stdout receipt reaches logs/summary;
stderr and partial payloads remain private. Refusal/timeout exits are preserved,
with no upload, cleanup, reuse or retry. This relies on the isolated trusted
runner, not resistance to hostile same-owner namespace replacement. A future
workflow would use network for checkout/setup and authorized HF reads; it is
model-free, not network-free.

The new workflow SHA256 is
`877e3c67e61fdbb4af3c0bbab55a8c8584a44f4480ce0ac7025595154a4fafc3`.
Reader, terminal verifier, runtime, grader, original 30 registrations, registered
8-cell study, pins, budget and model settings remain byte-identical to the base.
The two tests are the new read-route contract and the directly coupled exact
observation/workflow-shape assertions. The shared offline fixture and existing
test guards are unchanged.

### One offline validation

Static AST/import/guard-owner checks passed before pytest. The three changed
Bash snippets passed syntax-only checks. Removing only the declared new routing
fields/steps from the parsed workflow reproduced the base workflow exactly.
The tested commit was clean; only completion records changed after this run.

From `batch-runner`, the existing Python 3.10.12 environment ran once:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -p no:cacheprovider --tb=short -s \
  tests/test_codex_retention_ci_read_result.py::test_retention_result_read_workflow_is_fixed_and_model_free \
  tests/test_codex_retention_ci_observation.py::test_retention_locator_observation_is_closed_and_separate
```

Result: 2 collected, 2 passed in 2.40s, exit 0, no skips. Log SHA256:
`a769e460558533687bcac159fe4424d82810c9f85ab55e3f1b0523f6ad377d13`.
All 16 mode combinations were checked against parsed workflow/source-gate
expressions, including read exclusion despite a spuriously nonempty request
output. Exact permissions, source/hash preflight, fixed argv, credential removal,
private paths and receipt/exit handling were checked statically. The unchanged
reader's real parser and byte/registration bindings reached its real
`explicit_hf_token_required` refusal with an empty test environment, before
transport or clock entry. The existing observation selector retained real
closed formatting and refusal checks with synthetic locators and no effects.
No successful remote intake was simulated or claimed. No credentials, private
originals, model/grade calls or live services were used. Neither the 8.03s payload
selector nor the 295.37s private integration was rerun.

### Separate preserved observations

The prior NAS invocation at the reviewed base ran once from
`2026-09-30T13:51:08Z` to `2026-09-30T13:51:10Z`. It returned
`explicit_hf_token_required`, exit 2, with 210-byte stdout and empty stderr;
the outer timeout did not fire. Receipt SHA256:
`7fe9d0cc4db0538879ebbe0f97b1a6d4ee8b98bdc7d2ef99a3a607e2d31191d5`.
Its fields were `intake_verified=false`, `launch_authorized=false`,
`grading_launched=false`, `admission_attempted=false`, `grade=null`,
`invoice_complete=false` and `commands=[]`. This is an unsatisfied explicit-token
prerequisite, not invalid credentials, a remote 403, missing retained data or
failed inference. Token validity and remote access were not established.
No immutable terminal/claim/output revisions, result/intake
fingerprints, declared-file counts or retained accounting evidence were returned.
The NAS parent had mode 0700, its separate receipt mode 0600, and a local
directory lock was held through that invocation; parent identity checks passed.
No prior payload bytes or credentials were read in this implementation. The
original private parent, partial payload and receipt were not changed, deleted
or reused. Both uncommitted NAS records remain unchanged; these facts are folded
into this substantive handoff.

The producer remains the successful consumed cell at
`e355faf9a6212175a288e8473968915ffb2408d0`,
[run 36696961231, attempt 1](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36696961231/attempts/1),
[job 109837605787](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36696961231/job/109837605787).
The leader's receipt at `2026-09-30T10:58:12.8033229Z` reported `status=succeeded`,
`cleanup_confirmed=true`, `remote_terminal=acknowledged`, `grade=null`,
`grading_launched=false` and `invoice_complete=false`; the job and workflow
succeeded. The reader supports only cell
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1` and request
`ed8b51f6d80e641922013eba9e19d7d3e145d84ae15fb8d7d9509e643c975c68`.
Producer, later reader and historical observer identities remain distinct.
This produced outcome is not a score or independent retained-byte verification.

Prior offline evidence remains separate in the
[immutable PR707 record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/c787d5819eb52fa733bab4529d3a3c6dcbd9cb6a/tasks/LATEST_TASK_RESULT/README.md):

- `9c34db608209a084b61b18fdbeea067634028e36`: 1 collected, 1 failed in 2.75s,
  exit 1. Initial binding/refusal and valid synthetic intake checks completed;
  raw partial accounting hit `retention_accounting_mismatch` before later cases.
- `fdfb9b2757da9b164caf6985bd6155a48aaa6c0b`: 1 collected, 1 failed in 6.58s,
  exit 1. Projected partial accounting, empty-ledger, corruption and path checks
  completed; the omitted `ReferenceIntegrityError` stopped member post-refusal
  and subsequent marker/readback/fsync assertions.
- `e1206a704d649aac18d029670029def4c70fc18e`: 1 collected, 1 passed in 8.03s,
  exit 0, no skip. Real validators with synthetic retained records/transport
  completed the remaining publication and no-effect checks, not live intake.

### Remaining gates and future dispatch form

New-head immutable owner review and CI remain, followed by one separately
authorized CI read at an exact reviewed main/workflow SHA. The form below is
not a dispatch or permission to run it. `REVIEWED_MAIN_SHA` must equal that
later approved main HEAD and workflow source; the producer/request stay fixed
inside the reviewed reader and workflow.

```bash
gh workflow run codex-retention-first-cell.yml \
  --repo hyeonsangjeon/gdpval-realworks --ref main \
  -f reviewed_source_sha="$REVIEWED_MAIN_SHA" \
  -f cell_id=3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1 \
  -f read_result=true -f prepare=false -f observe_locator=false -f execute=false
```

A successful hash-bound intake receipt may support the separately directed
one-fixed-grade handoff; it grants neither grading nor execution authority.
Input/config/materialized-grader/source binding remains required for that grade.
No independent live retained-byte verification has completed. Missing or partial
accounting is not zero or an invoice; HTTP requests are not model-call counts.
No credential-store search, CI secret export, permission change, HF/OIDC/Azure/
model/grade call, dispatch, inference replay or successor cell occurred here.
Earlier worktrees, branches and `wip/local-main-preserved-20260719` are preserved.
The leader's unavailable M4 files were not updated.
