# Latest task result

## Directory-boundary regression passed; no empty-root defect demonstrated

The single authorized continuation reported **5 passed, 5 warnings in 0.99s**,
exit **0**; wrapper **1.408577s**. Only the missing `case` argument was added
to the parametrized test function. All other test bytes, including every
scenario and assertion, are unchanged. The real dispatcher/backend and
provenance verifiers accepted empty-root and after-write behavior and the
exact refusal cases below. No deterministic empty-root defect was
demonstrated on this source. No production correction is justified by this
result, and Task4's hidden requested path and historical cause remain unknown.

The earlier **0 collected, 1 error in 0.75s**, exit **4**, wrapper
**1.121007s** invocation remains a separate collection failure. It reached no
backend, dispatcher or verifier assertion. It is not combined with this pass.

### Reviewed and tested source

The single origin/main check matched accepted main
`4c5a32f7a0347081867fb95f94fc712bc0032ff6`, tree
`6800b87747919ea571c7908ae2b951d15a30fe20`. A fresh clean worktree was created at
`/ai-work/copilot/worktrees/codex-v2-directory-root-20261007`, on branch
`b/codex-v2-directory-root-20261007`. The leader's direction supplied the
verified Task4 facts below and authorized only the narrow directory-path
investigation. This continuation reused that worktree without another
origin/main check or source investigation. The leader reviewed the complete
failed-check record at `bdf2bbe729527b7ae057c8db44d13f2ad985e38d`, tree
`37a7a1c6413ce02734338c072aee84f61e1b1c96`, and authorized only the missing
test argument and one new invocation. No new reviewer-harness endorsement
is claimed.

Source inspection found that `canonical_relative_path` explicitly accepts
`"."`. `AgenticV2FixtureBackend._open_directory` checks root identity and returns
a duplicate of the verified root descriptor for that value. Listing depends
on `os.listdir` of that descriptor, not on whether it contains files. The
independent provenance replay initializes its directory set with `"."` too.
These are the previously recorded source observations, not a repeated
investigation. The new runtime assertions now exercise the declared root
syntax. Task4's actual requested path is unavailable in the safe projection
and was not guessed or fetched.

Test-only commit `473c04d51bd3db4ee7d23bdc81abd23fd587dae2`, tree
`fe14ba39b269782b59607f440a62e4818bb7af68`, adds only
`batch-runner/tests/test_time_budget_v2_directory_root.py`. Its five
cases cover empty `"."` followed by a synthetic write/list, file-as-directory
and missing-directory refusals, traversal rejection, and unsafe initial
symlink rejection. They use the actual scripted runner, dispatcher, backend
and success/failure provenance verifiers, not successful-verdict stubs.
Network, process, provider and private-storage entrypoints have explicit
test sentinels. None of those test-body checks ran in the original invocation.
The new test-only correction is `207604585333e73b2fce72bb55f9c4fc10236019`,
tree `62d9a24bacd876ba7ff0502018cde640be89ff7f`. The wrapper checked that its
delta from the reviewed completion is exactly the added function argument.
The corrected test SHA256 is
`177e5bd1f54bebec40a1b7c02eeeac4adb08297ba1ee654b3a8bf6122a33e38d`.
All five bodies ran in this continuation. No typed Responses seam,
kernel-ownership probe, original/private input or real model was needed.

No runtime, workflow, prompt/tool schema, compiler, registration or frozen
source byte changed. There was no necessary runtime-pin adjustment. The
current full registration seal remains
`3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`;
historical observations keep
`f3337bd80a168cf42b37314b425f5f5b221049fa87c1c15e2338de3441e0ae05` where
originally bound. No historical receipt is rewritten or relabeled.

### Exact behavioral outcomes

Five parameter cases cover six requested behaviors. These are synthetic
filesystem results, not additional study observations:

| Behavior | Exact observed assertion | Outcome |
| --- | --- | --- |
| Valid empty root | `"."` lists `{"entries": []}` with `ok=true` in a fresh empty workspace | Passed |
| After write | Root lists `{"entries": ["report.txt"]}`; finalization returns the exact synthetic bytes and the real success verifier accepts | Passed, in `empty_then_written` |
| File-as-directory | Exact `path_not_directory`, accepted by the real failure verifier; no fabricated success or finalization | Passed |
| Missing directory | Exact `path_not_directory`, accepted by the real failure verifier; no fabricated success or finalization | Passed |
| Traversal | Exact `invalid_arguments`; outside sentinel bytes remain unchanged | Passed |
| Symlink protection | Unsafe initial symlink gives exact `compute_start_failed`, stage `startup`, zero tool events, with verified failure | Passed |

Backend cleanup, unchanged outside bytes and forged-trace rejection also
passed. The positive case recorded four tool events and no runner error;
the file, missing-directory and traversal cases each recorded four tool
events with the errors above. The symlink case recorded zero. No network,
process, provider or private-storage sentinel was triggered. Ordinary
filesystem confinement is real here; this is not a kernel-ownership or
execution-host readiness proof.

### Prior collection-only failure, retained separately

At attempted source `473c04d51bd3db4ee7d23bdc81abd23fd587dae2` / tree
`fe14ba39b269782b59607f440a62e4818bb7af68`, pytest's first failure was
collection: `function uses no argument 'case'`. No body ran. No correction
or repeat was made in that original turn.

The wrapper ran only this selector from `batch-runner`:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout \
  tests/test_time_budget_v2_directory_root.py::test_time_budget_v2_directory_root \
  -m 'not integration' --tb=short -ra \
  --basetemp=/tmp/v2-directory-root-proof.Pi7089uf/pytest-tmp \
  --junitxml=/tmp/v2-directory-root-proof.Pi7089uf/junit.xml
```

The outer command was `timeout --signal=TERM --kill-after=5s 300s` with Python
`perf_counter` timing, no `-x` and no retry. Read-only source Git commands kept
their 30-second bound. The same invocation verified the exact clean source
and tree, the one-file delta and Python syntax before pytest collection.
Those static checks passed; they are not executed-test evidence. Versions were
Python 3.10.12, pytest 9.1.1, pytest-timeout 2.4.0, jsonschema 4.26.0,
openai 2.46.0, httpx 0.28.1 and huggingface-hub 1.24.0. No unavailable time
command, broad audit trap, old selector, full suite or real NAS kernel probe
was used.

All proof artifacts are in `/tmp/v2-directory-root-proof.Pi7089uf/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `55de0460cb9e94d529762c392312397a4cbab9e6a7bb63087bca7cdca3d047e6` |
| `command.json` | `384f734170a935738d693da673bb50a78eac14a09c187ca6528bc1ac8627c152` |
| `source.json` | `d3e2943d53ae3def0b44f8660059813b071d7ad02599c0988291f7bf4f6d7627` |
| `pytest.log` | `dd81ffbb50e1b2f3b8f4dab28b7cc056b42976bd0c87f57f0e38514cfb116d44` |
| `junit.xml` | `7943a977e58af5aa785a59acb7ed0540ee3d565b20ec362bd1c23e74d3872291` |
| `cases.json` | `a79aede01e33af27d3f726175fe3cc3dc54680b64912cd4531d4d35bd1648079` |
| `outcome.json` | `b72099a947fc85117e424dd8cc5ed6c7191271f9226de25e97f4323cf630462f` |

That invocation's post-check changes were limited to CHANGELOG, this record
and the direct V2 README evidence/consumed-state passage. Its completion was
`bdf2bbe729527b7ae057c8db44d13f2ad985e38d`, tree
`37a7a1c6413ce02734338c072aee84f61e1b1c96`. The original `handoff.json` SHA256
is `e164a4f556697bde4852e0f5e35d6449ea24d247a5d1e67cbeb095bfedb200c4`.
Its artifacts and source remain unchanged.

### Single authorized continuation and artifacts

At the pinned correction, the wrapper ran exactly this selector once:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout \
  tests/test_time_budget_v2_directory_root.py::test_time_budget_v2_directory_root \
  -m 'not integration' --tb=short -ra \
  --basetemp=/tmp/v2-directory-root-continuation-proof.Tj987B1r/pytest-tmp \
  --junitxml=/tmp/v2-directory-root-continuation-proof.Tj987B1r/junit.xml
```

The outer command was:

```bash
timeout --signal=TERM --kill-after=5s 300s \
  /ai-work/venvs/gdpval-realworks-py310/bin/python \
  /tmp/v2-directory-root-continuation-proof.Tj987B1r/run-proof.py
```

It used the same offline environment, explicit timeout plugin, Python
`perf_counter` timing, no `-x`, no retry and 30-second read-only Git bounds.
Python and package versions are unchanged from the failed invocation listed
above. Before pytest, the wrapper verified the clean HEAD/tree, the exact
one-line correction, syntax and unchanged runtime/workflow/registration/
prompt/frozen bytes. The selector then executed all five cases. Its five
warnings are `record_property` incompatibility warnings for JUnit xunit2;
they are preserved in `pytest.log`, not hidden by changed flags.

All new proof artifacts are in
`/tmp/v2-directory-root-continuation-proof.Tj987B1r/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `4405d916cf5d5f9fdb17e7b752c193426e71c60d28d8255a40b25f7f73e1da2e` |
| `command.json` | `0e885437d900804b79002b3efe0188d17e7c9ed2542082f3f917ad71d6f7e45c` |
| `source.json` | `df0e9eb2de6864c9021f05f5539b6a4ff0bc86518507d08e30844c1aa5a03061` |
| `pytest.log` | `60b7d7636dbb610fb574170da048037a0f5e8909babf8746765eb91cd055b85e` |
| `junit.xml` | `5496479973a5d195a4097ae91bc4e13971b4584a7dcb211dfe6c8afea67486bd` |
| `cases.json` | `d0540f1d360973434cde0aa981579f8bacbd6d0dafa75f31288e5b30ade88d52` |
| `outcome.json` | `c4aa12753392044140f4e78f10f7079bbaeb0da823e562b98fe33665a5bacb28` |

Only CHANGELOG, this record and the direct README evidence paragraph change
after the new proof. The exact final HEAD/tree, tested identity and unchanged
test hash are recorded in this directory's `handoff.json` after the record-only
commit. This is a justified test-only regression, not a production fix. No
additional selector, full suite or real kernel body was run.

### Leader-verified Task4 outcome, separate from this check

Task4 `3baa0009-5a60-4ae8-ae99-4955cb328ff3` is permanently consumed. The leader
verified run `37559598835`, attempt 1, as a canonical error, then verified the
successful read-only run `37561844854`, attempt 1, artifact `11457461122`.
The 2595-byte safe projection has SHA256
`7613c67af330fd136603b80035723948c0474a6935fd1e21f89ed2a577829622` and matched
the independently bound controller/runtime/request/result identities. These
are supplied leader observations; no CI query or private retrieval occurred
in this task.

The retained result is 6449 bytes at output commit
`380e08e7422b47fad5e1e33c97504d58c4e87f8b`, SHA256
`c2532b2c03d79938aecb0706366f873c2831f775837317398f6dfa85da2a0a60`, fingerprint
`8c1e9b7b6d5633a24492db698d850f2a5b7cba98c4a8bc1a314284dc1d5f552f`.
Both `error` and `runner_error` are `path_not_directory`;
`runner_result_verified=true`, `runner_success=false`, the required deliverable
is missing and the deliverable count is 0. Admission, cleanup and host reuse
are true; terminal reason is `failed`, with no interruption. The earlier
failure-code preservation reached this verified retained error; it does not
recover the original path or establish an empty-root cause.

Reported usage is 2462 input / 570 output tokens. Cached input 0 and reasoning
output 546 are subsets, not additional tokens. The client-construction,
Responses-create and completed-response counters are each 1; model binding
is `matched`. These fields do not establish native model-attempt counts,
money charged or a score. Native attempts and cost remain unknown.

### Remaining work and fixed limits

The missing test argument is corrected and the bounded runtime regression
passes. No deterministic empty-root defect was demonstrated on this source.
Task4's historical path and cause remain unknown; the safe projection cannot
recover them. Final source review and CI remain required. No live request,
replay, Task5 or ABBA advancement is issued.

`experiment-design` kept the question limited to directory semantics, with
synthetic inputs and no study-condition change. The existing twenty planned
observations, five tasks, ABBA ordering, GPT-5.4/direct-v1/xhigh, V2 nine-turn/
8192 settings, concurrency 1, one external attempt, 1200-second generation,
shared 20-second cleanup and 45-minute job ceiling remain unchanged. Frozen
F `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, the old source profile and
historical claims/outputs are untouched. No money hard cap is claimed.
`experiment-report-en` and `im-not-ai-en` keep the failed collection, new
synthetic result and leader-verified Task4 facts separate in these English
records. No new design or reviewer loop was performed.

Task1/Task2 remain consumed/uncertain; Task3 remains consumed with its earlier
canonical error. Task4 is retained as a failed planned cell, not zero score,
excluded data or permission to try again. No Task1-Task4 replay, Task5,
provider/grader/private-HF/Azure operation, readout execution or CI query/
dispatch/retry occurred. PR764 remains unchanged at
`6fc1992e6e4e5348a820a1f32ad32e2338004886`; its 2-passed/20.69s proof is
separate and was not repeated. [The accepted-base record][prior] preserves
the earlier failure-preservation proofs and their distinct failed invocations.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/4c5a32f7a0347081867fb95f94fc712bc0032ff6/tasks/LATEST_TASK_RESULT/README.md
