# Latest task result

## PR755 checkout CURRENT reader-refusal correction

The omitted CURRENT expectation in the disposable-checkout launch-boundary
test is corrected. One offline invocation of the sole failed node reported
**1 passed in 2.82s**, exit 0. The first-cell adapter is unchanged. Delivery
still requires corrected-HEAD review and CI acceptance; this proof grants no
live authority.

### Scope and reviewed basis

Work started from clean `c766c3b80365d1ff4c7b1dc1e1a91bef569c7b9f`, tree
`b7ca9c4593db5b08aa08b778163940e8b7c1adaa`, on the existing
`b/codex-time-budget-first-v2-entrypoint-20261006` branch. The leader's
[source review 5423001724][source-review] and
[CI/source finding 5423178464][finding] supplied the reviewed basis and exact
omission. PR756, other worktrees and prior evidence remain untouched.

The only test change adds
`source_pin:batch-runner/gpt54_prepared_input_attestation.py` at index 4 in
`tests/test_gpt54_disposable_checkout.py::test_comparison_runtime_launch_boundary_current_source_bindings`,
after `gpt54_run_config_bundle.py` and before `gpt54_run_input_bundle.py`.
Every other expected refusal remains in order.

Before editing, the primary worker applied the established source-role
guidance: CURRENT R legitimately differs in the reader; the genuine positive
compilation uses `frozen_local_comparison_source`. The correction preserves
that fixture, its historical source/profile/template hashes, the real
validators and the final `launch_allowed` / `full_220_allowed` false
assertions. No production, configuration, workflow, usage README, source pin,
frozen profile, core, grader, adapter or launch gate byte changes.

### Supplied CI evidence

At reviewed `c766c3b80365d1ff4c7b1dc1e1a91bef569c7b9f`, the leader read completed
[comparison-contracts run 37400663932, job 112067100288][ci-failure], attempt 1:
**1 failed, 1462 passed in 1855.84s**. The sole failure was this expected-list
omission; the preceding genuine F compilation had completed. All other
applicable checks succeeded. The supplied raw-log SHA256 is
`4d8a7ad0f73bbc05cd2dcd9a8274c17b2bb175fbfe1aee57e623e33a19aa833c`.
The downstream host receipt refused only for `comparison_step_not_successful`.
That refusal is neither a new kernel finding nor positive-host evidence.
These are supplied CI facts, not a new local run or a CI query.

### One bounded local proof

Tested correction: `8e37ed79df606f7eee3eccfed557a42de5ddb573`, tree
`5974a01e2868caaab34ccab77855c5e79395179f`. This commit contains exactly one
test-line insertion relative to the reviewed basis. The retained command file
checked the exact HEAD/tree and clean worktree, confirmed Python 3.10.12, then
ran this invocation from `batch-runner`:

```bash
timeout --signal=TERM --kill-after=5s 300s \
  env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -o addopts= -p no:cacheprovider -m 'not integration' \
  -vv --tb=short --color=no \
  --basetemp=/tmp/pr755-checkout-reader-refusal-proof.NYwDGg/pytest-tmp \
  --junitxml=/tmp/pr755-checkout-reader-refusal-proof.NYwDGg/junit.xml \
  tests/test_gpt54_disposable_checkout.py::test_comparison_runtime_launch_boundary_current_source_bindings
```

Exactly that node completed and passed. Pytest reported **1 passed in 2.82s**,
exit 0; JUnit records one test, zero failures, zero errors and zero skips.
There was one invocation, no `-x` and no rerun. Artifacts remain at
`/tmp/pr755-checkout-reader-refusal-proof.NYwDGg/`:

| Artifact | SHA256 |
| --- | --- |
| `command.sh` | `cea99b66d9bb8bb54d04446a18ee9a9d9bf44059ab0c002dc2ac1e57e9c86497` |
| `output.log` | `24e0c8280e1b781ff27ee1c05b8181c745c43b35213255f681f112a8eb4a1a80` |
| `junit.xml` | `a81dfe12126b05c754b21f87ecfb537fb6042edc1d712b1b8e4d17d6061a1861` |
| `receipt.json` | `de63988f331b1b601414946f64cdb42c342ce211820b4af7f0611c38aab780d3` |

The command digest identifies the complete retained file, including its source
guards, not the shorter displayed invocation or redacted public command text.
The exact post-proof repository delta is `CHANGELOG.md` and this LATEST record
only. No further test or source change follows the pinned proof.

### Distinct prior evidence and remaining gates

The [immutable prior correction record][prior] retains the original
`a1380d827814699265e1406cc8e84b0f6187b87a` invocation: **32 passed, 1 failed in
81.67s**, exit 1. All five roundtrips were synthetic, not real execution.
The separate [fixture correction][fixture-correction],
`9cf4429c377449e98b2c595703d873622c3390dc`, remains unrerun locally. The same
record preserves the prior **2 passed in 2.15s**, exit 0, at
`53d17831df0bc3fd569c00baeffb6ac34d5c5d7c`, tree
`aed06bccd29064dc4feca872f4945397529aab21`, and links the distinct 53/41/8-case
proofs, earlier deadline/ownership evidence, NAS refusal and model-free CI host
outcomes. Those observations, the supplied CI failure and this one-node pass
remain separate. No aggregate 33-pass result is claimed. No prior selector or
platform probe was repeated; all original command/log/JUnit/receipt files
remain intact.

The catalog was checked once. `im-not-ai-en` applies only to the changed English
records, protecting counts, source identities, hashes, links, failed
observations and pending gates. No experiment-design rerun or new readiness
investigation was needed.

Remaining gates are corrected-HEAD review and applicable CI acceptance. Before
any live observation, genuine independent source/input/preparation/host values
and a source-bound execution direction are required. Actual-host admission
remains mandatory; live grading is separate. Neither source review nor this
test supplies execution permission. No CI query, dispatch, retry, polling or
waiting occurred. No private-input operation, provider/model/grader/HF/Azure
operation, Project edit, merge or launch enablement occurred in this task.

[source-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/755#pullrequestreview-5423001724
[finding]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/755#pullrequestreview-5423178464
[ci-failure]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37400663932/job/112067100288
[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/c766c3b80365d1ff4c7b1dc1e1a91bef569c7b9f/tasks/LATEST_TASK_RESULT/README.md
[fixture-correction]: https://github.com/hyeonsangjeon/gdpval-realworks/commit/9cf4429c377449e98b2c595703d873622c3390dc
