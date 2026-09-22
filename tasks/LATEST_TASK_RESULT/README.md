# Latest substantive task result

## PROJECT5-PR649-GRADER-BINDINGS-1553

Both active grading contracts now bind the current full grader source closure.
One focused invocation passed all nine cases: current bindings are accepted,
old expected hashes and changed selector source bytes still refuse, and all
existing live blockers and false launch flags remain unchanged. This is an
offline source-contract correction, not a grade or live execution result.

### Defect and supplied CI evidence

Work continued from `a2685e91b704218c657da41bd1505f40b6d1da66` on the existing
feature branch, with integrated main
`eba56139f95443a715e8309e75c57fe5688c1f2b`. No further fetch was needed.
The approved selector and its tests were left unchanged.

The unchanged `step8_grade.compute_grader_source_hash()` includes all core
Python files, including `deliverable_selector.py`, plus requirements, schema,
prompts and the original grading config bytes and path. The selector change
therefore changed both full-template identities. The active plans still named
the old hashes: GPT-5.4 refused through `_configuration_problems()` when
checking shared controls and conditions; Foundry refused through
`gpt56_pilot_identity_plan._grader_identity()`.

The leader supplied Backend run `35695570658` at exact HEAD
`a2685e91b704218c657da41bd1505f40b6d1da66`:

| Job | Supplied result | Completed (UTC) |
|---|---|---|
| `comparison-contracts`, `106641640717` | `559 failed, 71 passed, 312 errors in 99.37s` | `2026-09-22T06:40:15Z` |
| `pilot-preflight-contracts`, `106641640514` | `161 passed, 143 deselected, 35 errors in 41.54s` | `2026-09-22T06:39:04Z` |

These are two representative jobs from seven failing non-core lanes. Their
`shared_controls, conditions` and `grader_template_source_drift` refusals
identify the shared binding cause, not hundreds of independent selector
failures. No full logs were fetched or unchanged failure reproduced.

### Active identities and preserved controls

Each identity was recomputed with the unchanged repository helper using the
original template path and actual configuration bytes in this worktree.
No fixture pin, renamed template, hash stub or waived comparison was used.

| Original template | Previous full-source SHA256 | Current full-source SHA256 |
|---|---|---|
| `batch-runner/grading_configs/default_v2_sol_max.yaml` | `40ada97c41117e3966e5a192c19dafcf4db34d4dd2ddd4230c4b729f421d6e08` | `c92bf13696fa506c84dbee649d5ba3c03fb33244810f30e2be4a05630ca204e1` |
| `batch-runner/grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml` | `56fdb74e2f9fd1afbe9d064fc2cb1e1410d5cebec55edcca8324effd1a1dc9e1` | `785352daa052b105f0dfce08d8de7b3f41633a8e6b312111bec5bdbc8806144b` |

The first value is registered in GPT-5.4's
`shared.grading.template_source_sha256`, inherited by both conditions. The
second is registered in Foundry's
`dispatch_grading_identity.grader_template_source_hash` and its matching
preflight constant. That constant change requires the active Foundry source
pin for `gpt56_sol_codex_pilot_preflight.py` to become
`df62b761638a9afce831a839bf6a5eba3134919cf728d6b56c9ee5e3222f82a9`.
The GHCP contract's `FOUNDRY_SHA256` now binds the resulting active YAML bytes,
`7f7331440f0c13a254353acd4a715f7eb7d3d4c0ba3d9ed32615640cc24ceeef`.
Its equality assertion and `WORKFLOW_SHA256` are unchanged.

Only these five binding values changed outside the new tests and records.
Tasks, models, effort, limits, repeats, grader config bytes, historical
source/base identities, live blockers and launch flags are preserved.
Historical plans, completed-run configs, grades, results, costs and private
artifacts were not updated. A refreshed active future binding does not upgrade
old runs or establish comparable scores.

### Focused validation

Exactly one pytest invocation ran, with no targeted rerun:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_gpt54_comparison_preflight.py::test_active_grader_template_source_comparison batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight batch-runner/tests/test_gpt56_pilot_identity_plan.py::test_active_grader_template_source_foundry_identity batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_preserves_history_foundry_and_backend_partition
```

Result: `9 passed in 4.44s`, exit 0. The tested contract/guard/test bytes were
committed unchanged as `acabb11b383c2b6cfea9291da0d58c9848ba201f` after this
invocation; later completion-record changes are outside that implementation
commit. `git diff --check` passed.

The selection comprises three GPT-5.4 cases, two Foundry preflight cases,
three Foundry identity cases and the existing Foundry/GHCP byte-digest guard.
Actual hash and validation functions are exercised. Negative source-drift
cases change real selector bytes only in temporary source trees, with original
relative template roles and unchanged expected pins. They do not replace the
hash function with an expected value. The checks retain all existing live
blockers and false launch flags; no provider evidence is supplied or inferred.

This is focused offline contract evidence, not a passing full comparison job.
No selector tests or whole CI lanes were rerun. No dataset staging,
preparation, grading, model/provider execution, VM launch, Azure/HF request or
paid operation took place in this correction.

### Preserved selector and preprocessing evidence

The first invocation at `6cd3360e092fbf1505c672fd37f249ecf09a1a39` reported
`42 passed, 19 deselected in 0.29s`, exit 0. A subsequent code read found that
the new suffix guard would reject a sentence-ending period followed by a
closing quote, including an ordinary standalone `.docx` requirement. That
patch regression was corrected, with three added punctuation cases.

There were exactly two earlier selector invocations, both using this command.
The necessary rerun selected 27 `parenthesized_docx` cases and 18 directly
related existing format, filename and reference guards:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_deliverable_selector.py batch-runner/tests/test_selector_reads_a_filename_as_a_filename.py -k 'parenthesized_docx or an_extension_written_against_a_name or an_extension_standing_on_its_own or a_trigger_word_cannot_reach_a_filename or the_expert_answer_is_no_longer_refused_for_its_format or the_supplied_file_is_still_kept_out_of_what_gets_graded or a_task_that_really_asks_for_one_format'
```

Corrected selector result: `45 passed, 19 deselected in 0.28s`, exit 0, on the
unchanged selector/test bytes committed as
`d0de31307d7cc6e7dfa665d95e97b4eb6e651e25`.
The recorded-task case uses real requirement/file-list evidence; the guard
cases are synthetic counterexamples. All assertions exercise deterministic
selection, not a model judge, render pipeline or benchmark run.

For exp035 task `15ddd28d-8445-4baa-ac7f-f41372e1344e`, the public selector
chose `Modlev_Tail_Lamp_Negotiation_Strategy.docx` from the recorded two-file
set in both tested orders; `modlev_tail_lamp_negotiation_strategy.md` remained
support. That replay establishes candidate choice only, not document quality,
grading correctness, score lift, eight restored tasks or a repaired historical
comparison. The selector and both existing test files still match reviewed
HEAD `200a35070bc0ffbf5938fea2a1fc85a470c98544` byte-for-byte. They were not rerun.

The complete #648 real canonical-source/preparation/Step 1 changelog entry and
all unrelated entries are preserved. Its
[historical preprocessing evidence](https://github.com/hyeonsangjeon/gdpval-realworks/blob/eba56139f95443a715e8309e75c57fe5688c1f2b/tasks/LATEST_TASK_RESULT/README.md)
is separate from these contract tests and was not revalidated. Original inputs,
all successful and failed prepared artifacts, handoffs and the GHCP bundle
remain untouched.

### Review boundary and remaining work

The leader supplied `FINAL-APPROVE` review `5274748991` at exact HEAD
`200a35070bc0ffbf5938fea2a1fc85a470c98544`, with no high-confidence
correctness findings. It covers the selector/test bytes tested as
`d0de31307d7cc6e7dfa665d95e97b4eb6e651e25` and the records at the reviewed
HEAD. It did not approve the stale active grading bindings. The leader then
supplied `REQUEST-CHANGES` review `5274961797` at
`a2685e91b704218c657da41bd1505f40b6d1da66` for the coupling defect above.
Neither review approves this new contract delta or its later records.
Final-HEAD automatic checks and leader review remain outstanding; the focused
nine-case result does not establish full-CI success. No CI query, manual rerun
or review waiting occurred.

The preceding `FINAL-APPROVE` review `5274558309` at records HEAD
`ae784cac096bb4cd3338390bddf47309de3e3667` for #648 remains limited to the
earlier real local preparation and Step 1 records, not this selector change.
Any future grading requires separate authorization; this change grants no
execution permission or card completion.

The complete skill catalog was inspected once. `experiment-design` was
applied before changing the active contracts to preserve the registered
comparison and selection-only evidence boundary. Repository grading-engineer
guidance, the consolidated grading specification and stable baseline preserved
historical identities and scoring. `experiment-report-en` and `im-not-ai-en`
were applied to the bounded changed records, protecting exact source hashes,
test counts, supplied CI evidence and review limits. UI/animation, workflow,
QA, upload, pricing, model/provider and new-framework work was not applicable.
