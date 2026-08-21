# PR3 / 301 — exp003 Re-grading: Formatting Gap and Bare-CSV Disambiguation

> Deliverable for [`301-exp003-revalidation.md`](../../../tasks/rebuilding_grading_task/301-exp003-revalidation.md).
> Analysis only — no grading run was dispatched for this report. Every number
> below comes from grade files already in `data/grades/`.
>
> **Location note.** 301 specifies this file at
> `tasks/rebuilding_grading_task/PR3_EXP003_REVALIDATION.md`. That spec predates
> `5349cbf` *"fix(privacy): cleanse public task specifications"*, which added
> `tasks/**` to `.gitignore` so no new file under `tasks/` enters this public
> repository. It lives here instead, alongside the other grade-file validation
> reports — which is where it belongs anyway: it analyses published grade JSONs
> and quotes nothing that those files do not already contain.

## Verdict

| # | 301 acceptance criterion | result |
|---|---|---|
| 1 | formatting bucket gap, absolute value < 5pp | **FAIL** — the gap widened from -25.5pp to **-46.0pp** |
| 2 | the 5 sample tasks' evidence names the file type (xlsx vs csv) | **PASS**, where a rubric item asks — 3 of the 5 have such an item, all 3 evidenced from the opened workbook |
| 3 | report written | this file |

Criterion 1 fails, and it fails in the direction opposite to the one the spec
predicted. That is the substantive finding of this report, and it is not a
defect: **the prediction rested on a diagnosis that turns out to be backwards.**

## Inputs

All three runs grade the **same inference** — `inference_9c639f50…` appears in
every filename — so the deliverable files under comparison are byte-identical.
Only the grader differs.

| label | file |
|---|---|
| v2 sol | `exp003_…__judge_gpt-5_6-sol__regrade_exp003_v2_sol_max_score_excluded__cfg_71c325ee…__v2.2.json` |
| v1 mini | `exp003_…__gpt-5_4-mini__11e7900__v1.json` |
| v1 hybrid | `exp003_…__gpt-5_4-hybrid__11e7900__v1.json` |

Regenerate the raw stratification with:

```bash
python3 scripts/stratify_critical_gap_v2.py \
  data/grades/exp003_…__judge_gpt-5_6-sol__…__v2.2.json \
  data/grades/exp003_…__gpt-5_4-mini__11e7900__v1.json \
  --out-md /tmp/strat.md --out-json /tmp/strat.json
```

The script names its two sides `hybrid` and `mini` because it was written for
the v1 hybrid-vs-mini comparison. Run this way, **`hybrid_*` is v2 sol and
`mini_*` is v1 mini.** The raw output is deliberately not committed: an
artifact whose column headings say "hybrid" when hybrid is not in the
comparison is worse than no artifact. Everything it contains is below.

## 1. The formatting gap did not collapse. It doubled.

483 critical rubric-item pairs (`|max_score| >= 4`), of which 161 fall in the
formatting bucket.

| bucket | pairs | v2 sol right-rate | v1 mini right-rate | gap |
|---|---:|---:|---:|---:|
| formatting | 161 | 0.224 | 0.683 | **-46.0pp** |
| content | 236 | 0.453 | 0.500 | -4.7pp |
| penalty | 86 | 0.942 | 0.698 | **+24.4pp** |
| overall | 483 | 0.464 | 0.596 | -13.3pp |

For reference, the v1 hybrid-vs-mini formatting gap was **-25.5pp**
([`STRATIFY_v2_exp003_critical_gap.md`](./STRATIFY_v2_exp003_critical_gap.md)).

### It is not the judge_error artifact

`model_did_right` is `verdict == 'pass'`, so an item the judge never reached
counts as a failure. The sol-220 run has 333 such items, which is a real
confound and the first thing to rule out. Restricting to items where v2
actually returned a verdict:

| set | n | v2 right | v1 mini right | gap |
|---|---:|---:|---:|---:|
| all formatting critical | 161 | 0.224 | 0.683 | -46.0pp |
| **judged only** (drop 20 judge_error) | 141 | 0.255 | 0.695 | **-44.0pp** |

The artifact is worth 2pp of 46. Ruling it out leaves the finding intact.

### It is not the binary metric either

`model_did_right` also scores `partial` as wrong, so a grader that prefers
`partial` looks worse without awarding fewer points. Checking the points
actually awarded on the same 141 items settles it:

| grader | pass | partial | fail | awarded / available |
|---|---:|---:|---:|---:|
| v1 mini | 98 | 38 | 5 | 636 / 725 = **87.7%** |
| v1 hybrid | 60 | 76 | 4 | 599 / 725 = **82.6%** |
| v2 sol | 36 | 83 | 22 | 448 / 725 = **61.8%** |

Outright `fail` goes 5 → 22 and a quarter of the available points disappear.
v2 is substantively harsher on formatting, not merely more cautious in how it
labels.

## 2. Why — and why the v1 diagnosis was backwards

The v1 report read the -25.5pp gap as **Scenario B: hybrid over-rejects
formatting, an extraction artifact.** The implied fix was to give the judge
eyes, and the implied prediction was that eyes would pull the formatting score
back *up*.

Eyes pulled it further down. The evidence strings say why. Every v2 formatting
downgrade cites something only a viewer can know; every v1 mini pass quotes
extracted cell text:

| task | v2 sol | v1 mini |
|---|---|---|
| `b5d2e6f1` | fail 0/5 — "Headers run together (e.g., 'Store NumBrand NamCategory Product N SKU Numb'), row text crowds columns, and the page has no title, borders, or visual hierarchy." | fail 0.0 — `[Sheet: Data]` |
| `f841ddcf` | fail 0/5 — "The second summary sentence is visibly cut off; table headers run together and are truncated, account names are clipped…" | **pass 5.0** — `Account,Total_Order_Value_Cost,Total_Shipped_Value_Cost,…` |
| `c357f0e2` | fail 0/5 — "Dense rows have concatenated column text, repeated 'Unnamed:' headers, no visible table structure, and content is clipped at the right edge." | **pass 5.0** — `Test No.,Role,Module,Source Event (user Action),…` |
| `83d10b06` | partial 1.25/5 — "Headers collide (e.g., 'Sub-DivisiCountry' and 'Legal EntitKRIS'), many labels are truncated, columns are cramped, and there is no title or visual hierarchy." | **pass 5.0** |

The pattern is the same in each row. v1 mini was asked whether a deliverable is
well formatted and shown a CSV dump of its cell values, in which formatting is
invisible by construction. Having no basis on which to object, it passed. Its
0.683 right-rate is not a measurement of formatting quality; it is a
measurement of how often a grader defaults to `pass` when it cannot see.

So the correct reading of the original -25.5pp reverses: **mini was
under-rejecting, not hybrid over-rejecting.** Hybrid sat between the two
because it had partial signal. Ranking the three by strictness on formatting —
mini 87.7%, hybrid 82.6%, sol 61.8% — orders them exactly by how much of the
document each one could actually see.

This also means the deliverables really are unformatted. `Store NumBrand
NamCategory Product N SKU Numb` is a default `to_excel` dump with untouched
column widths. A human expert would not call that a formatted spreadsheet.

### v2 is not uniformly stricter

Worth stating, because "the new grader is harsher" is the wrong summary. On
the penalty bucket — anti-criteria, `max_score < 0` — v2 is right 94.2% of the
time against mini's 69.8%, and there are **zero** items where v2 is stricter
and mini lenient. Whole-run mean score:

| grader | mean task pct |
|---|---:|
| v1 hybrid | 49.25 |
| v1 mini | 51.47 |
| **v2 sol** | **56.18** |

v2 scores the corpus *higher* overall. It gives back more than it takes: what
it removes on formatting it more than returns by correctly resolving penalty
items mini mishandled.

## 3. Bare CSV versus real xlsx

The spec named five tasks — `27e8912c`, `43dc9778`, `7b08cd4d`, `7d7fc9a7`,
`83d10b06` — and asked whether evidence distinguishes "openpyxl loaded, has
cell formatting" from "openpyxl failed, file is plain CSV".

| task | rubric items asking about file type | evidence |
|---|---:|---|
| `83d10b06` | 4 | all four quote the opened workbook: `"kind": "xlsx", "filename": "Sample.xlsx"`, `"name": "Sample Size Calculation"` |
| `7d7fc9a7` | 6 | `"kind": "xlsx"`, plus 19 items quoting sheet names and structure |
| `7b08cd4d` | 1 | `"kind": "xlsx"` |
| `43dc9778` | 0 | n/a — the deliverable is a Form 1040 draft, no workbook involved |
| `27e8912c` | 0 | n/a — a PDF checklist and a .docx; both *are* type-checked, via `"kind": "pdf", "size_bytes": 15321` |

Every task that asks gets an answer grounded in the opened file. **Criterion 2
passes.**

Two honest limits on that pass:

**The corpus contains no bare CSV.** Searching all 220 tasks for openpyxl
failure signatures (`BadZipFile`, `InvalidFileException`, "not a zip file")
returns **0 hits**, and **0 tasks** have a `.csv` primary target. The
discriminator was exercised on genuine workbooks only; its failure path is
untested by this run.

**The discriminator is weaker than `kind` suggests.** `kind` comes from the
file extension (`read_deliverable.py:206`), so a CSV renamed `.xlsx` would
still report `"kind": "xlsx"`. What would actually catch it is
`openpyxl.load_workbook` raising — the disambiguation works by exception, not
by design. That exception text reaching judge evidence is a known open defect
(board card *"Stop openpyxl exception strings leaking into judge evidence"*).

**The original question was mis-framed.** Re-reading the v1 material, "bare
CSV" described the *content* of these workbooks, not their container. They are
real `.xlsx` files holding bare-CSV-grade content: no styling, no widths, no
headers worth the name. No file-type check can detect that — only a renderer
can, which is exactly what v2 now reports. `7b08cd4d` shows the structural
form of the same signal, on a currency-formatting item: `"styled_cells_count":
15, "cells_scanned": 91`.

## 4. Residual risk

**Page-1-only render scope.** xlsx renders at `workbook_page: 1`, so a judge
complaining that "most of the page is unused blank space" may be describing the
render window rather than the deliverable. Bounding it: of 482 downgraded
formatting items, **36 (7.5%)** cite blank or unused page area, 27 of those on
`.xlsx`. Even if every one were spurious it cannot account for a 26pp drop in
awarded points. Worth fixing; not worth re-opening this conclusion over.

**One-run measurement.** Everything here is a single grading pass. Whether the
formatting severity is stable or partly sampling noise is exactly what
[303](../../../tasks/rebuilding_grading_task/303-variance-and-error.md) is for, and 303 needs a paid dispatch.

**The judge_error rate.** The sol-220 run recorded 3.19%, above the 2% gate.
Root-caused separately; PRs #189 (docx rendering) and #190 (selector recovery)
address 307 of the 333 items, and neither is reflected in the run analysed
here.

## 5. What this changes

- 301's numeric criterion fails; 301's *purpose* — find out whether the
  formatting gap was an artifact — is served, with a clear answer: it was, but
  the artifact was on the lenient side.
- **The v1 formatting-gap conclusion in
  [`STRATIFY_v2_exp003_critical_gap.md`](./STRATIFY_v2_exp003_critical_gap.md)
  should be treated as superseded.** Its Scenario A/B framing assumes the
  stricter grader is the suspect one. With a grader that can see the document,
  the leniency is the thing that needs explaining.
- No score was rewritten and no threshold moved. This report reinterprets
  published numbers; it does not alter them.
