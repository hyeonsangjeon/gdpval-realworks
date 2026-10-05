# Latest task result

## One-observation F-derived grading preparation — 2026-10-05

`gpt54_time_budget_grading_preparation.prepare_observation_grading` now
materializes a fixed grader config and its actual F-derived execution source
for one registered observation. The sole offline selector reported **41 passed
in 95.22s (0:01:35)**, exit 0. All 41 selected nodes completed, with no failures,
skips, deselections or timeout. No test was rerun.

This is a separate main-based implementation, not a stack on PR753. PR753's
reviewed branch remains untouched. Preparation does not create a provider,
grader, grading admission, command or execution authority. Final-HEAD owner
review and applicable CI acceptance remain pending.

### Inputs, bindings and output

The API requires the genuine registration, a caller-supplied typed
`ObservationIdentity`, its independently supplied input binding, explicit
runtime R/frozen F/input-registration roots and full commit anchors, local
parquet/reference/result locators, independently expected result `sha256`/`size`,
and the result's deliverable root. Result metadata is bounded to 8 MiB; this is
an input-file safety bound, not a model or experiment budget. Codex must supply
canonical Step0; V2 refuses it without reading it.

The existing compiler and input validators check registration/cohort equality,
R/F Git commits and trees, tracked regular blobs, local input bytes and the
sealed observation binding. The new helper also checks its own tracked bytes
against R. The independently expected result must be canonical, have a valid
result fingerprint, contain this exact terminal observation identity, and carry
one matching task/model/condition row with exact deliverable hashes and sizes.
Coherently changed metadata does not replace the independent anchors. A missing
output is retained as a supplied terminal error row; the helper does not invent
a result for an absent source file or discard a failed outcome.

The destination must be new and disjoint from every source/input/result path.
Held directories, single-link regular reads, no-clobber publication and final
source/input/member rereads are reused. A retained sibling reservation blocks
adoption after an interrupted or invalid publication. The marker is last.

```text
<destination>.time-budget-grading-reserved.json
<destination>/
  source/
    batch-runner/
      step8_grade.py                         # exact tracked F bytes
      core/**/*.py                          # F's complete Python core
      prompts/...; schemas/...; requirements*.txt
      <other verified F batch-runner source/config roles>
      grading_configs/default_v2_sol_max.yaml # unchanged F template
      time-budget-grading.json              # materialized config
      workspace/
        step2_inference_results.json         # exact bound result bytes
        upload/deliverable_files/<task>/...   # selected result files, if any
    data/gdpval-local/
      rubric_snapshots/<revision>/
        data/registered.parquet              # exact verified input bytes
        rubric_snapshot_manifest.json
      datasets--openai--gdpval/snapshots/<revision>/reference_files/...
  grading-preparation.json                   # final marker
```

The source derivation contains verified F batch-runner roles and its whole
Python core, not a Git checkout claiming a new commit. It copies no `.git`,
workflow, credential or historical result files. The exact finite member set
and each file's `sha256`/`size` are recorded under `files`. Only selected
references/deliverables are copied; Step0 is verified but not copied for grading.
The original F checkout is unchanged.

The returned marker binds the observation, registration file, R/F origin
commits/trees, input registration and verified input bytes, result digest and
fingerprint, terminal outcome, preparation-helper identity, reservation and
exact output members. Its `grader` object names:

- `template_path` and `template_source_sha256` for the genuine F template;
- `config_path` as the actual absolute path, with a relative `config_file`
  identity containing its exact bytes/size;
- `materialized_source_sha256`, calculated by the unchanged whole-closure
  helper against the destination's actual config and copied F source;
- `execution_source: source`, `working_directory: source/batch-runner` and
  `entrypoint: source/batch-runner/step8_grade.py`.

Only the rubric revision and local cache path are materialized from the frozen
config. Judge, visual/audio routing, prompts, scoring and retry settings stay
unchanged. The policy remains one grading attempt per resulting observation,
with failed/missing outcomes retained and no score-driven regrade. The marker's
`grading_attempt: 1` records that policy; preparation is not a grading claim or
an executor's global one-attempt enforcement. `launch_allowed` and
`execution_enabled` remain false.

### Source identities and reviewed basis

- Accepted main: `a5a04701fed3067b56bd80af424824c447f3075e`, tree
  `d36a356b0950bd44b0b789dfebf725035601d259`.
- Independent tested implementation: `3e81b74be73ff1a7a925d7780c9fbd9b896d7d6d`,
  tree `3e044527af08a438b5677e9f95be8d8ab3609e0e`.
- Frozen F: `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
  `45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, TEMPLATE
  `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
- New helper SHA256:
  `c1f8e8de571bf15a3ce80fd7c7fa0549d19769993376af9dd1a149463d39774c`.
- Separate PR753 remains frozen at
  `a9dd6d12ee52344d3f0e329d2d355d429a175df8`, tree
  `f30a46e0960de628a7dc777ea2fc64a5167f107c`, with leader review `5420090699`.
  It was not modified, pushed, stacked or cherry-picked here.

Before edits, the consolidated grading specification and overview and the
grading-engineer/source-provenance/architecture charters were read. The
same-session decision was APPROVE-WITH-CONDITIONS for independent anchors,
actual F execution bytes, distinct materialized hashing, fixed routing,
validation before publication, retained partial state and synthetic proof.
This was the primary worker applying the charters, not owner approval of this
new implementation. The user's bounded offline scope excludes the charters'
broad-suite and paid-smoke defaults.

The directly coupled CURRENT/source roles were audited once. The new helper
has an independent R tracked-blob check, so no comparison manifest or source-pin
change is needed. The new `test_time_budget_grading_preparation.py` remains in
ordinary backend discovery, outside the explicit `test_gpt54_*.py` comparison
inventory. No workflow/selection guard changed. The comparison compiler and
manifest, core/runtime/ownership, frozen F, grader hash scope, historical
profiles, paid evidence, registered study/model/1200/20 policy and launch gates
are unchanged.

### One bounded offline proof

Python 3.10.12 / pytest 9.1.1 ran once at the clean tested HEAD, token-free and
offline, with a 300-second outer limit plus 5-second termination grace and no
`-x`. The 41 cases covered 4 positive materializations (both owners, success and
failed/missing output), 26 pre-publication refusals, 2 existing-state refusals
and 9 final-reread/partial-publication cases. The effect guards observed no
provider, model, grader, network or observation-admission call.

Fixtures used actual temporary Git/config/source bytes and explicit synthetic
input/result declarations. Only source metadata needed to declare synthetic
inputs differed in their R/F/input commits; the real F grader closure retained
TEMPLATE `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
No successful source-validator or hasher verdict was mocked. Existing fixture
helpers were reused; no prior selector or real platform case was run.

In the synthetic positive evidence, the materialized config was 2306 bytes,
SHA256 `62a6d99d9e74d187e517d60d9a5afb112e38926917710ac6e6606eb28404dfa0`,
with actual whole-source fingerprint
`51d42b300d17d933fffbd73b2cdea645a803c63a4246af4f37cb193bf951bd7c`.
The tests independently recomputed that fingerprint, the copied F template's
original fingerprint and R's unequal template fingerprint. These are software
identity observations, not preparation of real original assets or grading.

Redacted command display follows. Only absolute local paths are redacted. The
command digest identifies the exact private 928-byte script, including log
capture, not a digest of this public display.

```bash
#!/bin/bash
set -o pipefail
cd "<worktree>/batch-runner" || exit 90
timeout --signal=TERM --kill-after=5s 300s \
  env -i PATH="<py310-bin>:/usr/bin:/bin" \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTEST_ADDOPTS= \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  "<py310-bin>/python" -m pytest \
  -o addopts= -p no:cacheprovider -m 'not integration' \
  -vv --tb=short --color=no \
  --basetemp="<proof>/pytest-tmp" \
  --junitxml="<proof>/junit.xml" \
  tests/test_time_budget_grading_preparation.py -k time_budget_f_grading_preparation \
  2>&1 | tee "<proof>/pytest.log"
```

| Preserved file | Bytes | SHA256 |
| --- | ---: | --- |
| `command.sh` | 928 | `b5c7df88221b858c66398765217204a15cb72f60821a4d69a55f3be2f028d096` |
| `pytest.log` | 6087 | `542956190a00d7e677788a8e9aea3191d87d00ab8534d3feadc1a67d234cce72` |
| `junit.xml` | 6890 | `8559514b53b7c1966e2117d4dd97356f4585fe6bc4117be7d90d8faa887931f0` |
| `pre-edit-review.md` | 4985 | `bd52b3c3b71e5542057e3f31b09433b8051d5d9a0a899dc54c44de4d18bc8ec6` |

### Separate prior evidence and remaining gates

The [immutable PR753 record] preserves its 53-case software proof and links to
earlier preparation, deadline, ownership and host evidence. Those observations
are not repeated or pooled with this one. The leader supplied PR753 retry
run `37364096520`, job `111963051664`, attempt 2: the runner received a shutdown
signal, not a test assertion failure. The supplied GitHub status was Actions
`major_outage`, [incident 3q1yb5m7ltvb], investigating hosted-runner assignment
and failures. No CI/status query, retry, wait or weakening occurred here.

The post-proof delta is exactly `CHANGELOG.md` and
`tasks/LATEST_TASK_RESULT/README.md`. The new helper and tests remain identical
to the tested commit. These two completion records are the only shared surfaces
with PR753; any later reconciliation belongs in substantive delivery.

Final-HEAD owner review and applicable CI remain outstanding. A future
source-bound grading execution direction must consume/revalidate this exact
preparation, enforce the one-attempt/no-score-regrade policy and invoke Step8
from its F-derived source with the bound observation/result/input identities.
No live caller, provider/credential selection, original input acquisition,
generation/dispatch enablement or grading attempt is added. Host support,
private-input authority and live grading evidence remain separate gates. The
offline result does not establish live execution, backend cancellation or billing.

The catalog was inspected once. `experiment-design` preserved fixed controls
while checking the config mapping; it did not reopen study design or spending
authority. The bounded `im-not-ai-en` changed-passage fidelity check passed
with no failures or warnings, preserving the protected counts, source
identities, links and evidence limits. No unrelated skill was applied. There was no private
original/inference/receipt/consumed-artifact read, real preparation, paid call,
HF/Azure operation, Project edit or merge.

[immutable PR753 record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/a9dd6d12ee52344d3f0e329d2d355d429a175df8/tasks/LATEST_TASK_RESULT/README.md
[incident 3q1yb5m7ltvb]: https://www.githubstatus.com/incidents/3q1yb5m7ltvb
