# Latest substantive task result

## PROJECT5-PARENTHESIZED-DOCX-SELECTOR-1453

The public `select_deliverables()` path selects
`Modlev_Tail_Lamp_Negotiation_Strategy.docx` from the recorded exp035 task's
two-file set in both tested file orders. This deterministic replay establishes
candidate choice only. It does not establish document quality, grading
correctness, a score improvement or a repaired historical comparison.

### Scope and source

The clean feature branch started at
`6f7c77a9de52678e188f025b86de537ce8825dee`. The tested selector and test bytes
were committed unchanged as `d0de31307d7cc6e7dfa665d95e97b4eb6e651e25` after
the focused rerun. Subsequent completion-record changes are outside that tested
implementation commit. At initial publication, one GitHub source fetch found
main unchanged and no integration was needed. For the later authorized
integration, one `git fetch --quiet --no-tags origin main`
returned 0 and exact main `eba56139f95443a715e8309e75c57fe5688c1f2b`.
That source baseline was integrated through an ordinary non-destructive merge.
The only conflict was in this latest-result document; no production or test
conflict occurred. The complete #648 real canonical-source/preparation/Step 1
changelog entry and all unrelated entries were preserved. Its detailed
[historical preprocessing evidence](https://github.com/hyeonsangjeon/gdpval-realworks/blob/eba56139f95443a715e8309e75c57fe5688c1f2b/tasks/LATEST_TASK_RESULT/README.md)
remains distinct from this selector result. The old branch and real artifacts
were not changed.

The selector recognizes a standalone parenthesized `.docx` in an explicit
local deliverable-format clause. It does not widen the shared whitespace
boundary or let a distant trigger reach a parenthesized reference mention.
Word tokens with attached unsupported suffixes are rejected. Ordinary
standalone `.docx` requirements, filename/reference exclusions and ambiguous
multiple-Word-candidate refusals retain their focused test coverage.
Other format aliases, word-order cases, multi-primary routing, scoring and
`critical_fail` math are outside this change.

For task `15ddd28d-8445-4baa-ac7f-f41372e1344e`, the test uses this unchanged
rubric criterion from `openai/gdpval` revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf`:

> The deliverable is provided as a single Word (.docx) or PDF (.pdf) document.

Only that task's prompt/rubric projection was read from the saved original
parquet; there was no source hash audit or download. The test reads the exact
file set from the committed
`batch-runner/docs/run_records/exp035_run34685779030_partial/deliverable_manifest.json`.
The Word file is the sole selected primary and
`modlev_tail_lamp_negotiation_strategy.md` remains support. Neither generated
file's contents were opened. The historical refusal record remains unchanged.

### Focused validation

The first invocation at `6cd3360e092fbf1505c672fd37f249ecf09a1a39` reported
`42 passed, 19 deselected in 0.29s`, exit 0. A subsequent code read found that
the new suffix guard would reject a sentence-ending period followed by a
closing quote, including an ordinary standalone `.docx` requirement. That
patch regression was corrected, with three added punctuation cases.

There were exactly two focused pytest invocations, both using this command.
The necessary rerun selected 27 `parenthesized_docx` cases and 18 directly
related existing format, filename and reference guards:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_deliverable_selector.py batch-runner/tests/test_selector_reads_a_filename_as_a_filename.py -k 'parenthesized_docx or an_extension_written_against_a_name or an_extension_standing_on_its_own or a_trigger_word_cannot_reach_a_filename or the_expert_answer_is_no_longer_refused_for_its_format or the_supplied_file_is_still_kept_out_of_what_gets_graded or a_task_that_really_asks_for_one_format'
```

Final result: `45 passed, 19 deselected in 0.28s`, exit 0, on the unchanged
selector/test bytes committed as `d0de31307d7cc6e7dfa665d95e97b4eb6e651e25`.
The recorded-task case uses real requirement/file-list evidence; the guard
cases are synthetic counterexamples. All assertions exercise deterministic
selection, not a model judge, render pipeline or benchmark run.
`git diff --check` passed. No full suite, grader, provider/model, VM or paid
operation ran, and no HF request was made.

The existing `compute_grader_source_hash()` includes the selector among the
core Python files, so future grading uses a changed source fingerprint.
No fingerprint rule or pin assertion was relaxed. Published exp035/exp003
grades, results, artifacts, costs and baselines remain unchanged, as do all
successful and failed real-preparation artifacts. No claim is made that all
eight historical refusals are fixed.

After integration, the selector and test files were compared byte-for-byte
against approved HEAD `200a35070bc0ffbf5938fea2a1fc85a470c98544` and were
unchanged. No other non-record file changed relative to that HEAD.
Whitespace and conflict-marker checks passed for the merged records.
No tests were rerun; the 42-case and 45-case results above retain their
original tested-commit scope and are not fresh final-HEAD results.

### Review boundary and remaining work

The leader supplied `FINAL-APPROVE` review `5274748991` at exact HEAD
`200a35070bc0ffbf5938fea2a1fc85a470c98544`, with no high-confidence
correctness findings. It covers the selector/test bytes tested as
`d0de31307d7cc6e7dfa665d95e97b4eb6e651e25` and the records at the reviewed
HEAD. This later integration/records delta is outside that review. The review
does not assert CI success, establish a grade or authorize execution.
Final-HEAD automatic checks and integration review remain outstanding; no
CI status was queried. The leader controls review and merge order.

The preceding `FINAL-APPROVE` review `5274558309` at records HEAD
`ae784cac096bb4cd3338390bddf47309de3e3667` for #648 remains limited to the
earlier real local preparation and Step 1 records, not this selector change.
Any future grading requires separate authorization; this change grants no
execution permission or card completion.

For the selector implementation, `experiment-design` kept the selection-only
evidence boundary fixed; repository grading-engineer guidance, the consolidated
grading specification and its stable baseline guided that work. For this
integration, the complete skill catalog was inspected once.
`experiment-report-en` and `im-not-ai-en` were applied only to the edited
record paragraphs, preserving the exact command, counts, identities, quotation
and non-claims. Experiment/control, implementation, workflow, UI/animation,
model/provider and repository-readiness guidance was not applicable to this
integration-only update.
