# Latest task result

## PR762 prospective Arrow startup configuration

The V2 workflow now sets `JE_ARROW_MALLOC_CONF=background_thread:false` at
job startup, before Python imports. Only the `time-budget-contracts` job's
runner label changes from `ubuntu-latest` to production's `ubuntu-22.04`.
The strict ownership gate is unchanged. The fresh-child regression reads
the actual V2 workflow's static environment and asserts the shared host and
45-minute ceiling; it does not supply an independent test-only allocator
setting. This is a prospective infrastructure correction, not a new study
condition or a claim of identical timing.

The installed Arrow prefix was verified statically. The one local validation
invocation then **failed, exit 1, in 22.966132s**: syntax/scope checks passed,
the real-kernel node was collected without execution, and the four contract
nodes recorded **3 passed and 1 failed**. The proof guard blocked an existing
argv-only Bash check. No retry or post-proof code change followed. Real
admission and cleanup on the new Ubuntu 22.04 CI host remain pending.

### Reviewed basis and exact source

| Identity | Value |
| --- | --- |
| Leader-inspected starting source | `c41291dda23581318d904815a1af2af792d726c9` |
| Starting tree | `2d1a54d33b2a569317a70f35f25bd840ee7d55a1` |
| Accepted main basis | `793c8778a75348fcb4070f2c8bec135b428ae731` |
| Main basis tree | `b765bf7a089b56b602aba363d615ec87f8a35a81` |
| Tested implementation | `12a0309592d4d5780ffa123eda889fddc2c70d4d` |
| Tested tree | `bc847003bf690a09e33b81dedad5306804078cce` |
| Backend workflow SHA256 | `ff89fe6ffc6bfda1ed151fd8b4d6a49aeada28fd97b7a7271be45b9e943785f4` |
| V2 workflow SHA256 | `849b316dc4011c41ecfa2263d8305bc548860cdf2977dcdf99e714409a1ed721` |

The existing PR762 worktree was clean at that starting source. The leader
performed the source-grounded CI/cost decision approving this bounded
change. The mandatory allocator-review invocation failed before execution
because of the unavailable legacy Opus preference. It was not a successful
spawned review; no harness retry, model-setting change or new design loop
was performed. PR761 remains untouched at
`55639ee4f642a4f951909a3d4e066eee3776cfd7`.

The five-file implementation changes two workflows, the existing startup
test, and only the current backend hash/runner expectations in the two
coupled CI-contract test files. All other parsed workflow fields are equal
to the starting source. The historical reconstruction still validates and
removes the time-budget job and its single ignore token before comparing
`fd2871a0ec60895d50fd16650a0ddfe47b71634a53fe0164b2fb765ea3319c47`.
HISTORICAL, FOUNDRY, frozen F and registered source-profile hashes are unchanged.
No exact V2 environment assertion in another test file required modification.
The new static contract checks the environment used by the existing child.

### Confirmed hosted startup blocker, supplied by the leader

Run `37511729194`, job `112434320613`, at the starting source completed
**1 failed, 239 passed in 621.38s** on `ubuntu-latest`. The 127428-byte log
has SHA256
`f7c6b88aabcb624c891f977c1359937714620971ad30e38913a6b9240dcf3825`.
No CI query or download was made for this continuation.

Before controller import there was one kernel task, `python`. By NumPy
completion, and through PyArrow/Pandas/datasets, the synchronous reader,
reconstruction and admission, there were two: `python` and
`jemalloc_bg_thd`. NumPy was 2.2.6 and PyArrow was 25.0.1. Actual pidfd open,
signal 0, waitid ECHILD and proc-child interfaces worked; child count and
subreaper state were 0 and no owner existed. The first real refusal was
`_single_threaded`. Admission receipts, construction stops, network attempts
and process refusals were all 0. This identifies an allocator background
thread in this CI reproduction. Import chronology does not establish that
NumPy created it, and this is not a historical Task2 cause, call-count or
cost diagnosis.

### Static Arrow identity and setting

The 30s+5s-bounded static check completed successfully in **0.512644s** using
Python 3.10.12. It read wheel metadata and binary bytes only; it did not
import Arrow/NumPy/Pandas/datasets or execute any kernel body.

| Installed artifact | Identity |
| --- | --- |
| PyArrow | `25.0.1` |
| Wheel tag | `cp310-cp310-manylinux_2_28_x86_64` |
| Binary | `/ai-work/venvs/gdpval-realworks-py310/lib/python3.10/site-packages/pyarrow/libarrow.so.2500` |
| Binary size | 55368864 bytes |
| Binary SHA256, matching wheel RECORD | `169a4b46f606daa5a9c142c64f7b35c516bd60c63b6a9699d25099e96dc8ecec` |
| Distribution METADATA SHA256 | `12ed8d0988a6f7153fec923ee47b7fc1d6134463a86b1b89fa36f24c250163ff` |

The binary contains the null-terminated `JE_ARROW_MALLOC_CONF` at byte offset
34846167, `background_thread:true` at 35967669, and the
`je_arrow_malloc_conf`/`je_arrow_mallctl` symbols. This verifies the exact
prefix described by the leader's Arrow memory-pool/toolchain and jemalloc
5.3 source trace. It does not measure the setting's runtime effect. The
workflow uses that prefixed startup setting, not unprefixed `MALLOC_CONF`,
a memory-pool switch after import, native mallctl, thread killing or a
relaxed ownership check. Dependency versions were not changed.

### One bounded local validation

```sh
bash /tmp/pr762-arrow-startup.rY7mXj/command.sh
```

The command uses the existing Python 3.10.12, pytest 9.1.1 and pytest-timeout
2.4.0, with one overall 300s+5s/no-`-x` bound. Source reads keep the 30-second
Git bound. Timing uses `time.perf_counter`, not `/usr/bin/time`.

Syntax and scope checks verified the exact five changed paths, parsed YAML
delta and unchanged kernel/diagnostic/validator bodies. Collection selected
only `tests/test_time_budget_owned_startup.py::test_time_budget_owned_startup`
in 2.49s, with 0 fixture entries, 0 test-protocol entries and 0 denied effects.
No real-kernel body ran on the known-unsupported NAS.

The single contract invocation selected exactly:

```text
tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_preserves_history_foundry_and_backend_partition
tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_budget_readout_partition_preserves_exact_commands_and_guards
tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts
tests/test_time_budget_owned_startup.py::test_time_budget_owned_startup_workflow_contract
```

JUnit retains all four outcomes: **3 passed, 1 failed, 0 skipped, 0 errors**,
with duration **19.963s**. The budget-readout node failed at its existing
`subprocess.run` on line 484. The validated `/bin/bash --noprofile --norc`
script replaces `python()` with an argv-only `printf`; the proof-only audit
guard refused its `subprocess.Popen` because it allowed only nested pytest
collection. Bash did not start. The guard's final zero-denied-effects
assertion also failed, so pytest's normal terminal summary did not finish.
The node remains failed even though it had already reached the historical
canonical-hash comparison before that operation. No assertion was weakened,
no harness correction was applied and no successful case was repeated.

The other three nodes passed. Six nested collection-only subprocesses came
from the existing partition test. These are contract/collection outcomes,
not a full CI pass, successful startup, live input verification or an
ownership/admission/cleanup verdict. The guard recorded one denied process
event and no network event. `result.json` records the overall failed phase;
JUnit and the session records retain the completed individual outcomes.

| Artifact under `/tmp/pr762-arrow-startup.rY7mXj/` | SHA256 |
| --- | --- |
| `arrow-binary.json` | `0d1c0f89dac486fb8d2fadb91583ab04e863e3fb09810f2e5ddd5dba056764dd` |
| `command.sh` | `891b2303fbfbc5a3a95acf14ac7706c23b32bd7d10b475d288b2870f732ddfab` |
| `check.py` | `8ffde0e9ae84d15afa9c8c87259dce8c7f17f199e549781655a328da5fa7d88a` |
| `startup_contract_guard.py` | `6162be5108257af6519e7fbcf032b1b29d7bb3bb3e224d019f95f948ed4b8f58` |
| `validation.log` | `8e9377840d666f1f9a9210a1ffc27e07e4a31b0c27ab160a7b5179beb5dbd849` |
| `result.json` | `13178c125417e9c3af2181283735fda524fc6e3f38cb8d8bc19d544d0994ea05` |
| `junit.xml` | `556bb3aabf9e923d649f974d091d608cb726950422655208dd71f954f5ec04eb` |
| `exit.txt` | `88b555aaa75b49fc5c1f5b70ba78c3f9f641894bd5b38628a452f464b226be1d` |

Exact collection/test argument arrays and per-process session records are
retained alongside these files. The final handoff identifies the final
HEAD/tree and artifact manifest. Only CHANGELOG, this record and the direct
README usage section change after the proof; implementation bytes stay pinned.

### Prior evidence, historical cells and remaining gates

The [immutable prior record][prior] retains the full source/artifact hashes
for the **19.890s, exit 2** NAS reproduction and the separate **2.874s,
exit 1** collection/sentinel check. Neither was rerun or became a kernel
positive. NAS pidfd ENOSYS 38, waitid EINVAL 22 and proc-child ENOENT 2 remain
unsupported interfaces; none was patched or bypassed. PR761's separate
`/usr/bin/time` exit 127 remains an unstarted proof, not a test verdict.

The prior record also retains Task2 run `37501571165` / run_number 2 /
attempt 1 / job `112399621053`, source `793c8778a75348fcb4070f2c8bec135b428ae731`,
and all request, artifact, envelope and log hashes. Its permanent claim is
`3def41563f98b70201dc42814bc45b4fd9f1d70c`; acknowledged output is
`bf82b283576411b66dfc7e962de4c587d6de4b02`. Execute returned 2 with safe reason
`time_budget_owned_process_host_required`. Task2 remains retained uncertainty
with null result/fingerprint/terminal/usage/cleanup/host reuse, retry false,
grading false and other cells 0. Task1 also remains consumed/uncertain with
claim `e53fe8d4c47ef2a05aea8ffcc0fe1745a9b3c288` and output
`f602355f945471963a338ccf79783a6f802ac6dd`. Neither cell is removed from the
planned denominator, treated as a zero score, replayed or adopted. No
historical model-call count, cost or exact first failing prerequisite is inferred.

Final review and new-HEAD ordinary CI must establish real admission and
cleanup on `ubuntu-22.04`; no manual dispatch/query/retry/poll was performed.
Actual execution-host readiness, accepted source, immutable input/direction
and per-observation claim/CAS remain later leader-owned gates. No live Task3
or replay authority is issued. Core/readers, source/input/provider controls,
ownership/pidfd/subreaper/ECHILD semantics, credentials, permissions, other
jobs and their selectors/receipt producer are unchanged. The fixed five-task,
20-cell ABBA study, GPT-5.4/direct-v1/xhigh, V2 nine-turn/8192-output settings,
concurrency 1, one external attempt, 1200-second generation and shared
20-second cleanup remain fixed. V2 and time-budget CI retain 45-minute
ceilings. Experiment-design was used only to preserve those boundaries and
identify the prospective infrastructure change; no timing equivalence is
claimed. English records were checked with `im-not-ai-en` without changing
the evidence or uncertainty.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/c41291dda23581318d904815a1af2af792d726c9/tasks/LATEST_TASK_RESULT/README.md
