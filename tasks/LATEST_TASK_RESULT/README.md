# Latest task result

## Task2 failure event and uncertainty retention

Exactly one synthetic test exercised the new Task2 interaction:
**1 passed in 19.36s**, exit 0. The test reached the reserved construction
failure, exact safe stderr event, private uncertainty retention and duplicate
execution refusal. It added no production or workflow change and authorized
no live observation.

### Reviewed and tested source

| Basis | Exact identity and evidence |
| --- | --- |
| Leader-reviewed integration | `741c0fabcf7ad612b470df0c966d32a7e17f8b23`, tree `fdbfaf46a168868ac529bf7da30797b7d8e90ec0` |
| Selected-task parent | `0ff2bd7378c392f3d3380a2983107a696f0bc75b`, tree `1c1b29aad70c3b31a4ea980ef6a4d43f1183d11f`; review `5429517883` |
| Diagnostic parent | `86bf684706bdbfc641f10c2774b7e4884d8fc7cd`; reviewed diagnostic source `7aebe28c402cfb71463231f2fb1a75825a26391f`, tree `0165ff4f9f7d226a4cac8f34803d6134f53ba693`, review `5428735621` |
| New test commit, tested clean | `3d66290d364f41efabfeb598bf9e322fa1b8596b`, tree `88f2c0db1e6d8b5f9aed1b5a402ac76d40fe2733` |

The existing clean PR760 worktree was fetched and fast-forwarded to the exact
integration commit after its tree, parents and ancestry were checked. No other
worktree was altered. The leader supplied the Python parse, AST and complete
1783-blob integration checks. Those checks establish structure, not behavior;
they were not repeated or relabeled as a combined pass. This one test adds
behavioral evidence only for the selected Task2 failure-retention interaction.

### What the test reached

The existing request selects registered Task2
`0112fc9b-c3b2-4084-8993-5a4abb1f54f1` in
`gpt54_time_budget_v1_v2_r1` / `sandbox_v2` / repeat 1 without changing
`CELL` or `PREFIX`. Existing temporary linked-source, registration, synthetic
input, direction, kernel and private transport fixtures run the real validators.
After the invocation reserves execution and constructs the observation control,
the ordinary voice-construction seam raises the existing secret-bearing test
exception. Its text is never formatted.

The invocation returns CLI exit 2 with the unchanged generic stdout. Its exact
four-field stderr event is non-authoritative diagnostic metadata:

```json
{"category":"unexpected_error","format":"gpt54-time-budget-first-v2-ci-failure-v1","reason":"execution_refused_or_uncertain","stage":"observation_callable"}
```

The actual failure receipt is read for the snapshot and reread before private
retention. The synthetic CAS and immutable readback acknowledge only Task2's
claim and output manifest under its selected namespace. Completion is checked
against the independently requested cell, never against the returned cell.
Its status is `uncertain`; result identity, result fingerprint, terminal reason,
usage, cleanup and host reuse remain null. The manifest retains the safe receipt
with `unavailable_no_fabricated_study_row` and no result files.

Duplicate execution refuses with `execution_already_consumed`, without another
construction, request, event or claim. The one permanent Task2 claim and local
reservation bytes remain intact. Explicitly invented old Task1 claim/output
bytes and their writers are preserved in every checked synthetic revision.
Storage tokens are absent at construction, and the event, receipt, manifest
and completion contain no secret text. These are model-free transport facts,
not live host, provider, publication or billing evidence.

### One bounded proof

Only this full node was run, once:

```text
tests/test_time_budget_first_v2_ci.py::test_time_budget_v2_selected_task_failure_retention
```

The existing Python 3.10.12 environment ran with a clean pinned HEAD/tree,
300 seconds plus 5 seconds termination grace, no `-x`, and the unchanged
30-second temporary Git setup bound. Socket, write and credential sentinels
remained active. No old selector, full suite, kernel probe or CI operation ran.

Artifacts are retained in `/tmp/pr760-selected-task-failure-proof.pVEtO1SO/`:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `command.sh` | 1311 | `867ae5871d3886d8df15a4018411bd5509d798b25eaff46e9c62124ee4137d1a` |
| `pytest.log` | 614 | `7d855c859382bdac8f4e4bfb10436f82cbbdc5aa3b09f729ace0043aa24b2aff` |
| `junit.xml` | 441 | `4fce83bb8423462c0d84373cab8abddffe18724e7a612141f542d27c696ba31b` |
| `exit-status` | 2 | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |

### Separate earlier evidence

The [five-path selection continuation][selection] remains **5 passed in
96.48s**, exit 0, at `70a02619276bc9da072567d5ee0e4060aed6dbbf`, tree
`1d85a59c1baf5660d80a3abd5eedf14053dc54b2`. The [original failed
invocation][original] at `e99fbc774a6fa2e2c02624e8f78bcc40200928cb` remains
**6 passed, 4 failed, 1 setup error in 215.64s**, exit 1. Correction
`9b1d5b7fddf887a4233630452a261ff3bebfe880` was unrerun at that handoff.
The [diagnostic proofs][diagnostics] remain **5 passed in 95.25s** and
**8 passed in 162.87s**. None of those tests was repeated. These separate
observations do not become an aggregate selector pass.

Historical Task1 run `37456739936` / attempt 1 / job `112246098370` remains
permanently consumed and uncertain. Claim
`e53fe8d4c47ef2a05aea8ffcc0fe1745a9b3c288` and acknowledged output
`f602355f945471963a338ccf79783a6f802ac6dd` were not read or changed. Its first
throw, model-call count, cost and cleanup remain unknown. It is not a zero
score, an excluded planned cell or permission to replay, resume, regrade or
adopt old state.

### Post-proof delta and remaining gates

The post-proof delta is exactly `CHANGELOG.md`, this LATEST record and the
direct evidence paragraph in `batch-runner/README.md`. The new test and all
production/workflow bytes remain those of the tested commit. The final
records-only child commit's exact HEAD/tree is returned in the delivery handoff;
no final-HEAD behavioral or CI pass is claimed.

Final review and ordinary final-HEAD CI remain leader-owned. A live Task2
request still requires accepted combined runtime source, independently bound
input/direction identities, actual run/host/canonical paths, a finite window
and the private parent CAS. Existing one-attempt/1200+20/host guards and the
fixed 20-observation study are unchanged. No live request, private input/result
read, HF, Azure, provider, model or grader operation was performed.

The retained source/CI guidance and `im-not-ai-en` were applied to the changed
English records. No new design review or unavailable reviewer-harness retry
was undertaken; the leader's reviews are not attributed to a spawned model.

[selection]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/0ff2bd7378c392f3d3380a2983107a696f0bc75b/tasks/LATEST_TASK_RESULT/README.md
[original]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/70a02619276bc9da072567d5ee0e4060aed6dbbf/tasks/LATEST_TASK_RESULT/README.md
[diagnostics]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/7aebe28c402cfb71463231f2fb1a75825a26391f/tasks/LATEST_TASK_RESULT/README.md
