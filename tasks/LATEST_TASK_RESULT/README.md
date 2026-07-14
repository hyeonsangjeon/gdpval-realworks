# Latest Task Result

- Updated: 2026-07-14
- Status: Implementation merged; exp027 Actions run in progress

## Task

Analyze `exp026_sandbox_skills_multimodal`, add behavior-neutral sandbox
observability, and prepare one bounded subprocess comparator before changing
Sandbox or Agent Skills behavior. Keep the canonical result synchronized after
the implementation merge and experiment dispatch.

## Result

- Confirmed from Actions Runs #91/#92 and the Step 1/2 data path that historical
  `exp025` and `exp026` dropped their declared `reasoning_effort`; both actually
  used the deployment's server-default reasoning behavior.
- Added privacy-bounded sandbox provenance: prompt/code hashes, token usage,
  latency, stable error categories, skill match evidence, preprocessor status,
  and CI run identity. Raw response text, stdout/stderr, exception messages,
  generated filenames, and heavy verification reports are not persisted.
- Added deterministic `data.filter.task_ids` support and propagated exact task
  scope through task preparation, parquet filling, validation, formatting, and
  self-report generation. Duplicate/missing/unexpected task IDs fail closed.
- Added `exp027_GPT54_default_subprocess_bridge50`, an outcome-selected 50-task
  diagnostic comparator covering 9 sectors and 26 occupations. It uses the
  coherent post-fix subprocess prompt/QA/audio setup, the exp026 video
  preprocessor, server-default reasoning, 32K code tokens, and a 1,200-second
  timeout. The comparison measures the runner/prompt bundle and is not a causal
  estimate of Sandbox or Skills alone.
- Added checked-in 42/6/2 task-group provenance with task-list SHA-256
  `33b18c57f4a5227ebeccbdc68480b9b702df7927928ac086f63114bb5676a47a`.
- PR [#64](https://github.com/hyeonsangjeon/gdpval-realworks/pull/64)
  was squash-merged to `main` as
  `4306fa55d5df32314c449e89243638c24e1d686a`.
- Actions run
  [#93](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/29324114951)
  was dispatched from that merge commit for
  `exp027_GPT54_default_subprocess_bridge50`. Step 1 completed, the sandbox
  image step was correctly skipped for subprocess mode, and Step 2a inference
  is currently in progress. No relay or result PR exists yet.

## Verification

- Nine changed Python modules compile with `py_compile`.
- Focused regression suite: 206 passed, 0 failed.
- `git diff --check`: passed.
- Independent final code review: APPROVE, with no blocker, major, or minor
  findings.
- GitHub confirms PR #64 is merged and Actions #93 is running on head SHA
  `4306fa55d5df32314c449e89243638c24e1d686a`.

## Remaining Work

- Monitor Actions #93 and any automatically triggered relay legs through Steps
  3-7 and the generated result PR.
- Compare exp027 and exp026 on the pinned 50-task set before changing Skills
  selection, manifest delivery policy, or repair behavior.
