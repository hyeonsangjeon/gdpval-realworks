# Latest substantive task result

## PROJECT5-GPT56-FOUNDRY-EVIDENCE-INTAKE

The active Foundry GPT-5.6 Sol Codex pilot now has an offline evidence intake
schema, compiler, publisher and verifier. The unit binds externally acquired
local evidence; it does not acquire Azure evidence, authenticate its issuer,
approve capabilities or authorize a run. `launch_enabled` and
`full_220_enabled` remain false. The preflight still reports every existing
launch blocker, with `launch_allowed` and `full_220_allowed` false.

### Scope and outcome

The six ordered evidence roles are `identity`, `reasoning`, `context`,
`native_caps`, `usage` and `tariff`. Each role binds its local JSON artifact's
path, size and SHA256, source kind, observation/issuance time and validity end.
The descriptor binds a separately supplied full reviewed source SHA, the
active plan's canonical SHA256 and base, and run ID
`gpt56_sol_foundry_codex_pilot5_v1`. Historical source, dataset and grader
revisions cannot stand in for the reviewed source.

Requested Azure/Codex/Sol/Max/1M values remain separate from documented and
observed values. The Max and at-least-1,000,000-token observations must name
the same completed response; aggregate thread usage is not accepted as one
context observation. Native limits distinguish calls from tokens and require
per-attempt native enforcement. Usage and tariff evidence must agree on meter
IDs, currency, region and effective times. Cached input stays part of total
input, and the existing `cost-receipt-v1` null/partial vocabulary is preserved.
No cost is computed, no unknown value becomes zero and no currency is converted.

The exports use a closed, bounded JSON vocabulary. Account, project and
deployment identities use separate SHA256 fields over externally supplied
resource ID bytes, not raw resource names or endpoint strings. Raw credentials,
tokens, keys, headers, endpoint URLs, personal fields and free-form logs are
outside the accepted schema. The tool rejects them without copying or echoing
their contents. These are privacy-screened local exports, not a claim that
the repository has invented or verified an Azure native API format.

All input artifacts and active source pins are validated before reservation.
The publisher uses the existing held-parent pattern and atomic no-clobber
writer, with descriptor-anchored exclusive directory creation. It checks
source and installed bytes again, then publishes
`foundry-pilot-evidence-ready.json` last. A retained sibling reservation makes
partial attempts non-reusable; there is no overwrite or cleanup operation.
The verifier reconstructs the marker and requires the exact reservation and
current file bytes. Symlinks, hardlinks, path escapes, duplicates, extra roles,
stale bindings and collisions fail closed. Missing/null required evidence is
preserved in the read-only result and cannot receive a ready marker.

The active source set increased from 23 to 30 pins. The fixed five tasks,
input/reference fingerprints, Sol-not-Fast request, Max/1M settings, limits,
grader, result contract, record-only cost policy and superseded Copilot record
are unchanged. Production runtime/grader defaults, workflows, `core/qa.py`,
HF upload scripts and historical evidence/ledger bytes were not changed.

### Immutable base and review boundary

This work started in a new clean development worktree at immutable main
`d8fd52d9c75687a8e088748c589f9a9a07834a41`, on branch
`b/gpt56-foundry-evidence-intake-20260920`. The preservation checkout
`wip/local-main-preserved-20260719` was not used as a work branch or edited.

Implementation HEAD: `5a09f59dd4bf8bf5855aa170fa45ec1173fe0fae`.
`first-reviewer` reviewed this immutable seven-file implementation/spec
boundary against the base above and returned APPROVE, with no BLOCK, MAJOR
or MINOR findings and no second-review escalation. The reviewer read immutable
Git objects and directly related helpers without running tests or live calls.
The verdict covers offline local consistency only, not Azure facts or CI
success. Only this completion record and `CHANGELOG.md` are outside that
implementation boundary; the implementation did not change after review.

The repository's existing author and committer identity,
`hyeonsangjeon <wingnut0310@gmail.com>`, was preserved without changing Git
configuration. No attribution trailers or hook bypass were used.

### Exact validation evidence

Exactly one targeted pytest command ran:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt56_foundry_evidence_intake.py
```

Result: `152 passed in 18.33s`, exit 0, with Python `3.10.12` and pytest
`9.1.1`. No selector rerun, broad/full suite or manual workflow run was used.
`git diff --check` and `git diff --cached --check` passed before the immutable
implementation commit.

The tests use small temporary fixtures and the real active-plan checker,
schema validator, file-integrity reader, held-parent helper and atomic writer.
Only immutable fixture bytes and byte-keyed YAML parse results are shared;
each case owns fresh single-link files and validators re-read actual bytes.
Cases cover complete publication/reverification, null/documentation-only
claims, incorrect identity/capability/units/records, plan/source-pin drift,
secret and personal fields, path/link refusals, every publication write
failure, races, partial reservations, canonical marker drift and expiry.
Subprocess, network, credential discovery, provider/client and grader
construction are forbidden by the fixtures. These are synthetic evidence
tests, not observations about a real Foundry deployment.

### Changed files

- `batch-runner/gpt56_foundry_evidence_intake.py`
- `batch-runner/schemas/foundry-pilot-evidence.schema.json`
- `batch-runner/tests/test_gpt56_foundry_evidence_intake.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot.yaml`
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py`
- `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Skills and roles

The full supplied skill catalog and repository agent catalog were inspected
once. `experiment-design` was applied before planning or configuration. It
kept the intervention limited to local evidence binding, distinguished
requested settings from controlled capabilities, and kept fixture results
separate from provider observations. `llm-systems-engineer` supplied a
read-only design and static audit, including the shared Max/context response
identity, exact string matching and tariff/usage timing boundaries.
`first-reviewer` completed the immutable implementation review described above.

`im-not-ai-en` was applied to the English specification, changelog, completion
record and PR wording while preserving hashes, counts, commands, uncertainty
and scope. UI/animation skills do not apply to this backend evidence unit.
`extreme-reasoner` does not apply because no workflow, `core/qa.py` or HF
upload file was changed. No grading pipeline role or code change was needed.

### Evidence boundary and remaining work

A ready marker proves local consistency only. It does not authenticate the
external export, issue review approval, verify current Git checkout lineage,
prove Azure identity/capability or actual wire consumption, issue an inference
publication identity, or authorize a pilot. Resource and response hashes are
claims bound to local files, not substitutes for independent provider evidence.
Missing tariff evidence blocks this marker; it does not change the general
record-only cost policy into a cost ceiling.

Remaining work includes real privacy-screened evidence acquisition and
independent review for the Foundry account/project/deployment, served model
version, Max/1M and native caps; verified native sandbox/result-bundle hosting;
actual pilot deployment and checkout lineage; input/wire evidence; pilot
dispatch/grading and external inference publication identity; and integration
of native usage/tariff evidence into runtime receipts and execution gates.

Section 16 of `tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md` documents the
offline compile/publish/verify commands. They were exercised only with fake
temporary evidence in the selector, not real provider artifacts. This unit
adds no paid pilot command. No Azure/API/CLI, credential/OIDC, deployment,
model/client, inference, grading, download, workflow dispatch or paid
execution occurred. Project fields and merge decisions remain with the leader.
All statements here are pre-merge facts; no carrying-PR merge SHA, time or
state is claimed.
