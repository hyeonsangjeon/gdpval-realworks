# Grading configs

## Active configs (top level)

| file | path | grader path | when to use |
|---|---|---|---|
| `default_v2_sol_max.yaml` | tool-calling judge | v2 (`ToolCallingJudge` via `judge.tools.read_deliverable`) | **Production default.** GPT-5.6 Sol 1M Max for main, visual, and bounded finalization; gpt-audio-1.5 for audio perception. |
| `default_v2.yaml` | tool-calling judge | v2 | Historical gpt-5.4 medium comparison identity. Pass explicitly when reproducing that condition. |
| `regrade_exp003_v2_mini_score_excluded.yaml` | tool-calling judge | v2 | Full-220 exp003 rerun only. Pins score-excluded semantics, the historical mini judge condition, rubric commit, inference revision, and all 220 task IDs in canonical order. Its source predates the provenance sidecar, so it declares the legacy allowance; the complete pin keeps it publishable. |
| `regrade_exp003_v2_sol_max_score_excluded.yaml` | tool-calling judge | v2 | Planned full-220 exp003 Sol Max rerun. Pins score-excluded semantics, production judge/perception settings, rubric commit, inference revision, and all 220 task IDs in canonical order. Its source predates the provenance sidecar, so it declares the legacy allowance; the complete pin keeps it publishable. |
| `validation_exp003_v2_sol_max_anchor4.yaml` | tool-calling judge | v2 | Paid four-task Sol Max anchor with pinned diagnostic-error and visual/audio coverage, plus the same runtime semantics and source identities as the planned full rerun. |

Since task 207 the tool-calling judge is the only grading path. Every config
here must define `judge.tools.read_deliverable`; `Grader.__init__` raises on one
that does not, rather than falling back to a path that would produce grades not
comparable with these. The removed knobs (`batch_size`, `judge_routing`,
`deliverable_extract_max_chars`) are asserted absent by
`tests/test_grader.py::test_no_active_grading_config_declares_legacy_knobs`.

`grade-run.yml` defaults to `default_v2_sol_max.yaml`. The 1.05M context window
belongs to the deployment and is not represented by a synthetic request field.
There is no automatic hybrid follow-up in the active workflow.

The workflow itself defaults to `dry_run: true`. Any non-dry invocation must
set `paid_approval: true` and pass the protected `grading` GitHub Environment.
If a time-bounded run needs another chunk, the exact config, inference revision,
task limit, and paid-approval input are inherited by the continuation. Each new
chunk is a separate workflow run and requires a fresh protected Environment
approval. Model prices are not guessed: grade payloads and analyses remain
explicitly `unpriced` until verified FDPO rates are configured.

## Provenance and diagnostic scopes

The grading downloader requires `inference_provenance.json` by default and
binds it to the embedded prepared fingerprint, ordered tasks, and Azure AI
routes. Inference runs that predate the sidecar cannot satisfy that binding:
their payloads carry neither `prepared_fingerprint` nor `azure_ai_routes`, so
the file cannot be written after the fact without inventing both. They declare
`rerun_identity.allow_legacy_missing_provenance` instead, and the downloader
permits a confirmed remote sidecar 404 only when the workflow experiment and
both the requested and resolved revisions exactly match the config's pinned
lowercase SHA. Any embedded routes, sidecar validation error,
auth/network/local-file error, or other config remains fail-closed. The
allowance always requires pinned `task_ids` whose count equals
`expected_task_count`, and the grade always persists
`source_azure_ai_provenance_status: legacy-missing`.

What the allowance costs depends on **scope**, because the missing sidecar is a
gap in the audit trail rather than in the graded corpus — the judge reads
deliverables, rubric, and prompts, never the inference routes. A config that
pins a *proper subset* of the source corpus has narrowed what was graded, so it
stays diagnostic; the four-task Sol Max anchor is that case. A config that pins
the *complete* corpus in canonical source order has dropped nothing, so it keeps
the root output path and `run_status: final`; the 220-task Sol Max regrade is
that case, pinning all 220 IDs with ordered SHA-256
`df1fcd6415c55a17e4f39a254aaf0f0f9f2f55c751189f74d2713a873373aa3c`. The
`--allow-legacy-missing-provenance` CLI flag on the downloader pins nothing, so
a bare local override still lands in the diagnostic tree.

Runs selected with `--tasks` or `--limit`, plus any legacy-provenance run whose
scope is not a config-pinned complete corpus, are saved with
`run_status: diagnostic` under `data/grades/_diagnostic/<ordered-task-sha256>/`.
The full task hash prevents a subset from sharing a cache/resume path with a
complete run, and the dashboard aggregator only discovers root-level grade JSON.
A complete run keeps the root output path and `run_status: final`; when it was
graded from a pre-sidecar source, the aggregator carries
`source_azure_ai_provenance_status` into the dashboard projection so the
unverified route provenance is labelled rather than silently published.

## Judge-error score boundary

New grade payloads use output schema `1.3`: every `judge_error` item is excluded
from task score numerators and denominators, while `summary.wow.judge_error_rate`
remains required and visible in the dashboard. If every item in a task is
excluded, the task is unscored rather than silently contributing a zero.

Headline scores from schema `1.3` are not directly comparable with schemas
`1.0`-`1.2`, where some judge failures could contribute score-included zeros.
Historical payloads remain readable and unchanged; do not backfill or combine
partial results across this boundary. Compare conditions only after a complete
rerun under one grader source and one schema identity.

The read-only baseline analysis used tracked payload
`data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json`
(SHA-256
`b5cbb6a80c776b458f99f007841a946c1c5f9ec8bf60be052500713dd6f13570`).
It contains 355 `judge_error` items. Of those, 100 were score-included zeros
across 53 tasks: 61 `final_json_parse_failed`, 31 `empty_final_text`, five
`RateLimitError`, and three content-policy `BadRequestError` items. The other
255 errors were already score-excluded selection failures. This analysis did
not mutate or partially regrade the payload.

The approved future exp003 full rerun is fixed to:

- config: `regrade_exp003_v2_mini_score_excluded.yaml`
- config hash: `82685843dbc4d457`
- rubric commit: `11e7900cdcac61bc4daf59e65feb238acda98fbf`
- inference revision: `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f`
- expected task count: `220`

Inside Step 8, the config's `rerun_identity` block is checked before its Azure
route preflight and before model-client construction, so a partial task set or
identity drift cannot start model grading. The workflow may authenticate and
perform its own route checks earlier.

The pinned Sol Max identities are:

| purpose | config | config hash | tasks |
|---|---|---|---:|
| full rerun | `regrade_exp003_v2_sol_max_score_excluded.yaml` | `e2e15dae3b268e97` | 220 |
| paid anchor | `validation_exp003_v2_sol_max_anchor4.yaml` | `fbb9b175f63398c6` | 4 |

Both pin rubric commit `11e7900cdcac61bc4daf59e65feb238acda98fbf`
and inference revision `9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f`.
Their audio block remains the production `gpt-audio-1.5` configuration with a
32-call task cap and 30-second trim, and their visual task cap remains 112.

### Config hashes that committed payloads still carry

A grade payload's filename embeds `cfg_<config hash>` as it stood when the run
was dispatched. Raising the audio task cap from three to 32 moved five of those
hashes, and raising the visual task cap from 72 to 112 moved all six, so the
table below is what a reader needs to resolve an older filename back to the
file that produced it. Nothing in the code parses `cfg_` back out of a path;
this is the only place the mapping is written down.

| config | hash at dispatch | hash now | committed payloads |
|---|---|---|---:|
| `gold_ceiling_30_v2_sol_max.yaml` | `d1bfc8217c9981d2` | `ca01239a6aa768b6` | 12 |
| `regrade_exp003_v2_sol_max_score_excluded.yaml` | `71c325eee0e48c13` | `e2e15dae3b268e97` | 4 |
| `gold_smoke_audio_v2_sol_max.yaml` | `ddacb72418fc5400` | `b66f0b09a9a31c5a` | 3 |
| `gold_ceiling_185_v2_sol_max.yaml` | `b3609ec13f8fa51e` | `c16c39bc4b299ab4` | 2 |
| `validation_exp003_v2_sol_max_anchor4.yaml` | `7f3c7c2e542cf580` | `fbb9b175f63398c6` | 1 |
| `regrade_exp003_v2_mini_score_excluded.yaml` | `0aebaaa2d0e51d74` | `82685843dbc4d457` | 0 |

`gold_ceiling_30_v2_sol_max.yaml` heads that table, and it was very nearly left
out of it. The argument for freezing it was that it carries the most committed
payloads of any config, that it is the Stage 1 measurement already published,
and that a config should change only if a future run will use it. Two checked-in
contracts refused that. `tests/test_gold_ceiling_contract.py` and
`tests/test_full_gold_corpus_contract.py` require the 30-task sample, the
185-task full run and the production default to carry byte-identical `judge`
blocks, allowing only `config_name`, `description` and `rerun_identity` to
differ. They exist because Stage 1's 82.87 per cent is the number Stage 3's
result is placed next to, and two ceilings measured under different perception
caps are not comparable. Freezing one config was therefore never available: the
30-task sample is not a retired artefact but the control the later stages are
read against, and Stage 1 has already been re-run once for exactly that reason.

The rest of the table moved for plainer reasons. `default_v2_sol_max.yaml` is
`grade-run.yml`'s default config and `default_v2_mini.yaml` its mini
counterpart, both live templates that any future dispatch picks up; and
`tests/test_grading_config.py` couples the two exp003 reruns to those defaults
by an audio-block equality assertion, so they move together or not at all.

None of the moved payloads can have scored differently for it. Every audio
call this pipeline ever made was sent to the Responses endpoint, which does not
accept an `input_audio` content part, so all of them were refused with a 400
before a model heard anything. The cap is consulted before the call, so it did
decide whether an over-cap item recorded `cap_exceeded` or `provider_error` —
but both are `judge_error` and both score zero.

The mini reference below is not like-for-like. Its tracked payload uses schema
`1.0`, has no top-level `config_name` or `grader_source_hash`, and all 220 tasks
have `perception_call_count=0`. Although its items are labelled with 337 visual
and 58 audio routing decisions, those criteria predate perception wiring and
were silently handled by the text judge. Therefore its calls and latency are a
main-judge-only historical reference, not a "Sol Max multiplier" and not a
basis for scaling newly active visual or audio work.

### Pinned anchor tasks and selection rules

The paid anchor pins these tasks in canonical inference-source order (the
tracked payload array indices are authoritative):

1. index 10 — `99ac6944-4ec6-4848-959c-a460ac705c6f`
2. index 29 — `4c18ebae-dfaa-4b76-b10c-61fcdf26734c`
3. index 78 — `40a8c4b1-b169-4f92-a38b-7f79685037ec`
4. index 179 — `a73fbc98-90d4-4134-a54f-2b1d0c838791`

The tasks were selected by targetable score-included mini errors, not by score.
The baseline payload is
`data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json`
(SHA-256
`b5cbb6a80c776b458f99f007841a946c1c5f9ec8bf60be052500713dd6f13570`).

| task | final JSON parse | empty final text | targetable | visual | audio | main calls | main latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| `99ac6944-4ec6-4848-959c-a460ac705c6f` | 2 | 1 | 3 | 10 | 13 | 52 | 679.03787 s |
| `4c18ebae-dfaa-4b76-b10c-61fcdf26734c` | 5 | 1 | 6 | 1 | 0 | 50 | 387.76369 s |
| `40a8c4b1-b169-4f92-a38b-7f79685037ec` | 3 | 5 | 8 | 0 | 0 | 72 | 635.26040 s |
| `a73fbc98-90d4-4134-a54f-2b1d0c838791` | 3 | 2 | 5 | 32 | 0 | 60 | 747.13748 s |
| **Total** | **13** | **9** | **22** | **43** | **13** | **234** | **2,449.19944 s** |

These 22 errors are all `final_json_parse_failed` or `empty_final_text`; none is
wrong-format, rate-limit, content-policy, or selection failure. They cover 22%
of the 100 historical score-included judge errors while adding 43 visual and 13
audio criteria. Every latency value and the
2,449.19944-second total above are derived from raw `judge_total_latency_ms`;
display precision is decimal formatting, not per-task truncation.

When config `rerun_identity.task_ids` is present, Step 8 resolves it through the
existing `filter_tasks` validation path. Canonical source order is authoritative.
CLI `--tasks` is accepted only when it resolves to the same ordered task set;
otherwise the run fails. `--limit` must be either `0` or the pinned count (`4`),
so the protected workflow may continue to pass `tasks_limit=4` without adding a
new workflow input. Any pinned subset is emitted as a diagnostic grade.

### Preregistered anchor decision

The paid result is judged against the same four mini task rows above:

1. **Diagnostic outcome.** Count `final_json_parse_failed` and
   `empty_final_text` by task. Fewer than the mini baseline total of 22 is an
   improvement; zero is elimination. A total of 22 or more is **no improvement**
   and means the model-switch rationale has no diagnostic support. Other judge
   errors make the diagnostic inconclusive and block the full run; they cannot
   be credited as finalization improvement. The
   baseline is the four selected rows in the 220-task payload above, not a
   different cohort payload.
2. **Operational reference.** Report observed main calls and main latency
   against 234 calls and 2,449.19944 seconds. Label those ratios
   **main-judge-only references**, never Sol Max multipliers, because the mini
   baseline had no active perception. Also report main, visual, audio, and
   unknown token/cache/call/latency planes. No USD amount is inferred.
3. **Modality-normalized projection.** Never extrapolate the whole anchor by
   task count alone. Project and sum these components independently:
   - main plane: scale the measured non-perception wall/main component by
     `220 / 4 = 55`;
   - visual: scale measured visual latency by `337 / 43 ≈ 7.837209`;
   - audio: scale measured audio latency by `58 / 13 ≈ 4.461538`.
   Unknown perception makes the projection incomplete. Compare the known
   component total with the 44-hour envelope.
4. **Wiring and cap gates.** `audio.call_count` must be greater than zero;
   otherwise report dead audio wiring and stop before 220. The count of
   `task_visual_budget_exceeded` must be zero; any occurrence means visual work
   was silently excluded at cap 72 and blocks the full run.

   At or above 44 hours, stop before a full run and return to the owner with the
   existing choices: expand the chunk range, reduce the visual cap, or approve
   an explicit split/resume plan. This preparation authorizes none of them.

The analyzer only projects a JSON-Schema-valid `1.3` diagnostic payload whose
current repository config file matches the persisted config name and hash, and
whose judge/perception, rubric, inference, prompt, and four source-ordered task
identities match that preregistered config. Partial/resume payloads, missing,
duplicate, or reordered tasks, incomplete task/item/summary usage, and any
task-level error make the projection incomplete and block owner review.
For an anchor config identity, a missing or `null` `anchor_projection` is also
blocked rather than falling back to task-count extrapolation. Step 8 requires
the persisted projection contract to exactly match the current config before
accepting either a completed cache entry or a partial `--resume` payload.

All diagnostic, operational, modality, audio, visual-budget, and envelope
results must be reported numerically. Improvement alone does not justify the
full run if any wiring, cap, unknown-attribution, or time gate fails.

## Visual file cap per rubric item

`judge.perception.visual.file_cap_per_item` bounds how many files one visual
rubric item may render and perceive. It is a positive integer; omit it and the
grader uses **10**. A value that is not a positive integer is rejected by
`validate_grading_config`, so a typo fails at dispatch rather than partway
through a paid shard.

This is not the same bound as `judge.perception.visual.call_cap_per_task`,
which is the task-wide budget (112 in the production configs). The per-item cap
limits one item's evidence; the task cap limits what the whole task may spend.

Where it applies:

- `primary_bundle` / `file_target` — the item's selected files.
- `split_children` — each child's own files, and then the union across
  children. The union counts because the runtime hands it to a single batched
  prepass that renders and perceives every path in it. Failing the union
  before that call is also what keeps an over-cap item from booking its whole
  union into the task visual budget and failing the task's other items with it.

Exceeding the cap fails the item closed with
`required_visual_file_cap_exceeded:planned=<n>,cap=<n>` — the item is scored as
`judge_error` and excluded, and nothing is rendered. It is a deliberate refusal
to judge breadth from a partial view rather than a truncation to the first *N*
files.

### Why the default moved from 3 to 10

A hard-coded 3 was below the size of an ordinary multi-deliverable submission.
On R1 it failed three rubric items closed on tasks where nothing was over
budget and nothing was unrenderable — the items simply spanned four or more
files. Truncating to the first three alphabetically was rejected: on all three
items the un-rendered files were exactly the ones that could change the
verdict, so a truncated pass would have been less honest than the refusal.

The full fix costs +20 vision calls, 3.48% of R1's 575. That did not move the
task budget's binding constraint, which is settled below from a run rather than
from a projection.

## Why the visual task cap is 112

`judge.perception.visual.call_cap_per_task` was 72 from the day harness-owned
visual grading landed (`6ad789a`, #69) until this change. Three configs carried
the comment `# checked-in 220 inventory: max 68 supported calls`, and
`tests/test_track2_visual_inventory.py` did hold a checked-in 220-task
projection reaching that figure. Two things were wrong with reading it as a
basis for 72.

**It could not see the case the cap exists for.** The projection calls
`resolve_runtime_routing(criterion, selected_paths)` and leaves the text-layer
signals unset, and only a *measured* signal escalates. So the no-text-layer
escalation — a TEXT criterion promoted to VISUAL because its file carries no
text to read — contributes nothing to it. On the 185-task gold run the two
heaviest renderers, `43dc9778` at 68 renders and `b9665ca1` at 59, both project
as **2**. The third, `9a8c8e28` at 39, projects as exactly **39** — and that
contrast is the point rather than an inconsistency: where a task's renders are
asked for by criteria that name something visual, the projection is exact;
where they come from escalation, it is blind. The class that caused the
incident the cap was raised against was the one class invisible to the count.
`tests/test_track2_visual_inventory.py::test_the_projection_is_exact_or_blind`
holds those six figures.

**Its maximum was a property of one run's file selection, not of the task.**
The projection's own maximum of 68 belongs to `a73fbc98` — a different task
from the one that *rendered* 68 above, and the two counts landing on the same
figure is a coincidence worth naming before it misleads somebody. Running that
same projection over the *newer* selection the gold run recorded for
`a73fbc98` gives 102 — over the old cap. The selector had moved
(`set_diff_then_uniform_primaries`) and the projection's own note said that
would not move the max. It did.

### What the run actually cost

Measured from the 185-task gold payload, which is the only committed run graded
with the escalation live and per-item `render_call_count` recorded:

| | renders |
|---|---:|
| tasks needing at least one | 131 of 185 |
| median of those | 2 |
| 90th percentile of those | 13 |
| whole corpus | 670 |
| largest single task (`43dc9778`) | 68 |

Two tasks wanted more than 72: `43dc9778` at 134, at the earlier grader
`955be41e`, and `a73fbc98` at 102, on the merged run. They are not the same
kind of demand.

- `43dc9778`'s 134 was **reducible**, and a code change reduced it. Almost all
  of it came from the no-text-layer escalation sending a whole task to pictures
  because one of its files carried no text layer. `058d4f8` (#303) narrowed
  that, and on the next grader generation the same task plans 68, renders 68,
  excludes nothing and scores 92.23% — at the same cap of 72. Nothing about the
  budget changed. (68 is not the projection's 2: an item whose files *all* lack
  a text layer still escalates, and the projection cannot see that either way.)
- `a73fbc98`'s 102 is **irreducible**. Every one of its 34 visual items is
  visual because the criterion names something visual, so
  `Grader._relax_to_fit_visual_budget` — which re-plans without the escalation
  and grades the smaller plan rather than dropping the task — returns the
  strict plan unchanged and the task fails closed. That relaxation was live on
  this run: the payload's `grader_source_hash` is the tree of `e82bc66`, the
  commit that added it. In the committed gold payload all 34 items carry
  `task_visual_budget_exceeded:required_calls=102,cap=72`, all are
  `score_excluded`, not one has a perception call, a tool call or a render
  against it, and **not one is marked `visual_budget_downgraded`** — the
  signature of relaxation having been tried and having freed nothing. The
  task's published 76.74% is 33 points out of the 43 that were graded — from a
  rubric worth 87.

So 72 was not a ceiling nothing reached. It amputated more than half of one
task's rubric in the corpus this benchmark treats as its gold ceiling.

### Where 112 comes from

112 = 102 + 10. The 102 is the largest irreducible per-task demand measured
across the 185-task corpus; the 10 is `file_cap_per_item`, one further visual
criterion's worth of room, so the worst task in the corpus can gain a rubric
item without being amputated again.

The number deliberately does **not** cover `43dc9778`'s old 134. That is not a
live saving — the current grader plans 68 for that task and would not spend 134
at any cap. It is a guard on the *shape* of demand that produced it: one
unreadable file sending a whole task to pictures is a mistake that can be
reintroduced, and at a cap of 134 or more the benchmark would quietly pay for
it rather than refusing and saying so. Sizing above the irreducible demand is
what stops silent amputation; staying below the reducible one is what keeps the
budget able to notice. A cap between the two is the point.

Cost: on a re-run of this corpus, +102 renders on one task of 185, against 670
today. Nothing else in the corpus comes near, because nothing else in the
corpus was refused — every other task planned inside 72 to begin with, the
largest at 68 (`43dc9778`), then 59 (`b9665ca1`). The raised ceiling changes
what 1 of the 185 tasks does and leaves the other 184 exactly as they are.

One assumption those figures rest on, stated because it is easy to miss: they
are **strict** plans. `visual_budget_downgraded` is false on all 17,743 items
that carry it across every committed payload, so relaxation has never once
fired in production and no render count here is a relaxed one. A payload that
breaks that is a payload whose totals mean something else;
`test_the_way_out_of_the_budget_has_never_had_to_fire` is where it surfaces.

`tests/test_the_picture_budget_was_counted.py` holds every figure above and
recomputes it from the committed payload, so a change to routing, to the
selector, or to the supported-format set that moves the demand fails there
rather than at the next paid dispatch.

### What is still not counted

The 185-task corpus is not all 220 tasks, and the escalation depends on whether
a specific deliverable file carries a text layer — which cannot be determined
without the file. A projection over the other 35 tasks would have to guess the
signal the escalation reads, so none is offered here. The honest claim is
narrower than "112 is enough for GDPVal": it is "112 is above every demand
anyone has measured, and 72 demonstrably was not."

### Effect on `grader_source_hash` and comparability

`compute_grader_source_hash` covers `step8_grade.py`, `core/**/*.py`,
`schemas/grade.schema.json`, `requirements.txt`,
`scripts/download_inference_from_hf.py`, and the configured prompt, tool
prompt, and config file. This change edits `core/tool_calling_judge.py`,
`core/grader.py`, `core/grader_preflight.py`, `step8_grade.py`, and the grade
schema, so **`grader_source_hash` moves.** Grades written before it and after
it are not the same grader identity, and a resume or shard merge across the
boundary is refused by the existing identity checks — as intended.

`config_hash` does **not** move. No shipped config sets `file_cap_per_item`;
the raised default lives in code and the resolved value is written to
`judge.visual_file_cap` in every new grade payload. That keeps the archived,
regrade, and validation configs byte-identical, so runs already published under
them keep their identity, and a reader can still tell which cap produced any
given grade file without inferring it from a code revision.

`judge.visual_file_cap` is optional in the grade schema. Payloads written
before this change do not carry it; for those the cap was 3.

Scores are comparable within one `grader_source_hash`, not across this one.
An item that previously scored `judge_error` under the cap of 3 may now carry a
real verdict, which changes both the numerator and the denominator of its
task's score. Compare conditions only after a complete rerun under one grader
source and one schema identity — the same rule as the schema `1.3` boundary
above.

## Archived (no longer recommended)

Under `_archive_v1/`. These files are provenance references, not runnable inputs
to the current typed-route validator: they retain the historical
`judge.endpoint_env` contract that is now rejected. To reproduce an old run,
use the historical commit/environment or copy the config to a new top-level
file, remove `endpoint_env`, add an explicit matching `deployment`, and record
the migration as a new run identity. Never resume an old partial across that
boundary.

| file | why archived |
|---|---|
| `recommended_gpt5_4_mini_2026-05-24.yaml` | cost-sweep winner from 2026-05-24 — v1 mini judge, text-extract path, no tool calling. Retained for provenance; not directly runnable under the typed endpoint contract. |
| `validation_hybrid.yaml`, `validation_pro_only.yaml` | tier-routing PR2-preceding validation configs. v2 is single-tier; tier configs no longer match the grader path. |
| `tiered_critical_pro_mini.yaml` | tier-routing experiment config. Same reason as above. |
| `_sweep_template.yaml` | cost-sweep parameterization template. Useful only for reproducing the v1 sweep; v2 has a different cost surface and will get its own template if/when needed. |
| `default_gpt5pro.yaml` | the last v1 text-extract config. Archived by task 207 together with the code that ran it. Retained as the provenance record for the grades it produced; it can no longer be graded with. |

## v1 vs v2 quick reference

|  | historical v1 (`_archive_v1/default_gpt5pro.yaml`) | production v2 (`default_v2_sol_max.yaml`) |
|---|---|---|
| schema_version | `1.0` | `2.0` |
| judge tier | mini / standard / pro routing | single (gpt-5.6-sol) |
| reasoning_effort | medium / high / mini-low (per tier) | max for main, visual, and finalization |
| deliverable input | pre-extracted text, 1500 char cap | live file via `read_deliverable` tool |
| `deliverable_extract_max_chars` | present | **removed** |
| tools | none | `read_deliverable` + opt. `vision_judge` + opt. `audio_judge` |
| perception | none | gpt-5.6-sol max vision / gpt-audio-1.5 (modality-routed) |
| visual files per item | n/a | `file_cap_per_item`, default 10 |
| critical rule | `weight >= 4` | `\|max_score\| >= 4` (sign-aware, includes 94 penalty items) |
| score math | clamp-hidden negatives | sign-aware, explicit non-positive total_max handling |
| rubric execution | one final verdict per rubric item | one final verdict per rubric item (plus bounded tool/finalization calls) |

## How to add a new config

1. Copy `default_v2_sol_max.yaml` to `<your_name>.yaml` and edit only the
   fields you mean to change. `schema_version` must stay `2.0`.
2. `python step8_grade.py <exp_id> --config grading_configs/<your_name>.yaml --dry-run`
   to validate.
3. Run the model-free `--dry-run` first. Any paid smoke or full 220 run requires
   separate operator approval and artifact-level acceptance.
