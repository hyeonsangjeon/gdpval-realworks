# Copy audit — PR #1 (dashboard_cleanup)

Mandatory pre-implementation grep (per spec 005 §"Mandatory grep audit"):

```bash
rg -in "self-?QA|self-?assess|LLM-?judge|external grad|grading pipeline|pre-?grad|Awaiting" \
   src/ scripts/aggregate-grades.mjs
```

Each match is classified as **OK** (already compliant), **EDIT** (this PR
edits the copy), or **DELETE** (this PR removes the line / element).

## OK — already compliant

| Location | Snippet | Why OK |
|---|---|---|
| `src/pages/GradeDetail.tsx:689` | `Item-level partial credit grading powered by our LLM-judge…` | Factual WOW description; already names the LLM-judge correctly and contrasts with task-level binary. |
| `src/data/tooltipTexts.ts:41` | `grading.perfect` — "Tasks scored 100% by the LLM-judge (rubric-based, automated)…" | Already correct rubric language. |
| `src/data/tooltipTexts.ts:43` | `grading.partial` | Already correct rubric language. |
| `src/data/tooltipTexts.ts:45` | `grading.zero` | Already correct rubric language. |
| `src/data/tooltipTexts.ts:79` | `sectionHintTexts.grading` — "LLM-judge (rubric-based, automated). … Grading runs separately from inference via grade-run.yml." | Already disambiguates self-QA vs LLM-judge. (spec 005 amends `leaderboard` hint, not grading hint.) |
| `src/pages/Dashboard.tsx:161` | `label: 'Best Self-QA'` | KPI tile label; tooltip carries the long-form disambiguation (covered by `kpi.bestQaScore` edit). |
| `src/pages/ExperimentDetail.tsx:764` | `Self-QA` (column header) | Short label; column has its own tooltip / context. |
| `src/pages/ExperimentDetail.tsx:891` `:893` | `Self-QA Score` per-task card | Per-task tile label, already paired with "Self-QA Score" wording. |
| `src/pages/ExperimentDetail.tsx:898-902` | `External Grade — Awaiting Grade` (per-task tile) | Per-task tile, outside dashboard_cleanup scope (task-level UI, no spec entry). |
| `src/components/ScopeBadge.tsx:15` | `✓ LLM-Judge Graded` (graded badge) | Kept by spec 002 D4 as legacy `graded` scope (emerald). |
| `src/components/ScopeBadge.tsx:26` | `⏰ Awaiting LLM-Judge Grade` (self_assessed badge) | Spec 002 D4 explicitly preserves `self_assessed_pre_grading` (amber). This is a true "warning"-class use of amber. |
| `src/components/ScopeBadge.tsx:28` | `tooltipTexts.badge.selfAssessed` reference | Tooltip text itself is in EDIT list below. |
| `src/components/dashboard/PromptArchitectureView.tsx:122` `:125` | `Self-QA` column | Label only. |
| `src/components/dashboard/LeaderboardView.tsx:379` | `Self-QA Score` (leaderboard column) | Already short-labeled; long-form tooltip covered by `leaderboard.qaScore` EDIT. |
| `src/components/dashboard/GradingAnalysisView.tsx:118-119` | empty-state body — "Grading results will appear here after running the LLM-judge via grade-run.yml. This is separate from the self-assessed QA scores shown in other tabs." | Already disambiguates. (Spec 005 explicitly marks this as OK.) |
| `src/README.md:85` `:94` | inline doc comments | Documentation, not user-facing UI copy. |

## EDIT — copy revised by this PR

| Location | Spec ref | Change |
|---|---|---|
| `src/data/tooltipTexts.ts:6` `kpi.bestSuccessRate` | 005 | Rewrite per spec sample: clarify self-QA inference signal vs LLM-judge grade. |
| `src/data/tooltipTexts.ts:12` `kpi.bestQaScore` | 005 | Rewrite per spec sample. |
| `src/data/tooltipTexts.ts:24` `leaderboard.successRate` | 005 | Rewrite per spec sample. |
| `src/data/tooltipTexts.ts:28` `leaderboard.qaScore` | 005 | Rewrite per spec sample. |
| `src/data/tooltipTexts.ts:46` `grading.graderDisagreement` | 004 D3 | Add "Visible only in multi-judge mode (Phase B)…" |
| `src/data/tooltipTexts.ts:52-53` `badge.selfAssessed` | 005 + 002 | Rewrite per spec sample (independent signal phrasing). |
| `src/data/tooltipTexts.ts:97-98` `aboutContent.sections[2].bullets` | 005 | Expand to 4 bullets per spec sample. |
| `src/data/tooltipTexts.ts:73` `sectionHintTexts.leaderboard` | 005 | Append "Numbers here reflect inference-time self-QA…" sentence. |
| `src/data/tooltipTexts.ts` (new) `health.*` (6 keys) | 003 D4 | Add new block for HealthStrip pills. |
| `src/data/tooltipTexts.ts` (new) `grading.judgeVsInference` | 001 D3 / 005 | Add disambiguation key referenced by GradeDetail header. |

## DELETE — element removed by this PR

| Location | Spec ref | Reason |
|---|---|---|
| `src/components/GradesSummary.tsx:115-118` `⏳ Awaiting LLM-Judge Grade — run grade-run.yml…` per-card banner | 002 D3 | Misleading — replaced by neutral `DEMO` badge + dashed border. |
| `src/components/dashboard/GradingAnalysisView.tsx:131-148` Amber "Awaiting LLM-Judge Grade" top banner | 002 D2 | Replaced by zinc/sky banner driven by `grade_status` mix (legacy_only / mixed). |
| `src/components/dashboard/GradingAnalysisView.tsx:319-323` `⏳ Awaiting real grading` mini banner inside `GradeOverviewCard` | 002 D3 | Misleading — replaced by neutral DEMO badge geometry; legacy cards get dashed border. |
