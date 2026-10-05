# Latest task result

## One-observation time-budget handoff — 2026-10-05

The model-free preparation API is implemented, but its offline proof is
**incomplete**. The one authorized selector reported **38 passed, 9 failed,
177 deselected in 19.00s**, exit 1. All nine failures were test-fixture
`IndexError`s before the API was called: the first selected task has no
references, but the tests indexed its first reference. These are failed tests,
not successful refusal evidence.

The test-only correction now selects a declared reference-bearing task. Two
explicit positive reference-payload cases were added because the four passing
handoffs covered tasks without references. The nine repaired cases and two new
cases have not been run. No selector, successful subset, platform probe or CI
job was repeated. Delivery remains on hold for that evidence and review.

### Scope and prepared output

`gpt54_time_budget_comparison.prepare_observation_handoff` accepts the genuine
time-budget registration, one `run_id`/`task_id`, explicit runtime R and frozen
grader F roots/commit anchors, and an explicit input-registration path/root/full
commit. The input registration supplies dataset/cohort facts only, after exact
equality checks with this study. It does not supply legacy dispatch authority.
The caller provides existing local parquet and reference bytes. Codex also
requires the full canonical Step0 manifest; V2 requires it to be absent.

The new destination has this finite shape:

```text
<destination>/
  configuration.json
  task.json
  reference_files/...  # only the selected task's files; absent when none
  preparation.json    # completion marker, published last
<destination>.time-budget-preparation-reserved.json
```

`configuration.json` is an envelope with actual template-derived factory
settings, the registered model/route binding, and a required
`TimeBudgetObservation` identity. V2 carries its existing local settings and
factory profile, not the old stage plan's dollar approvals or escalation.
Codex carries a typed, validated experiment config with one selected task and
no external retry/resume. Neither envelope is a standalone CLI launch config.

`task.json` holds a model-safe V2 `TaskToRun` projection or Codex `run` arguments.
Reference paths are relative to the handoff directory. Rubric and expert-answer
bodies are excluded. The pinned parquet and Codex Step0 bytes are verified, not
copied. No grader config, command, provider instance, admission, generation
clock or execution capability is created.

The marker binds study/run/condition/repeat/task, registration digest, independent
R commit/tree, frozen F/template identity, condition template and generated
config digests, input-registration source, actual input-byte identities and the
required observation control. The implementation uses existing tracked-blob,
held-directory, hash/size, no-clobber and final-reread helpers. A retained sibling
reservation blocks adoption after partial publication. Final-reread/quarantine
regressions remain unvalidated because of the fixture failure described above.

All launch authority and execution-enable fields remain false. No current
runtime/workflow caller selects this API or changes its launch refusal. The
fixed five-task, four-run ABBA/two-repeat/concurrency-1 study, at most 20
observations, GPT-5.4/direct-v1/xhigh binding, 1200/20 policy and frozen judge are
unchanged. No shared native request/token cap, money cap or backend-cancellation
claim is added. No closed study is reopened or pooled.

### Source identities and review basis

- Accepted basis: `36ba69e59e4196d653ca046e064809ca2a8f5bb3`, tree
  `2d96778657188d7a80c32076fd6121707eb790f0`, following PR751 source
  `e0e270b67b3c7f63b8f94f945c4839b778c7572b`, source review `5416820324`
  and actual-host receipt review `5417240401` supplied by the leader.
- Tested implementation: `ccf6e880caa8e5b3dfccea5139fe2c114baa4602`, tree
  `407f36bb0848811191cbabe0a45469356a09949b`.
- Test-only correction, not revalidated:
  `184cba2e042518c0e22af104c42e5ef0b099f4a9`, tree
  `63b03670161112bb0e5c4b3ab678e0dadd4b9ed0`.
- Frozen F remains `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
  `45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, with genuine TEMPLATE
  `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
  No materialized-grader identity is claimed.

The same-session architecture/source-provenance and grading charter review
preceded edits. Its conditions required independent R/F/input anchors, reuse
of input-only validators, one-task output, held/no-clobber publication, and no
provider, grader or admission effect. This was the primary worker applying the
charters, not independent owner approval. The consolidated grading specification
was read; no grading policy or source closure was changed.

The directly coupled CURRENT consumers were audited once. The prospective
compiler pin advances, and its new use of the existing
`ghcp_vm_input_bundle.py` publication primitives adds that helper's real pin,
bringing the prospective inventory to 42. Its bytes are unchanged. The
corresponding test inventory and usage documentation are updated. Historical
manifests, the 37-source frozen profile, core/runtime/ownership/finalization,
workflows, grader algorithm and paid evidence remain unchanged.

### One bounded offline invocation

The existing Python 3.10.12 environment ran pytest 9.1.1 with no credentials,
network or provider access, without `-x`, under a 300-second bound plus 5-second
termination grace. All 47 selected nodes completed. The log retains every
passed and failed node. This public command display redacts the private proof
directory; its bytes are **not** the command-file bytes hashed below.

```bash
cd batch-runner
timeout --signal=TERM --kill-after=5s 300s \
  env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -o addopts= -p no:cacheprovider -m 'not integration' \
  -vv --tb=short --color=no \
  --basetemp='<private-proof-directory>/pytest-tmp' \
  tests/test_gpt54_time_budget_comparison.py -k time_budget_observation_handoff
```

Retained private evidence identities:

| Evidence | SHA256 |
| --- | --- |
| Exact `command.sh`, including private paths and log capture | `c58b418e711c3305ce204c84ed55e297e37f601a544b514c1209daa919a6fc19` |
| `pytest.log`, 12155 bytes | `38a6761913a88893f9a9a2a3c4a2ee846c6411ea704b685cf6c7f9a157b1e0ff` |
| `result.json` | `3e4c5655d4350d1bcaa50ac1c4eefd741dc498ceb78d1ebcccd0232a2de433dd` |
| Same-session review memo, with later source-locator annotations | `c45fa6f167a0b10fd123b955b8534fe695bf46ae35e503a0979449455c086b77` |

The failed nodes, all under `tests/test_gpt54_time_budget_comparison.py`, are:

- `test_time_budget_observation_handoff_tamper_and_clobber[reference_digest]`
- `test_time_budget_observation_handoff_tamper_and_clobber[reference_symlink]`
- `test_time_budget_observation_handoff_final_rereads_quarantine[parquet]`
- `test_time_budget_observation_handoff_final_rereads_quarantine[reference]`
- `test_time_budget_observation_handoff_final_rereads_quarantine[step0]`
- `test_time_budget_observation_handoff_final_rereads_quarantine[runtime_source]`
- `test_time_budget_observation_handoff_final_rereads_quarantine[input_source]`
- `test_time_budget_observation_handoff_final_rereads_quarantine[installed_config]`
- `test_time_budget_observation_handoff_final_rereads_quarantine[parent_swap]`

The passing nodes include four actual one-task handoffs without references,
both conditions/repeats, independent anchors, invalid selections, source/input
drift and clobber refusals, V2's no-Step0 path, false launch authority and the
unchanged argument-free runtime refusal. Fixtures use real temporary Git
commits/trees and explicitly declared synthetic parquet, prompts, rubrics,
references and Step0 hashes. Successful source/input validators were not mocked.
No private original-input verification or live result follows from this proof.

The post-proof repository delta is the test-only fixture correction/two new
reference-payload cases plus this record and CHANGELOG. Production code, the
prospective manifest and usage README have not changed since the tested commit.
There is no aggregate passing claim for the corrected selector.

### Remaining work and evidence boundary

The nine repaired cases and two new reference-payload positives need focused
evidence; this turn did not run them again. Full-HEAD owner review and applicable
CI acceptance also remain pending. The supplied [PR751 platform evidence]
confirmed a synthetic, model-free reparenting lifecycle only for job
`111834532570`, run `37331226376`, attempt 1, GitHub-hosted Linux X64, at tree
`2d96778657188d7a80c32076fd6121707eb790f0`. It is not support for this changed
source/another host or authorization for a study observation. The earlier NAS
refusal and all prior software proofs remain distinct in the [immutable prior
record]. No platform probe was run locally.

The single next execution wiring gap is a consumer that revalidates this
one-observation handoff and supplies the required control to the existing V2 or
Codex factory under a separately reviewed source-bound execution direction.
That future work must still bind a usable host, verified credentialed originals,
provider identity, live dispatch/capture and eventual F-derived grading. None
is selected or enabled here; no spending-approval question is reopened.

The full skill catalog was reviewed once. `experiment-design` preserved the
already fixed study controls and kept synthetic software proof separate from
experiment evidence. `im-not-ai-en` protected English facts, identities, failure
counts and qualifications in the usage passage and completion records. No
UI/animation or experiment-reporting skill was used. No model/grader/HF/Azure
call, real input/runtime-receipt/consumed-artifact read, real preparation, CI
query or dispatch, Project edit or merge occurred.

[PR751 platform evidence]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37331226376/job/111834532570
[immutable prior record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/e0e270b67b3c7f63b8f94f945c4839b778c7572b/tasks/LATEST_TASK_RESULT/README.md
