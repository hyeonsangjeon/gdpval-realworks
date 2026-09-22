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
implementation commit. One pre-publication `git fetch --no-tags origin main`
returned 0 and the same main SHA, so no integration was needed. The preceding
records work remains separate in #648; its branch was not changed.

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

### Review boundary and remaining work

The leader supplied `FINAL-APPROVE` review `5274558309` at records HEAD
`ae784cac096bb4cd3338390bddf47309de3e3667` for #648. That review covers only
the earlier real local preparation and Step 1 records, not this selector
implementation. Independent review of this new implementation and its final
automatic checks remain outstanding; no CI status was queried. The leader
controls review and merge order. Any future grading requires separate
authorization; this change grants no execution permission or card completion.

The complete skill catalog was inspected once. `experiment-design` kept the
selection-only evidence boundary fixed. Repository grading-engineer guidance,
the consolidated grading specification and its stable baseline guided the
implementation. `experiment-report-en` and `im-not-ai-en` protected the exact
command, counts, source identities, quotation and non-claims in these records.
UI/animation, workflow, model/provider and repository-readiness skills were
not applicable to this bounded selector correction.
