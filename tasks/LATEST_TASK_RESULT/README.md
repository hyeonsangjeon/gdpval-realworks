# Latest substantive task result

## PROJECT5-GPT56-EVIDENCE-PREFLIGHT-GATE

The Foundry GPT-5.6 Sol Codex pilot preflight now has an optional read-only
evidence gate. It calls the existing intake verifier and can satisfy exactly
five local evidence requirements for a complete, current bundle. Four runtime
and deployment blockers remain. Both `launch_allowed` and `full_220_allowed`
stay false, as do `launch_enabled` and `full_220_enabled` in the manifest.

The sole local selector reported `4 failed, 92 passed in 9.95s`. All four
failures came from one privacy assertion matching a required blocker name as
a substring. That assertion was corrected without a rerun. A parser correction
and one added regression also remain unrun after immutable review.
Automatic CI must validate these changes; no local green result is claimed.

### Scope and outcome

The CLI accepts `--evidence-bundle`, `--reviewed-source-sha` and `--as-of`.
`inspect_plan` exposes the corresponding typed optional arguments. An explicit
evidence request requires the whole group. With all three absent/null, the
existing plan-only path keeps all nine blockers, report fields, ordering and
serialization and does not import the verifier.

The gate invokes the real `verify_foundry_evidence`, which rechecks the ready
marker, sibling reservation, current artifacts, active plan, source pins and
validity windows. The preflight also checks the returned plan/base/run/source
binding and exact `evidence_complete=true`. Reverification uses the caller's
full reviewed SHA and current explicit UTC evaluation time, not the original
intake time, local clock, Git base or dataset revision.

The closed mapping satisfies only these requirements:

| Cleared blocker | Evidence roles |
| --- | --- |
| `foundry_account_project_deployment_identity_unverified` | `identity` |
| `foundry_served_model_version_unverified` | `identity` |
| `max_and_long_1m_capability_unverified` | `reasoning`, `context` |
| `native_call_and_token_limits_unresolved` | `native_caps` |
| `foundry_usage_and_tariff_mapping_unverified` | `usage`, `tariff` |

The four remaining blockers retain their original order:

- `live_identity_and_input_bytes_unverified`
- `pilot_dispatch_and_grading_identity_not_wired`
- `native_sandbox_and_result_bundle_host_unverified`
- `actual_pilot_deployment_not_prepared`

Evidence-mode output is canonical JSON. Its `evidence_gate` records the
consumed canonical ready SHA256, caller-reviewed source SHA, evaluation time,
complete status, cleared/remaining blocker lists and `offline_local_consistency`
boundary. It does not expose raw evidence, resource/response identity hashes,
endpoints or credentials. Refusals retain all nine blockers and return
`foundry_evidence_gate_refused`, with unverified digest/SHA/time fields null.
All CLI argument errors use a non-echoing refusal path, including misspelled
options that cannot identify the intended mode. Plan-loading and verifier
exceptions in evidence mode do not echo their input values. Every preflight
report returns CLI exit 2; there is no launch command.

The active source set still has 30 pins. Only the preflight source digest was
refreshed. That necessarily changes the active plan seal and makes old-plan
bundles stale; the no-bundle byte-compatibility assertion applies to the same
sealed plan, not to equality with an obsolete digest. There is no old-seal
exception. The fixed five tasks, model/Max/1M requests, null verified fields,
limits, grader, result/cost contracts and historical Copilot record are unchanged.

### Immutable base and review boundary

The new clean development worktree started from main
`0c54611a30b586c6f42ab9e364cde0746374d0ae` on branch
`b/gpt56-evidence-preflight-gate-20260920`. The preserved checkout
`wip/local-main-preserved-20260719` was not used for work or edited.

The first immutable review of `f4123b2c6bd228cee91c85876e2415d37bd6d6f5`
returned REQUEST-CHANGES with one BLOCK. A transposed option,
`--evidence-bundel`, could select ordinary argparse and echo an untrusted value.
The correction removes heuristic mode detection and uses the non-echoing
parser for every argument error. It adds that exact regression, refreshes the
source pin and documents the refusal behavior.

Corrected implementation HEAD: `7cccfc675adfa856e499ca428dcf755a481716b4`.
`first-reviewer` returned APPROVE with no BLOCK, MAJOR or MINOR findings and no
second-review escalation. This is a four-file code/config/test/spec review,
not passing execution evidence. This completion record and `CHANGELOG.md` are
outside the immutable implementation review boundary.

The existing author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was preserved without changing Git
configuration. No attribution trailers or hook bypass were used.

### Exact validation evidence

Exactly one targeted selector ran:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt56_evidence_preflight_gate.py
```

It collected 96 cases and reported `4 failed, 92 passed in 9.95s`, exit 1,
with Python `3.10.12` and pytest `9.1.1`. The four complete-bundle cases had
already passed their exact report, closed blocker transition, real-verifier
call and read-only assertions before reaching the flawed substring check.
`served_model_version` was found inside the required blocker
`foundry_served_model_version_unverified`; this was not raw evidence exposure.

After the run, the privacy assertion was changed to check JSON field names
recursively and actual private values separately. Immutable review then found
the malformed-option echo path. The parser correction, refreshed source pin,
specification note and one additional transposition regression also followed
the sole run. No case was removed, skipped or marked xfail. None of these
corrections, including the later value assertions in the four failed cases,
was rerun locally. Automatic CI must validate them; immutable review does not
replace execution evidence. The recorded 96-case count belongs only to the
actual invocation, not to the corrected selector.

The selector uses a real published bundle prepared once under offline guards,
then copies immutable bytes into fresh single-link files for each case. It
shares no mutable tree or cached validator verdict. The real verifier reads
current bytes in normal and tamper/refusal cases; a separate injected exception
checks error redaction. Coverage includes absent/null compatibility, complete
and later-time verification, partial groups, missing/null/partial artifacts,
stale plan/run/SHA/time, source-pin drift, links, traversal, extra files and
static CLI refusals. Subprocess, network, credentials, provider/client and
grader construction are forbidden by the fixtures.

The #631 152-case selector was not rerun. No broad/full suite, manual workflow
run or benchmark was used. `git diff --check` and `git diff --cached --check`
passed before both implementation commits.

### Changed files

- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/tests/test_gpt56_evidence_preflight_gate.py`
- `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Skills and roles

The full supplied skill catalog and repository agent catalog were inspected
once. `experiment-design` was applied before planning or configuration. It
kept the intervention limited to evidence consumption, preserved every
experiment variable and separated synthetic gate tests from Azure observations.
`llm-systems-engineer` provided read-only design and static audits of the
mapping, recursion, plan/time linkage and redaction. Its malformed-option
redaction finding was fixed before the sole selector. `first-reviewer` found
the separate transposed-option issue after the run and approved its correction
at the immutable boundary described above.

`im-not-ai-en` was applied to the English specification, changelog, completion
record and PR wording without changing hashes, counts, commands, uncertainty
or the failed-test evidence. UI/animation skills do not apply to this backend
gate. `extreme-reasoner` does not apply because no workflow, `core/qa.py` or
HF upload file changed. No grading pipeline implementation or role was needed.

### Evidence boundary and remaining work

Clearing these five blockers means a local evidence requirement was satisfied
for this invocation. It does not authenticate the external export, approve
review or inference publication identity, verify checkout lineage, prove Azure
served capability/wire equality or prove runtime enforcement of the recorded
native caps. It does not populate the manifest's null fields or authorize a run.

Remaining work includes corrected-selector CI evidence; actual Foundry evidence
acquisition and independent review; external inference identity and live
input/wire evidence; native sandbox/result-bundle hosting; actual pilot
deployment and lineage; dispatch/grading; and runtime usage/tariff receipt and
execution integration. Section 17 of `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md`
documents the offline preflight invocation, not a paid launch command.

No Azure/API/CLI, credential/OIDC, deployment, provider/model/client, inference,
grading, download, workflow dispatch or paid execution occurred. Production
runtime/grader defaults, workflows, `core/qa.py`, HF upload and historical
evidence/ledger bytes were not changed. Project fields and merge decisions
remain with the leader. This record contains only pre-merge facts and no
carrying-PR merge SHA, time or state.
