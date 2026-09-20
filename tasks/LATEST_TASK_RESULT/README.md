# Latest substantive task result

## PROJECT5-PR638-THREE-WAY-PARTITION-FIX

Backend Tests now has three independent jobs. Core `pytest` keeps its exact
20-file exclusions, `comparison-contracts` selects the 11 GPT-5.4 files, and
the new `pilot-contracts` selects the 9 GPT-5.6 files. The prescribed static
selector passed once. Fresh automatic CI must still establish all three
results and durations within their individual 45-minute ceilings.

### CI finding and correction scope

The leader supplied two measured CI rounds. No cancelled job was rerun.

| HEAD | Backend run / job | Result |
| --- | --- | --- |
| `c88f76f02c43ef9b2672e61d6cdd6d4630235305` | `35514065313` / `106086906143` (`pytest`) | Cancelled at `45:13`, still progressing at `87%`, with no assertion failure. |
| `8117a667a49133cfd11f3401d17ddfd36d82db55` | `35517208735` / `106095045010` (`pytest`) | Succeeded in about `25:13`. |
| `8117a667a49133cfd11f3401d17ddfd36d82db55` | `35517208735` / `106095045151` (`comparison-contracts`) | Cancelled at about `45:16`, at `91%`, with no assertion failure. |

In the first round, comparison succeeded with only the 11 GPT-5.4 files while
all 9 GPT-5.6 files remained in core. The first correction moved all 20 into
comparison. That made core green but moved the timeout: the combined job
completed every GPT-5.4 file and reached `test_gpt56_pilot_wire_receipt.py`
before cancellation. Neither round is a complete passing Backend run.

This correction leaves core's executable job unchanged, restores comparison's
GPT-5.4-only selection and adds one explicit GPT-5.6 sibling. The existing
static test node now requires exactly these three jobs, identical setup,
independently derived nonempty sorted families, exact core union exclusions,
duplicate rejection, pairwise disjointness and complete coverage of every
discovered `test_*.py` file.

Existing job/check names, runner, setup, pinned actions, dependencies, pip
cache, dispatch/checkout SHA checks, integration filter, repo-root script tests,
triggers, permissions and ref-scoped concurrency are preserved. The new job
copies the same six setup steps and 45-minute ceiling. There is no job
dependency, matrix, secret, credential, OIDC access, test deletion, new skip or
xfail. No timeout was increased.

### Exact three-way partition

Paths below are relative to `batch-runner`. Core excludes their sorted union
and retains all other discovered tests plus the existing repo-root script step.
`comparison-contracts` selects only these 11 sorted GPT-5.4 paths:

```text
tests/test_gpt54_codex_grading_input.py
tests/test_gpt54_codex_input_capture.py
tests/test_gpt54_comparison_preflight.py
tests/test_gpt54_disposable_checkout.py
tests/test_gpt54_prepared_input_attestation.py
tests/test_gpt54_run_config_bundle.py
tests/test_gpt54_run_input_bundle.py
tests/test_gpt54_runtime_checkout.py
tests/test_gpt54_v2_grading_input.py
tests/test_gpt54_v2_input_capture.py
tests/test_gpt54_workflow_gate.py
```

`pilot-contracts` selects only these 9 sorted GPT-5.6 paths:

```text
tests/test_gpt56_evidence_preflight_gate.py
tests/test_gpt56_foundry_evidence_intake.py
tests/test_gpt56_pilot_config_bundle.py
tests/test_gpt56_pilot_deployment_binding.py
tests/test_gpt56_pilot_identity_plan.py
tests/test_gpt56_pilot_input_bundle.py
tests/test_gpt56_pilot_input_capture.py
tests/test_gpt56_pilot_wire_receipt.py
tests/test_gpt56_sol_codex_pilot_preflight.py
```

### Exact validation evidence

Exactly one pytest invocation ran for this correction, from the existing PR
worktree root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner /usr/bin/python3 -m pytest -q -p no:cacheprovider --tb=short batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts
```

Result: `1 passed in 0.18s`, exit 0, one collected. This is evidence for the
three-way static workflow and filesystem partition, not execution of the
20 contract files or a measurement of full-suite duration. `git diff --check` and
`git diff --cached --check` passed. No core pytest suite, comparison-contracts
suite, pilot-contracts suite, wire receipt selector, earlier pilot selector,
broad suite or manual workflow was run locally. The previous two-job correction
also reported `1 passed in 0.18s` at implementation HEAD
`70334bb35f7916a4db7a1e1d1a18da10847cb9e1`; its subsequent combined-job timeout
shows why that static result was not a hosted runtime guarantee.

The prior receipt evidence is preserved as historical evidence only. Its single
local command, run from `batch-runner`, was:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -q tests/test_gpt56_pilot_wire_receipt.py --tb=short
```

That command reported `88 passed in 642.32s (0:10:42)`, exit 0, at
`59aa7f00de5505e0ed5c1bff8e8ae7757ff9398a`. Both reviewers subsequently found
the endpoint-account binding defect. The corrected receipt implementation
`89e9a33baa3b6c4b3c404f7c2c6f61798003a868` added a wrong-account parameter,
bringing its selector to 89 cases. That corrected selector has not been rerun
locally. The 88-pass result does not validate the correction, and the cancelled
core run is not a completed pass. Fresh automatic CI is still required.

### Mandatory pre-edit decision

`extreme-reasoner` was invoked before editing and returned
APPROVE-WITH-CONDITIONS against
`8117a667a49133cfd11f3401d17ddfd36d82db55`. Its structured memo identified
missing or duplicated coverage, loss of effective GPT-5.6 merge gating and
increased runner consumption as the main risks. It required exact family
selections, core's unchanged exclusions, identical read-only setup and all
existing security controls. The integration filter is not a network sandbox.

The nominal aggregate allowance rises from `2 × 45 = 90` to
`3 × 45 = 135` runner-minutes, an increase of 45 minutes or 50%, excluding
shutdown overhead. One more checkout/Python/pip/cache cycle adds unmeasured
overhead and uses another runner slot. The second round consumed about 70.5
combined job-minutes (`25:13 + 45:16`) despite incomplete comparison execution;
it is not a completed-work baseline. File counts and `91%` progress do not
predict either new contract job's duration. No paid provider operation was
authorized.

All three job verdicts must succeed at the same relevant HEAD before a later
readiness decision. Adding `pilot-contracts` does not establish that it is an
externally required check; repository rulesets were neither queried nor
changed. The existing result-PR caller checks aggregate Backend success but
waits only 1,800 seconds, a separate unchanged limitation. Ref-scoped cancellation
and independent job verdicts remain in place. A separately authorized rollback
would restore both selectors and the guard with a normal forward patch; it
would also restore the known combined-job timeout risk. This memo is not CI,
launch or merge approval.

### Immutable review boundary

Correction base: `8117a667a49133cfd11f3401d17ddfd36d82db55`.
Fixed implementation HEAD: `c6bf7269480bfc804e7f2aaf6427613cdab3fda9`.
Both `llm-systems-engineer` and `first-reviewer` returned APPROVE with no
blocking findings on this exact HEAD. Both reviews were read-only; neither
reviewer ran tests, runtime imports, network calls or CI queries. They confirmed
the partition and preservation conditions without predicting hosted duration.
These reviews cover only the two-file partition correction. This record and
the changelog are a later records-only commit outside that implementation
review boundary. The prior receipt implementation's two APPROVE verdicts at
`89e9a33baa3b6c4b3c404f7c2c6f61798003a868` remain separate static evidence.

The existing branch and worktree are retained:
`b/gpt56-live-wire-receipt-20260920`, originally based on main
`0cd4c5e76805384a77afabf28b3663a3ad6596c0`. No new checkout or branch was created
for this correction.

### Changed files

- `.github/workflows/backend-tests.yml`
- `batch-runner/tests/test_a_test_file_nobody_runs_is_not_a_test.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

Runtime receipt logic, experiment settings, source pins, launch flags and
grading behavior are untouched. No other workflow, `core/qa.py` or HF upload
code changes.

### Skills and unchanged live-wire limits

The mandatory workflow decision used `extreme-reasoner` before editing;
`llm-systems-engineer` and `first-reviewer` cover the immutable implementation.
`im-not-ai-en` was applied to the English records without changing hashes,
commands, timings or evidence limits. UI/animation, grading and repo-readiness
skills do not apply to this CI partition correction. It introduces no new
experiment axis or runtime evidence contract.

The receipt still observes the pinned Codex app-server's actual serialized
stdio requests, correlated replies and native thread usage. It does not
observe Foundry HTTP payloads or returned served-model identity. Unavailable
fields remain `not_available`, and
`live_inference_identity_and_wire_unverified` stays unresolved. The boundary
remains `codex_app_server_transport_not_foundry_http_or_served_identity`.
Synthetic fixtures prove verifier behavior only, not that the pilot was served.
`launch_enabled`, `launch_allowed`, `full_220_enabled` and `full_220_allowed`
remain false; no launch command was added.

Fresh results and duration evidence for all three Backend jobs remain required.
Real Foundry evidence acquisition/approval, actual HTTP/input-consumption/wire
and served identity, native sandbox/result-bundle hosting, deployment/execution,
native-cap enforcement and usage/tariff/billing receipts remain separate work.

No Azure/HF/OIDC lookup, provider/model/client/grader execution, inference,
grading, download, paid execution or manual workflow dispatch occurred. The
preserved checkout and other worktrees were not edited. Git author/committer
identity `hyeonsangjeon <wingnut0310@gmail.com>` was preserved without configuration
changes, attribution trailers, history rewriting, force push or hook bypass.
Project and merge decisions remain with the leader. This record stops at
pre-merge facts.
