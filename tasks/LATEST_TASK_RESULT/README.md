# Latest task result

## PR761 retry-probe cleanup continuation

The retry fixture now closes its SDK, invokes the existing descendant sweep,
and only then removes its workspace. This correction is unverified: the one
authorized local proof launch failed before pytest because its wrapper used
an unavailable `/usr/bin/time`. No selected node ran, and no retry was made.

### Original CI evidence

The leader read run `37497507989`, job `112385735261`, at
`2fe4adf221078c9b36ec53fdb6d76cce31f8ce10`. Pytest completed with **1 failed,
13391 passed, 64 skipped, 46 deselected, 1 warning in 1982.61s**; ten other
checks succeeded. This was a completed test failure, not a timeout. Its
219971-byte log has SHA256
`dcf8b8d537c76243118ecbb8a6319d1addcac76fb72e22225e2092132f7eec2a`.
These are leader-supplied observations; this task did not query CI.

The failed node was
`tests/test_codex_retry_pins_are_enforced.py::test_leaving_the_counters_unset_multiplies_one_turn[500-False-20]`.
Its `_one_turn` finally block called `workspace.cleanup`, which reached
`core/codex_runner.py:521` and `shutil.rmtree`. The reported failure was
`OSError` errno `39`, `Directory not empty`, at
`codex_home/.tmp/plugins-clone-.../plugins/zoom/skills`. No request-count
assertion was reported as failing. A still-active plugin writer is a
hypothesis consistent with that path, not a demonstrated process identity or
historical cause.

### Correction and source identities

| Identity | Exact value |
| --- | --- |
| Leader-inspected starting head | `2fe4adf221078c9b36ec53fdb6d76cce31f8ce10` |
| Starting tree | `e311f122e6a01361b5e243c410e73af7b9a7a871` |
| Pinned fixture correction / attempted test source | `bebce09ff6893ed6308127df36c14e4c2bc7ce97` |
| Pinned tree | `c5a10eed1d0c0106a9903edf1141032d3f5683d0` |
| Changed test blob | `6df7d5909b57188fbed49b4abd81a22a9c442cea` |

The existing native worktree was clean and fast-forwarded to the exact
leader-created single-parent continuation before editing. The only code
change is in `batch-runner/tests/test_codex_retry_pins_are_enforced.py`.
`_one_turn` snapshots descendants before opening its runtime, then reuses
`sweep_orphans(before_pids)` after SDK close and before workspace deletion.
Pre-existing children remain outside that sweep. SDK close, sweep and
workspace cleanup errors propagate; there is no deletion retry, ignored
cleanup failure, added sleep or process-name kill.

The stream is still consumed against the real local refusing server. The
synthetic token printer, provider/auth isolation, pinned SDK/CLI and the
original `overran` and request-count assertions are unchanged. The selected
HTTP 500 case still requires at least 20 requests with counters 4 and 5.
One added regression uses real owned child handles and the real sweep to
check close/sweep/removal order and preserve a pre-existing child. Only its
SDK transport is replaced. It fails explicitly if enumeration cannot see a
known live child; an empty unsupported listing is not clean-host evidence.

Production, core, native observation, provider settings, counters, ownership,
workflow, manifest, frozen F and experiment settings are unchanged. PR762 and
all preserved worktrees were left untouched. The leader's source-grounded
direction governs this limited correction; no new design or model-review
loop was run. Final source review is still required.

### One local proof attempt

The clean pinned source was selected for these two nodes only:

```text
tests/test_codex_retry_pins_are_enforced.py::test_leaving_the_counters_unset_multiplies_one_turn[500-False-20]
tests/test_codex_retry_pins_are_enforced.py::test_runtime_descendants_finish_before_workspace_removal
```

The exact command is retained in
`/tmp/pr761-retry-cleanup-proof.oyHpxk/command.sh`. It specifies the existing
Python 3.10.12 interpreter, an isolated offline environment, the explicit
timeout plugin, a 300-second ceiling plus 5-second kill grace and no `-x`.
Installed package metadata was read as pytest `9.1.1`, pytest-timeout `2.4.0`,
openai-codex `0.147.0` and openai-codex-cli-bin `0.147.0`.

The single launch was `bash /tmp/pr761-retry-cleanup-proof.oyHpxk/command.sh`.
It exited **127** at line 8 with `/usr/bin/time: No such file or directory`,
before the timeout command, interpreter or pytest started. Both timestamp
files contain `2026-10-06T18:49:51Z`. There is no measured pytest duration,
JUnit report, node collection or execution result. Cleanup order, process
enumeration support and native request counts remain unproved locally.
This launch is not a test pass, a skipped positive or a host-support verdict.

| Retained artifact under `/tmp/pr761-retry-cleanup-proof.oyHpxk/` | SHA256 |
| --- | --- |
| `command.sh` | `59387487c32966bc4d757a330ade53d245dc4aad010ac7491e15910997668337` |
| `source-and-environment.txt` | `22acefdef20a5f517b00dd8c95c2798a1df51e849e9d24c1b8c1de4dae3b41d3` |
| `pytest.log` | `622780fbfd1284f1c6a79c28f948c5258dcf82ac8bc3e3c6e78be73683ff602e` |
| `exit.txt` | `bd86e875b9555a045f96c9475726ab0b84fd0cf6e76de54ac8dbd64845613399` |
| `started-at.txt` and `finished-at.txt` | `1c3f8f81a0ddf2801fdb5ed4822ab22ad5a0d0d3578d48337cc1dd115a0098ad` |

`outcome.md` records the failure boundary. `junit.xml` and `timing.txt` were
not produced. No proof command was repeated or extended. After the failed
launch, only this record and `CHANGELOG.md` changed; the pinned test blob is
unchanged. The final commit/tree and artifact hashes are supplied in the
handoff, without recording the carrying PR's future integration state.

### Separate evidence and remaining gates

The earlier native callable proof remains **9 passed in 22.91s** at
`c6c8b2135f7e363d6c3371f023187641dbc0802f`, tree
`4f14c866b6b05def538e05ca9296b75837e78e73`, with its [own record][native].
The reused CI partition and previous ceiling failure retain their
[separate record][partition]. Neither proof was repeated or aggregated with
this unstarted invocation or the leader-read completed CI failure.

The correction still needs behavioral validation, final review and new-HEAD
CI. Main integration remains leader-owned. Trusted-controller integration,
real host/input/Step0/auth/path checks and a separately issued live direction
remain gates for the native observation capability. The 20-cell registration,
one attempt, 1200-second generation, shared 20-second cleanup and 45-minute
CI/observation job limits are unchanged. Historical V2 Task1 and Task2 remain
consumed/uncertain; no model-call count, cost, zero score, replay or Task3
authority is inferred. No private data, live provider, model or grader
operation occurred. English records were checked with `im-not-ai-en`, with
all failure boundaries and evidence kept intact.

[native]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/9183232103be1e46b654be76143c349b0cf0f425/tasks/LATEST_TASK_RESULT/README.md
[partition]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/2fe4adf221078c9b36ec53fdb6d76cce31f8ce10/tasks/LATEST_TASK_RESULT/README.md
