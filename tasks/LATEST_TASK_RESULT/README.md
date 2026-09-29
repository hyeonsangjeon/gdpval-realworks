# Latest task result

## PROJECT5-RETENTION-FIRST-CELL-CONTROLLER

At `8db003867a39c5a84bb5a544d0526c2128467e59`, the one authorized offline
selector collected 1 test and reported **1 passed in 26.20s**, exit 0, not
skipped. It verified real retained originals, a new Task4 preparation packet
and the actual Step2 runtime layout. Local admission, ownership and deadline
checks used an injected process transport and synthetic clock. No child,
model request, inference, grade or live admission ran.

Branch `b/codex-retention-first-cell-controller-20260929` starts at exact main
`1b4c28abdb74d196f97d968a27cd59d76d701107`, tree
`c1827f99f9534e69eb8101845cb07147755f177b`. The leader reported 10 passing
checks for delivered PR700 at `e8cd03b5b3d539cdb2369ac7cfd815626dd56da4` /
[review 5348364806](https://github.com/hyeonsangjeon/gdpval-realworks/pull/700#pullrequestreview-5348364806).
That review covers the base, not this new controller. Earlier preparation
failures, passes and identities remain separate in the
[immutable prior handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/1b4c28abdb74d196f97d968a27cd59d76d701107/tasks/LATEST_TASK_RESULT/README.md);
none was replayed or combined with this result.

### Scope and evidence

The [controller](../../batch-runner/codex_retention_first_cell.py) accepts only
`3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1`, ordinal 0
of the unchanged eight-cell registration. It reuses the real plan compiler,
packet verifier, prepared/config serializers, schema4/reference readers,
caller-held-FD publication helpers, owned-child primitives and deadline store.
The selected row, unchanged canonical manifest and required references are
staged in this dedicated checkout's actual Step2 paths. Original five-task
inputs remain unchanged. The actual materialized grader is recomputed and
bound to its config bytes and location; copying an old hash is not evidence.

Default planning is read-only. Explicit staging reserves file publication
only, not an inference slot. Both public execution and the internal protocol
refuse the real child transport before a reservation, clock or child. A
no-launch packet, caller boolean or caller-provided receipt cannot grant
authority. Partial staging is retained and cannot be overwritten or adopted.

The [focused test](../../batch-runner/tests/test_codex_retention_first_cell.py)
used genuine inputs and validators for source/cell/input refusals, staging,
readback and grader identity. Its separate simulated control cases exercised
the real host-state checksum, local flock, one-use reservation, unresolved-owner
refusal, ambiguous start/completion refusal and durable clock/expiry checks.
A zero-exit transport without a result stayed `missing_result`, with missing
accounting; it was not promoted to inference success. No policy or validator
was replaced with an always-true result. Process/network/SDK/credential guards
remained active. Only synthetic test-owned deadline stores started clocks.

The local lock covers one explicit host-state root, not other runners. The
10,800-second cumulative deadline includes recovery/downtime and is never
reset on re-entry. The native-turn wait remains 1,800 seconds, not an all-in
attempt ceiling. B recovery, keep/fresh semantics, filtering stops and the
absence of C feedback are unchanged; this slice introduces no experimental axis.

### Exact validation

The invocation ran once from `batch-runner`. Only the two private path values
are symbolic below; their exact values and the new artifact locations are
retained in the private receipt. This was one software contract test, not an
experiment execution.

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 GDPVAL_RETENTION_PREPARED_HANDOFF="$RETAINED_INPUT_HANDOFF" GDPVAL_RETENTION_CONTROLLER_TEST_RECEIPT="$PRIVATE_TEST_RECEIPT" /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p no:cacheprovider --tb=short -s tests/test_codex_retention_first_cell.py::test_first_retention_cell_staging_and_serial_control_are_closed
```

| Identity from this invocation | SHA-256 |
| --- | --- |
| Verified original-input roles | `40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38` |
| Controller file | `ca50d1c8845fc2cdb8be1baf6ae9b846ab3d30ef1b9c5bac2fc661398b64a50d` |
| Additional controller/helper source identity, not approval | `8eab122ac20b51847252064eb497323d43897c7dc0eeaa9c3bb84c9bb993ff36` |
| Registered plan | `412d25ddc91f62a8c22a035d26eda7d980c8df95c7645ff5933a9ec96ae51b5c` |
| New Task4 preparation packet | `1170122d8820fc11c81e1e7aeb47303e5edf3b2bca58e45682297879fe077270` |
| Staged prepared-task fingerprint | `e9ffd87a8da6f06e26449b7f8d68468e674ea241e787a84568dace72774a2247` |
| Reconciled staging record | `648e4523ffb1db21686d7474a074a816b8525896356f56dfd23db7d3b195bb8a` |
| Actual path-bound materialized grader | `7cdb83558959a767e18a3103cd62ffa0a8d2a5f9eb33a0a433a7a93b97d09cb9` |

The local log is 2,343 bytes, SHA-256
`a41c1c7f5624afe6c78d13e6c580b9f259117f2a962ea44eb42e4f05d0f97df2`.
Only the new controller and its test differ from the base at the tested SHA;
only these two completion records change afterward. Existing tracked runtime,
compiler, preparer, eight-cell and original 30-cell registrations/pins, graders,
workflows, original outcomes and upload code are byte-identical to the base.

### Next live-path blocker

`codex_budget_pilot_retention._binding` / `require_admission` and
`codex_budget_pilot_ci.compile_ci_cell` bind the original campaign and CI claim,
not this retention cell. `LocalTransport.require_execution` also binds that
campaign's parent/source and C-feedback capability. A separately reviewed
retention-aware integration must connect the existing source/cell/host/runtime/
input/spend boundaries to a real one-use serial CAS claim and terminal
reconciliation. No old registration, claim validator or approval is repurposed.
The current refusal is
`retention_ci_cas_and_execution_approval_adapter_not_registered`.

New-head controller/record review and CI remain required, along with that
CI/CAS integration, live source/deployment consumption checks and separate
paid-cell direction. The local packet and staging record retain `launch_authorized=false`
and `commands=[]`. There was no input recovery/intake, HF/Azure/OIDC operation,
storage setup, VM, paid call, CI replay or infrastructure change. No inference
slot or live budget was consumed. Preparation and simulated control evidence
are not admission authority.
