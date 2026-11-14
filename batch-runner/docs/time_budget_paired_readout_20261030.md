# Model-free time-budget capture and paired readout

Recommendation 3 continues local commit `445affbc3f140c45a8610a8059b84c74e994c42e`
on `leader/time-budget-2404-guard-20261030`. It adds no workflow, network intake,
launch authority, model call or grading execution. The existing observation and
grading execution controllers are unchanged.

## What this check does

| Item | Fixed scope |
| --- | --- |
| Study | `gpt54_sandboxv2_codex_time_budget_v1`, GPT-5.4/xhigh configuration bundles |
| Schedule | V2 r1 T1–T5, Codex r1 T1–T5, Codex r2 T1–T5, V2 r2 T1–T5 |
| Input | Twenty **synthetic** captured payloads, references and deliverables, not private Task4 results |
| Runner evidence | Synthetic GitHub-hosted Ubuntu 24.04/image metadata inside hashed capture bytes |
| Grader input | Existing `prepare_observation_grading`, frozen F source and rubric/config/source checks |
| Grading | Explicit file stubs serialized and schema-checked with F Step8; no `Grader` construction |
| Comparison | Ten `(task_id, repeat)` pairs, V2 minus Codex in percentage points |
| Boundary | Wiring and refusal tests, not model performance, hosted-kernel readiness or billing evidence |

The registration and source successor are unchanged, including their 42-pin
checks. F is still `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, whole-template
SHA256 `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
Sol/Max, prompt v2.2 and one grading attempt per resulting observation are not
changed. The time-budget study's findings-only/null cost policy is retained;
the separate native pilot's USD 200 policy is not imported here.

## Two explicit local stages

`gpt54_time_budget_paired_readout.prepare_fixture_captures(plan, captures)`
validates the whole inventory, then prepares one frozen-F input per available
scheduled ID, in ABBA order. A capture supplies the existing preparer's full
independent R/F/input/result anchors, not just a path or asserted success.
The scheduler derives every cell/ID; a changed repeat or ABBA position cannot
relabel it. The result file's digest, fingerprint, one-row scope, terminal state
and deliverables are checked by the existing preparation validator.
Sorting downloaded fixture inputs is not proof of execution order: the earlier
durable schedule admission/capture checks remain mandatory for any live intake.

Every captured row is retained, including error/timeout rows; each input still
contains exactly one observation's row.
The preparer's existing reservation and no-clobber rules prevent a second
preparation at the same destination. This is local test-input uniqueness,
**not** a new distributed grading-attempt guarantee or permission to replay
a consumed live observation. An inventory collision is refused before any
preparation; a later source/publication failure leaves its existing reservation
intact, with no automatic repair or adoption.

`aggregate_fixture_pairs(plan, prepared, grades)` consumes explicit local stub
files. Each binds the observation ID and the exact preparation-marker SHA256.
It rereads every materialized source/config/input/schema byte and runs the
existing grade-schema/identity/judge/rubric/scope validator without invoking the
execution controller. Rubrics are parsed from the verified local snapshot;
there is no rubric download fallback. No caller-provided grader callback exists.

Capture bytes must explicitly carry the synthetic fixture label; unlabelled
or real captures cannot silently become fixture evidence. The report, each
observation and each pair carry `evidence_kind=synthetic_fixture_not_model_quality_or_billing`,
`launch_allowed=false` and `execution_enabled=false`, together with the original
registration, schedule, helper and source identities. Input and grade digests,
the exact image version, reported rubric denominator and verdicts remain with
each observation. A digest does not authenticate a real remote artifact; that
intake remains outside this fixture-only API.

## Missing values and refusals

| Case | Behavior |
| --- | --- |
| One side absent, or no grade on one side | Retain the registered pair as `missing`; absent score and difference are `null` |
| Failed/cancelled/abandoned/timed-out generation | Prepare its retained row once; keep outcome/reason and any reported stub grade, but paired score is `null` |
| Cleanup not confirmed | Retain the uncertainty as another missing reason; do not promote a later positive stub |
| Partial grading, task/judge error or excluded rubric coverage | Preserve the reported grade/denominator; no comparable score |
| Nonpositive grading denominator | `grade_denominator_unavailable`; no zero imputation |
| A completed, valid zero-point grade | Keep the genuine zero and compare it normally |
| Duplicate capture/grade, unknown ID, >20 entries, changed cell/binding | Refuse; no deduplication, selection, retry or score-based extra observation |
| Grade without capture or wrong preparation/task/judge/F hash | Refuse |
| Ubuntu 22.04, missing runner image, mixed image versions or runtime sources | Refuse; no historical relabeling or pooling |
| Changed captured/materialized/grade bytes | Refuse existing digest/schema checks |

All twenty observation slots and ten pairs remain in the report. The descriptive
mean uses only complete pairs and reports its actual denominator **out of ten**;
no complete pair means a null mean. Outcome counts retain failures and missing
captures independently. A complete-case mean is not an overall success rate,
and selectively missing grades can bias it. ABBA does not remove time drift or
prove an isolated harness effect.

## Offline verification and remaining integration

The test fixture reuses the existing synthetic source factory, adding an
explicit four-point rubric **before** its parquet/catalog/source hashes are
computed. It does not repin original inputs or change F's code. For the normal
case, the four ABBA blocks receive stub scores 75/25/50/100 percent, respectively;
the ten expected differences are therefore +50 percentage points. These values
are deliberately planted to detect swapped sides/repeats and must not be cited
as measured model scores.

`tests/test_time_budget_paired_readout.py` is automatically selected by the
existing `time-budget-contracts` glob and excluded from core pytest by the same
glob. No workflow list or pinned workflow hash needs changing. Its offline
fixture rejects provider, model/grader construction, external network, shell
execution and non-allowlisted child processes; only existing local Git source
checks are allowed. Actual observation startup is not run on NAS. To run only
the new offline path from `batch-runner` with the existing test dependencies:

```bash
python -m pytest -m 'not integration' tests/test_time_budget_paired_readout.py
```

Final local verification: **512 distinct passed, 0 failed, 0 errors, 0 skipped**.
This is the selected related offline set, not the entire repository suite:

- 44 new paired-readout cases, including all twenty inputs and ten pairs.
- 19 existing Ubuntu 24.04/CI-partition guards.
- 449 existing registration, schedule, F input preparation, native grading
  execution-stub and native grading-mode cases.

Python 3.10.12 / pytest 9.2.0; empty inherited environment, plugin autoload
disabled, HF offline/implicit-token/telemetry guards, no integration or actual
kernel-positive observation startup. Final JUnit/logs, `test-summary.json` and
the retained synthetic `fixture-paired-readout.json` are under
`/ai-work/copilot/_tmp/time-budget-paired-readout-20261030.u9srSJ/`.
The three final reports are disjoint; the earlier exploratory 41-case run is
not added to the count. The summary binds the final tested Python/test byte
hashes and the synthetic JSON digest.

Before live dispatch, separate work is still needed: reviewed publication of
this branch; an approved 20-cell serial Actions dispatch/artifact-intake path;
independently anchored real capture/source/input/runner identities; a generalized
frozen-F grading admission/controller with durable one-attempt storage; and
Ubuntu 24.04 sandbox/cleanup validation on the hosted runner. Existing partial
or out-of-order private study history cannot be adopted by this offline path.
The single-cell live grading restrictions and all execution approvals remain
unchanged. No private results were read to make this fixture.
