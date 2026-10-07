# Latest task result

## Native callable validation boundary: no deterministic mismatch reproduced

The one new offline selector reported **1 passed, 1 warning in 21.97s**,
exit **0**; wrapper **22.641730s**. It reached the real native constructor,
pinned-runtime check and canonical capture without a refusal in the traced
operations. This is synthetic boundary evidence, not a historical cause or
a real-host proof. No production fix is justified by this result.

Only `batch-runner/tests/test_time_budget_first_codex_ci.py` changed before
the proof. CHANGELOG, this record and the directly related README passage
change afterward. No controller, callable, consumer, core runner, provider,
workflow, registration, F, history or experiment setting changed. The prior
[accepted-source record][prior] and [PR768 proof record][readout-proof]
remain immutable; earlier proofs are not rerun or pooled.

### Source and historical evidence

| Role | Commit | Tree |
| --- | --- | --- |
| Accepted base / leader's readout controller C | `9fbdc37fb0ec0e4eb79d32b22f37641235a24186` | `2e72a30ccf0cf7aeea6be5c2e842a023dfd0b4bc` |
| Historical native execution R | `b0bba8c71369605fd4261c59259e3cc3924de981` | `f9bb914a717d3fc1326ac8e1e925119cfaee307f` |
| Tested regression | `35ba64b8145ca5ff9401020a94f2f4aaec807662` | `98707a1b6a02372f72e9c7630b61ab70d882f6a5` |

Origin/main was fetched and checked once before creating the fresh branch
`b/codex-native-callable-boundary-20261007`. Relevant production files at
the tested source are byte-identical to historical R. Their Git blob and
SHA256 identities, plus the test identity, are in `source.json` below.
No current-runtime pin needs to advance. The unchanged full registration
seal is `3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`;
its file SHA256 is
`e1d16d350aeb21af34104cede0d3acc0f6dc8db134338708e70168fbd9642699`.

The leader verified historical readout run `37585054563`, run number 4,
attempt 1, artifact `11466485746`: projection 2027 bytes, SHA256
`36882db90cc0a348c60f760134a1a5955a09d83ed2083da571795faa339aaee2`;
ZIP SHA256
`b016f8622fab90cab1bf88fc25bf430f5c1af17b4cee9f566eb2aff8804ee7bb`.
Controller C, original R, fixed cell and registration matched, as did:

- Original execution request: 2369 bytes, SHA256
  `c78a581c482baf495b09efad70899e0067293752f3cc7320f54f2af0079fa062`.
- Permanent claim: `4ca4fd9c86fe1253059fffc66f6e4397c34c3c4e`.
- Acknowledged output: `d443e8045f58b6f7b4b35ed7f1888182b62296e0`.
- Observed manifest: 1096 bytes, SHA256
  `458db9999f436360072181f5e1907b15c4c9f2c1ed018829137920fd495ade5e`.
  This identity is observed, not independently expected; neither the
  original request nor claim object was reread by that readout.

The retained failure is exactly:

```json
{"stage":"observation_callable","category":"validation_refused","reason":"execution_refused_or_uncertain"}
```

No more-specific code, raw exception or original model-call trace survives
that projection. Historical native run `37574558224`, run number 3,
attempt 1, job `112640438630`, remains consumed and privately retained as
uncertain. Result identity/fingerprint, terminal reason, usage, cleanup and
host reuse remain unavailable. Model calls and cost are unknown, not zero.
The new regression neither replays that observation nor relabels its receipt.

### One bounded synthetic reproduction

The existing fixture created new local Git source/input declarations,
synthetic original parquet/reference bytes and full synthetic Step0. It
executed the real bootstrap Bash and request/source/preparation checks,
then created a fresh synthetic private-CAS claim. It did not adopt old
state or read actual private inputs. The nonsecret source-derived packet
at `/tmp/first-native-request-values-20261007.dM2p8mse/first-native-request-values.json`
(SHA256 `e9053078dbc55e4bf163f7d867af9b94fe8a370ff22055d41de74dec2b4d23a5`)
supplied the already-known cell/root/Step0 contract context, not execution
authority. Its source was `5026a8e14224124a9c7282334bd09abf32328e2e`; the
new fixture independently binds its own synthetic source and bytes.

During `execute`, a test-local trace observed actual function code without
replacing validation, runner-factory or constructor verdicts. The direction,
provider, path, reviewed-source and input checks completed. The real
consumer, `CodexAgentRunner` constructor, pinned-package check, runner and
canonical capture each ran once. `boundary.json` records
`first_refusal=null`. It records only fixed operation labels, counts and
static source line numbers if an operation raises, never raw exceptions or
private body text. Generator trace entries are not distinct validations,
model calls or native attempts.

The existing auth seam returned a synthetic token; the SDK transport
handled only `initialize`, `thread/start` and `turn/start`. The test checked
the real provider settings, source/Step0 identities, unchanged direction
and claim bytes, isolated auth configuration, canonical result fingerprint
and captured synthetic deliverable bytes. Unavailable native measurements
remained null. The stateful kernel/syscall fixture exercised local control
flow and cleanup; it is not evidence of NAS or Actions-host admission.
No actual auth, native subprocess, provider/model, HF, grading or readout
operation occurred. No unsupported NAS kernel body ran.

The only selector was:

```text
tests/test_time_budget_first_codex_ci.py::test_time_budget_native_callable_validation_boundary
```

It ran once with offline Python 3.10.12, explicit pytest-timeout 2.4.0,
SDK/CLI packages 0.147.0, 300s+5s overall, no `-x`, the existing bounded
fixture Git/Bash seams and 30s wrapper Git checks. AST syntax, selector and
parametrized-function argument checks preceded pytest in the same bound.
One item was collected; no zero-body collection failure occurred. The one
warning was pytest's JUnit `record_property` / `xunit2` compatibility
warning; the property and extracted safe boundary record were retained.
No old 8/11/17 selector, full suite, retry or timeout increase occurred.

Artifacts are under `/tmp/native-callable-boundary-proof.dW9NqX/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `0daff1a3576a9027228cd7248392442b21c638f51ec235f94e842c13a07f9216` |
| `command.json` | `5682d9beaf2d4933edca206862ac5b067641716bad7b3af20f0567fc3876f90e` |
| `source.json` | `88795d9031883e4bfffb102c0f7d80dd8ef75fc226c2718b1392afa80cd24205` |
| `pytest.log` | `b294709c2b1799ad6f62042ee53e90e982a21d2cbfef789e863b6bcd96b46e84` |
| `junit.xml` | `e74d163878b160610a3e929ba37796358c7cf215ad2d5f8b826c3aa7a4747d3e` |
| `cases.json` | `5b8e425d03f0ab527ee333b2e0b6c2f1fa9003e8fd06dbb5b0a1b0f8db73569f` |
| `boundary.json` | `5a39cc603fda53719ffc6a6130faa94a61620d4e22551540c9cb72e07c6c0773` |
| `outcome.json` | `7455b9fa4f224b8df9623fa0d695a01ae7c3fc7f8bc6c2c96f8e48f9a6aa7715` |

The exact command is retained in `command.json`. Final documentation-only
HEAD/tree and the draft PR are recorded after commit in this directory's
`handoff.json`; neither is presented as a second tested source.

### What remains unknown

The historical classifier recognizes registration/consumption and deadline
refusals before generic `ValueError`, but does not specially recognize
`CodexObservationRefused`. The actual generic classification does not
identify a host/deadline failure. Remaining source-level candidates include
the callable's own direction/provider/path guards, imported equality/byte
checks outside the consumer's registration wrapper, and returned
control/deliverable/schema validation. The successful synthetic path does
not tell which historical value or operation differed. It cannot recover
the historical auth/RPC response, kernel state or first failing guard.

The leader supplied the verified readout and narrow source trace; no new
reviewer-harness endorsement is claimed. Final source review and ordinary
new-HEAD CI remain pending. PR769 at
`2a8f6c754a160c50c4a13589132d09c99828b28b` and its worktree remain untouched;
its reviewed/CI-pending status is the supplied snapshot, not a new query.

The 20-cell registration, ABBA order, GPT-5.4/direct-v1/xhigh, null context
override, request/stream retries 0, one external attempt, concurrency 1,
1200-second generation/shared 20-second cleanup and 45-minute job ceiling
are unchanged. Frozen F remains
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`; scoring and historical results
are untouched. All consumed native/V2 cells stay consumed. Actual-host,
input/Step0, auth, direction and any future live decision remain separate
gates. No next cell, replay, model call, grader, readout, CI query/dispatch/
retry, Project mutation, merge or infrastructure change was performed or
authorized by this regression.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/9fbdc37fb0ec0e4eb79d32b22f37641235a24186/tasks/LATEST_TASK_RESULT/README.md
[readout-proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/4b5088a9f338adee58fe89436836ccc6c9f3363c/tasks/LATEST_TASK_RESULT/README.md
