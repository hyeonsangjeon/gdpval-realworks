# Latest task result

## PR #785 CI correction verified for owner-approved fast-forward delivery

Scope: verify and deliver the existing CI correction on
`codex/gpt56-direct-account-contract-20261022`, as explicitly authorized by
the owner. The clean direct-account integration worktree has tested commit
`cee9111d998f08015d767fb9fb2ad7be5326ee45` directly atop the inspected remote
head `dcf97b68663084b12472b8a8fd8d81799c47e938`; delivery is fast-forward only.
The user checkout is unchanged. Only these two completion records were updated
after the new local verification.

Cause: the intentional source-profile change in
`d02d8e08beab85d5c443baaf60f8036c2d7308d3` passes the supplied plan's seal
into the active-plan selector. Altering the expected grader hash changes that
seal, so source registration refuses the plan before the former
`active_contract_mismatch` check. The public compiler translates that refusal
to `pilot_identity_compile_refused`. CI reported **1 failed, 916 passed**.

Only the stale test expectation was changed, from `active_contract_mismatch`
to `pilot_identity_compile_refused`. The same test still directly requires
`grader_template_source_drift` for the altered hash. Production code, the
frozen grader hash, source checks, launch restrictions and all other test
assertions are unchanged; no skip or xfail was added.

### Fresh local verification

Python 3.10.12, pytest 9.1.1, at tested commit
`cee9111d998f08015d767fb9fb2ad7be5326ee45`. Each subprocess used an empty
inherited environment, explicit system PATH, offline Hub/dataset settings,
disabled plugin autoload and no pytest cache. No credential values were read.

| Selection | Result | pytest elapsed |
| --- | --- | ---: |
| Complete changed identity test file, including `stale_expected_hash` | 118 passed, 0 failed | 16.36s |
| Exact seven-file CI "Run pilot contracts" selection | 917 passed, 0 failed | 485.21s |
| Exact CI budget-pilot file selection, excluding readout files | 1537 passed, 0 failed, 3 warnings | 5129.92s |

These are separate invocations, not unique-test totals or model measurements.
Commands ran from `batch-runner/` using `python3 -m pytest -m "not integration"
-o addopts= -p no:cacheprovider --tb=short -q`, with `-rs` for CI selections
and `-x` for the budget selection. Both CI file selections match
`.github/workflows/backend-tests.yml`; no workflow was changed.

The initial budget attempt stopped at **71 passed, 1 setup error in 91.22s**
because the local environment lacked `openai_codex`. The repository-pinned
`openai-codex==0.147.0` and `openai-codex-cli-bin==0.147.0` dependencies were
restored only under this session's `files/test-deps/`, then exposed through
`PYTHONPATH` for the successful full rerun. No dependency manifest or shared
environment changed. The three successful-run warnings concern pytest
`record_property` with JUnit xunit2, not test failures.

Logs and JUnit reports are retained under
`/home/dev/.copilot/session-state/cc2a9ac6-2d8f-48e3-b68e-6a87c5d035e1/files/`
as `identity-tests.*`, `pilot-contracts.*`, `budget-contracts.*` (initial
dependency failure) and `budget-contracts-restored.*` (successful rerun).

### Evidence boundary and remaining work

The inspected failing CI head is
`dcf97b68663084b12472b8a8fd8d81799c47e938` (run `39932101762`).
The newly inspected and tested fix head is
`cee9111d998f08015d767fb9fb2ad7be5326ee45`; neither inspection nor the
owner's push authorization is final-source review approval. No new review
approval is claimed. The code delta remains one expected-message line;
all other delivery changes are completion documentation.

Only the approved branch push is authorized; no merge, manual workflow
dispatch, paid model/grader call or secret-value access is part of this task.
New automatic CI and final-source review, plus the existing frozen-grader
binding and live-admission gates, remain required. These offline tests do not
authorize benchmark execution or change any spent/uncertain right.
