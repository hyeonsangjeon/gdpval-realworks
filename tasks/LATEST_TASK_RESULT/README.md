# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 V2 Grading-Input Materializer

### Scope and Outcome

`materialize_v2_grading_input` converts one independently bound Sandbox V2
`run_record.json` and its deliverables into canonical local step8 inputs. It
reuses `compile_grading_plan` and its dispatch plan, the existing result
projector, manifest binding, source identity resolver, and deliverable
validators. It does not execute inference or grading, materialize a checkout,
or authorize a launch.

Work started from immutable main
`641eee488ad6cd9a7bc33d0beeab061dcae8f52b` in branch
`b/gpt54-v2-grading-input-materializer-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-v2-grading-input-materializer-20260919`.
The preservation checkout and prior worktrees were not changed.

Exactly nine files differ from that base:

- `batch-runner/gpt54_v2_grading_input.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Binding and Materialization Boundaries

The supplied typed `ComparisonGradingRunSpec` must exactly match a compiled V2
run. Codex specs, altered specs, missing or changed source pins, and control
drift are refused. The four-run order remains V2 r1, Codex r1, Codex r2, V2 r2;
each run retains the same ordered `advance_check_5` tasks, Foundry GPT-5.4
identity, `xhigh` request, limits, and pinned grader contract. This is still a
configuration-bundle comparison, not an environment-only causal claim.

The caller supplies a separate inference identity document and its
independently approved SHA256. That document binds the canonical inference
repo/revision, run/condition/repeat, task order, producer path/pointer,
manifest and combined grading-plan digests, config/source-pin digests, actual
run-record bytes, and each task's deliverable paths, sizes, and hashes. A
self-asserted verification flag is not accepted. Known dataset provenance or
the Git base cannot substitute for inference identity. This is an offline
check against an approved binding, not proof that a live revision exists;
issuing and verifying that document remains an external gate.

The function checks the producer's task-content binding, chosen settings,
config path/digest, terminal cardinality, and run summary. Missing, duplicate,
reordered, extra, partial, resumed, or contradictory rows are refused.
Terminal error rows remain errors. Files must belong to their task and match
the approved bytes. Extra task trees/files, missing files, empty successful
deliverables, hardlinks, symlinks, traversal, and destination collisions are
refused. Receipts pass through `project_result_row`; absent and present-null
fields remain distinct, and unknown/partial costs never become zero.

After input validation, the function stages snapshots of the verified bytes
in a private sibling tree. The destination is an input bundle, with only:

```text
batch-runner/workspace/step2_inference_results.json
batch-runner/workspace/upload/deliverable_files/<task_id>/...
```

The real `load_local_inference_results`, `resolve_source_inference_identity`,
ordered task filter, result fingerprint validator, and deliverable validators
read the resulting fixture without an alternate schema. Creation, writes,
and cleanup remain anchored to one open parent descriptor, including when its
pathname is replaced. Installation requires native Linux
`renameat2(RENAME_NOREPLACE)`; there is no unsafe overwrite fallback. Failed
staging is cleaned up with Python 3.10-compatible operations.

The GPT-5.4 required source set grows from 22 to 23 by adding the materializer.
The combined plan binds its function name. The Sol YAML only refreshes the
existing shared-parser digest; its 16-file source set and launch gates are
unchanged. The grader source-closure digest remains
`c10ea303f212bab87ea6303cb41ee51e21430e6bc35df7a69b9a63d265f3a241`.
Production runtime/grader defaults, schemas, pricing, receipt arithmetic,
historical ledgers, and sealed evidence are unchanged.

### Verification

Only this selector was run, first on the initial implementation and once more
after the immutable review found blocking defects:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_v2_grading_input.py::test_v2_grading_input_is_bound_atomic_and_offline
```

- Initial implementation, preserved at
  `d798905ceb89b6d8116f7adeb4398eeab244bad9`: `7 failed, 69 passed in 45.47s`.
  Native rename was unsupported on this host, and Python 3.10 rejected the
  original cleanup API. The first review also found writes tied to a mutable
  parent pathname and native-support assumptions in positive tests.
- Corrected implementation, committed at
  `4a656026c81453a4b6f9a86bbe27db23deaf373b`: `79 passed in 48.22s`.
  This was the single permitted corrective rerun. No other selector ran.

The successful cases use an explicitly test-only, single-threaded primitive
double to check canonical output bytes, real step8 compatibility, both V2
repeats, preserved errors, and null/partial receipts. Failure cases check
binding drift, unsafe/missing/extra files, collisions, write/rename failures,
and parent replacement at staging and during writes. They assert no forbidden
calls and verify cleanup or preservation of an existing destination.

The separate native case reported:

```text
Native RENAME_NOREPLACE unavailable (errno 22); refused with no destination or staging residue.
```

The host is Python 3.10.12 on Linux 3.10.102, with btrfs at `/tmp`. Fixture
success is not native atomic-install success on this NAS. A materialization
host with working native no-clobber rename support is still required.

Subprocess, network, provider auth, route preflight, grader/rubric-loader
construction, typed Azure client creation, and cost-recorder construction are
forbidden by the fixture. No standalone preflight, broad suite, build, actual
five-task/220-task run, model/grader/VM/Azure/HF operation, credential lookup,
workflow dispatch, or Project edit was performed.

`git diff --check` against the immutable base passed. A byte comparison also
found no changes under `batch-runner/core`, `batch-runner/step8_grade.py`,
`batch-runner/grading_configs`, `batch-runner/schemas`, `.github/workflows`, or
`data`.

### Immutable Review Boundary

The first read-only `first-reviewer` audit of
`d798905ceb89b6d8116f7adeb4398eeab244bad9` returned `REQUEST-CHANGES`: two BLOCK
findings for Python 3.10 cleanup and mutable-parent writes, and one MAJOR
finding for tests that assumed native rename support. It found no additional
high-confidence source-binding defect and requested no escalation.

Those findings were corrected in the new implementation commit
`4a656026c81453a4b6f9a86bbe27db23deaf373b`, without amending the first commit.
The read-only review of that exact corrected HEAD returned `APPROVE`, with no
remaining BLOCK, MAJOR, or MINOR findings and no escalation requested. It
confirmed both blocking corrections and the separation between fixture and
native-capability evidence. The reviewer ran no tests, preflights, clients,
network calls, or mutations.

Only this record and `CHANGELOG.md` differ from the approved implementation
HEAD. Approval covers that HEAD, not the later records or the deferred live
gates. Leader review and automatic CI evidence remain pending. No carrying-PR
merge result or future merge SHA/time is claimed.

### Remaining Work

This unit implements only V2 result/deliverable conversion into step8 input.
Both `launch_allowed` and `full_220_allowed` remain false. The following gates
still need separate reviewed work:

- Externally verified inference identity issuance and approval.
- Native no-clobber rename support on the materialization host; this NAS
  refused it safely rather than installing the native fixture.
- Codex input/deliverable verification and checkout/config materialization.
- Workflow/materialization gates for the four-run comparison.
- Served V2/Codex reasoning capability, native call/token caps, and live
  model identity/input bytes.
- Usage/tariff evidence under the unchanged record-only null/partial policy.
- The separate Sol pilot's Copilot provider/auth route: no official
  runtime-to-Codex handoff contract has been established. No guessed bridge,
  personal OpenAI account, or Foundry substitution was added.

The generic `comparison_materialization_and_workflow_gates_not_wired` blocker
is retained. This function does not guard every paid entrypoint, and this unit
supplies no authorized launch command.

### Skills and Review Roles

The full available skill and repository-agent catalogs were inspected once
before implementation. `experiment-design` was applied before code or plan
changes to preserve the comparison question, task/input pins, repeats, units,
configuration-bundle scope, and stop boundaries. The consolidated grading
specification and stable `tasks/grading_task` baseline were read first. The
required `grading-engineer` role audited producer/projection, local step8,
deliverable, and source-identity boundaries. `first-reviewer` audited the
immutable implementation. These roles used the available engine, not an
external paid model invocation.

`im-not-ai-en` was applied to the English changelog, completion record, and PR
wording. Commands, SHAs, counts, results, and uncertainty were checked manually;
the owner's restricted validation scope takes precedence over an additional
fidelity-script run. Experiment-report skills do not apply because this task
has no measured experimental outcomes. Repository-readiness, UI, and animation
skills do not apply to the existing offline input boundary. Workflow files,
`core/qa.py`, and HF upload code are untouched, so no extreme-reasoner scope
was created. No API/provider authentication contract is introduced.

## Prior Result: #619 Offline Pinned-Grading Plan

[#619](https://github.com/hyeonsangjeon/gdpval-realworks/pull/619) compiled four
ABBA grading specs and the combined dispatch/grading document. Its reviewed
implementation HEAD was `e9d62ffac93ff69f151e113b4d84e7e725824f0a`, and its
final branch HEAD was `9982ca8517aac3cbd511267c80bde686b59bfd86`. The historical
selector `test_gpt54_pinned_grading_plan_is_bound_and_non_executing` reported
`36 passed in 22.79s`; first-reviewer returned `APPROVE` with no findings.
That selector was not rerun here.
