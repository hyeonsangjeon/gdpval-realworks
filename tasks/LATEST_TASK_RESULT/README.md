# Latest Task Result

- Updated: 2026-09-19 (UTC)

## Current Task: GPT-5.4 Prepared-Input Attestation

### Scope and Outcome

`compile_prepared_input_attestation` compares actual local input snapshots
with four supplied pre-execution captures. It returns deterministic canonical
JSON bytes and a SHA256 digest without writing, copying, downloading, or
launching anything. `validate_prepared_input_attestation` recomputes that
evidence and requires exact canonical byte equality.

Work started from immutable main
`c0fdd10c384ab31ccc65cf3019c4d838f370a6a9` in branch
`b/gpt54-prepared-input-attestation-20260919`, at
`/ai-work/copilot/.worktrees/gdpval-realworks-b-gpt54-prepared-input-attestation-20260919`.
The preservation checkout and prior worktrees were not used for edits.

Exactly eleven files differ from that base:

- `batch-runner/gpt54_prepared_input_attestation.py`
- `batch-runner/tests/test_gpt54_prepared_input_attestation.py`
- `batch-runner/gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_comparison_preflight.py`
- `batch-runner/tests/test_gpt54_v2_grading_input.py`
- `batch-runner/tests/test_gpt54_codex_grading_input.py`
- `batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison.yaml`
- `batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml`
- `tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

### Binding and Evidence Boundary

The compiler reuses the exact combined dispatch/grading plan and verifies
26 source pins before reading the supplied data. The source set adds the
attester and `prepare_dataset.py`, the non-core dependency imported by
Step 1's existing public config helper. Core helpers remain covered by the
unchanged grader source closure
`c10ea303f212bab87ea6303cb41ee51e21430e6bc35df7a69b9a63d265f3a241`.

The attestation binds the registered five task IDs and order, raw prompt
UTF-8 bytes, taxonomy, raw rubric JSON/pretty bytes, ordered source projections
and their fingerprints, reference logical paths and actual size/SHA256,
parquet size/SHA256, dataset revision, generated config digests, source pin
map, and each ABBA run's identity and capture. V2 repeats share config bytes;
Codex repeats have different experiment IDs/names and prepared fingerprints.
Both actual Codex prepared files are required.

Parquet physical row order is not execution order. The existing score-free
catalog selector supplies the order; missing or duplicate selected rows are
refused. Actual V2 `bind_stage` output and Codex prepared tasks must preserve
the same prompt, taxonomy, and reference projection. Rubrics remain source
provenance and are not inserted into model inputs. The source's answer
filenames and contents are not emitted. `needs_files` uses the existing
`deliverable_only` output policy, not reference presence. Other policies are
outside this fixed attestation contract.

Missing, extra, duplicate, reordered, or changed prepared/captured tasks;
prompt/rubric/metadata/reference drift; byte/fingerprint/plan/config/pin
drift; symlinks, path escapes, hardlinks, nonregular files, and unexpected
reference trees are refused. A freshly recomputed prepared fingerprint does
not excuse a prompt or metadata mismatch. Exact JSON checks preserve key
presence, nulls, number types, and order. Actual config bytes are checked
separately from the prepared fingerprint's existing `config_path` exclusion.

The result proves offline consistency of supplied snapshots and captures.
Existing runtimes do not yet emit this common pre-execution capture document.
The compiler does not establish capture time, later model consumption,
served capability, rendered/wire-request equality, or external publication
identity. It neither issues nor approves inference identities, and a claimed
`verified` flag or Git/dataset revision cannot replace a file digest or
approval. The study remains a configuration-bundle comparison because
standing instructions, prompt wrapping, and other harness behavior differ.

### Exact Verification Evidence

Only this pytest selector was run, exactly once:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider batch-runner/tests/test_gpt54_prepared_input_attestation.py::test_prepared_input_attestation_binds_actual_bytes_without_execution
```

Result: **86 passed in 49.43s**.

The fixture retains the committed five prompts, taxonomy, reference paths,
and catalog selection. It uses synthetic rubric/reference bytes in a small
parquet, with test-only substitutions at trusted catalog/envelope loading
seams. The production pins separately refuse that synthetic parquet. No
full-220 data snapshot was scanned or downloaded, and this result is not a
verification of the real dataset or an experimental measurement.

The selector uses the real Step 1 serializer, prepared/source fingerprints,
V2 binding, reference readers, and compiled-plan checks. It covers all four
runs, deterministic recomputation, relocated file paths with unchanged
bytes, both conditions' drift cases, forged metadata, unsafe references,
and attestation tampering. It checks that inputs are unchanged after both
acceptance and refusal. Subprocess, network, provider authentication,
model/grader/rubric-loader/client construction, dataset download, and
compiler file writes are forbidden by the fixtures.

`git diff --check` passed. Production runtime/grader code, schemas, workflows,
HF upload scripts, historical results, and ledgers are unchanged. The prior
V2/Codex materializer tests only update their expected source-pin count; they
were not rerun or weakened. The Sol YAML only refreshes its existing shared
parser pin. No standalone preflight, broad suite, build, live call, credential
lookup, paid execution, workflow dispatch, or Project edit ran.

### Immutable Review Boundary

Implementation HEAD: `b4e4c9dfd7fa1384a3dca84469b677cefc874af0`.
The read-only `first-reviewer` review of that exact HEAD returned `APPROVE`,
with no BLOCK, MAJOR, or MINOR findings and no escalation requested. It
reviewed the nine-file implementation diff and directly relevant contracts
without rerunning tests or executing runtime, network, auth, or dispatch
paths. No correction or selector rerun was needed. The LLM systems-engineer's
separate bounded audit also found no high-confidence blocking issue.

Only this record and `CHANGELOG.md` differ from that implementation HEAD.
Approval covers offline snapshot and supplied-capture consistency, not the
unproven live gates. Leader review and automatic CI evidence remain gates. No carrying-PR
merge result, future merge SHA/time, live readiness, or approval of later
records is claimed.

### Remaining Work

This unit implements offline prepared-input provenance/equivalence checks
only. ABBA order, two repeats per condition, the five-task cohort, Foundry
GPT-5.4/xhigh, limits, grading and result/receipt contracts are unchanged.
Both `launch_allowed` and `full_220_allowed` remain false.

- External inference identity issuance and approval.
- Actual pre-execution capture wiring and binding to consumption time.
- A host with native no-clobber support for the existing materializers.
- Actual checkout/config materialization and workflow gates.
- Served V2/Codex capability, live deployment identity, native call/token caps.
- Usage/tariff evidence with the existing record-only null/partial semantics.
- The separate Sol pilot's provider/auth handoff, which remains unsupported
  without an official runtime-to-Codex contract.

The combined live-input and materialization/workflow blockers remain. No
launch command or approval token was added.

### Skills and Roles

The full available skill and repository-agent catalogs were inspected once
before editing. `experiment-design` was applied before code or plan changes
to preserve the fixed cohort, repeat matrix, comparison scope, synthetic
fixture boundary, measurement units, and stop gates. The required
`llm-systems-engineer` role audited existing consumer contracts and the
implementation without editing or executing tests. `first-reviewer` reviewed
the immutable implementation HEAD. These roles used the
available engine; no external paid model call was made.

`im-not-ai-en` was applied to English changelog, completion-record, and PR
wording. Commands, SHAs, counts, test evidence, and qualifications are checked
manually; the owner's one-selector limit takes precedence over an additional
fidelity-script run. Experiment-report skills do not apply because this is
software verification, not a report of measured experimental outcomes.
Repository-readiness, UI, and animation skills do not apply to this existing
offline input boundary. No grading pipeline code was changed, so the optional
read-only grading-engineer role was not needed. Workflows, `core/qa.py`, and
HF upload scripts are unchanged, so no extreme-reasoner scope was created.

## Prior Result: #621 Codex Grading-Input Materializer

The prior unit validated and isolated existing Codex step2 results,
deliverables, and optional producer ledger using an externally approved
inference identity. Its corrected implementation
`373a39fd23b9adc6dc6b30db9ca03675565916b6` received `APPROVE`; its selector
reported `114 passed in 72.92s`, including 13 existing V2 cases. Both native
no-clobber checks on this NAS refused errno 22 without residue. Those are
prior facts, not tests repeated or native installation success in this unit.
