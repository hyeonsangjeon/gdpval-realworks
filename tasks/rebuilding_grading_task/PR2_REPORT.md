# PR2 Report — Tool-Calling Grader Rebuild

> **Status: 8/9 tasks closed, 1 PARTIAL.** All code + tests landed on
> `main`. PR3 unblocked. Acceptance for SPEC §7 deferred to PR3 (live
> grade-run jobs required).

## Headline

PR2 swaps the v1 *text-extract-then-judge* path for a v2 *tool-calling*
judge that opens the deliverable file directly. The judge has eyes
(through `read_deliverable` ops) and, for visual / audio criteria,
escalates to perception sub-judges. No more 1500-character pre-extracted
dump deciding whether a chart is "well formatted."

The legacy v1 path is **archived but still callable** so the
`default_gpt5pro.yaml` default keeps working until PR3 task 302
validates v2 cost. The full code strip happens in a single follow-up
cleanup PR after that flip — see task 207 PARTIAL note.

## Commit ledger

| task | commit | size | what landed |
|---|---|---|---|
| 200 env audit            | `05f30ae` | docs | `PR2_ENV_AUDIT.md` — wheel-only deps (`fitz`, PyAV) → no apt-get install needed in grade-run.yml |
| 201 read_deliverable tool | `69d2d89` | +650 | 6-op read-only file inspection module + 25 tests (22 pass + 3 env-skip) |
| 202 judge prompt v2       | `419b612` | +130 | `prompts/grader_judge_v2.md` tool-aware + `grader_judge_v1_archive.md` |
| 204 perception routing    | `ab161f9` | +230 | pure-function `classify_criterion` (visual > audio > formatting > text) + 19 tests |
| 205+206 perception sub-judges | `163bfdc` | +540 | `VisionPerception` + `AudioPerception` with DI client, per-task caps, graceful judge_error + 16 tests |
| 203 ToolCallingJudge      | `653ef1d` | +880 | Responses-API tool-calling loop + `Grader._judge` dispatch hook + 13 tests |
| 208 default_v2.yaml + validator | `f14c22a` | +230 | schema 2.0 accepted; tools/perception/critical blocks validated; new default config (opt-in) |
| 207 legacy archive        | `2aa6688` | rename+docs | v1 sweep/tier configs → `_archive_v1/`, two README files, code strip deferred |

**Total new code: ~2,200 LOC across 7 production modules; ~1,200 LOC of
tests across 7 test files. Net regression: 478 → 563 tests, 0 failures.**

## What the new path looks like

```
                              prompt: grader_judge_v2.md
                          (routing_modality hint injected)
                                     |
        ┌────────────── ToolCallingJudge.judge_item ──────────────┐
        |                                                         |
        |  Responses API loop (≤10 iterations, ≤8 tool calls/item):
        |   - tools=[read_deliverable, vision_judge?, audio_judge?]
        |   - dispatch function_calls → read_deliverable / sub-judge
        |   - echo function_call + function_call_output into next batch
        |   - on first message: parse JSON envelope, return verdict     |
        └─────────────────────────────────────────────────────────┘
                                     |
                              Grader._judge
                       (sign-aware aggregate from PR1)
                                     |
                               TaskGrade
```

## Acceptance status vs SPEC §7

| § | gate | status |
|---|---|---|
| 7.1 | gold-ceiling — gold deliverable hits ~90%+ | **deferred to PR3 task 300** (requires live gpt-5.4 + gold dataset run) |
| 7.2 | exp003 formatting gap collapses | **deferred to PR3 task 301** (requires live exp003 re-grade) |
| 7.3 | bare-CSV vs xlsx evidence distinguishable | structurally guaranteed by `inspect_formatting` op (cells / fonts / borders surfaced); confirmed by example in test_read_deliverable.py `test_inspect_formatting_xlsx`. Cross-experiment evidence pending PR3 |
| 7.4 | judge_error_rate < 2% | **deferred to PR3 task 303** (need full run measurement) |
| 7.5 | grades_per_task=3 + bootstrap CI | wired in `default_v2.yaml`; runtime confirmed in PR3 task 303 |
| 7.6 | PR1 headline numbers re-published with sign-aware math | ✅ done in PR1 (`PR1_REPORT.md`) |

## Autonomous decisions taken (excerpts; full list in OVERVIEW)

| topic | decision | why |
|---|---|---|
| PDF render backend | `PyMuPDF` (fitz), not `pdf2image`+poppler | wheel-only, grade-run.yml has no apt-get step |
| Audio/video probe | `PyAV` (`av`), not `ffmpeg-python`+ffmpeg binary | same reason as above |
| `soundfile` explicit pin | added to requirements.txt during 201 work via env audit recommendation | transitive deps are fragile |
| v1 prompt early swap | NOT swapped; created `grader_judge_v2.md` side-by-side; v1 stays active for legacy Judge | spec 203 says ToolCallingJudge co-exists; both files needed |
| perception routing test file | new `test_perception_routing.py`, not appended to legacy `test_grader_routing.py` | concern separation; 207 cleanup can drop the legacy test file without touching perception tests |
| perception DI direction | `client` injected at construction, NOT built inside class | main judge owns the Responses client; trivial mocking for tests |
| audio deployment missing | `judge()` graceful `judge_error=endpoint_missing`, never raise | audio is a minority path; failure must isolate to audio items |
| grade-run.yml default flip | NOT flipped in 208 → still `default_gpt5pro.yaml` | flipping before PR3 cost-validation risks a runaway $50+ accidental run |
| 207 scope | PARTIAL — archive YAML only; code strip deferred | full strip breaks 30+ tests in one commit AND requires grade-run.yml default flip; correct sequencing is post-PR3 |

## What changes for an operator today

1. `default_gpt5pro.yaml` still default. Existing grade-run jobs unchanged.
2. To try v2: trigger `grade-run.yml` with `grading_config=default_v2.yaml`.
   Recommend pairing with `tasks_limit=3` and `experiment_yaml=exp998_smoke_baseline_sample`
   first to bound cost.
3. PR3 will:
   - Run gold-ceiling check (task 300)
   - Re-grade exp003 with v2 and report formatting-gap collapse (task 301)
   - Re-estimate full-run cost (task 302) — if > $50/run alert per user contract
   - Variance + bootstrap CI + judge_error rate (task 303)
4. After PR3 PASS, a cleanup PR will flip grade-run.yml default, archive
   `default_gpt5pro.yaml`, and complete the 207 acceptance grep ⇒ 0.

## Regression evidence

```
$ pytest -q
========= 563 passed, 5 skipped, 37 deselected, 107 warnings in 44.27s =========
```

5 skips are env-conditional (PyAV / fitz not present in macOS dev
venv; both are in `batch-runner/requirements.txt` and verified
present in `grade-run.yml` per the task 200 env audit).

## Handoff to PR3

PR3 is a separate session because each of its tasks requires a live
GitHub Actions grade-run job (hours of wall-clock, real Azure API
spend). The contract for PR3:

1. Trigger `grade-run.yml` with `grading_config=default_v2.yaml`
   against `exp998_smoke_baseline_sample` and `tasks_limit=3`.
   Verify v2 path executes end-to-end without exceptions, evidence
   strings are tool-grounded, output schema is grade.schema.json v1.1
   compatible. (task 300 acceptance signal)
2. Repeat against gold deliverables and confirm avg_pct ≥ 90 on the
   gold subset. (task 300 strict acceptance)
3. Run full v2 on exp003 (`exp003_GPT52Chat_baseline_runner_exec`).
   Compare to existing v1 grade for the same experiment. Look for
   "Overall formatting and style" criterion no longer structurally
   under-graded. (task 301)
4. Compute observed per-task cost from `analyze_grade_run.py` output;
   project 220-task total; alert if > $50/run. (task 302)
5. Re-grade one task 3 times; report variance + 95% CI; compute
   `judge_error_rate` and alert if > 2%. (task 303)

If all four PASS: write `PR3_REPORT.md`, then flip `grade-run.yml`
default to `default_v2.yaml`, archive `default_gpt5pro.yaml`, and
complete the 207 code strip in a single cleanup PR.
