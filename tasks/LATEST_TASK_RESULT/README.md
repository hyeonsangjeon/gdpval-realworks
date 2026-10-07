# Latest task result

## Prospective safe native failure event

Native `execute` now emits the existing validated failure fields after this
invocation successfully reserves execution and writes its failure receipt.
The one new offline selector reported **11 passed in 89.78s**, exit 0;
wrapper **90.404412s**. The change is future operator visibility only. It
does not diagnose the consumed native observation or alter execution,
retention, completion, canonical results, failure classifications or budgets.

### Scope and provenance

`gpt54_time_budget_codex_ci.execute` calls the existing shared
`_emit_execution_failure` immediately after the successful failure-receipt
write. The shared formatter adds one keyword-only `format_version` argument
whose default remains `gpt54-time-budget-first-v2-ci-failure-v1`. The only
other accepted value is the fixed native constant
`gpt54-time-budget-first-codex-ci-failure-v1`; no request text or new workflow
input selects it. V2's default output is byte-for-byte unchanged.

The event contains only `format`, `stage`, `category` and `reason` from the
current validated in-memory failure. Existing stage/category/reason
vocabularies and private-receipt/completion/canonical schemas are unchanged.
There is no receipt read for emission and no adoption of previous state.
Pre-reservation failures, reservation or receipt I/O failures and absent or
malformed metadata do not emit. A failed stderr write remains a refusal,
without I/O retry, another attempt, renewed deadline or success fallback.
No raw exception text, dynamic class name, path, filename, token, header,
provider/model/reference prose or traceback is projected.

The leader read both execute paths and the existing emitter and approved
this narrow privacy/CI scope. The required new reviewer invocation failed
before execution on unavailable legacy Opus; it was not an endorsement.
No reviewer harness was retried or independent spawned review claimed.

### Historical uncertainty is not changed

The leader-verified native run `37574558224`, run number 3, attempt 1, job
`112640438630`, executed at `05:07:26..05:07:30Z` and returned 2 with only
the public `refused_or_uncertain` message. Input/full Step0, permanent claim,
approved login/identity and retained uncertainty succeeded. The completion
has null result identity/fingerprint, terminal, usage, cleanup and host reuse;
retry and grading are false, with other cells 0. No historical native cause,
model-call count, confirmed cleanup, price or score follows from these fields.

The permanent claim is `4ca4fd9c86fe1253059fffc66f6e4397c34c3c4e` and
acknowledged output is `d443e8045f58b6f7b4b35ed7f1888182b62296e0`. The
[separate uncertainty record][readout] preserves the full request, host,
completion, ZIP and log identities. This prospective change cannot backfill
that job's log and cannot justify replay.

PR768 remains at `4b5088a9f338adee58fe89436836ccc6c9f3363c`, tree
`ab4c3af7e9daa726430bb5d97adceb886059cfe5`, with leader-reported source
acceptance `5438334969`. Its ten-passing/one-running CI state is the leader's
snapshot, not a new query. This branch neither changes nor integrates that
worktree or readout. A later retained-manifest read remains separately
directed after its final gate. No actual read was made here.

All V2 r1 Task1-Task5 and native r1/Task1 remain consumed. V2 Task1/Task2 are
uncertain; Task3/Task4/Task5 are canonical errors. These are not successes or
zero quality scores. The [prior accepted record][prior] preserves older
grading/input evidence and its already-consumed authorization, not replay
permission. Earlier native 8-case/2-node and readout 17-case proofs remain
separate and were not rerun or pooled with this selector.

### Pinned source and one bounded proof

| Role | Commit | Tree |
| --- | --- | --- |
| Accepted base | `b0bba8c71369605fd4261c59259e3cc3924de981` | `f9bb914a717d3fc1326ac8e1e925119cfaee307f` |
| Tested implementation | `42506c920de9e09bcdbcb4e28f50007e3f595450` | `e4922d258e03cb9ee71443bddb6dd038ed9fd05d` |

Before the proof, only the native controller, shared emitter module and
existing native controller test file changed. Their SHA256 values are:

| File | SHA256 |
| --- | --- |
| `batch-runner/gpt54_time_budget_codex_ci.py` | `f76c3e1ea65da2897b72879b36f24a4c02a671d383c3bf107eeff9dc163f0cb6` |
| `batch-runner/gpt54_time_budget_v2_ci.py` | `88f29f07a2035059639a606d3dd4e934d3d397df03cb42fe54909e011730bc8c` |
| `batch-runner/tests/test_time_budget_first_codex_ci.py` | `dffdce1fa2c4664937fbcefcd7422b948f0af059e770da822fc42281a75a0880` |

The new selector reused existing original-input/preparation/private-CAS
fixtures and actual source/receipt validators. In the fresh synthetic case,
the actual callable reached its direction-file `os.open` after controller
reservation; the fixture raised a secret-bearing `TypeError` there. No
exception string was formatted. Exactly one native four-field event followed
the receipt write. This synthetic category is not the historical cause.

All 11 cases passed: `fresh_secret`, `pre_reservation`, `old_state`,
`reservation_io`, `receipt_io`, `receipt_ack_io`, `missing_metadata`,
`malformed_metadata`, `invalid_protocol`, `stderr_io` and `v2_compatibility`.
The I/O cases include persisted bytes whose write acknowledgement fails.
Duplicate synthetic calls emitted nothing and left permanent claim,
reservation and receipt bytes unchanged. Stderr was attempted once on its
failure path, with no retry. The V2 case checked the exact existing JSON line.

Native/kernel admission was explicitly denied. Storage effects used existing
synthetic transports; provider/auth/model/grading effects were denied.
There was no real kernel probe or runtime-positive proof. Python 3.10.12,
pytest 9.1.1 and pytest-timeout 2.4.0 were used with 300s+5s/no-`-x`, existing
30s Git bounds and named fixture Git/Bash allowances. No broader audit trap,
`/usr/bin/time`, previous selector or full suite was run. From `batch-runner`:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout \
  tests/test_time_budget_first_codex_ci.py::test_time_budget_native_failure_event \
  -m 'not integration' --tb=short -ra \
  --basetemp=/tmp/native-safe-failure-event-proof.zo6agw/pytest-tmp \
  --junitxml=/tmp/native-safe-failure-event-proof.zo6agw/junit.xml
```

The single outer invocation was:

```bash
timeout --signal=TERM --kill-after=5s 300s \
  /ai-work/venvs/gdpval-realworks-py310/bin/python \
  /tmp/native-safe-failure-event-proof.zo6agw/run-proof.py
```

Artifacts are in `/tmp/native-safe-failure-event-proof.zo6agw/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `33059e0ed7c2e2b5cd8f656b8f5b6363810239212f50f16e6b32b7eae51522e7` |
| `command.json` | `29893b5c9fe5ff26839e8b545244c429cd52f53c5339d8ebc45b2cdc7d0f76d1` |
| `source.json` | `abd2699558509694ac099c7e6046b3df62f80f98d08a50d9c64188d044f49bb4` |
| `pytest.log` | `edeb1fe365b184ccb7d862dbec7ae9b29309c245bbda31c5c3de3bc27ff33dfa` |
| `junit.xml` | `108d9e9e17a8fa2deedf14c8266a109bd9e7c40a1977f101da58df2cc749b8f0` |
| `cases.json` | `f58b50fefb9f88c7571740d77a5f7c0dc3e34551268d7b50320a036f18c227b9` |
| `outcome.json` | `546185e602144f8483dec7c0eeef54c77b7dae8d361d12e36fd3887f121bbb19` |

### Fixed scope and remaining gates

Workflows, readout, core/runtime, F, registration and historical source pins
remain unchanged. Registration seal
`3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`, frozen F
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2` / tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, twenty planned observations,
GPT-5.4/direct-v1/xhigh, null native context override, request/stream retries
0, one external attempt, concurrency 1, nonrenewable 1200-second generation,
shared 20-second cleanup and 45-minute job ceiling stay fixed. No money cap
or new study condition is introduced.

Only CHANGELOG, this record and direct README usage change after the proof.
The final commit/tree and separate draft PR are recorded after that
documentation commit in
`/tmp/native-safe-failure-event-proof.zo6agw/handoff.json`. Final source review
and ordinary new-HEAD CI remain gates. This change does not authorize a
readout, another claim, consumed-cell replay, next cell, grade or ABBA advance.
No CI query/dispatch/retry, Project mutation, merge, Azure management,
private fetch or paid operation occurred.

The agent catalog was read once. Retained source/CI guidance and
`experiment-design` held the study boundaries; `experiment-report-en` and
`im-not-ai-en` kept historical uncertainty separate from synthetic evidence
and preserved the exact proof and source identities.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/b0bba8c71369605fd4261c59259e3cc3924de981/tasks/LATEST_TASK_RESULT/README.md
[readout]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/4b5088a9f338adee58fe89436836ccc6c9f3363c/tasks/LATEST_TASK_RESULT/README.md
