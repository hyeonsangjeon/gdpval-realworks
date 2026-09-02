# What `critical_item_pass_rate` Is Measuring — the Required-Item Definition, Priced

**Measurement only. No decision is taken here.** `core.grader.MAGNITUDE_THRESHOLD`
is unchanged, no payload was edited, no grade was republished, and no grading was
dispatched. Everything below was recomputed from payloads already in the
repository, through the production summariser, by
`batch-runner/scripts/analyze_required_item_definition.py`.

The board card asks for a real definition of "required item" and lists three
options. The only thing missing before anyone can choose is what each option
would do to the runs already published. That is what this file supplies.

## Why there is a question at all

GDPVal v2 rubrics carry a `required` field and it is `null` on **all 10,453
items**. With no author signal, the repository decided that weight stands in for
necessity (`core/grader.py:118-138`):

```python
MAGNITUDE_THRESHOLD = 4

def _is_critical_item(max_score) -> bool:
    return abs(max_score or 0) >= MAGNITUDE_THRESHOLD
```

The comment above it has always said 4 is a heuristic, to be re-evaluated once
gold-ceiling validation showed whether the boundary mis-classifies items. That
validation is finished, so the deferral has run out.

## What actually moves if the definition changes

Two published fields, and nothing else:

| field | where | shape |
|---|---|---|
| `summary.wow.critical_item_pass_rate` | run-level and per sector | micro rate over items (`step8_grade._tally_item`) |
| `tasks[].critical_fail` | per task | boolean (`core/grader.py:1949-1952`) |

`pct`, `total_max`, `total_awarded` and every headline score are computed from
`max_score` directly and do not consult the threshold. The blast radius is
bounded, and it is bounded to the two numbers most often read as "did the model
get the things that matter right".

## TL;DR

1. **Option 1 — raising the threshold to 5 — moves the gold figure the wrong
   way**, on the very run the card quotes. Stage 1 goes 0.5714 → **0.5312**, away
   from the 0.95 gate. Stage 3 goes 0.6394 → 0.6325. On the 220-task model run it
   drifts the other way (0.4903 → 0.4950), so the direction is not even
   consistent across corpora.

2. **One verbatim rubric line is most of what the metric measures.** `'Overall
   formatting and style of the deliverable'`, worth exactly 5, appears in 55–65%
   of tasks and makes up **54.3%** of stage 1's critical set and **33.8%** of
   stage 3's. Expert gold answers pass it at roughly a third the rate of
   everything else. Because it is worth 5, a threshold of 5 keeps every copy and
   drops only the genuine must-haves worth 4 — which is why option 1 goes
   backwards.

3. **Threshold 6 is not the fix either.** It does remove the boilerplate, but on
   stage 1 it leaves a **single** critical item out of 1,431 scored ones; the
   metric then reads a perfect 1.0000 on a denominator of one. On stage 3 it
   still reads 0.8776, and it flips `critical_fail` for 93 of 185 gold tasks.

4. **A fourth option exists that the card does not list**: exclude
   deliverable-wide style lines using the predicate the grader already ships,
   `core.grader_routing.is_overall_style_criterion`. Gold then reads **0.7500**
   (stage 1) and **0.8128** (stage 3) — still short of 0.95. That shortfall is
   itself a finding: what remains is real must-haves the expert gold answer
   genuinely misses.

5. **Six published payloads cannot be priced at all** and are reported as
   refused rather than given a number.

## The sweep

`items` is the size of the critical set at that threshold; `share` is its
fraction of all scored items; `rate` is `critical_item_pass_rate` as recomputed
by `step8_grade._compute_summary` with `core.grader.MAGNITUDE_THRESHOLD`
rebound; `critical_fail tasks` is the recount of the per-task boolean. `*` marks
the shipped definition, where published and recomputed agree to the digit.

### Stage-1 gold ceiling — 30 tasks, 1,431 scored items (published 0.5714)

| threshold | items | share | rate | `critical_fail` tasks |
|--:|--:|--:|--:|---|
| 2 | 695 | 48.6% | 0.7568 | 29 (96.7%) |
| 3 | 46 | 3.2% | 0.6087 | 13 (43.3%) |
| **4 \*** | **35** | **2.4%** | **0.5714** | **13 (43.3%)** |
| 5 | 32 | 2.2% | 0.5312 | 13 (43.3%) |
| 6 | 1 | 0.1% | 1.0000 | 0 (0.0%) — denominator too thin to use |
| 8 | 1 | 0.1% | 1.0000 | 0 (0.0%) — denominator too thin to use |
| 10 | 1 | 0.1% | 1.0000 | 0 (0.0%) — denominator too thin to use |

### Stage-3 gold ceiling — 185 tasks, 8,759 scored items (published 0.6394)

| threshold | items | share | rate | `critical_fail` tasks |
|--:|--:|--:|--:|---|
| 2 | 4277 | 48.8% | 0.7335 | 175 (94.6%) |
| 3 | 543 | 6.2% | 0.6796 | 103 (55.7%) |
| **4 \*** | **355** | **4.1%** | **0.6394** | **99 (53.5%)** |
| 5 | 302 | 3.4% | 0.6325 | 96 (51.9%) |
| 6 | 98 | 1.1% | 0.8776 | 6 (3.2%) |
| 8 | 69 | 0.8% | 0.8551 | 6 (3.2%) |
| 10 | 62 | 0.7% | 0.8710 | 4 (2.2%) |

### OFFICIAL sol-220 model run — 220 tasks, 10,421 scored items (published 0.4903)

`…regrade_exp003_v2_sol_max_score_excluded__…src_595c7254caf8fbd7__v2.2.json`,
graded 2026-08-23. (The older `src_1c967673eb8081a6` payload publishes 0.4848;
they are different runs and must not be conflated.)

| threshold | items | share | rate | `critical_fail` tasks |
|--:|--:|--:|--:|---|
| 2 | 5057 | 48.5% | 0.4813 | 212 (96.4%) |
| 3 | 717 | 6.9% | 0.5091 | 123 (55.9%) |
| **4 \*** | **465** | **4.5%** | **0.4903** | **118 (53.6%)** |
| 5 | 402 | 3.9% | 0.4950 | 113 (51.4%) |
| 6 | 131 | 1.3% | 0.6718 | 14 (6.4%) |
| 8 | 98 | 0.9% | 0.8061 | 11 (5.0%) |
| 10 | 91 | 0.9% | 0.8242 | 10 (4.5%) |

### Why "denominator too thin to use" is a refusal and not a caveat

`step8_grade._rate` returns `0.0` on an empty denominator and `1.0` on a single
passing item. Both look like measurements. The floor used here is derived from
the gate the metric serves rather than chosen: `analyze_gold_ceiling.py` pins
`CRITICAL_ITEM_PASS_FLOOR = 0.95`, whose entire margin is `1 − 0.95`, so below
`ceil(1 / 0.05) = 20` items a single failure costs more than the whole distance
between the floor and a clean sweep. Stage 1 at threshold 6 has one item.

## The concentration

Within the shipped critical set, grouping criteria by text (case, whitespace and
a trailing period folded), requiring a line to appear in more than one task and
in at least 10% of tasks:

| run | items | tasks | share of tasks | share of critical set | weight | pass rate |
|---|--:|--:|--:|--:|--:|--:|
| stage-1 gold | 19 | 19 | 63.3% | 54.3% | 5 | 0.4211 |
| stage-3 gold | 120 | 120 | 64.9% | 33.8% | 5 | 0.3000 |
| sol-220 | 121 | 121 | 55.0% | 26.0% | 5 | 0.1901 |

("weight" is `abs(max_score)`, the quantity the shipped definition thresholds.)

In every case the one line is `'Overall formatting and style of the
deliverable'`. It is the only criterion in any of the three runs that clears the
floor. Stage 3 carries it 119 times bare and once with a full stop; sol-220 the
same, plus one genuinely different line — `'Overall formatting and style of the
deliverable matches that of a professional legal document'`.

That third line is why the census and the predicate differ by one item on
sol-220 (121 vs 122). Both counts are correct; they answer different questions.
The census asks "which exact line repeats", and that sentence is its own string.
The predicate asks "is this criterion about deliverable-wide polish", and it is.

## The four options, priced

Every figure below is a recomputation of the two published fields. Nothing else
in any payload changes under any option.

### 1. Raise the threshold (e.g. to 5)

| run | rate now | rate at 5 | `critical_fail` now | at 5 |
|---|--:|--:|--:|--:|
| stage-1 gold | 0.5714 | **0.5312** | 13 | 13 |
| stage-3 gold | 0.6394 | **0.6325** | 99 | 96 |
| sol-220 | 0.4903 | 0.4950 | 118 | 113 |

Cost: both gold figures move away from the 0.95 gate, and the model run moves
toward it, so the same change makes the benchmark's own ceiling look worse and
the system under test look better. The cause is mechanical — the dominant line
is worth exactly 5.

Raising further does not rescue it: threshold 6 leaves stage 1 with one item and
no usable denominator, still reads 0.8776 on stage 3, and reclassifies
`critical_fail` for 93 of 185 gold tasks and 104 of 220 model tasks.

### 2. Stop publishing the metric

Countable cost, per payload:

| run | run-level rates | sector rates | task booleans |
|---|--:|--:|--:|
| stage-1 gold | 1 | 4 | 30 |
| stage-3 gold | 1 | 9 | 185 |
| sol-220 | 1 | 9 | 220 |

Across the 88 payloads under `data/grades/` that this could price, it withdraws
every `critical_item_pass_rate` the dashboard renders
(`src/components/wow/CriticalItemCard.tsx`, `src/components/wow/SectorHeatmap.tsx`)
and every per-task `critical_fail` flag in the payloads. It costs no accuracy —
nothing published becomes wrong — and it removes the only per-task signal that
distinguishes "scored 60% by missing small things" from "scored 60% by missing
the point".

### 3. Judge necessity from the criterion text

A separate predicate over the wording, rather than the weight. The repository
already ships one such predicate for a neighbouring purpose —
`core.grader_routing.is_overall_style_criterion`, used by the grader to route
perception and covered by the routing tests. Applying it as an **exclusion**
inside the shipped critical set:

| run | excluded items | excluded rate | remaining items | remaining rate |
|---|--:|--:|--:|--:|
| stage-1 gold | 19 | 0.4211 | 16 | **0.7500** |
| stage-3 gold | 120 | 0.3000 | 235 | **0.8128** |
| sol-220 | 122 | 0.1967 | 343 | 0.5948 |

Stage 1's remaining 16 items are below the 20-item floor above, so 0.7500 should
be read as indicative for that corpus, not as a gate-quality figure. Stage 3's
235 items carry it comfortably.

The honest part of this option is that gold still does not reach 0.95. Removing
the boilerplate does not make the gold ceiling clean; it makes the residual
visible, and the residual is real must-haves the expert answers miss.

Building a *general* text predicate — not just this one exclusion — is untested
work. `is_overall_style_criterion` was measured to catch exactly the
deliverable-wide boilerplate and nothing else; no comparable evidence exists for
any broader rule, and inventing one would put an unvalidated classifier
underneath a published number.

### 4. Keep the threshold and publish what it contains

No recomputation, because nothing changes. What it costs is that
`critical_item_pass_rate` continues to be, on the gold corpora, a majority
measurement of one formatting line. The mitigation available without touching
`core/grader.py` is to publish the concentration alongside the rate, which the
tables above make computable for any payload.

## Refusals

`scripts/analyze_required_item_definition.py` prices nothing it cannot
reproduce. Over the whole tree (94 payloads, 6.7 s) six were refused, and the
causes are the two already named by `scripts/summary_wow_drift.py`:

| cause | payloads | why it cannot be priced |
|---|--:|---|
| pre-#100 payload — no `model_did_right` on items | 4 | the metric counts that field; without it every item reads as a failure the model never had |
| pre-#69 payload — stored rate does not reproduce | 2 | the stored rate came from a summariser that is no longer running, so a sweep would compare two definitions while reporting one |

The tool exits non-zero when any payload is refused, and prints: *"A refused
payload was not priced. Do not read a number for it off another payload's
table."* Fourteen further payloads report no repeated criterion above the floor,
which is a finding about those corpora rather than a refusal.

## Reproducing this

```bash
cd batch-runner
python scripts/analyze_required_item_definition.py \
  ../data/grades/_diagnostic/82d14ac9*/exp_gold*.json \
  ../data/grades/_diagnostic/cef3a5b9*/exp_gold*.json \
  '../data/grades/exp003_*src_595c7254caf8fbd7__v2.2.json'

# or the whole tree
python scripts/analyze_required_item_definition.py ../data/grades
```

The tool lives outside `compute_grader_source_hash`'s input set
(`step8_grade.py:159-200` covers `step8_grade.py`, `core/**/*.py`, the grade
schema, `requirements.txt`, `scripts/download_inference_from_hf.py`, the prompt
templates and the config file — no other file under `batch-runner/scripts/`), so
running or changing it moves no grader fingerprint and invalidates no published
grade.

## What is still open

The definition itself. Changing `MAGNITUDE_THRESHOLD`, or replacing it, changes
this metric on every run already published, and `core/grader.py` **is** a
grader-fingerprint input — so the decision belongs to the owner and the card's
완료 기준 requires it in writing. This file exists so that the decision can be
made against measured consequences instead of an assumption about what "worth 4
points" means.
