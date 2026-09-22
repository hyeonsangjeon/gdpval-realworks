# Latest task result

## Opt-in cumulative Codex task deadlines

Implemented the first external-budget control slice on independent baseline
`eba56139f95443a715e8309e75c57fe5688c1f2b`. The tested implementation is
`fe4d772df69c1653709bdfaf5bede8d005a6bf01`. This is implementation and synthetic
offline evidence, not a pilot result, model observation or execution approval.
It is separate from the frozen selector correction in #649; no approval of
that work covers this implementation.

### Behavior and default boundary

The opt-in `execution.codex.task_deadline` block declares `condition: A`, `B`
or `C` and `repetition: 1` or `2`. Existing configs are not opted in. The
consumer requires `codex_foundry`, one prepared condition, a stable run lineage,
`timeout: 1800`, `max_retries: 3`, no Self-QA/preprocessors and an explicit
host-owned `--codex-deadline-state` directory. New cells require explicit
initialization into an absent directory; restart/resume must restore that same
state, not initialize another directory.

One 180-minute expiry is persisted per run/task/condition/repetition and bound
to the ordered task IDs and prepared fingerprint. It includes backoff and
restart downtime. Missing, incompatible, linked, checksum-tampered or
backward-clock restore state refuses. Atomic private-JSON persistence and a
nonblocking process lock protect the host record outside agent-writable roots.
The checksum detects damaged/edited state, not a hostile host replacing both
payload and checksum.

The existing retry loop and `TaskExecutor` pass this deadline to the real Codex
turn runner. Every attempt is admitted against remaining time. Native waiting
is bounded by `min(1800, remaining_seconds)`; backoff cannot extend the expiry.
A retains four durable attempt admissions. B/C replace that cap with the
cumulative deadline and retain identical partial-artifact capabilities. The
existing transient-error retry categories are unchanged; this is not an
adaptive retry policy. `task_deadline_exhausted` records exhaustion without an
additional turn. Missing/invalid state records `task_deadline_state_refused`.

Interrupted attempt workspaces remain available. Path-free result records
carry expiry, remaining time, admissions and observed completed waits. The
existing receipt ledger records observed token usage with missing-call/cost
qualifications, not complete API-call or invoice accounting. There is no
automatic monetary cutoff. Without the opt-in, legacy exp035 and other modes
retain their existing retry, timeout and cleanup behavior.

### Focused evidence

One fresh pytest process ran this exact command on the tested implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_codex_task_deadline.py batch-runner/tests/test_ghcp_vm_gate_contract.py::test_ghcp_vm_gate_contract_preserves_history_foundry_and_backend_partition
```

Result: `30 passed in 40.83s`, exit 0. The 29 deadline/binding cases cover retry
and process resume without resetting expiry; bounded native waits; backoff;
no turn after exhaustion, including expiry during receipt reservation; new
cell identities; retained partials and observed usage; invalid restore refusal;
config/CLI propagation; legacy behavior; and genuine current/stale grader
bindings. The additional case preserves the coupled Foundry/GHCP digest and
workflow/history assertions. Clocks and the native runtime were stubbed;
provider/auth/network/subprocess construction and real sleeps were blocked.
No full lane, selector family, prior binding family or real-data preparation
was rerun. `git diff --check` passed.

The unchanged `step8_grade.compute_grader_source_hash()` recomputed both full
closures from each original template path and its actual configuration bytes:

| Active template role | Previous SHA256 | New SHA256 |
|---|---|---|
| `default_v2_sol_max.yaml` | `40ada97c41117e3966e5a192c19dafcf4db34d4dd2ddd4230c4b729f421d6e08` | `fdfb7b9160635859d2c46ee9a79d5d908bc4ad546f9d240893da98159752258d` |
| `exp035_codex_foundry_full220_v2_sol_max.yaml` | `56fdb74e2f9fd1afbe9d064fc2cb1e1410d5cebec55edcca8324effd1a1dc9e1` | `c85f5b7ac5a723266172fedae39d38a69bd93cebae25888c63469f038c97ef01` |

Only active GPT-5.4/Foundry source bindings and their coupled guards change.
The new deadline module is pinned explicitly; exact source counts become
37 and 58 respectively. The Foundry YAML digest guard is
`824533c9e08b1b24217c66497ee9c269e2c156411e3a5d95238a1bcc578e80f0`.
Historical source/base identities, grader templates/results, task/control
settings, live blockers and false launch flags remain unchanged. No workflow,
model/effort/context, pricing, `core/qa.py` or HF-upload code changes.

### Remaining work and review boundary

The intended pilot remains `advance_check_5` × A/B/C × two repetitions, 30
executions, ABC then CBA per task, with one active inference execution on the
same deployment. This slice does not implement that dispatcher, agent-session
rehydration or adaptive planning. End-to-end state recovery and equal B/C
continuation behavior still need later implementation/review. The supervisor's
Astra Max/1M settings are not a target-model selection. Leader-directed paid
launch remains separate from this implementation-only authorization.

This implementation and these records are unreviewed. Final-HEAD automatic
checks and leader review remain outstanding. One normal GitHub source fetch
occurred at intake; the prepublication main read still returned the exact input
baseline above, so no integration merge was needed. No CI query, manual rerun,
review wait, Project edit or PR merge occurred. No Azure/HF/provider/model, VM,
grader or paid operation ran. Original inputs, prepared/failed real artifacts,
published grades and the earlier operational changelog entries were untouched.
This does not complete the pilot or Project card.

The full skill catalog was checked once for this phase. `experiment-design`
kept the approved controls fixed before active pin edits. Repository backend
and LLM-systems guidance governed the existing retry/runtime integration;
grading guidance governed genuine source-identity coupling, not grading.
`experiment-report-en` separated synthetic evidence from unmeasured outcomes;
`im-not-ai-en` preserved exact commands, values and qualifications. UI/animation,
framework, workflow, QA/upload, pricing and repository-publication skills did
not match this bounded implementation.
