# TASK_STEP8_TASK50_FAIL — step8_grade.py exits 1 after task #50 (cost-sweep unrelated)

> Discovered during exp003 head-to-head validation (TASK_TIERED_VALIDATION.md).
> Status: open, low priority (cost optimization sweep already merged).

## Repro

Two independent GH Actions runs, different grading configs, same experiment:

| Run | Config | Exit | At task |
|---|---|---|---|
| 26394620211 | default_gpt5pro.yaml (single mini) | exit 1 (no traceback) | #50 |
| 26394637568 | tiered_critical_pro_mini.yaml (pro/critical + mini/rest) | exit 1 (no traceback) | #50 |

Both runs processed the same first 50 tasks of `exp003_GPT52Chat_baseline_runner_exec`, last log line per run:

```
[50/220] d025a41c -> 42.2% (30.0/71)   # Run A
[50/220] d025a41c -> 42.4% (30.1/71)   # Run B (essentially identical)
##[error]Process completed with exit code 1.
```

No Python traceback in the GH Actions logs. The "Commit grade result" and "Upload artifact" steps did not run (conditional `if: success()`). The partial grade JSON saved at task #40 (per `partial_save_every_n_tasks: 10`) is preserved in `actions/upload-artifact` because that step is `if: always()`.

## What is NOT the cause

- Mini judge verdict consistency: same fail in tiered config (mostly pro for critical) at same task → judge model not the trigger
- Grading config (`grader.*`): both configs share `grader.deliverable_extract_max_chars=1500`, `grader.batch_size=1`, etc.
- API auth: 50 tasks succeeded, no 401/403 in log
- HF download: both got full inference results (deliverables 629)
- TPM throttling: max_concurrent=1, no 429 in log

## Suspect

1. **Memory accumulation in step8_grade.py main loop.** Each task adds to in-memory grade structure; at task #50 (~3-4 hours of accumulation) something hits a limit on the GH Actions runner (default 7GB).
2. **Schema validation failure** after partial save at task #40, then process exits silently. Check `step8_grade.py` lines ~430-470 (task loop).
3. **task #51 entry crash before any log emission** — task list ordering specific to exp003.

## Diagnostic next steps (when prioritized)

1. Re-run with `--limit 51` to force fail at the exact boundary, examine `runner.log` from artifact for stderr
2. Add explicit `logging.exception` in step8_grade's main task loop catch
3. Memory-profile: `tracemalloc` or `psutil` on a local 60-task subset
4. Check if exp003 task #51 has anomalous rubric (e.g., very large rubric, missing field)

## Out of scope

- Cost optimization sweep (PR #53, #54 — already merged successfully)
- Tiered routing validation (TASK_TIERED_VALIDATION.md / COMPARISON_REPORT.md — concluded: tiered is worse than single-mini)

## Workaround for now

If a real exp003 full grade is needed urgently:
- Use `--limit 50` (or less) to grade in chunks, then merge grade JSONs manually
- Or run locally (not GH Actions) with `--tasks=<list>` to isolate task #51

## Cost impact

This bug blocked the head-to-head full validation but did not consume excess Azure credit (each fail at task #50 ≈ ~2.5h of mini-tier grading; tiered ≈ ~4h). Total ~$30 spent across both attempts. Within $2,500 monthly cap.
