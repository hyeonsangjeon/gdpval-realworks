# Latest task result

## PROJECT5-RETENTION-CANONICAL-ENTRYPOINT

The script footer now delegates to canonical `codex_retention_ci.main`, keeping
the CLI, controller dispatch and authority classes in one module namespace.
At `2833511e5a00a88ea442e85968c3dc742e8730a5`, the single offline regression
reported 1 collected, 1 passed in 2.13s, exit 0. This verifies entrypoint and
refusal behavior, not private preparation, live authentication or admission.

Branch `b/codex-retention-canonical-entrypoint-20260930` starts at exact main
`cea5fae1d1c975cfda079263cb552dad7ef46bed`, tree
`6443916ea56431b734a0c8c3e363956864c29303`. The leader supplied all 10 passing
checks at PR705 head `8d352b0585d1e82e2ecfa37db9cd9a7fa9a35a21`,
[review 5362287830](https://github.com/hyeonsangjeon/gdpval-realworks/pull/705#pullrequestreview-5362287830).
That review does not approve this new source. Earlier branches/worktrees and
`wip/local-main-preserved-20260719` remain untouched.

### Supplied live evidence and source trace

The leader read [run 36681464982, attempt 1](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36681464982/attempts/1),
[execution job 109786614084](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36681464982/job/109786614084).
At `2026-09-30T07:36:23.5257322Z`, preparation repeated the same request SHA256
`0d29d245677ce2f7900aa888d595c0eddbdab29ee6c174846be8dca77e62af0c`
and materialized-grader SHA256
`c391424e7ff45f375c6bb17135440aab85b29748fa0c52215805594a1517a320`.
The exact owner approval persisted once, deployment `6753601005`;
[approval job 109778536686](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36681464982/job/109778536686)
succeeded. These are supplied run observations, not new local materialization.

Step 12 signed approval/job-origin verification succeeded at
`2026-09-30T07:36:31.8798539Z` with `approval_verified=true` and
`admission_attempted=false`. Sandbox 13 and Azure login 14 succeeded. Step 15
failed at `2026-09-30T07:36:55.5792115Z`, exit 2, with
`retention_ci_verification_refused:RetentionCIRefused`,
`launch_authorized=false` and `grading_launched=false`. No model result or
grade exists from this failure; it is not poor model performance or zero.
The run was not re-investigated or replayed. These facts are preserved here;
the leader's unavailable local M4 volume was not accessed or updated.

The workflow invokes `python3 batch-runner/codex_retention_ci.py`. Previously,
that script's `main` constructed an `__main__.ExecutionGrantRequest`; controller
dispatch imported canonical `codex_retention_ci.execute`. Its exact grant-type
check rejects the distinct script class before canonical request/transport/CAS.
The canonical `RetentionCIRefused` is also foreign to the old script formatter,
which emits the observed generic category. This concrete source trace is
consistent with the supplied failure; it does not reopen locator authentication.

### Change and offline validation

The mandatory bounded auth/extreme-reasoner decision approved footer-only
delegation before editing and confirmed conformance afterward. It is not owner
approval of the new head or execution authority. All definitions, exact type
checks, request construction, validators, refusal policy and workflow bytes
remain unchanged; no production module alias or new adapter layer was added.

From `batch-runner`, exactly once in the existing isolated environment:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -p no:cacheprovider --tb=short -s \
  tests/test_codex_retention_ci_entrypoint.py::test_retention_script_entrypoint_uses_canonical_authority_types
```

The result was 1 collected, 1 passed in 2.13s, exit 0, with no skips. Log SHA256:
`e76664dfe019298af9748129681b18d81311a45e2251bb178a98f49c5565da8c`.
The test undoes only the footer in memory to reproduce the actual old class
definitions and generic formatting of a real canonical refusal. It isolates
the unique unchanged grant-check AST statement with real canonical bindings:
the canonical grant passes only that predicate; script grants, subclasses and
invalid objects retain `retention_execution_grant_required`. This is not a full
`execute` call or a successful private-context/authentication verdict.

Actual `runpy.run_path(..., run_name="__main__")` calls through to real canonical
`main`; imported and script modes produce identical safe source refusals and
redacted observation output. Real controller checks reject the old `_Admission`
type; the canonical instance reaches only the real context refusal for an invalid
request. Temporary module registration is restored. Shared offline guards and
fail-on-effect spies confirm no transport, preparation, reservation, deadline,
child, model or grader activity and no output files. No validator was replaced
with a success verdict; no external transport or harmless child was needed.

The prior 2.25s locator result and separate observation, CI, corrected-fixture,
old live-refusal and genuine private 295.37s results remain linked through the
[immutable PR705 handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/8d352b0585d1e82e2ecfa37db9cd9a7fa9a35a21/tasks/LATEST_TASK_RESULT/README.md).
None was replayed or combined with this entrypoint result.

### Byte scope and remaining gates

Only `codex_retention_ci.py`, its new entrypoint test and these two completion
records differ from the base. All other tracked bytes match, including the
workflow, runtime, registrations/pins, shared fixtures and input/grading code.
The unrelated changelog tail is unchanged. Adapter file SHA256 is
`0b8f2f45859d20da64b733729c045c25c7081f1072379d8a4b67043f9623c82a`;
this is its new byte identity, not source approval.

New-head immutable owner review and CI remain required. Any later execution
needs separate leader authorization bound to the reviewed source, exact cell,
current request/input/config/grader identities, host/deployment and spend scope,
plus the existing authenticated owner-review/job-origin and CAS/deadline/
cleanup/no-replay gates. The old run's approval does not authorize this source
or a retry. No live issuance, token/HTTP/HF/OIDC/Azure/model/grade call, workflow
dispatch, CI polling or paid operation occurred in this task. The failed cell
was not relaunched; this result grants no live authority.
