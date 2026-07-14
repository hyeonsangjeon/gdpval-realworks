# exp027 Subprocess Bridge 50

## Decision

Run one 50-task subprocess control before changing sandbox or Skills behavior.
This is an outcome-selected diagnostic comparison of the complete subprocess
runner/prompt bundle against the historical sandbox runner/prompt bundle. It
does not estimate a population success rate and does not causally isolate the
sandbox, Skills, or any other individual component.

## Historical Correction

`exp025` declared `reasoning_effort: high` and `exp026` declared
`reasoning_effort: low`, but `step1_prepare_tasks.py` omitted that field from the
prepared condition consumed by Step 2. Actions Runs #91 and #92 contain no
`Reasoning effort:` startup line. Both historical runs therefore used the
deployment's server-default reasoning behavior.

The propagation bug is fixed before exp027. exp027 sets the value to `null`
intentionally so the API still receives no explicit reasoning value and remains
comparable to the actual exp026 runtime.

## Paired Task Set

- Group A: all 42 tasks where exp025 or exp026 was not successful.
- Group B: 6 paired-success controls from Audio and Video Technicians / Film and
  Video Editors.
- Group C: 2 paired-success general controls (`403b9234...`, `dfb4e0cd...`).
- Coverage: 50 unique tasks, 9 sectors, 26 occupations.
- Sorted task-ID SHA-256 (newline-joined with a final newline):
  `33b18c57f4a5227ebeccbdc68480b9b702df7927928ac086f63114bb5676a47a`.

Source revisions:

- exp025: `44423f97f355c4ec22163c4a45db99b95f1bb757`
- exp026: `47aed3c0b13eaa90eb02803bec9d5c75e559f416`

Checked-in group membership and coverage metadata:
`tasks/0714_tuesday/exp027_bridge50_selection.json`.

## Frozen Inputs

- GPT-5.4 through Azure, temperature 0, server-default reasoning.
- 32,768 code-generation tokens and 1,200-second task timeout.
- gpt-audio-1.5 audio and GPT-5.4 frame-sampled video preprocessors.
- Condition-level prompt, audio preprocessor, and Self-QA are structurally
  identical to the post-fix subprocess baseline exp025. The exp026 video
  preprocessor is appended unchanged. Self-QA uses one retry and minimum score 5.
- Exact 50-task allowlist in the experiment YAML.

## Changed Bundle

exp027 uses the hardened subprocess runner. Relative to exp026 it removes:

- Docker sandbox execution and resource isolation.
- Agent Skills selection, manuals, and mounted toolkit.
- Per-task dependency manifest injection.
- Deliverable contract, deterministic verification/render QA, and local repair.

The subprocess and sandbox runners also select different built-in codegen
prompts, and exp026 adds Skills-specific condition guidance while exp027 keeps
the coherent exp025 subprocess guidance. Those prompt differences are part of
the measured bundle, not controlled variables.

## Analysis Gates

Compare exp027 against exp026 on the same 50 task IDs:

1. Success/qa_failed/error transition matrix.
2. Paired Self-QA delta, reported separately for all tasks and both-success tasks.
3. Retry count and latency delta.
4. Error categories by syntax/API/runtime/network/task-data.
5. Media subset and Group C stability controls.

Because Group A was selected using historical outcomes, report transitions only
for diagnosis. Do not extrapolate its success rate to the full 220-task set.

Do not promote a sandbox/Skills behavioral change from Self-QA alone. Use the
rubric-based LLM judge when available and inspect task-level artifacts for any
apparent gains.

## Post-Control Improvements

After exp027 completes:

1. Replace substring skill matching with extension-first, word-boundary matching.
2. Reject stale manifests whose attempt identity differs from the final result.
3. Keep `manifest.json` as sidecar metadata instead of a submitted deliverable.
4. Add syntax parsing and exception-specific repair for generated code.
