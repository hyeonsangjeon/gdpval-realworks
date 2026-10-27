# Grader USD guard: schema scope and control-flow fix

## Decision

The USD guard belongs on grading. The owner-approved **USD 200** ceiling is for
inference plus grading, and neither origin may bypass their shared reservation
ledger. Removing grading admission would violate that contract.

The defect was narrower: the request estimator interpreted JSON Schema
metadata as runtime input objects. The actual `read_deliverable` tool declares
`scope.type = ["object", "null"]`; the old visitor required every `type` value
to be a string. That rejected a normal tool request before the fake upstream
call in an offline reproduction. A second boundary defect let the resulting
financial refusal become a `judge_error`, excluding an item from the score
denominator.

This local successor branch fixes those boundaries without changing the amount,
price table, source registrations, frozen grader seal, prompt, rubric, scoring
formula, requested model, effort or context. It does not authorize launch.

## Previous review, kept separate

The comparison was `8ac891e3e0e4752fe15a00139a2691ddf9df7dce` against
`7c7a637967a0f2af4e5482d98d205a1d2ceeedf8`: four changed files had conditional
grading impact, four were optional guards/observations, none remained unclassified.

| File classified (a) | Impact in the earlier source |
| --- | --- |
| `step8_grade.py` | Connected the USD guard to the actual judge client. |
| `core/cost_metering.py` | Admission/settlement refusal could be consumed as a judge error. |
| `core/codex_runner.py` | The separate fresh-retention mode changes prior workspace/output state. |
| `core/codex_task_deadline.py` | The separate keep/fresh policy can change files supplied to later evaluation. |

The fresh-retention mode is prohibited alongside this pilot's input capture;
this fix does not enable or change it. Step8's scoring functions and the core
grader/rubric/tool-judge source were unchanged in that review. Normal unguarded
synthetic outputs matched; adding the money guard reproduced pass/10-point
denominator becoming judge_error/zero denominator before any provider call.
That was not a real GDPVal zero score or an actual five-task model run.

Prior evidence is `/tmp/p5-grader-impact.PmIz8B/REPORT.md`: 154 common tests
passed on each source, and 19 separate guard tests passed. Those counts are not
the validation result for this fix and are not pooled with it.

## Implementation boundaries

- `gpt56_pilot_usd_budget._request_allowance` recognizes only the root
  `tools[index]` Responses function tool's `parameters` as JSON Schema. It
  validates that schema using the already installed JSON Schema validator and
  refuses external references. Nullable unions and property names are metadata,
  not active image/file inputs. Every schema byte still enters the original
  request-size/reservation calculation. Outside this position, existing opaque
  input, override, output-limit, stream and type refusals remain.
- `GradingUsdAdmission.grading_request` translates its typed money refusal into
  `GradingUsdStopped`, a run-control `BaseException`. The original reason and
  source are bounded to the existing vocabulary. Ordinary provider exceptions
  are not translated, and native inference's `PilotUsdRefused` contract remains.
- `MeteredClient` applies that context only when a USD admission is attached.
  Reservation, settlement, unknown-spend consumption and failure receipts are
  unchanged. The control signal crosses the tool/perception retry code without
  becoming a rubric verdict or an excluded item.
- Step8 catches that signal around `grade_task`, preserves already completed
  tasks as partial, emits the fixed grading refusal receipt and exits **4**.
  The existing finish path exports metering receipts and closes the judge.
  It does not add the interrupted task to the grade payload or request another
  paid chunk. A checkpoint-write failure retains refusal/cleanup and does not
  expose the error's private text.

Money refusal can still prevent completion; that is intentional fail-closed
behaviour. It must not be interpreted as a low model score. With valid usage and
an admitted request, the judge request, verdict, denominator and summary remain
the same as the frozen source in the bounded offline fixture.

## Validation scope

`tests/test_gpt56_grader_guard_scope.py` adds:

- the real tool schema through metering, the tool judge and score aggregation;
- schema metadata/byte accounting, invalid schemas/external references, opaque
  inputs, and attempts to reuse the schema exception inside message payloads;
- ceiling and missing-usage stops escaping without a judge verdict;
- a child-process comparison against immutable local Git source `8ac891e3e`,
  using the same fixed fake reply, input files, synthetic tariff and clock;
- Step8 exit/receipt/cleanup, preservation of completed tasks, no fabricated
  interrupted score, and checkpoint failure redaction.

The comparison uses synthetic cases, not the five real task answers. Both child
processes deny network and subprocess effects; no SDK login or provider exists
in the fixture. The synthetic tariff is explicitly not an approved price.

One final invocation of the new scope tests, shared USD/ceiling/USD200 tests,
cost metering, grader, tool-calling judge and Step8 tests passed **598 cases,
0 failures/errors/skips**, exit **0**, **88.98s** pytest / **88.961s** JUnit.
The frozen-source comparison is included in that invocation. Preliminary
invocations are not added to this count.

The final related invocation is also recorded in
`tasks/LATEST_TASK_RESULT/README.md` and the local handoff under
`/tmp/p5-grader-guard-fix.yWSNpq/`. Earlier red tests, test-invocation mistakes
and an interrupted preliminary invocation remain separately labelled there.

## Still closed

The frozen registrations and monetary decision retain their original bytes.
This branch's source changes do not satisfy the old source pins or grant a
successor grader seal. Owner review/registration, approved price/usage mapping,
served-model/Max/1M evidence and the other pilot prerequisites remain separate.
No model call, workflow dispatch, paid execution, push or PR was performed.
