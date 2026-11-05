# PR797 offline CI repair

This changes tests and the offline Backend Tests envelope, not observation or
grading admission. No push, dispatch, model call or real grading is part of the
repair. The registered model, inputs, grader, 42 source pins, eight helper pins,
ABBA schedule and 1,200/20-second generation/cleanup budget remain unchanged.

## Evidence

Line numbers below count the complete output of `gh run view --job ID --log`,
not the shorter `--log-failed` output.

- PR run [41700556354](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/41700556354),
  head `bfcc2180ff094c29671de56c9e0db0ed46fc71dd`, tested merge
  `d26b5e378bb171ff9b2e354dcf59a7b2c5bbe0ae`.
- Comparison job 126142399807 lines 12-20 reports Ubuntu 24.04.5, image
  `ubuntu-24.04`, version `20261025.353.1`. The Ubuntu 26 migration warning is
  not the OS used by this run.
- Lines 1120-1128: the sole failure among 1,541 cases is
  `test_current_source_requires_explicit_successor_not_an_implicit_repin`.
  Its assertion incorrectly expects original registration `e1d16d35...` as
  D3's direct predecessor; D3 correctly names schedule registration
  `1e316eec...`. The test now checks both D3 -> schedule and schedule -> original,
  including their paths, exact digests and the single retained history entry.
- Line 1157: the subsequent platform gate refuses with
  `comparison_step_not_successful`. It is not evidence of a platform failure.
- Time-budget job 126142400396 lines 1089-1115: 854 tests collected, continuous
  progress through `test_time_budget_owned_startup.py` (two passing cases),
  then job cancellation. Pytest started at 19:11:41Z; its last progress at
  19:53:59Z shows 52%; cancellation at 19:54:26Z enforces the 45-minute job.
  The quiet output does not identify the exact in-flight node after that file,
  so it cannot establish a hang in any particular test.
- Latest main run [41043654263](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/41043654263)
  at `8f6d00fef0e994bbc9542e2f3f813497644e0416` passed both jobs: comparison
  1,541 cases in 1,824.82s; time-budget 495 cases in 1,511.48s (job 124022292891,
  lines 1068 and 1101). The workflow at the PR head is byte-identical to main.
  The stale D3 assertion and expanded suite are branch-specific regressions.

## Bounded changes

- Pin the two affected jobs to `ubuntu-24.04`; unrelated jobs are unchanged.
- Raise only the offline time-budget job from 45 to 120 minutes, under the
  hosted six-hour maximum. At the observed pace, 42m18s / 52% projects about
  82 minutes of testing. This is a planning estimate, not a measured total or
  a guarantee; 120 minutes allows setup and variance without splitting or
  silently dropping fixtures. Per-node verbose progress and the 20 slowest
  durations will make the next run diagnosable.
- Preserve every test target, tmp-path retention policy, integration exclusion,
  permission, checkout guard and fail-closed platform evidence step. Historical
  workflow reconstruction now reverses exactly the two runner labels, one
  timeout and one logging-only command change before checking the existing hash.
- Current workflow hash moves from `a2e0e2fe...` to `b16dc71d...`; the
  retention-option-stripped hash moves from `7bd20c54...` to `dcb20f9a...`.
  The historical workflow and experiment registration hashes are not repinned.

## Local validation

- Before the fix, the exact comparison regression reproduced: 0 passed,
  1 failed, 0 skipped, with the same predecessor-digest assertion as Actions.
- After the fix, comparison/source-successor contracts: 357 passed, 0 failed,
  0 skipped; the one real-kernel platform case was deselected only in this
  local invocation. CI still runs it and still requires its positive evidence.
- Workflow partition/history, GHCP workflow hash, job budget, tmp-path lifetime,
  startup static contract and resource-workflow shell syntax: 178 passed,
  0 failed, 0 skipped. The new CI budget/runner regressions contribute eight
  cases. Total final focused validation: 535 passed, 0 failed, 0 skipped.
- The source-successor tests revalidated all 42 source and eight helper pins,
  both predecessor records and the D3-only delta. Original/schedule/D3 record
  SHA256 values remain `e1d16d35...`, `1e316eec...`, `be7b8a14...`.
- Ruff fatal/syntax checks and `git diff --check` passed. No full Backend Tests
  rerun or hosted-platform claim is inferred from this focused local result.

Local verification uses isolated synthetic/offline fixtures. NAS kernel support
is not used to accept or reject the hosted platform requirement. A new approved
push and subsequent PR CI are still needed to verify the hosted result and
full-suite runtime; the repair itself performs neither.
