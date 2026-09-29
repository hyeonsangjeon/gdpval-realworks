# Latest task result

## PROJECT5-FIRST-LOCATOR-COMPATIBILITY

The diagnostic-only patch passed its one authorized offline selector at
`d4011844a0ee1efacd56304718f66c9bc038c32f`: 1 collected, 1 passed in 2.17s,
exit 0. The actual provider locator and failed constraint remain unknown.
This is not a proven provider compatibility fix and does not authorize another
dispatch or token request.

The new branch `b/codex-retention-first-locator-20260929` starts at exact base
`f3c86f50b63120446cf80ea4ff31bda5578241e9`, tree
`50bede9ae7f2ecb2f2741367d4faad8e2b36b5a4`. The leader reported all 10 checks
passing at prior reviewed HEAD `18f578b0923b128623f706d19f4167973ced66e3`,
[review 5353481985](https://github.com/hyeonsangjeon/gdpval-realworks/pull/702#pullrequestreview-5353481985).
That reviewed base does not approve this new adapter source. Old worktrees and
WIP were preserved.

### Live observation supplied by the leader

In [run 36582068074](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36582068074),
attempt 1, prepare job `109452538758` and approve job `109454515872` succeeded.
The exact owner environment review persisted once. At execution source
`f3c86f50b63120446cf80ea4ff31bda5578241e9`,
[execute job 109477606197](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36582068074/job/109477606197)
failed at step 11, “Authenticate the owner review and signed job origin before
Azure login or claim.” At 15:22:14 UTC, `--verify-approval` returned
`github_job_issuance_locator_refused`, exit 2, with `launch_authorized=false`
and `grading_launched=false`. Sandbox step 12, Azure login step 13 and
claim/run/reconcile step 14 were skipped.

The second actual preparation reproduced request SHA256
`79fd3920d2dc0bfb709892773aef63235341f37ad1fdbe69a9b8931a92136ebf`
and materialized-grader SHA256
`c391424e7ff45f375c6bb17135440aab85b29748fa0c52215805594a1517a320`.
These are leader-supplied observations, not local revalidation. This was a
pre-admission controller refusal, not a Codex task failure, zero score or paid
model result. The URL was not captured; no failing host, route or query
constraint can be inferred from the combined refusal.

### Evidence and closed diagnostic scope

One authoritative comparison established only the provider handoff:

- The [pinned GitHub runner](https://github.com/actions/runner/blob/5b3c03247427231abb553a8914910c3b4437e7b4/src/Runner.Worker/Handlers/ScriptHandler.cs#L314-L318)
  copies service `GenerateIdTokenUrl` into `ACTIONS_ID_TOKEN_REQUEST_URL`.
- The [pinned Actions toolkit](https://github.com/actions/toolkit/blob/85d7331b2bfbb4a135803df662f00069e9388f27/packages/core/src/oidc-utils.ts#L38-L43)
  reads that value and [appends an encoded audience](https://github.com/actions/toolkit/blob/85d7331b2bfbb4a135803df662f00069e9388f27/packages/core/src/oidc-utils.ts#L66-L72).
- The [official OIDC documentation](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-cloud-providers#using-custom-actions)
  describes the request environment variables, but does not establish this
  run's host, route or API query.

The mandatory bounded auth review approved diagnostics with conditions before
editing and found no concrete blocker in the resulting narrow delta. No
issuance request was made to inspect the locator.

`LocalTransport.github_job_token` retains its original parse/acceptance
predicate and exact `RetentionCIRefused` reason. Only that refusal can carry
optional diagnostics: fixed boolean checks, counts capped at 16 and at most
16 route tokens drawn from fixed keywords or redacted segment classes. Values
longer than 4096 receive a truncated summary. The CLI validates this closed
schema again before emission. No raw URL, host, job identifier, arbitrary
path/query value or credential is emitted. Extraction failure retains the
original denial; diagnostics cannot authorize transport.

### Offline validation

The command ran once from `batch-runner` with no private-input locator or
real credential in its isolated environment:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -p no:cacheprovider --tb=short -s \
  tests/test_codex_retention_ci_locator.py::test_retention_job_issuance_locator_diagnostics_are_closed
```

The result was 1 collected, 1 passed in 2.17s, exit 0. The log SHA256 is
`89196d543fb0f022a77c04d70cf04aebd0f1c36d3c5fb7882db3090a91b56d3d`.
The real parser and predicates exercised two previously accepted synthetic
forms and 23 refusal cases, not recovered provider URLs or 25 pytest passes.
All locator refusals occurred before opener/HTTP calls. Assertions checked
redaction, output bounds, the closed formatter, single-audience binding,
credential isolation, bounded reads/closure, the unchanged 302 refusal and
missing-credential refusal. Actual CLI source rejection also remained closed.
Only HTTP transport/responses were simulated. Fail-before-effects guards covered
preparation, staging, admission and execution; no private preparation,
signature/CAS integration, child, model or grade ran.

The genuine private result at `da0fb6bea28826c9287adaff95e6d4daf8996642`
remains separate: 1 passed in 295.37s, not skipped or repeated. Its original
real-versus-simulated boundaries, the earlier archive/wait/auth failures and
probe, the public CI failure, `a74413ae08d960c2f6fc97717abe53dcc01734ac`
(1 passed, 3 failed in 2.64s) and `d784da0d3da283ea7a396c05431ea85103513d4a`
(4 passed in 2.49s) remain distinct in the
[immutable prior handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/f3c86f50b63120446cf80ea4ff31bda5578241e9/tasks/LATEST_TASK_RESULT/README.md).
None was replayed or combined with this result.

### Source scope and remaining gates

Only `codex_retention_ci.py`, its new locator test and these two records differ
from the base. The adapter file SHA256 is
`ed5dbc4e7140ff5899c17b4f13bfc3a9871119bf7c994b43777b25ca333f3713`,
an actual new file identity, not source approval. All other tracked bytes,
including workflows, runtime, old registrations/pins, inputs/grading code,
shared guards and the original private integration/wait registry, are
unchanged. Static comparison preserves the existing acceptance predicate,
request path and downstream transport, signature/freshness, exclusive-job,
owner/source/request/job/boot, CAS/deadline and no-replay gates. The unrelated
changelog tail is preserved. Protected im-not-ai-en copyediting retains the
exact evidence and limitations.

New-head leader review and CI remain required. A later model-free observation
needs separate leader authorization and must use only the closed diagnostic;
the provider form and any compatibility correction remain unresolved. Real
execution still requires exact reviewed-source/cell/host/runtime/input/spend
approval, protected-job authority, serial CAS admission and verified owned
cleanup/terminal reconciliation. No token exchange, workflow rerun/dispatch,
environment approval, live CAS/HF/Azure/model/grade or paid operation occurred
in this task. No new launch authority is granted.
