# BOLT: Hermetic Deliverable Selector Contract Corpus

- Date: 2026-07-22
- Status: `SHIPPED`
- Base: `main@23e9cdea5bdd26205a2c1211415b3d8b5c3c1a42`
- Branch: `bolt/hermetic-deliverable-selector`
- Execution boundary: model-free, offline, no secrets

## Outcome

Make the complete deliverable-selector contract suite collect and pass in a
clean checkout without the ignored 1.9 MB GDPVal parquet, pandas, PyArrow, or
network access. Preserve the current 20 owner-gold targets, seven wrong-format
guards, and criterion-routing cases with a compact, provenance-bound fixture.

## Falsifiable Hypothesis

`test_deliverable_selector.py` fails during collection only because it imports
pandas and reads the ignored local parquet at module import time. Replacing that
runtime dependency with a checked-in minimal selector-signal corpus should keep
all selector outcomes identical while making collection hermetic.

## Reproduction

```text
python3 -m pytest --collect-only \
  batch-runner/tests/test_deliverable_selector.py

FileNotFoundError:
data/gdpval-local/data/train-00000-of-00001.parquet
```

The source snapshot is public `openai/gdpval` revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf`; its 220-row parquet SHA-256 is
`f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202`.

## Data-Minimization Contract

The fixture is not a dataset mirror. It may contain only:

- exact full and eight-character task identities for the 28 covered tasks;
- synthetic minimal instruction signals needed by selector regex contracts;
- the three exact criterion strings already asserted by routing tests;
- source repository, revision, row count, parquet SHA-256, projection policy,
  and a canonical self-hash.

It must not contain full source prompts, full rubrics, reference bytes,
deliverables, grades, model output, personal data, or secrets.

## Scope

- `batch-runner/tests/fixtures/deliverable_selector_contract_v1.json`
- `batch-runner/tests/test_deliverable_selector.py`
- `scripts/verify_deliverable_selector_fixture.py`
- `scripts/__tests__/test_verify_deliverable_selector_fixture.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`
- this BOLT record

## Non-Goals

- Do not change selector production behavior or grader routing.
- Do not download, commit, or regenerate the GDPVal parquet.
- Do not add pandas/PyArrow to test collection requirements.
- Do not run grading, Step 8, model/API calls, HF uploads, or paid workflows.
- Do not copy full benchmark prompts or rubric text into the repository.

## Implementation Steps

1. Add a schema-checked, self-hashed 28-task minimal signal corpus.
2. Replace import-time parquet loading with strict fixture loading.
3. Add an offline verifier for fixture structure and optional local source
   provenance checks.
4. Test unknown/missing/duplicate task IDs, self-hash drift, source identity,
   and synthetic signal constraints.
5. Run selector, root scripts, and broad model-free collection/regression gates.
6. Update canonical completion records and obtain independent grading review.

## Acceptance Gates

- Clean checkout collects `test_deliverable_selector.py` without local data.
- Existing owner-gold 20/20, wrong-format 7/7, and routing tests are unchanged.
- Fixture has exactly 28 unique task IDs, a valid canonical self-hash, and a
  canonical payload smaller than 8 KiB.
- Fixture source metadata is exact and optional source verification passes
  against the known local public snapshot.
- Test module contains no pandas/PyArrow import or parquet read.
- Root scripts and relevant grading tests remain green.
- `git diff --check`, Ruff, compile, and diagnostics pass.
- No model/API, grading, Step 8, HF upload, manual workflow, network fetch, or
  paid execution occurs. After merge, only the repository's automatic free
  validate and Pages deploy jobs may run.

## Evidence

| Check | Result |
|---|---|
| Clean-checkout reproduction | Collection fails on missing ignored parquet |
| Fixture contract | 28 tasks, 6,889 canonical bytes, valid self-hash |
| Selector + verifier tests | `15 passed` |
| Source provenance verifier | Public revision, parquet SHA, 220 rows, 28 task/source hashes verified |
| Root scripts suite | `44 passed` |
| Adjacent grading suite | `90 passed`, `2 skipped` |
| Static checks | Ruff, `py_compile`, diagnostics, and `git diff --check` passed |
| Broad model-free regression | Collection blocked by missing local `datasets` and `ijson`; no code failure claimed |
| Independent review | `grading-engineer` approved with 0 mandatory findings |
| Merge | PR #124, squash commit `a82776113d617b3fa4bd12c480f36b51cd7b16a3` |
| Post-merge gate | `Aggregate Tests & Deploy` run `29862415519` succeeded |

## Decision

`SHIPPED` — PR #124 merged the model-free corpus and the automatic free validate
plus Pages deploy jobs succeeded. Selector contracts are hermetic and source-
bound; production selector/grader behavior and every paid path remain unchanged.
