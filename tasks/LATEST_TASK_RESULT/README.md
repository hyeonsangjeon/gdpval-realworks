# Latest task result

## PROJECT5-PREPARE-GUARD-OWNER

The single authorized offline selector collected 1 test and reported **1 passed
in 5.69s**, exit 0, at `45ef631d76d2c92a1d0263e5dab9c36680939ef7`.
The explicit private locator was present, and the test was not skipped. Real
preparation, readback and materialized-grader hashing ran; no inference slot was
reserved and no deadline was started. Preparation is not admission.

### Scope and source boundaries

The only test change since `e224a750dbdbabe74490ff9c87459d14d5e01d40` replaces
`core.codex_task_deadline.CodexTaskDeadlineStore.admit_attempt` with the actual
owner, `core.codex_task_deadline.CodexTaskDeadline.admit_attempt`. Static checks
confirmed all guard targets before pytest. Strict attribute checking and the
existing process, network, SDK, model, credential and admission guards remain
intact. No preparer, runtime, compiler, registration, pin or grader changed for
this correction.

The [preparer](../../batch-runner/codex_retention_prepare_packet.py) accepts
explicit original-input paths, one exact registered cell and an external
preparer-source digest. It reuses the source/schema4/prepared-projection
validators and no-clobber materialization helpers. It writes only
`inference-config.json`, `grader-config.json`, `selected-task.json` and
`preparation.json` beneath a new owned directory in the source checkout's
ignored `batch-runner/workspace/`, as required by the real grader hash helper.
The focused test verified the original five-task bundle remained unchanged,
the selected row/config identities, readback, actual grader hash, closed
input/source/cell/path/output refusals and cleanup after interrupted writing.

Branch `b/codex-retention-prepare-packet-20260929` retains exact base
`1c777374af6fcbd2b5a07c94585e35899dc5847e`, tree
`0ade78cb0a3522707765cf082ea8fe467a2dd2c6`. The leader's reviewed
`5932ac85905bf9e25e668ffc7be43c3229f391ac` /
[review 5347346570](https://github.com/hyeonsangjeon/gdpval-realworks/pull/699#pullrequestreview-5347346570),
11 applicable CI passes and deploy skip cover that base, not this new preparer.
All tracked bytes outside the new preparer/test and these two records match
the base. The preparer itself is unchanged from `e224a750dbdbabe74490ff9c87459d14d5e01d40`.
Only completion records change after the tested SHA; old worktrees, branches
and WIP remain untouched.

### Verified input and packet identities

The accepted original-byte evidence came from the named retained handoff,
without HF intake or credential access. This invocation additionally reached
the real schema4/provenance/prepared-projection reconciliation. It did not
verify a transport archive, stage runtime inputs or run a campaign.

| Input role | Bytes | SHA-256 |
| --- | ---: | --- |
| Original parquet | 1913489 | `f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202` |
| Original XLSX reference | 329418 | `bb09ca2a9999b404d7fced9202b42949cd9f142f39554e254bac77b3686dae9e` |
| Original PDF reference | 47850 | `901e943a97328a661f9e704ae43eeea167e7805385a99322f1c24f8e159125c4` |
| Canonical schema4 Step0 manifest | 218405 | `463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512` |

Selected cell: `0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_fresh_r1`.
Paths and payloads remain private. The verified packet and source-byte checks
establish these distinct identities; the materialized grader fingerprint was computed by the real
`compute_grader_source_hash`, not copied from a template or earlier campaign.

| Identity role | SHA-256 |
| --- | --- |
| Verified original-input roles | `40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38` |
| Unchanged registration compiler | `c8ac9d0ec3eca0d4251c345f733009f506d366d312c5357836e6c67332a76c53` |
| New preparer source, not reviewed | `0895e0536599b893a215f96e5dcafba2f2a4b556720452cf6d99d50b2d65c627` |
| Actual materialized grader source | `15d11db5e00cca1fa6e98b9805c52d8d0e543198f16ff90066c235f332bf4e19` |
| Verified preparation packet | `4f11ec470b33334bc7e3e073946fc58bd8e92037a82182b598c4941af483520b` |

### Separate validation observations

| Source or observation | Actual outcome |
| --- | --- |
| Earlier static fixture finding | The tracked 4,142-byte fixture, SHA-256 `48c188e0a82a515d7c8ea3bb491a0c04f1c344467eaa2797e20d013d184169e3`, is not the canonical Step0 manifest. No test ran at that stop. |
| `e224a750dbdbabe74490ff9c87459d14d5e01d40` | 1 collected; **1 failed in 2.06s**, exit 1. Strict guard installation raised `AttributeError` because `CodexTaskDeadlineStore` has no `admit_attempt`. No compiler/preparer call, packet or grader fingerprint was reached. |
| `45ef631d76d2c92a1d0263e5dab9c36680939ef7` | 1 collected; **1 passed in 5.69s**, exit 0; not skipped. Real packet preparation/readback and refusal assertions completed with zero guarded calls. |

The earlier log is 1,791 bytes, SHA-256
`2470cc62e9229f0f7d0f0c6e74910518cfaf5cd27e752ea4740dd2e9da4502a1`.
The new log is 1,016 bytes, SHA-256
`b73137d1072a1ed79000d90b86b2577f697e97522b270ef6770c6ddc19765334`.
Both observations and private receipts remain separate. Earlier registration
results remain in the [immutable registration handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/5932ac85905bf9e25e668ffc7be43c3229f391ac/tasks/LATEST_TASK_RESULT/README.md).

The sole invocation at the new tested SHA ran from `batch-runner`. Only the two
private path values are represented symbolically; their exact values are
retained in the session handoff. All other environment entries and argv are
literal. The original locator was reused, with a fresh private receipt path.

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 GDPVAL_RETENTION_PREPARED_HANDOFF="$RETAINED_INPUT_HANDOFF" GDPVAL_RETENTION_TEST_RECEIPT="$PRIVATE_TEST_RECEIPT" /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p no:cacheprovider --tb=short -s tests/test_codex_retention_prepare_packet.py::test_retention_preparation_packet_is_verified_closed_and_no_launch
```

### Remaining gates

The packet retains `launch_authorized=false`, `commands=[]`,
`inference_slot_reserved=false`, `deadline_started=false` and
`runtime_inputs_staged=false`. Grading has not run. New-source review and CI,
serial execution/reservation, runtime input staging, live-source/deployment
verification and separate launch direction remain outstanding. The local pass
is not source approval or live authority. No model, paid run, Azure/OIDC
operation, HF intake/write, infrastructure change or CI replay ran. Protected
English copyediting preserves these evidence levels and limits.
