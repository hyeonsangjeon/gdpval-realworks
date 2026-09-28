# Latest task result

## PROJECT5-DETERMINISTIC-BIRTH-EDGE

One combined offline invocation at
`eb9971b1b8ce94e559481d56dd6cdbe1ca854c61` passed all four selected nodes
in 1.02s, exit 0. The new regression reproduces a defect in the former test
double and checks the corrected ordinary-launch path. The existing positive
checks the fake `TimeoutExpired` path; two existing negatives preserve the
pre-existing-PID and missing-PID refusals. The original CI cause remains
unknown. This deterministic reproduction does not recover its missing evidence.

### Scope and deterministic evidence

Only `batch-runner/tests/test_agentic_v2_first_boot.py` and the two current
records change relative to `dac0421ca5b05d35eae85a9b666eb351a9f84744`.
`_Clock.host_reading` supplies synthetic ticks. `_boot` stamps each known
stand-in's immutable birth during the fake jailer call, after the launch floor
and before PID publication, including when the jailer raises `TimeoutExpired`.
Ordinary and pinned-reference probes return that same birth without sampling
the real host clock. The elapsed wait clock and both signal spies are unchanged.

The regression captures floor `100`, fake launch `101` and PID-read ceiling
`102` before the former lazy probe has invented a birth. The unchanged
`_started_during_this_runs_launch` reads boot identity at tick `103`, then the
lazy probe stamps birth `104`. Its exact refusal is:

```text
process 4242 began 2 clock ticks after this run already had that number in hand, so it is not what the number was published for
```

The fixed ordinary and timeout paths keep birth `101` between floor `100` and
ceiling `102`; later ordinary and pinned-reference probes still agree. The
timeout assertion still requires exactly `[(4242, SIGKILL)]`, with `pidfd`,
verdict `taken`, target `4242` and null `left_alone_because`. It now includes
safe interval/handle/refusal details if the signal assertion fails.
All production, ownership, anti-PID-reuse, confinement, handle, cutoff, guard,
image, workflow, pin and registration bytes remain identical to `dac0421ca5b05d35eae85a9b666eb351a9f84744`.
No real PID was signalled, and no guest process or VM was launched.

### Exact invocation and result

All four owning definitions were checked statically. From `batch-runner`, the
sole invocation was:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p no:cacheprovider --tb=short \
  tests/test_agentic_v2_first_boot.py::test_synthetic_birth_tick_edge_refuses_lazy_identity_and_accepts_launch_birth \
  tests/test_agentic_v2_first_boot.py::test_this_runs_own_machine_is_stopped_when_it_is_still_running \
  tests/test_agentic_v2_first_boot.py::test_a_pid_file_that_was_already_there_is_not_this_runs_to_kill \
  tests/test_agentic_v2_first_boot.py::test_a_launcher_that_times_out_leaves_the_jail_and_says_why
```

```text
collected 4 items
============================== 4 passed in 1.02s ===============================
pytest exit status: 0
```

The new log is `/tmp/project5-deterministic-birth.M3m9ws/pytest.log`. No other
pytest invocation ran in this task. No passing CI check was rerun or polled.

### Original CI and unchanged local observation

At `dac0421ca5b05d35eae85a9b666eb351a9f84744`, the leader reported 13 passing
checks and only pytest failing. CI run
[36486057815](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36486057815),
job `109143110210`, reported 1 failed, 13284 passed, 61 skipped and 46 deselected
in 1445.06s. The owned-machine positive expected `[(4242, SIGKILL)]` but saw
`[]`. CI omitted `caught.value.teardown["process"]`, so the exact refusal and
original cause remain unknown.

The earlier unchanged local observation passed once in 0.67s, exit 0, with
read-only profiling at that same SHA. Floor, ceiling, birth and pinned birth
were all `361895512`; jail/confinement checks passed and `pidfd` was `taken`
for `4242`, with `signalled=True` and null `left_alone_because`.
`confirmed_stopped=False` matched the deliberate `_still_running=True` fixture.
That diagnostic task made no code change, commit or push. Its observer,
`/tmp/project5-owned-process-boundary.PtI0GO/observe_once.py`, used the same
offline environment to profile only the owned-machine positive; its SHA-256 is
`6ec80bee0e704c55d7617c7e6b642097ab3db4e84c63ed6c06d1f2d48f73d8a6`.
The observer, safe diagnostic and CI log remain in that session directory.
Neither this prior pass nor the new reproduction proves nondeterminism in CI.

### Separate local validation observations

These are distinct PR698 invocations, not combined totals or a claim that a
single full selector passed. Earlier stops without an invocation add no result.

| Tested SHA | Actual result | Exit |
| --- | --- | --- |
| `b1854e5b50eda9c25c9db5bc2627acf35022e70d` | 5 failed, 42 passed in 334.92s | 1 |
| `91ffae589b240dd9d31978af0dd2cf19532e96c7` | 5 passed in 24.02s | 0 |
| `6710299c5776c30ccf3927a1f8a54c6ee4ffab09` | 3 passed, 1 setup error in 93.52s | 1 |
| `6665c183c215aa6594622eb9fe92ca55633c7013` | 1 setup error in 8.44s | 1 |
| `7bbe61f7880ce0bdb3a130fbf8f89856cb8efc27` | 3 passed in 49.11s | 0 |
| `88b8a62b4b5f4802f6fc22c25b9348d78a931f65` | 3 passed in 9.04s | 0 |
| `3fdc5a95853619135d4165063392144eb6fea540` | 8 passed in 26.06s | 0 |
| `1fa84f2b2cff4d51a323aabd2051130fd8b119c8` | 3 passed in 61.92s | 0 |
| `3188e27a2eac24fd7ed3f3e074c9a088ad7d79e0` | No tests ran; selector not found; 7 collected; 5.49s | 4 |
| `3188e27a2eac24fd7ed3f3e074c9a088ad7d79e0` | Corrected owner: 8 passed in 139.10s | 0 |
| `93e96b342386482cb9e7f60805781f0009620629` | 3 passed in 16.55s | 0 |
| `dac0421ca5b05d35eae85a9b666eb351a9f84744` | Unchanged node, read-only diagnostic profiling: 1 passed in 0.67s | 0 |
| `eb9971b1b8ce94e559481d56dd6cdbe1ca854c61` | Deterministic edge and fixed paths: 4 passed in 1.02s | 0 |

The [two-boundary fixture result and preceding CI evidence](https://github.com/hyeonsangjeon/gdpval-realworks/blob/dac0421ca5b05d35eae85a9b666eb351a9f84744/tasks/LATEST_TASK_RESULT/README.md),
[49-file fixture scope and both selector attempts](https://github.com/hyeonsangjeon/gdpval-realworks/blob/5d35dc440cdf7cdf2b53cc61ebd6a55ff9549350/tasks/LATEST_TASK_RESULT/README.md),
[complete prior handoffs](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/tasks/LATEST_TASK_RESULT/README.md),
[54-module inventory and prior CI results](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/tasks/LATEST_TASK_RESULT/README.md#project5-final-legacy-fixtures)
and [prior changelog](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/CHANGELOG.md)
remain immutable Git evidence. Session artifacts, including
`/tmp/project5-final-legacy-fixtures.S8DFVq/failed-nodes.tsv`, were preserved.
Historical handoffs are linked here rather than copied into this current record.

### Remaining gates

The original CI refusal category remains unavailable. The reproducible fixture
defect justifies this test-only correction, not a claim of recovered CI
forensics or a blind CI replay. Leader
[review 5345028254](https://github.com/hyeonsangjeon/gdpval-realworks/pull/698#pullrequestreview-5345028254)
is conditional on all CI, not a waiver, approval of a future delta,
authorization of modified runtime for the old campaign, or launch authority.
The new HEAD for draft
[PR698](https://github.com/hyeonsangjeon/gdpval-realworks/pull/698) still requires
delta review and CI. The capability remains unregistered and live-unverified.
No model, live readout, Azure, OIDC, HF credential or paid operation, VM,
infrastructure change, new campaign, CI rerun/poll or merge occurred.
