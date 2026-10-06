# Latest task result

## Fixed native r1/Task1 Actions controller

The one new offline selector passed **8 cases in 94.87s**, exit 0. Its bounded
wrapper took **95.498829s**. This proves synthetic controller integration,
not real host readiness or permission to execute a native observation.

### Source and review basis

Accepted main is `1e4519d71a6cead3a2dd8de7e60d884a21ba954d`, tree
`9464969952af79c359e5c4236692f0dc4ca844e3`; origin/main was checked once
before creating this independent worktree. The leader's source-grounded
pre-edit CI/storage decision approved only this fixed-cell implementation.
The required reviewer invocation failed before execution because its legacy
Opus preference was unavailable. No spawned review is claimed and no retry
was attempted.

The tested implementation is
`546498510996573f5855d449593df0b4a60ec414`, tree
`ca7b7e75ad29d9fd1b91994b12886c55a1b07742`. It adds only:

- `.github/workflows/gpt54-time-budget-first-codex.yml`
- `batch-runner/gpt54_time_budget_codex_ci.py`
- `batch-runner/tests/test_time_budget_first_codex_ci.py`

Existing V2, readout, core, native callable, registration, dependencies and
frozen F bytes are unchanged. Only `CHANGELOG.md`, this record and the direct
native section of `batch-runner/README.md` change after the proof. Exact final
HEAD/tree and the draft PR are recorded in the local `handoff.json` beside
the proof artifacts; the implementation identity above does not include
those later records.

### Implemented boundary

The route permits exactly `gpt54_time_budget_v1_codex_r1` / `codex` /
repeat 1 / task `02aa1805-c658-4069-8a6a-02dec146063a`. It reuses the
accepted `run_codex_observation`, generic preparation and consumer, existing
original-input/Step0 readers, and bounded private CAS/retention primitives.
It does not compile or reopen the closed pilot, select another task/run or
change the twenty-observation registration.

An independently digest-bound request fixes the reviewed main/workflow R and
tree, F `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2` / tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, input registration and dataset
seals, full canonical Step0 provenance, owner/ref/run number/attempt 1,
admission window, canonical paths and expected private parent. The actual
`GITHUB_WORKSPACE` remains an ordinary bootstrap; R/F are genuine detached
linked worktrees with the same common Git directory. Native and login roots
are fixed private directories under `RUNNER_TEMP`; the existing resolver
must validate the native root outside the system temporary directory.
Source, path, host and input bindings are reread rather than accepted from a
local readiness marker.

Original parquet/reference bytes and the complete Step0 manifest come from
their accepted immutable origins. The Step0 identity is 218405 bytes,
SHA256 `463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512`,
at revision `6c7e07ee7365f145dfcf898263365b5c8c97b224`; no replacement
manifest is manufactured. A permanent add-only claim and immutable readback
bind the native task prefix on the fixed private dataset. Occupied claims
refuse without adoption. Execution is reserved once, and returned canonical
result/deliverable bytes or explicit uncertainty are retained under that same
prefix. Missing result or unavailable native usage never becomes a zero or
fabricated row. Only allowlisted completion metadata may be published.

HF_TOKEN appears only in bounded input/claim and retention steps. It is
removed before inference. Approved login, direct-v1 provider settings and
isolated native auth remain unchanged. The empty private login directory
exists before provider-direction hashing so the later approved login uses
the same bound auth-helper path. The workflow sets
`JE_ARROW_MALLOC_CONF=background_thread:false` before imports and shares the
existing V2 concurrency group. GPT-5.4/direct-v1/xhigh, null context override,
zero request/stream retries, one external attempt, concurrency 1,
1200-second generation, shared 20-second cleanup and the 45-minute job
ceiling remain unchanged. None is a money hard cap.

### Single offline proof

From the new worktree's `batch-runner`, the wrapper ran only:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout \
  tests/test_time_budget_first_codex_ci.py::test_time_budget_first_codex_ci \
  -m 'not integration' --tb=short -ra \
  --junitxml=/tmp/time-budget-first-codex-ci.yqfbZJ7y/junit.xml
```

The outer bound was `timeout --signal=TERM --kill-after=5s 300s`; there was
no `-x`, `/usr/bin/time`, retry or prior selector. Python was 3.10.12,
pytest 9.1.1, pytest-timeout 2.4.0, huggingface-hub 1.24.0, and native SDK/CLI
0.147.0. Source/tree cleanliness, three-file scope, Python syntax and workflow
YAML were checked in the same invocation.

The eight cases were `roundtrip`, `failed`, `source`, `selection`, `step0`,
`direction`, `occupied` and `uncertain`. The roundtrip uses real temporary
Git, workflow layout/CLI parsing, source/registration/input/direction
validators, the consumer and accepted native callable. Synthetic original
HTTP, private CAS and native SDK transports exercise canonical success/error
capture, byte/fingerprint readback, permanent duplicate refusal and preservation
of seeded old V2 bytes. Explicit sentinels reject unapproved network, auth,
provider, grading and process operations. Fixture Git operations keep their
30-second bound.

Kernel state is synthetic: real proc-based thread/child checks read fixture
data alongside the existing stateful pidfd/waitid/subreaper seam. No
unsupported NAS kernel body or real Actions-host admission was run. The
`uncertain` case verifies refusal with no result; it is not counted as a
host-positive observation. No source validator, consumer or runner factory
was replaced with a successful verdict.

All artifacts are under `/tmp/time-budget-first-codex-ci.yqfbZJ7y/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `d795f8cb6df38715d2327698cdc588508548b43692c54554bb9ecc628773b000` |
| `command.json` | `37b6d3d0339b364148eb95a390ddc51e08f64fe621c780a0e841aaccd3f64bb3` |
| `source.json` | `8dffd4f3d43518a9242f7fbad0792179cdb9128774355cd6177c022e3c1de027` |
| `pytest.log` | `ceed24bfdfa739ca9b9fb801fbb8ea15486a325697bbc6799d59a7b1c88d42fc` |
| `junit.xml` | `fdba538caa9ab9a081b002961cb470b96df58f69e4d147909d65cb06f7171e2f` |
| `outcome.json` | `e01d0d3fa5b8dc2f70f0afd72c280a3234ff269464840a9e5381c1c063e96772` |

### Limits and remaining gates

Final source review/CI and accepted-main delivery remain pending. A future
native request must independently bind the actual accepted R/tree, workflow
run number, finite window/digest, private parent and canonical host paths.
Genuine input/Step0 acquisition, approved auth, supported execution-host
admission and controller behavior in Actions remain live gates. This local
proof is not permission to advance ABBA order or execute any observation.

The native callable emits `execution_mode: codex_foundry`. This controller
validates that canonical capture directly; it does not weaken or modify the
existing grading helper's `codex` expectation. Grading integration and its
separate input/result/publication direction remain outside this route.

[The accepted-main record][prior] preserves earlier native, allocator and
V2 proofs separately. Real V2 Task1/Task2 remain consumed and uncertain.
Task3 remains consumed with a canonical error, terminal reason `failed`,
confirmed cleanup and reported usage of 2913 input / 326 output tokens. Its
6632-byte result remains at output commit
`2460c45c3896371b011624f13fc7817d5f670969`, SHA256
`a2f21666eb53542ead8b780404fd241056d3cc129167f6e7b1be36c6b64160f7`.
No cause, model-call count, bill or score is inferred. The separate PR763
readout branch/worktree at leader-reported
`f1f79f27b8ffd3e67cf7af60810be5abde86333b` is untouched and its CI was not
queried. No private readout, Task4 or Task1-Task3 replay occurred.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/1e4519d71a6cead3a2dd8de7e60d884a21ba954d/tasks/LATEST_TASK_RESULT/README.md
