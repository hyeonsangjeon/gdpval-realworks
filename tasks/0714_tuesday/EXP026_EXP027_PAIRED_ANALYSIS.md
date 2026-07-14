# exp026 vs exp027 Paired Diagnostic Analysis

## Scope

This analysis compares the exact 50 task IDs pinned in
`exp027_bridge50_selection.json`:

- Group A: 42 tasks where exp025 or exp026 was not successful.
- Group B: 6 paired-success media controls.
- Group C: 2 paired-success general controls.

The set was selected using historical outcomes. It is useful for diagnosing
runner failures, but its success rate must not be extrapolated to the full
220-task benchmark. Both reports are self-assessed and pre-grading; Self-QA is
not an external rubric score.

Sources:

- exp026 pinned HF revision: `47aed3c0b13eaa90eb02803bec9d5c75e559f416`
- exp027 pinned HF revision: `830d476f24da9d842882ac69ed785c546b362a91`
- exp026 self-report SHA-256:
  `ec93ad9ae193734bfc7cb78c1879328ef8a1ff6777af80dcd57b38acc5a0fa3a`
- exp027 self-report SHA-256:
  `783183dbc9d8aae3811b164c40ee8681998c005ebc8b63a8fcd943c829f72a80`
- Task-list SHA-256:
  `33b18c57f4a5227ebeccbdc68480b9b702df7927928ac086f63114bb5676a47a`

Reproduce the calculations with:

```bash
python scripts/analyze_exp026_exp027.py
```

The script uses only the Python standard library. Bootstrap intervals use
10,000 percentile resamples with seed `20260714`.

## Status Transitions

| exp026 ↓ / exp027 → | Success | QA Failed | Error | Total |
|---|---:|---:|---:|---:|
| Success | 19 | 5 | 6 | 30 |
| QA Failed | 4 | 6 | 4 | 14 |
| Error | 0 | 3 | 3 | 6 |
| Total | 23 | 14 | 13 | 50 |

- Success changed from 30 to 23 (`-7`).
- Hard errors changed from 6 to 13 (`+7`).
- Ordered outcome changes were 7 improved, 28 unchanged, and 15 degraded.
- Success discordance was 4 tasks in exp027's favor versus 11 in exp026's
  favor. The exact two-sided binomial value was `0.118469`.

The direction favors the exp026 Sandbox/Skills/repair bundle for execution
reliability, but the comparison does not isolate any single component. Because
the task set was selected using historical exp026 outcomes, the exact value is
reported only as an exploratory descriptive statistic. Confirmatory significance
or threshold interpretation would require a pre-specified independent sample or
the full benchmark.

## Self-QA

| Paired set | n | exp026 avg | exp027 avg | Mean Δ | Median Δ | Win / Tie / Loss |
|---|---:|---:|---:|---:|---:|---:|
| Both scores present | 34 | 5.206 | 5.265 | +0.059 | 0 | 11 / 11 / 12 |
| Both successful | 19 | 6.263 | 6.316 | +0.053 | 0 | 6 / 7 / 6 |

The deterministic bootstrap mean-delta intervals were `[-0.412, +0.559]` for
both scores and `[-0.474, +0.579]` for both-success tasks. Both cross zero.
There is no Self-QA evidence that removing Skills improved or degraded quality.
These intervals are descriptive because of outcome-based task selection. No
Skills selector change should be justified from this run alone.

## Runtime

- Mean task latency changed from 115.54s to 76.78s (`-38.76s`; descriptive
  bootstrap interval `[-79.09s, -11.61s]`).
- On the 19 tasks successful in both runs, mean latency changed from 84.78s to
  65.72s (`-19.06s`).
- exp027's 13 errors often terminated early, so the overall latency reduction
  overstates useful throughput improvement.
- exp027 retried 37 tasks; only 10 ended successful. Generic retry/reflection
  within the same execution bundle was a weak recovery mechanism.

## Media Results

- Audio and Video Technicians: success remained 5/5; mean Self-QA increased
  from 6.0 to 6.6.
- Film and Video Editors: success changed from 3/5 to 1/5.
- `75401f7c...` regressed to a binary stderr decoding error.
- `a941b6d8...` regressed to an OpenCV out-of-memory error despite successful
  video preprocessing.

This does not estimate perception impact because both configurations retained
audio/video preprocessors. A separate on/off ablation is required.

## exp027 Hard Errors

| Category | Count | Representative tasks |
|---|---:|---|
| Syntax / packaging | 3 | `4122f866...`, `7de33b48...`, `854f3814...` |
| Input schema assumptions | 3 | `6a900a40...`, `7d7fc9a7...`, `e996036e...` |
| API / data-shape / version compatibility | 5 | `02aa1805...`, `105f8ad0...`, `1752cb53...`, `1d4672c8...`, `f84ea6ac...` |
| Binary ffmpeg output decoding | 1 | `75401f7c...` |
| Video memory | 1 | `a941b6d8...` |

Of these 13 tasks, exp026 had 6 successes, 4 QA failures, and 3 errors. The
three errors shared by both runs were all Software Developer tasks with
unterminated triple-quoted strings. This supports improving preflight and
strategy-changing repair before changing skill selection.

## Conclusions

- **Sandbox bundle improves execution reliability:** directionally supported at
  the bundle level, not causally isolated.
- **Skills over-selection harms quality:** inconclusive.
- **Perception improves media tasks:** inconclusive.
- **Generic retries are effective:** not supported; most retried exp027 tasks
  remained unsuccessful.

## Engineering Priorities

1. Run `ast.parse` and `py_compile` before executing generated code.
2. Feed a normalized workbook/document schema manifest into generation and
   repair: sheets, headers, merged ranges, and data types.
3. Use exception-specific repair for syntax, schema, API compatibility, binary
   decoding, and memory failures. Retry only when the strategy changes.
4. Use binary-safe ffmpeg subprocess capture and explicit decoding policies.
5. Stream/chunk video processing with ffmpeg-first fallbacks and memory limits.
6. Capability-gate tasks requiring live web evidence; never treat fabricated
   placeholders as successful completion.
7. Keep execution manifests as sidecar provenance tied to the final attempt.
8. Evaluate skill selection only in a controlled selector-vs-off ablation.
9. Evaluate audio/video perception separately with a fixed on/off media subset.
