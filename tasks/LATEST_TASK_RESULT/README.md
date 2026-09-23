# Latest task result

## Immutable HF reference redirect correction

The intake now accepts the observed equivalent encoding of an immutable Hub
cache member, while retaining the exact repository/revision/member identity.
This independent branch starts at
`ea5dcc61c2beaad3a287d3d8dd064533ce33ed41`. Code and tests were committed at
`44e276163e8a241a0a146304c14c64d7437e6914` before the one offline test run.
Subsequent completion-record edits are not another test run or final-head
approval. No workflow, dependency, permission, credential or experiment
control changed. Frozen #662 was not edited or retested.

### Original failure and separate metadata observation

The leader supplied the failed model-free input-check
[35841798539](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/35841798539),
job `107118366778`, on exact source
`ea5dcc61c2beaad3a287d3d8dd064533ce33ed41`. At 09:17:25 UTC on 2026-09-23,
intake reported `hf_original_redirect_refused`, `stage=hf_reference_1`,
`http_status=307`. Plan creation passed; OIDC, identity and model steps were
skipped. This remains a redirect refusal, not evidence of invalid HF
credentials. Its receipt was neither replaced nor rerun.

One separately authorized HEAD used the genuine `_hf_origins` and `hf_hub_url`
to derive exactly that registered reference-1 URL from
`openai/gdpval@11e7900cdcac61bc4daf59e65feb238acda98fbf`. The request began
at 09:25:38.658426 UTC on 2026-09-23 and returned HTTP 307 in 0.25118 seconds,
within its 20-second limit. It was unauthenticated, with no HF token/cache
credential, ambient proxy, redirect following or response-body read. There
was one request, zero followed redirects and zero body bytes read. The
one-use reservation and raw request/Location metadata remain private.

The Location was relative and resolved to the canonical HTTPS HF Hub cache
route. A query was present; no fragment was present. Its namespace, repository
and immutable revision prefix matched literally. The registered member has
three components: the redirect represented their two separators as `%2F`
and left parentheses literal instead of `%28`/`%29`. After exactly one decode,
the complete member bytes and component boundaries matched the expected
cache path, with no residual percent escape, traversal, backslash or control
byte. No input URL, query value, header, payload or private locator is
published here.

The base guard rejected that retained Location because it compared the paths
literally. The equivalent-encoding defect is therefore verified for this HEAD
response, not merely assumed. The original CI Location was not captured, so
these later headers are not assigned retrospectively to its receipt. Neither
this metadata-only observation nor the offline patch validation establishes
current authenticated GET access to all four files or live input acceptance.

### Surgical change and preserved gates

[The redirect guard](../../batch-runner/codex_ci_input_intake.py) keeps the
Hub namespace/repository/revision prefixes literal. Only the exact expected
member is compared after one strict percent decode; case differences in
valid escapes do not change its bytes. Raw paths are also checked so URL
joining cannot hide literal dot segments. Malformed escapes, residual percent
signs/double encoding, traversal, duplicate separators, backslashes and
control bytes refuse with the existing closed reason and logical-role/actual
HTTP-status context. A different host, repository, revision or member is not
an equivalent path.

The existing host allowlist and no-bearer-to-CDN rule remain. So do explicit
transport selection with no fallback, plan-only no fetch, all four original
byte pins, offline local verification, importer/ready-last/no-clobber checks,
request/transfer limits and the external canonical archive binding:
2,519,040 bytes, SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
No original payload was opened or rehashed, and neither campaign was changed
or rematerialized. The workflow, main/ref/rerun and OIDC/model gates, public
completion envelope, fixed host/model policy, 30-cell order and 180/30-minute
cell/attempt limits are untouched. No real payload was downloaded; no model,
grader or Azure call, workflow dispatch or CI query was made.

### One focused offline validation

Tested SHA: `44e276163e8a241a0a146304c14c64d7437e6914`.
`HF_REDIRECT_PYTHON` resolved to the existing isolated Python 3.10.12
interpreter from the known private handoff. No dependency was installed.
From the feature worktree, the exact selector invocation was:

```bash
env -i PATH=/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$HF_REDIRECT_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_ci_hf_originals.py -k redirect
```

Result: `28 passed, 63 deselected in 2.81s`, exit 0, from one invocation.
The 2.81 seconds are pytest wall time, not live transfer or model latency.
Twenty-one new cases and seven adjacent redirect cases use synthetic
provenance/files and a fake HF transport through the real intake CLI. The
shared synthetic fixture gained only opt-in reference filenames; its default
inputs are unchanged. Role derivation, URL/header helpers, deterministic
archive serialization, importer, genuine installed-input readers, byte/hash
checks and no-clobber behavior remain real.

Accepted cases cover the observed encoded separators/literal parentheses,
lowercase escapes, the existing literal path and a subsequent token-free CDN
hop. Refusals cover foreign repositories/hosts, changed or mutable revisions,
encoded identity prefixes, wrong members, malformed/double encoding,
literal/encoded traversal, dot/empty components, backslashes and controls.
The CLI preserves `hf_reference_1`/307 for refused redirects without reading
their bodies or logging private values. Existing bounded-loop and no-response
status cases also passed. No 71/66/31/19 family, full suite, workflow execution,
live input-check or second metadata request was run.

### Review boundaries and remaining work

The leader reported #661 review `5288470314` at
`fcfe5feb7698af78c18d5257807fc0ee0d4351ff` and all nine exact-head checks
passed. Its `71 passed in 3.68s` remains at
`fbd038173aa36d67bda8d0aad3f3ecb35aa7c8af`, not this patch or live access.
The [immutable prior record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/fcfe5feb7698af78c18d5257807fc0ee0d4351ff/tasks/LATEST_TASK_RESULT/README.md)
preserves the original intake controls, prior reader review, GitHub metadata
403, private staging successes/failures and separate successful native
diagnostic `35817078746`. Those observations remain distinct and were not
repeated here.

#662 remains frozen at `0ff95ba41ce7ce961ee333bbcac9f8e3db539697`.
Its `66 passed in 109.70s` belongs to
`731ec479c742a11bcbeb6ce05d8b4f2da971ed3d`. Leader review was incomplete at
the supplied observation; no FINAL-APPROVE is claimed. This patch still needs
its own immutable-head review and automatic final checks; none was queried.

Live input acceptance, publisher review, approved output-target readiness,
output workflow wiring, the canonical pilot grading-input adapter, ordered
execution of all 30 cells, cross-run admission deduplication and fixed grading
remain unfinished. The leader retains live-run control. This change neither
authorizes a retry nor proves durable output or graded quality.

`experiment-report-en` and `im-not-ai-en` kept the original failure, later
metadata, synthetic validation and unknown live acceptance separate without
strengthening their claims.
