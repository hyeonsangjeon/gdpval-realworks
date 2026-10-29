# Native pilot runner admission and receipts — 2026-10-29

This is the leader's **runner-admission/receipt subtask only**, based on
`cf1401e1cedc5e2e051ef38de46a2f90a34b370a`, in branch
`leader/runner-receipt-20261029`. It does not migrate workflows from Ubuntu
22.04 to 24.04, wire a pilot dispatcher, approve a host, or run a model/judge.
NAS remains a development, offline-test and result-reading host only.

## Admission

`core/runner_environment.py` reuses the GHCP gate's operational rule: explicitly
allowlisted Actions metadata **and actual OS release/platform** must agree.
The GHCP module is on another branch, not a runtime dependency of this branch;
its small observation rule is shared here by the three native entrypoints.

| Candidate host | Required evidence | Result |
| --- | --- | --- |
| GitHub-hosted Ubuntu | `GITHUB_ACTIONS=true`, `RUNNER_ENVIRONMENT=github-hosted`, Linux, matching `ImageOS`/actual Ubuntu version, matching `RUNNER_ARCH`/machine, nonempty runner name, image version, run ID and attempt | Admit consistent Ubuntu **22.04/ubuntu22** or **24.04/ubuntu24** only. Keeping 22.04 is deliberate: migration is a separate task. |
| Explicitly approved Azure VM | `NATIVE_AZURE_VM_APPROVAL=owner-approved`, a 64-hex `NATIVE_AZURE_VM_APPROVAL_SHA256`, and `NATIVE_AZURE_VM_ID` matching the local Microsoft DMI system UUID, on supported Ubuntu/Linux | Admit only the explicit direct-VM route. No default approval or self-hosted-Actions fallback. No Azure/IMDS request or credential lookup. |
| NAS, local, self-hosted, missing/conflicting evidence | Missing host admission | Refuse model execution; pure plan/reader/dry-run operations remain available. |

The VM marker and approval digest are operator-supplied, not cryptographically
authenticated owner approval. DMI and Actions environment values are locally
observed evidence, not remote attestation; same-user metadata spoofing is not
ruled out. No Azure VM or marker was supplied or approved during this task.

The receipt retains `RUNNER_ENVIRONMENT`, `ImageOS`, `ImageVersion`, `RUNNER_OS`,
`RUNNER_ARCH`, `RUNNER_NAME`, `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, actual OS and
machine, and the hosted/admitted booleans. Unknown fields remain null. Only those
nonsecret names and the explicit VM metadata names are read; there is no token,
credential-store or complete-environment dump.

## Request and persistence boundaries

| Path | Before-model guard | Saved runner evidence |
| --- | --- | --- |
| Connection diagnostic | CLI paid-mode admission before settings/auth; native `probe` before runtime; valid Responses POST before transmission | Native observation/diagnostic record plus emitted receipt |
| Native inference | `CodexAgentRunner.run` before task admission and `open_runtime` before auth/SDK; the owned HTTP observer rechecks before each upstream reservation/connection | Native result, Step2 `observability.runner_evidence`, and hash-bound pilot wire receipt; the native result host requires the same observer evidence before sealing the complete handoff |
| Step8 grading | Main entry before config/auth, recheck before route setup; wrapped grader, perception and retry clients recheck every request, including unmetered clients | Grade payload `runner_evidence`; refusal JSON under `workspace/runner-receipts/` |

Missing/invalid host evidence uses **`execution_environment_refused`**; changed
admitted evidence uses **`execution_environment_changed`**. HTTP observers stop
and clean up their existing owned runtime/socket path before forwarding another
request. Existing request/token/USD counters and the USD **200** limit are not
changed or reset by this guard.

Grading host refusal is a `GradingEnvironmentStopped` control exception, not a
rubric verdict. Ordinary `except Exception` handling cannot turn it into
`judge_error`. Step8 preserves already completed tasks, writes a separate
refusal receipt, uses existing cleanup and returns exit **4**, rather than
publishing a partly marked task or reducing its denominator.

## Schemas and immutable source registrations

The additive evidence envelope is **`native-runner-evidence-v1`**, with stage,
bounded observation and SHA256 of canonical JSON. Readers validate shape,
stage and digest. Existing `cost-receipt-v1`, grade schema **1.4**, diagnostic
schema **/3 and /4**, and pilot wire receipt **v1** are not rewritten/versioned
away. The grade schema already allows additive root metadata; the closed cost
receipt is untouched. Historical records without runner evidence stay historical
records without that proof, not retrospectively verified executions.
The live native handoff now requires `runner_evidence` and compares it with the
owning observer before computing the existing complete-result digest. An old
handoff without this field is refused, not silently upgraded or exempted.

No sealed registration, cap, grader template, schema file or workflow was
changed. The active 2026-10-27 response-capture source profile already mismatched
`step8_grade.py` at the base commit. It now mismatches **seven** pinned files:
`core/codex_runner.py`, `step2_run_inference.py`, `gpt56_pilot_wire_receipt.py`,
`gpt56_pilot_native_result_host.py`, `step8_grade.py`, `core/grader.py`, and `core/grade_payload.py` (**six additional**
mismatches). The new `core/runner_environment.py` also needs explicit inclusion
in a subsequently reviewed source closure; the diagnostic script's new source
must be included in diagnostic publication review. The grader source hash
changes as well. No pin check, rejection condition or old seal was relaxed to
make these bytes appear approved. Subsequent registration/sealing remains
necessary before this branch becomes an executable reviewed pilot source.

## Offline verification boundary

Tests use synthetic hosted/VM metadata and fake clients or guarded loopback
servers, not a NAS model runtime. They cover missing/mismatched labels and OS,
architecture/run/attempt fields, explicit VM markers plus DMI match, receipt
tampering, pre-auth/native refusal, HTTP pre-forward refusal, per-request grader
refusal, Step2 persistence and Step8 refusal without a fabricated score. The
existing frozen-grader replay retains its network/process denial and compares
the same nullable-tool-schema request, verdict, denominator and score.

Development diagnostics are retained under
`/tmp/p5-native-runner-receipt.6RBA4c/`: system Python lacked the pinned SDK;
the existing isolated SDK/CLI **0.147.0** environment was reused without an
install or CLI launch. A later interrupted run exposed missing fixture work
paths, an outdated fake-thread `Event`, a newly required source-drift expectation,
and a mismatch between returned/emitted diagnostic metadata. Integration tests
also found runner evidence being added after the private-result hash was sealed.
It is now required and bound to the owning observer **before** that seal; the
existing complete-digest equality and unknown-field rejection remain enforced.
Those issues were repaired
without relaxing the host, source, budget or scoring checks. Final combined test
counts are recorded in the local handoff and LATEST after completion. The
expanded 1,476-case run hit its test-only 900-second limit without a completed
JUnit result and is **not** reported as passed. Expanded reruns were interrupted
to repair the handoff issue. Final evidence uses completed targeted suites,
including the real five-task verifier path and missing/tampered runner evidence.
One focused suite used real tmpfs-backed temporary files (not mocked file/SQLite
operations); its temporary fixture override was removed from the final change.

The experiment-design boundary is unchanged: runner metadata is not a served
model/Max/1M proof, a passing fixture is not a benchmark result, and the same
grader result does not establish equal real billing. No model call, auth/token
issuance, workflow dispatch, push or PR was made for this branch.
