# Latest task result

## PROJECT5-PREPARE-CALLER-HELD-WRITER

At `2d206b032f2236310b119a831303d57152323b1a`, the single authorized offline
selector collected 1 test and reported **1 passed in 6.62s**, exit 0, not
skipped. It exercised real preparation/readback and both deterministic output
directory swaps with the existing private fixture. No intake or recovery was
replayed. Preparation reserved no slot and started no deadline.

### Review scope and publication boundary

[Review 5348128931](https://github.com/hyeonsangjeon/gdpval-realworks/pull/700#pullrequestreview-5348128931)
requested changes at `a3362bbe484debd8c5b78263198a1dd84f6d04b8`: the old writer
reopened the output pathname after the preparer's outer check, so a replacement
could receive bytes before a later refusal. The earlier local pass remains
valid but did not cover this gap. The new delta is not yet reviewed or approved.

The [preparer](../../batch-runner/codex_retention_prepare_packet.py) now reuses
`ghcp_vm_input_bundle._publication_parents` and `_write_no_clobber` unchanged.
After exclusive creation, it retains `directory_fd(output)` and passes that
same descriptor as `parent_fd` to every member write and final `preparation.json`
write. The helper checks the path against the caller-held inode before any
temporary-file allocation and uses that FD for temporary bytes, no-clobber
linking and temporary-link removal. It never reopens or adopts a replacement
parent. Existing fsync, no-link/path checks and outer identity checks remain.
The new preparer source identity includes the reused helper's actual bytes;
no shared helper, compiler, runtime, config, registration, grader algorithm,
workflow or frozen source pin changed.

The two test-owned swaps occur after the outer checks, immediately before the
first member write and final marker write. Each reached the real helper's
`ghcp_input_bundle_refused` predicate before any temporary allocation. Assertions
checked parent identity/bytes, the replacement's exact sentinel-only contents,
the original held inode and partial bytes, absence of both markers and refusal
to reuse either directory. The first original stayed empty; the final original
retained its three payload files. Original five-task input bytes and all
network/model/credential/process/admission guards remained intact.

Interrupted publication **retains partial output and refuses reuse**. Only a
writer's private temporary link is cleaned up; partial production outputs are
not deleted. This corrects the earlier record's "cleanup after interrupted
writing" wording.

### Exact validation and identities

The invocation ran once from `batch-runner` with the same explicit locator and
a new private receipt path. Only those two path values are symbolic below;
their exact values are retained privately. The selected test was not skipped;
this turn used one invocation.

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 GDPVAL_RETENTION_PREPARED_HANDOFF="$RETAINED_INPUT_HANDOFF" GDPVAL_RETENTION_TEST_RECEIPT="$PRIVATE_TEST_RECEIPT" /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p no:cacheprovider --tb=short -s tests/test_codex_retention_prepare_packet.py::test_retention_preparation_packet_is_verified_closed_and_no_launch
```

The selected cell remains
`0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_fresh_r1`.
Actual identities from the new receipt and source-byte checks are below; none
confers source approval or launch authority.

| Identity role | SHA-256 |
| --- | --- |
| Verified original-input roles | `40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38` |
| Preparer file bytes | `c0cbc6e332d6ebf3a48b58094c4bffc1e2f032b48ac61ee6a771f474ba11633a` |
| Preparer and helper source identity | `39cc0a553aa5a47778ea303d198cbf7775c55003b0e144fec279653521095103` |
| Unchanged caller-held-FD helper | `f6b57eacdcb93715bb286dc7bc979599d5c5a14a948f5b14a1c8561631780d39` |
| Actual materialized grader for this packet | `b948e1e50dcd6031749464cbf2f8d5362933191361371f98b51dc9b3fad8a3f9` |
| Read-back preparation packet | `3c39313149d902db6b6c8d05139cdf343cd8c5184a8721d255c4461b3ff4eb41` |

The grader fingerprint binds this packet's materialized config location and
bytes. It is not a template hash, an executed grade or the earlier packet's
identity. The new log is 1,377 bytes, SHA-256
`3bce963792a209895ddbbb0f44acd5b700d4ca59fd59a6761788fdecf58d1b76`.

| Separate observation | Actual result |
| --- | --- |
| Earlier static fixture finding | The tracked 4,142-byte fixture was not canonical Step0; no test ran at that stop. |
| `e224a750dbdbabe74490ff9c87459d14d5e01d40` | 1 collected; **1 failed in 2.06s**, exit 1, during guard installation before compiler/preparer execution. |
| `45ef631d76d2c92a1d0263e5dab9c36680939ef7` | 1 collected; **1 passed in 5.69s**, exit 0, not skipped; valid original packet observation, without the new swap cases. |
| `2d206b032f2236310b119a831303d57152323b1a` | 1 collected; **1 passed in 6.62s**, exit 0, not skipped; both exact-gap swaps refused with unchanged replacement bytes and zero temporary allocations after swapping. |

The accepted original byte pins, old log hashes, original materialized grader
`15d11db5e00cca1fa6e98b9805c52d8d0e543198f16ff90066c235f332bf4e19` and packet
`4f11ec470b33334bc7e3e073946fc58bd8e92037a82182b598c4941af483520b` remain in the
[immutable prior handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/a3362bbe484debd8c5b78263198a1dd84f6d04b8/tasks/LATEST_TASK_RESULT/README.md).
Earlier registration observations remain linked there. Counts and outcomes
are separate; no combined test total is claimed.

### Remaining gates

Branch `b/codex-retention-prepare-packet-20260929` retains base
`1c777374af6fcbd2b5a07c94585e35899dc5847e`. Its prior review `5347346570` is not
approval of this new source. Only the preparer, its existing test and two
completion records differ from the old PR head; only records change after the
tested SHA. Protected English checks preserve exact evidence and these limits.

New-head delta review and CI, serial reservation/execution, runtime-input
staging, live-source/deployment verification and separate launch direction
remain required. The packet retains `launch_authorized=false`, `commands=[]`,
`inference_slot_reserved=false`, `deadline_started=false` and
`runtime_inputs_staged=false`. No grading, live model, paid run, Azure/OIDC/HF
operation, VM, CI replay or infrastructure change ran. Preparation is not
admission.
