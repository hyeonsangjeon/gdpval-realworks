# Latest task result

## PROJECT5-OBSERVED-LOCATOR-ROUTE-FIX

The issuance predicate and closed diagnostics now share one exact matcher for
the unchanged legacy route and `/<digits>//idtoken/<UUID>/<UUID>`. At
`0fab70ea73cd1fe8ede065db5ef42bc5a84781e0`, the extended offline locator
selector reported 1 collected, 1 passed in 2.25s, exit 0. This verifies support
for the observed structure, not successful live authentication or admission.

Branch `b/codex-retention-observed-locator-route-20260930` starts at exact
main `bbf6f8b98f7783f448ee2da5a7ef589c65f61fd3`, tree
`7da0dcf9f25b0e4cb650f2b6f3d4391aee2a981c`. The leader supplied all 10 passing
checks at prior PR704 head `bbf5454254ebded6cbcb94b7773bcf7f284044dd`,
[review 5361514862](https://github.com/hyeonsangjeon/gdpval-realworks/pull/704#pullrequestreview-5361514862).
That review does not approve this new source. Prior branches/worktrees and
`wip/local-main-preserved-20260719` remain untouched.

### Actual observation supplied by the leader

In completed [run 36669478415, attempt 1](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36669478415/attempts/1),
[execution job 109754018823](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36669478415/job/109754018823)
reported the following at `2026-09-30T05:33:53.5678235Z`:

- Reason `github_job_issuance_locator_observation_only`; `launch_authorized=false`,
  `grading_launched=false`, `truncated=false`.
- `registered_route=false`. All other checks were true: `allowed_host_pattern`,
  `hostname_only_authority`, `https`, `known_api_query`, `length_within_limit`,
  `no_fragment`, `not_oidc_issuer`, `query_parsed`, `url_parsed`.
- Counts: `api_version_parameters=1`, `audience_parameters=0`, `host_labels=4`,
  `other_query_parameters=0`, `query_pairs=1`, `route_segments=5`.
- Route skeleton `["{number}","{empty}","idtoken","{uuid}","{uuid}"]`.

Observation step 11 succeeded. Signed-token verification 12, sandbox 13,
Azure login 14 and claim/run/reconcile 15 were skipped. This establishes the
current run's route mismatch, not the old run's exact URL or a model result.
No bearer, raw URL or identifier was supplied in the evidence, and no hostname
or UUID meaning is inferred. The observation was not repeated here.

[Preparation job 109741183729](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36669478415/job/109741183729)
succeeded. Execution preparation reproduced request SHA256
`c9651a51284b0ea71a0e8858f330b8e11ad0a3bba1e17c6ddf008b7c8e23abbf`
and materialized-grader SHA256
`c391424e7ff45f375c6bb17135440aab85b29748fa0c52215805594a1517a320`.
The owner observation-only approval persisted once in `grading18744914306`,
deployment `6751627582`; [approval job 109741872495](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36669478415/job/109741872495)
succeeded. Those facts are not an execution grant. They are preserved in this
substantive repository change; the leader's unavailable local M4 volume was
not accessed or updated.

### Exact change and offline evidence

The mandatory bounded auth/extreme-reasoner decision approved the design with
conditions before editing, then found those conditions satisfied in the diff.
This is an implementation decision, not immutable owner approval of the new
head or live authority. Production changes are limited to one compiled union
and its two full-match uses. The new alternative uses ASCII `[0-9]+`, a literal
empty segment, exact `idtoken` and the existing UUID syntax. It adds no numeric
magnitude limit, decoding, slash normalization, optional segment or suffix.

The 4096-character bound, HTTPS/host/authority/fragment constraints, sole parsed
`api-version=2.0`, single appended audience, credential isolation and bounded
response closure remain unchanged. Signed RS256 issuer/audience/job/source/
request/boot/freshness verification, owner review, serial CAS, deadline and
no-replay gates are unchanged.

From `batch-runner`, exactly once in the existing isolated environment:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -p no:cacheprovider --tb=short -s \
  tests/test_codex_retention_ci_locator.py::test_retention_job_issuance_locator_diagnostics_are_closed
```

The result was 1 collected, 1 passed in 2.25s, exit 0. Log SHA256:
`0c30ba4348154d2fc769035e3a28649ab52979ff23f12904552dce7cc28346b2`.
The real parser, matcher, issuance method, transport guards, CLI and closed
formatter ran with synthetic locators and simulated HTTP responses only.
Coverage includes both exact routes, numeric zero, a 4096-character locator,
4097 refusal, missing/extra/encoded segments, nonnumeric/non-ASCII numbers,
malformed UUIDs, host/query refusals, response closure and credential separation.
All original refusal, redaction and no-effect checks remain. Observation of
accepted shapes runs without credentials, with transport and source verification
guarded to fail; it reports the matching classification and both authorization
flags false. No validator verdict was substituted.
This selector does not execute signed job verification, private preparation
or admission.

The separate 2.04s observation-path pass and earlier 2.17s local pass,
malformed-URL CI failure, 2.22s corrected-fixture pass, old live refusal and
genuine private 295.37s pass remain linked through the
[immutable PR704 handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/bbf5454254ebded6cbcb94b7773bcf7f284044dd/tasks/LATEST_TASK_RESULT/README.md).
None was replayed or combined with this result.

### Byte scope and remaining gates

Only `codex_retention_ci.py`, its existing locator test and these two completion
records differ from the base. All other tracked bytes match, including the
workflow, runtime, registrations/pins, shared fixtures and input/grading code.
The unrelated changelog tail is unchanged. Adapter file SHA256 is
`130294b798a42f55b170bde48c3d57efc71f17941cb55d093b47dc071d99f130`;
this is its new byte identity, not source approval.

New-head immutable owner review and CI remain required. Any later execution
needs separate leader authorization bound to the reviewed source, exact cell,
current request/input/config/grader identities, host/deployment and spend scope,
plus the existing authenticated owner-review/job-origin and CAS/deadline/
cleanup/no-replay gates. Observation-only approval cannot be reused as that
grant. No live issuance, token/HTTP/HF/OIDC/Azure/model/grade call, workflow
dispatch, CI polling or paid operation occurred in this task. No live success
is claimed for this compatibility change.
