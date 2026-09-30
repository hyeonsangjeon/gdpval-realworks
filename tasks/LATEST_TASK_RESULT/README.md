# Latest task result

## PROJECT5-CLOSED-LOCATOR-OBSERVATION

The explicit observation-only CLI and workflow route passed one focused offline
selector at `fede773394b97690a1146a50c022972d47f16d49`: 1 collected, 1 passed
in 2.04s, exit 0. No real provider locator was observed. This remains a
diagnostic path, not a proven provider compatibility fix or launch authority.

The new branch `b/codex-retention-locator-observation-20260930` starts at exact
main `944c490ad2d1d172fffd18dc71a07caad6bb2425`, tree
`953ae15903d352fd8eafcb07b8a47fe7d5e815bc`. The leader supplied all 10 passing
checks at prior reviewed `dfab2edc3e9ce57bed492ffdabc586e31ed20ba4`,
[owner review 5360812285](https://github.com/hyeonsangjeon/gdpval-realworks/pull/703#pullrequestreview-5360812285).
That review does not approve this new source. The old PR703 worktree and
`wip/local-main-preserved-20260719` remain untouched.

### Observation and authority boundaries

The mandatory bounded CI/auth review approved the approach with conditions
before editing, then found no concrete blocker in the implemented delta.
No new permission or protected-environment policy was needed.

`--observe-locator` is mutually exclusive with preparation, approval verification
and execution. It rejects all input/request/output/host-state arguments before
reading the locator. Its cell and SHA syntax checks do not attest source or
job identity. It returns before source-verifier Git calls, plan compilation,
preparation, transport construction, CAS, clocks, children or grading.

The observer reads only the URL into memory, bounds parsing at 4096 characters
and reuses the existing closed diagnostic formatter/schema. The output contains
only fixed flags, capped counts and a redacted route skeleton inside the fixed
non-authorizing envelope. Its reason is
`github_job_issuance_locator_observation_only`, with `launch_authorized=false`
and `grading_launched=false`, including for a normally accepted locator shape.
No bearer, raw URL, host, identifier or arbitrary path/query value is emitted.

The existing workflow adds `observe_locator=false` by default. Observation
conflicts with both user-supplied `prepare` and `execute`, checked before
credentials. It retains exact source/main/attempt/cell checks, prepared-request
availability and the `grading` protected review before the existing execution
job. That job remains the only job with `id-token: write`; permissions,
environment placement, concurrency and normal execution gates are unchanged.
The observation command strips `ACTIONS_ID_TOKEN_REQUEST_TOKEN` and
`GITHUB_TOKEN` before Python starts. Approval verification, sandbox setup,
Azure login and claim/run/reconcile each independently require
`inputs.execute && !inputs.observe_locator`.

A future observation retains the existing preparation/input-transfer stages
in both preparation and execution jobs. Those stages install dependencies,
transfer original inputs and materialize request context; the whole workflow
is not network-free. Only the locator diagnostic step is network-free and
cannot launch another process. Protected observation review is not authenticated
execution approval. No token or signed job-origin verification is attempted
by observation; the normal execution path still requires both.

### Exact offline validation

From `batch-runner`, once in the existing isolated environment:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -p no:cacheprovider --tb=short -s \
  tests/test_codex_retention_ci_observation.py::test_retention_locator_observation_is_closed_and_separate
```

The result was 1 collected, 1 passed in 2.04s, exit 0. Log SHA256:
`bee414ab1ef4a1e3cbebf52534f3568f6e5412438e234365377adfaf7cabb0c8`.
The test parses the real workflow command and invokes the real CLI/formatter
with synthetic accepted, malformed, foreign, oversized and absent locators.
It checks redaction, credential non-access, refusal before effects, contradictory
arguments, normal-source rejection and every workflow exclusion. Workflow
routing is checked statically, not by dispatch. No external transport response
or validator verdict was substituted; transport and effect-capable calls were
guarded to fail. No private preparation, token, HTTP, child, model or grade ran.

The prior 2.17s local pass, malformed-URL CI failure and corrected 2.22s pass
remain separate in the [immutable prior handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/944c490ad2d1d172fffd18dc71a07caad6bb2425/tasks/LATEST_TASK_RESULT/README.md).
Its links preserve the earlier live pre-admission refusal, exact source/input
identities and genuine private 295.37s pass. None was replayed or combined
with this result; the actual provider locator remains unknown.

### Byte scope and remaining gates

Only the existing workflow, `codex_retention_ci.py`, the new observation test
and the two completion records differ from the base. Static comparison confirms
that the original authentication predicates, transport, normal CLI body and
live-step bodies remain unchanged. All other tracked bytes, including runtime,
registrations/pins, shared guards, inputs/grading code and prior tests, match
the base. The unrelated changelog tail is preserved. Actual file SHA256 values:

- Adapter: `153cb666df279ecf68ce9a86259812814a9247ac78b8aa523b2a3014292f2f37`.
- Workflow: `b1839f8df86649ab50fcc0c85bef8108e2035b7334f7b77676ed710f4cb4e933`.

These are new byte identities, not approval. New-head immutable review and CI
remain required, followed by separate leader authorization for one observation.
The following is the later dispatch form only; it was not run. The leader must
first bind the exact reviewed main/workflow SHA in
`RETENTION_OBSERVATION_REVIEWED_MAIN_SHA`:

```bash
gh workflow run codex-retention-first-cell.yml \
  --repo hyeonsangjeon/gdpval-realworks --ref main \
  -f reviewed_source_sha="${RETENTION_OBSERVATION_REVIEWED_MAIN_SHA:?leader-approved immutable main SHA required}" \
  -f cell_id=3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1 \
  -f observe_locator=true -f prepare=false -f execute=false
```

No workflow dispatch, token exchange, environment approval, live CAS/HF/OIDC/
Azure/model/grade or paid operation occurred. Live source/input/owner-review/
job-origin, spend, CAS/deadline, cleanup and no-replay gates remain in force.
Protected im-not-ai-en copyediting preserves these facts and limitations.
