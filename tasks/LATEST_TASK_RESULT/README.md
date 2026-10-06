# Latest task result

## Test-only V2 startup gate; real-host proof pending

Added one regression in `batch-runner/tests/test_time_budget_owned_startup.py`.
There is **no production startup fix and no positive local kernel proof**.
The decisive test body was not run on known-unsupported NAS. The single local
syntax/collection/scope check ended **exit 1 in 2.874s**: syntax and scope
checks succeeded and pytest collected one node in **2.58s**, exit 0, but the
final zero-effects assertion found one blocked audit event. That failed
check is retained without a retry.

The accepted source and leader-reviewed basis are
`793c8778a75348fcb4070f2c8bec135b428ae731`, tree
`b765bf7a089b56b602aba363d615ec87f8a35a81`. The leader reviewed the retained
reproduction and authorized this one automated supported-host assertion.
No new design review or unavailable model-reviewer invocation occurred.
The test-only checked commit is `3c0325bebe439a75cc551ec5c13d547fa1e2490f`,
tree `5d682a1dba1aa7d83b72550b8b7e45a3fb40eb72`; the test file has SHA256
`eae12f848d0f4e8b13527d13b679b0820bc6280ab26cb274757d24a60ba930a2`.
The post-check delta is only this record and the CHANGELOG entry. Final
source review and ordinary final-HEAD CI remain pending. This draft must not
be merged or described as a fix until the real startup failure is understood.

## Actual Task2 uncertainty, supplied by the leader

The real selected cell was `gpt54_time_budget_v1_v2_r1` / `sandbox_v2` /
repeat 1 / `0112fc9b-c3b2-4084-8993-5a4abb1f54f1`. Run `37501571165` /
run_number 2 / attempt 1 / job `112399621053` used source `793c8778a75348fcb4070f2c8bec135b428ae731`.
Original inputs, preparation, the permanent private claim, approved login and
identity checks succeeded. Execute ran at `17:13:41..17:13:47Z` and returned 2.
Its exact safe event was:

```json
{"category":"deadline_refused","format":"gpt54-time-budget-first-v2-ci-failure-v1","reason":"time_budget_owned_process_host_required","stage":"observation_callable"}
```

Retention, envelope verification and artifact publication succeeded. The
completion remains `uncertain` with acknowledged retention; result,
fingerprint, terminal reason, usage, cleanup and host reuse are null.
`retry_allowed=false`, `grading_performed=false`, and `other_cells_executed=0`.
The static refusal code also covers later ownership rechecks. It does not
identify which prerequisite failed, establish whether a provider call
occurred, or establish a model-call count or cost. No live evidence was
queried again for this task.

| Immutable evidence | Identity |
| --- | --- |
| Permanent Task2 claim | `3def41563f98b70201dc42814bc45b4fd9f1d70c` |
| Acknowledged Task2 output | `bf82b283576411b66dfc7e962de4c587d6de4b02` |
| Request SHA256 | `e7839f57002e20ce9488fa8c6e90d6ded8f916835619c2486280faad1e03cd9a` |
| Artifact `11430455885`, ZIP SHA256 | `abe03b702245b5b438ad2fdc8cea863aac98f0ed5bec8263d9ae8954e2fce2a6` |
| Envelope SHA256 | `55edb4b7df3159f664bc5e3e577e01743f02033f55d869515ccd3fbd815bd2e4` |
| Log, 185747 bytes, SHA256 | `ee35534bbe3b89ba29850b715b81c0e4e0be74bbb0dc5bf9a5d095db0e923ee0` |

Task1 run `37456739936`, attempt 1, also remains consumed and uncertain.
Its claim `e53fe8d4c47ef2a05aea8ffcc0fe1745a9b3c288` and acknowledged output
`f602355f945471963a338ccf79783a6f802ac6dd` remain untouched. Neither cell is
a zero score, an excluded planned cell, or permission to replay or adopt state.

## Retained NAS reproduction, not rerun

The one reproduction at accepted source `793c8778a75348fcb4070f2c8bec135b428ae731`
/ tree `b765bf7a089b56b602aba363d615ec87f8a35a81` ended **19.890s, exit 2**.
It used offline Python 3.10.12 under a 300s+5s overall bound, a 60-second
child bound and the existing 30-second temporary Git bounds. Real source,
input and direction validation reached the common consumer and ownership.
One synthetic handoff was consumed; one admission was entered. No factory,
provider or generation was reached in that local reproduction; no network
attempt or reusable-host claim was recorded. These local observations do
not recover facts missing from the historical Actions attempt.

There was one kernel task before controller import and two by NumPy import
completion. Two remained through synchronous input reconstruction and
admission; `_single_threaded()` was the first unmet local admission predicate.
The timing does not identify who created the task or prove the same condition
caused the Actions failure. PyArrow was 25.0.1 with the mimalloc allocator.
Task comm names were not retained by the old script because its combined
proc read stopped at the missing children interface; the new test separates
those reads.

Before imports, NAS already returned pidfd ENOSYS 38, waitid EINVAL 22 and
proc-child ENOENT 2. SIGCHLD was default, the alarm idle, no process owner
was registered, and subreaper state was 0. These unsupported interfaces
preclude a genuine positive NAS proof. They were not patched or worked around.

Artifacts remain unchanged under
`/tmp/pr762-v2-owned-startup-reproduction.Wvs1WxG6/`:

| File | SHA256 |
| --- | --- |
| `command.sh` | `0fdafced8a1a79930fd9710666eb4c98636b4edced981e04b6b02862cc9e52b4` |
| `reproduce.py` | `3ccf9eb892fd1f8c2e5fd7cb03181cc272954f3f343b538f5fae98b21cbb77ce` |
| `startup_child.py` | `8d56b2e22d3c76d7d74244cb812058e3a0888e82482975ba66e7018823170b0f` |
| `synthetic-packet.json` | `cc1551596b3ed9fd20a5efb69156554566df8843adb05644f5a4187ef7143d24` |
| `child-command.json` | `72cbdf16f7add28716418777db242cf744d0aaa1f925df83523310078ed791ac` |
| `child.stdout`, 2814 bytes | `9deb7ea508b6554b4b57fffc07586a83a511d970001f601e3492969f06140541` |
| `child.stderr`, empty | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `result.json`, 363 bytes | `a6b9233513a3f584254d1a53f6e2636e1a10871bce0022ab39c8406c752ba66f` |
| `reproduction.log`, 3164 bytes | `90c6ebfa7f4ce1f4d2330f5fb4070b8cb2c4257c3694a858ef997efee5c9f80c` |
| `exit-status` | `53c234e5e8472b6ac51c1ae1cab3fe06fad053beb8ebfd8977b010655bfdd3c3` |

That reproduction used separately declared synthetic runtime
`d40d563f695f4326cb7a3a61cddcd04ebbd31d02`, tree
`375b905f552b2320075ebddf3029528dcdbc9a92`, and synthetic frozen input source
`530bc6cee8762116799c0bb1a212e7a1dff7fb8c`, tree
`ac0ab4e0a0a7893fffdb6b342c786f2526c625a7`. Its synthetic profile SHA256 was
`e7c44a239ead984f97c8f11e427550d96accfe6bd49c72d0d670d996b7409fc6`.
These are fixture identities, not accepted production replacements.

## Committed regression and local check

The single node is
`tests/test_time_budget_owned_startup.py::test_time_budget_owned_startup`.
It reuses the existing synthetic linked-source/input preparation fixtures,
then starts one fresh Python child with no inherited credentials. It sets
the same shipped `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`,
`MKL_NUM_THREADS` and `NUMEXPR_NUM_THREADS` values to 1, with offline HF and
telemetry disabled. Git fixture operations retain their 30-second bounds;
the child has a 60-second bound and no retry, sleep or unknown-PID cleanup.

The child imports the actual controller, reconstructs synchronous synthetic
inputs, validates the source, registration, inputs and digest-bound direction,
and calls the real consumer in an exclusive temporary synthetic store.
A construction-stop factory prevents provider effects after real admission;
the consumer's existing cleanup must complete and release its owned host.
The test requires one retained synthetic admission and consumed handoff, no
returned row and no generation. No ownership, pidfd, waitid, subreaper,
cleanup or admission method is replaced. Existing adverse-case assertions
are untouched and were not rerun.

Fixed nonsecret JSON diagnostics report kernel task counts and comm names,
child counts, SIGCHLD, pidfd/waitid outcomes and errno values, subreaper
state, the first observed failed prerequisite/operation, and installed NumPy
and PyArrow versions before/after relevant imports and reads and immediately
before admission. The diagnostics are observations, not admission authority.
Unexpected exception text, tracebacks, paths and environment contents are
not forwarded by the child. Refused or unsupported admission fails the test;
there is no skip, xfail or passing-refusal substitute.

The only local check was:

```sh
bash /tmp/pr762-owned-startup-collection.8RG6XJey/command.sh
```

The retained command uses offline Python 3.10.12 with a 60s+5s bound and
no `-x`. Its syntax and source-scope checks precede this exact in-process
pytest argument list, from `batch-runner`:

```text
--collect-only -q -o addopts= -m "not integration" -p pytest_timeout -p no:cacheprovider tests/test_time_budget_owned_startup.py::test_time_budget_owned_startup
```

Pytest 9.1.1 and pytest-timeout 2.4.0 were already installed; no dependency
changed. Pytest returned 0 after collecting exactly that node in 2.58s.
Fixture entries and test-protocol entries were both 0. The overall check
returned 1 in 2.874s because the process/socket audit guard recorded one
denied event. The first retained failing assertion checks that all three
counters, including denied effects, are zero. The harness did not save the
event name, so its precise operation cannot be recovered from this output.
This is a failed local check, not a passing behavioral or kernel proof, and
not evidence that a connection was made. Neither the check nor the decisive
body was rerun.

Artifacts are under `/tmp/pr762-owned-startup-collection.8RG6XJey/`:

| File | SHA256 |
| --- | --- |
| `command.sh` | `c1db86c1ab3ba6244c619c936a397a2b70fd2a22409b6fa97d14210f9919c75c` |
| `check.py` | `fe9c149909ed9839a02c121ac4a5ef7f63c95e15f4b2db8216220111fbb2c5af` |
| `collection.log` | `26841e7d19d45f3b278858b2513db7085ca189cb1430535ffc31edf4b7c619bd` |
| `result.json` | `ca45695c9077edde4a1b60122572f932582a752b2fb2073bb32a579c8a1cea73` |
| `exit-status` | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |

## Remaining gates and unchanged boundaries

Ordinary existing `time-budget-contracts` CI selects this filename and runs
on `ubuntu-latest` with Python 3.10.12. Its result remains pending and must
be labeled that host. It is not the actual observation workflow's
`ubuntu-22.04` host; production execution-host readiness remains a later gate
even if CI admission succeeds. A failure must retain its safe diagnostics
before any source-grounded correction is considered. No workflow was added
or changed, and no CI query, dispatch, retry or polling was performed.

Production, dependencies, frozen F, experiment settings and all previous
worktrees are unchanged. The registered 20 planned observations, five-task
cohort, ABBA order, GPT-5.4/direct-v1/xhigh, V2 nine-turn/8192-output settings,
concurrency 1 and one external attempt remain fixed. Generation retains
1200 seconds from first start and the same shared 20-second cleanup; the
actual V2 job remains 45 minutes. These are not money caps or guarantees
of remote cancellation. The frozen grader stays
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`; real intake, source/host admission,
permanent claim/CAS and separate grading gates remain unchanged. No new
live cell, Task1/Task2 replay, Task3 execution or grade is authorized.

The [prior accepted-source record][basis] and its [earlier proof record][proof]
retain their separate source, CI, collection and synthetic results. None
was rerun or aggregated into this check. The original 30-cell pilot, eight
retention observations and #649 remain closed. Experiment-design was used
only to preserve these boundaries; English evidence editing preserved the
observed results, uncertainty and immutable identities.

[basis]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/793c8778a75348fcb4070f2c8bec135b428ae731/tasks/LATEST_TASK_RESULT/README.md
[proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/e817d592ca0e38be29d26da4122d5b6d7ed7395f/tasks/LATEST_TASK_RESULT/README.md
