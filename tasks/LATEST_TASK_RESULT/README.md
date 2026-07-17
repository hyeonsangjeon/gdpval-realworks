# Latest Task Result

This is the canonical rolling record of the most recently completed repository
task. It must be refreshed before a task is reported complete.

- Updated: 2026-07-17
- Status: Atomic fix merged and preflight passed; paid rerun approval pending

## Task

- Run paid Stage B once from the fully recorded, preflighted `main` identity.
- Diagnose the absence of a grade artifact after all ten tasks completed.
- Fix persistence without changing cohort, rubric, prompt, or grading semantics.

## Result

- Paid run `29591036089` graded all 10 tasks from
  `main@6bdcfcf9dd4d5feb8890e13d9f69baefc4162b38` in 1h25m58s. Seven empty
  max-output finals recovered and no runtime/task/judge error appeared.
- At task 10 persistence failed before any JSON existed:
  `OSError: [Errno 36] File name too long`. The 242-byte final basename was
  valid, but the atomic temp format added two dots, an 8-byte random name, and
  `.tmp`, producing 256 bytes against Linux `NAME_MAX=255`.
- Step 8 exited 1. Grade/analysis commits, durable resume, child dispatch, and
  uploaded grade artifact were all absent. The run is rejected and cannot be
  resumed because no partial JSON exists.
- `_save_json` now derives a bounded 16-hex SHA-256 temp identity while keeping
  same-directory `fsync` and atomic replace. The corrected grader hash is
  `011ef05cf7f7a951b9bc2322888605549ee4fa9486c775f4154b89c83526d270`.
- Usage was not persisted, so attempt-1 spend is conservatively booked at the
  higher preflight raw sensitivity estimate, USD 3.81. A same-envelope rerun
  would put estimated cumulative raw Stage B spend at USD 7.62, below the USD
  10 cap. This is an estimate, not billing evidence.
- Atomic-save fix PR #99 merged as
  `3af01d423518d3a344b45cf1cb1a40bcba499d14`. Corrected grader/output identity
  is `011ef05cf7f7a951b9bc2322888605549ee4fa9486c775f4154b89c83526d270`
  / `src_011ef05cf7f7a951`.
- Post-fix model-free preflight `29599249906` passed. Its plan differs from the
  prior accepted plan only in repository/grader identity: 435 items, 436 main
  judgments, 402 text / 16 formatting / 16 visual / 1 mixed, 26/26
  render-perception, and zero prechecks/audio/errors. Plan artifact SHA-256 is
  `76f514bff56c2d2b32ac2b21325f7092542d7538b6da39bd1cd038e87a402faa`.

## Verification

- Failure audit: 10/10 task progress lines, seven recovered finalization
  retries, no runtime/judge errors before atomic save, `rc=1`, no artifact.
- Exact overflow reproduction: 242-byte target, 256-byte legacy temp basename.
- Atomic-save focused tests: **2 passed**; full Step 8 suite: **98 passed**.
- Broad non-integration suite: **1,225 passed, 5 skipped, 37 deselected**.
- Real 242-byte output probe: JSON round-trip **PASS**, temp residue zero.
- Independent grading-engineer review found no code blocker; docs and explicit
  owner deviation approval are required before any second paid attempt.
- Post-fix preflight artifact and environment matched the prior accepted plan;
  active grade/preflight runs were zero after completion.

## Remaining Work

- Obtain explicit owner approval for a second paid Stage B attempt and for
  counting failed attempt 1 as USD 3.81 raw toward a cumulative USD 10 cap.
- Only after approval and active-run guard, run a fresh `resume=false` attempt;
  audit actual cumulative cost and every Stage B gate before any full run.
