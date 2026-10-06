# Latest task result

## PR755 CURRENT reader-refusal correction

The omitted CURRENT reader-refusal expectation is corrected. One offline
invocation of the two failed parameters reported **2 passed in 2.15s**, exit 0.
The adapter and its earlier proofs are unchanged. Delivery remains pending
final-HEAD review and CI acceptance; this proof grants no live authority.

The existing branch is `b/codex-time-budget-first-v2-entrypoint-20261006`.
The leader reviewed `b6ba71115c36075acde2c8f2cece1a3de28cc180`, tree
`db706ece066c2a5bacdca257242a10357ceb8a6f`, including the adapter, reader/default
split, prospective bindings, tests and records, without an additional blocking
implementation finding in that scope. This correction started from that clean
HEAD and preserved all previous worktrees and artifacts.

### Scope and source roles

The only test change adds
`source_pin:batch-runner/gpt54_prepared_input_attestation.py` at index 4 in
`tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight`.
It follows `gpt54_run_config_bundle.py` and precedes `gpt54_run_input_bundle.py`.
Every other expected refusal remains in order.

Before editing, the primary worker applied the existing source-role charter:
CURRENT R legitimately differs in this reader, while the historical positive
and stale-template checks use the unchanged, genuinely anchored
`approved_pilot_source`. The fix changes neither that fixture nor its real
hash, whole-source validator, positive/stale assertions or closed launch gates.
No production, configuration, workflow, usage README, source pin, frozen
profile, core, grader or first-cell adapter byte changes in this correction.

The leader supplied completed [CI run 37398278085, job 112059370013][ci-failure],
attempt 1, at reviewed `b6ba71115c36075acde2c8f2cece1a3de28cc180`:
**2 failed, 196 passed, 143 deselected in 711.89s**. Both parameters failed at
line 84 because the expected CURRENT refusal list omitted the reader at index 4.
The supplied log SHA256 is
`441e55db421b98278b668c6447e85bb0c43665c907bd8693158b647c3773847b`.
These are leader-read CI facts, not a CI query or a new local observation.

### One bounded local proof

Tested correction: `53d17831df0bc3fd569c00baeffb6ac34d5c5d7c`, tree
`aed06bccd29064dc4feca872f4945397529aab21`. This commit contains exactly one
test-line insertion relative to the reviewed basis. The retained command file
verified the exact HEAD/tree and clean worktree, confirmed Python 3.10.12, then
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
  --basetemp=/tmp/pr755-current-reader-refusal-proof.ZRm9M3/pytest-tmp \
  --junitxml=/tmp/pr755-current-reader-refusal-proof.ZRm9M3/junit.xml \
  tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight
```

Exactly two nodes completed, both passed, with no `-x` or rerun:

- `tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight[current]`
- `tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight[stale_expected_hash]`

Pytest reported **2 passed in 2.15s**, exit 0. Both cases retained the real
source/hash checks and the offline fixture's no-effect assertions.
Artifacts remain at `/tmp/pr755-current-reader-refusal-proof.ZRm9M3/`:

| Artifact | SHA256 |
| --- | --- |
| `command.sh` | `223180c3ea74e4a6d1dca2072bc9a7b823ee04825e606059d293cabb1f6b5309` |
| `output.log` | `7d65f27fb4a9026088a7ab2d6d3e9e79cd76b27fe6b4dd56dfd8bb1f4f5b8cf6` |
| `junit.xml` | `52ee9f9b57b069386a8ca992b15b912b627a13df2993f2bc1b1d8e520f3c27a3` |
| `receipt.json` | `9dc64174fe334ff5dd7e7a6964b8185db01fcee0aa4dd50119e8e3d002d94f3a` |

The command digest identifies the complete retained file, including its source
guards, not the shorter displayed invocation or redacted command text.
The exact post-proof repository delta is `CHANGELOG.md` and this LATEST record
only. No additional test or source change follows the pinned proof.

### Prior evidence and remaining gates

The [immutable first-cell record][first-cell] preserves the original
`a1380d827814699265e1406cc8e84b0f6187b87a` / tree
`28cd1c7dfb471848dd4ce7b91eed8894da4b7e17` invocation: **32 passed, 1 failed in
81.67s**, exit 1. All five roundtrips were synthetic, not real execution.
The separate [fixture correction][fixture-correction],
`9cf4429c377449e98b2c595703d873622c3390dc` / tree
`db32151d10e0c5d777749b604fbc697aacc1c955`, remains unrerun locally. Neither that
corrected node nor the 33-case entrypoint selector was run in this continuation.
Ordinary CI may provide its evidence; no aggregate 33-pass result is claimed.
The same immutable record links the distinct 53/41/8-case proofs, earlier
deadline/ownership evidence, NAS refusal and prior model-free CI host outcomes.
The original command, log, JUnit and receipts remain intact.

The existing source-role charter guided the CURRENT/frozen classification.
`im-not-ai-en` applies only to the changed English passages, protecting counts,
source identities, hashes, links, failed observations and pending gates. No
experiment-design rerun, readiness investigation or full historical changelog
scan was needed.

Remaining gates are final-HEAD review and applicable CI acceptance. Before any
live observation, genuine independent source/input/preparation/host values and
a source-bound execution direction are required. Actual-host admission remains
mandatory; live grading is separate. Source review and these two tests grant
neither permission. No CI query, dispatch, retry, polling or waiting occurred.
No original/input/receipt preparation, provider/model/grader/HF/Azure operation,
Project edit, merge or launch enablement occurred in this task.

[ci-failure]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37398278085/job/112059370013
[first-cell]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/b6ba71115c36075acde2c8f2cece1a3de28cc180/tasks/LATEST_TASK_RESULT/README.md
[fixture-correction]: https://github.com/hyeonsangjeon/gdpval-realworks/commit/9cf4429c377449e98b2c595703d873622c3390dc
