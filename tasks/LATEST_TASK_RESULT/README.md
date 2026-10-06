# Latest task result

## PR756 prospective grading filename correction

The approved filename-only repair is implemented. One bounded offline
invocation reported **3 passed in 24.63s**, exit 0. The two retained
partial-output and timeout assertions pass unchanged. Final-HEAD source
review, applicable CI and leader-owned integration remain pending. No real
grade or study observation was executed.

### Scope and source roles

Work started from clean `91272409148a68c8d2c57b7c45d0541ee86b2810`, tree
`0f87a5fb45fe538d8ba0cc692f8379833ff7bfef`, on the existing PR756 branch.
The leader accepted the complete result-byte tuple comparison following
[review 5423395811][review] of `8722a9d91c3ef1b7c77a6e6b529052b0ce621cf8`,
tree `e27f9e2d573581feb20f052ac2be8c8034027b3d`, and explicitly approved this
prospective filename exception. That approval is not final-HEAD CI or live
execution authority. PR755, other worktrees and historical artifacts remain
untouched; integration with newer main is left to the leader.

The first failure occurred during real checkpoint temporary-file creation, not
in `TaskProgressDraft` or `build_progress`: the grade, checkpoint and temporary
basenames were 221, 259 and 263 bytes against `NAME_MAX=255`. It occurred
before grade publication and the fixture's simulated `TimeoutExpired`.
The controller therefore retained `failed`; the test never reached its
intended timeout. Frozen checkpoint code did not change.

`gpt54_time_budget_grading_preparation._materialized_config` now supplies both
preparation and executor reconstruction with this exact fixed value:

```text
{exp_id}__{judge_slug}__{config_name}__{config_hash}__{rubric_sha}__{inference_sha}__{grader_source_hash_short}__{prompt_v}.json
```

Only the literal `judge_`, `cfg_`, `rubric_`, `inference_` and `src_` labels are
removed, saving 31 ASCII bytes. All eight placeholders, their order, format
specifications, conversions, separators and full values remain intact. The
existing rubric revision/cache changes remain; every other config/output
field, including the output directory, stays fixed. This common naming rule
applies to both registered conditions, without adding a study axis or an
arbitrary filename override. The 20-observation policy, 1200/20 deadline,
single grading attempt and no-score-driven-regrade rule are unchanged.

The independent controller C/runtime R helper bytes change. Frozen F stays
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, with TEMPLATE
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
No core, grader algorithm, frozen profile, manifest, workflow or launch gate
changed. The shared helper is verified against the supplied source anchor;
config bytes and whole-source fingerprints are genuinely recomputed and
bound in the reservation, preparation, direction and executor reconstruction.
Stale preparations are refused, never rewritten or adopted.

At `source/batch-runner/time-budget-grading.json`, the synthetic proof measured:

| Identity | Approved materialization | Synthetic obsolete rule at the same path |
| --- | --- | --- |
| Config bytes | 2275 | 2306 |
| Config SHA256 | `094dd4c5da047a71c3cb087d023c57442c137d48fe621cbb0c4aa197b3597377` | `62a6d99d9e74d187e517d60d9a5afb112e38926917710ac6e6606eb28404dfa0` |
| Whole-source materialized SHA256 | `c7e08daf5fc7b5d92f234daa35837b20c1df3abf67501f7ce12eab1203680937` | `51d42b300d17d933fffbd73b2cdea645a803c63a4246af4f37cb193bf951bd7c` |

These are actual config/closure hashes from synthetic preparation, not new
TEMPLATE identities or claims about private inputs. The obsolete config,
reservation and marker were coherently rehashed in the test and refused with
`exact grading preparation mismatch` before admission/publication effects.
No real historical artifact was read or modified.

### One bounded correction proof

Tested HEAD `4f8deffb4080785b70d8f27bebf89b8047cec70d`, tree
`eee63b994df82d0ea6522e4717e5252ed4866d88`, changes only the preparation
helper, executor reconstruction and their shared test module. The retained
command checks this exact clean HEAD/tree before and after the invocation.
From `batch-runner`:

```bash
timeout --signal=TERM --kill-after=5s 300s \
  env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -o addopts= -o junit_family=xunit1 -p no:cacheprovider -m 'not integration' \
  -vv --tb=short --color=no \
  --basetemp=/tmp/pr756-materialized-filename-proof.9WaUXK/pytest-tmp \
  --junitxml=/tmp/pr756-materialized-filename-proof.9WaUXK/junit.xml \
  'tests/test_time_budget_grading_preparation.py::test_time_budget_first_f_grading_executor_roundtrip[partial-failed]' \
  'tests/test_time_budget_grading_preparation.py::test_time_budget_first_f_grading_executor_roundtrip[timeout-timeout]' \
  'tests/test_time_budget_grading_preparation.py::test_time_budget_f_grading_materialized_filename_contract'
```

All three named nodes passed: **3 passed in 24.63s**, exit 0, with no failed,
skipped or incomplete node and no `-x`. The two roundtrips retain partial
grade/checkpoint/ledger output, the correct `failed`/`timeout` terminal reason
and the permanent claim; a second attempt still refuses. Real source, input,
result, config, direction and serializer validators ran through the ordinary
model-free process seam. Namespaces, inputs, results and process outcomes are
explicitly synthetic; this was not a real Step8/provider or kernel probe.

The new contract used the real output formatter and checkpoint writer,
observing its actual temporary-file rename. Each row covers both repeats and
five tasks, for 20 registered run/task variants in total:

| Condition | Grade | Checkpoint | Temporary checkpoint | SQLite ledger | JSONL ledger |
| --- | ---: | ---: | ---: | ---: | ---: |
| V2 | 190 | 228 | 232 | 205 | 203 |
| Codex | 193 | 231 | 235 | 208 | 206 |

All measurements are UTF-8 basename bytes and fit 255 bytes. The 232-byte V2
temporary name is now measured software evidence, not only a calculation.
The existing shared config assertions were updated only for the approved
filename value; their four parametrized preparation cases were not rerun
locally and still need ordinary corrected-HEAD CI coverage.

Artifacts remain under `/tmp/pr756-materialized-filename-proof.9WaUXK/`:

| Artifact | SHA256 |
| --- | --- |
| `command.sh` | `2ae3088d17167f104c8ccd9d1385da5ada7974db471e093c68b21fec3405e20e` |
| `output.log` | `77d79b68ca3b9f9453172d34d00487ed3431c38a3bab92a2a3af6aaeee405421` |
| `junit.xml` | `c538ef8c411406758ea7e695d5b70b24283d286b14d21ba3944406a75e45ce41` |
| `receipt.json` | `63e1b594024628e54b81f5eb5b44f178c3505c829e0cfad75431f34790621f4e` |

The command digest identifies the full retained file, including its source
guards, not redacted display text. JUnit retains all 20 filename measurements.
The post-proof repository delta is exactly `CHANGELOG.md` and this LATEST
record; the complete correction adds only the three tested files above.

### Distinct prior evidence and remaining gates

The [prior immutable record][prior] retains **29 passed, 2 failed, 49 deselected
in 226.13s**, exit 1, at `b3587f7dc865812e416d6b49b3914d0d3c6ed037`, tree
`dbe3f311d35b20b941b4e61b9306cbe80647d118`, including the exact passed-node
inventory. That observation remains separate from this three-node result.
Its links retain the earlier local **31 failed, 49 deselected in 132.68s**
namespace failure, the separate unrerun-at-the-time `3642428f` synthetic
fixture correction, and supplied CI **31 failed, 13482 passed, 64 skipped,
46 deselected, 1 warning in 1376.58s** at `8722a9d`. The [initial record][initial]
also preserves the separate 53/41/8-case proofs and earlier host evidence.
No prior successful selector was repeated or combined into an aggregate pass.

Final-HEAD source review, applicable CI and leader-owned integration remain
pending. Genuine inference-publication/intake locators, verified private
input/result/deliverable identities, reviewed C/R/F, actual host context and
a leader-issued digest-bound live direction are still required. No source
locator was invented. Local claim checks do not prove distributed once-only
protection, backend cancellation, billing bounds or live enforcement.

The catalog was checked once. `experiment-design` kept this approved config
exception limited to output naming; grading/source guidance preserved the
judge and independent source roles. `im-not-ai-en` was applied only to the
changed English records with a bounded fidelity check. No real original,
result, receipt or consumed preparation was accessed. No provider/model/
grader/HF/Azure operation, platform probe, CI dispatch/retry/poll, Project
edit, merge or launch enablement occurred.

[review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/756#pullrequestreview-5423395811
[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/91272409148a68c8d2c57b7c45d0541ee86b2810/tasks/LATEST_TASK_RESULT/README.md
[initial]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/8722a9d91c3ef1b7c77a6e6b529052b0ce621cf8/tasks/LATEST_TASK_RESULT/README.md
