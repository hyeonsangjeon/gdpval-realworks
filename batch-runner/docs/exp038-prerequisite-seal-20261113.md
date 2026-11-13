# exp038 prerequisite source registration — 2026-11-13

This registration follows the existing predecessor-record convention. It
permits review/publication of five engineering fixes, not a model turn, quota
increase, paid grading run, GHCP policy choice or merge. The owner retains the
merge and exp038 spending decisions. Publication authority was recorded on
the card at 2026-10-30 14:15, item 4; the 2026-11-13 leader instruction requests
the combined Draft PR and this separate source-registration commit.

## The five source commits

The integration branch is `leader/exp038-prereqs-20261113`, based on
`e33cf06bc633d803f7985290bf671097ed7ca6d3`. The five local changes were committed
individually and applied in order without conflicts:

| Fix | Original branch commit | Integrated commit |
|---|---|---|
| Configured HTTP-429 retries through existing metering/USD reservations | `5974acd5c443` | `5974acd5c443` |
| Committed single-shard chunk approval inheritance | `8e6cb636ff28` | `7a09569e4` |
| Published partial/progress/refusal accounting and exact checkpoint cleanup | `8addccde4761` | `72f1d6ae9` |
| Observe pending result-PR checks within finite child-job time limits | `6d73d8672eb5` | `5493e09c6` |
| Pin PyMuPDF 2.1 / Python-3.10-compatible 1.28.2, with Actions wheel hashes | `d3bfac39cc13` | `f423114e0` |

The immutable reviewed source **A** is
`f423114e0122d75ed07a9d57a3dac5cee64c08fd`. This registration is the following
commit **B** and changes no file in A's grader closure.

**Merge with a merge commit, not squash/rebase.** Tests archive A directly.
Keep A reachable when merging main into this branch or when merging the PR.

## Seal chain, unchanged scope and unchanged money

The new record is
`experiments/execution_envelope/gpt56_sol_grader_seal_20261113_exp038_prereqs.json`.
It names predecessor
`gpt56_sol_grader_seal_20261106.json`, SHA-256
`bf4b38105c6b9bb5deb380f0faf53cafa58efd9d58e3f08b43be55cd5c65b19c`,
and the predecessor grader hash
`7a9aa01048b874c09642ee8cd73493cbe81065bb8d5c02ed52057c00ac78048c`.
Both predecessor records (20261030 and 20261106) and their readers retain their
original bytes. The new reader is `gpt56_pilot_grader_prereqs_seal.py`.

The hash algorithm, `source_files`, requirements-include traversal, freeze
scope, source-pin role sets and per-file checks are unchanged. The new
verifier function is copied byte-for-byte from its predecessor; AST equality
and function identity are regression-tested. The existing `core/**/*.py`
rule includes the added retry helper automatically: 153 files become 154,
with no exclusion or relaxed scope rule.

Exactly seven closure files differ from the predecessor:

- `core/grader.py`
- `core/grading_retry.py` (added)
- `core/perception/audio.py`
- `core/perception/vision.py`
- `core/tool_calling_judge.py`
- `step8_grade.py`
- `requirements-renderer.txt`

The new exp035-template grader hash is
`54eccf8de3d2f0bcb96de6fb4f9dc527520ca3d72b39090a410ff71d0b45f7c0`.
All changes are classified as impact: recovering a 429 can change which
criterion receives a response, and fixing a renderer version prevents drift.
No equivalence of real task scores or actual provider billing is claimed.

The copied `preserved_conditions` remain equal to the predecessor. Model,
effort, requested context, prompts, rubric, selection, tariff/unknown-usage
policy, USD records, experiment configs and approval registries are not edited.
Retry attempts still pass the existing reservation/meter/journal gate. This
does not authorize exp038, raise the exp037 USD 700 ceiling, or extend the
historical USD 200 pilot record to a different experiment.

## Source profiles and workflow auxiliary binding

The native source-only profile advances from the retained
`gpt56_sol_foundry_codex_pilot_source_20261106_selector_reseal.yaml` to
`gpt56_sol_foundry_codex_pilot_source_20261113_exp038_prereqs.yaml`. The exact
source-pin delta is preflight, step 8 and grader; the only non-source change
is the explicitly chained grader-template hash. Same-HEAD, clean-tree,
archive, imported-module-location and final reread checks stay enforced.

The changed `batch-run.yml` remains an auxiliary source binding, not a removed
guard. `source_auxiliary` records its old hash at main `e33cf06bc633` and its
new hash at A. The previous auxiliary map stays intact; the current map has
the same keys. Tests check the old blobs/hashes and the new exact bytes.

The GHCP model-free input contract also pins shared step-8/grader bytes. Its
source-only profile therefore advances to
`gpt56_sol_ghcp_source_20261113_exp038_prereqs.yaml`, linked to the unchanged
20261029 profile. Only those two source pins and its reader's metadata pin
advance. `_sources`, `inspect_plan`, the source role set, all policy values and
false execution flags are unchanged. The new record holds both profile hashes
and that exact three-pin delta. This is not a GHCP authentication run, option
1/3 decision, served-model claim or paid execution approval.

Old positive seal cases execute against their real immutable predecessor
blobs; they additionally require that old verifiers reject today's closure.
The new positive/mutation cases cover the current seal. No assertion is
removed in favor of a skip, xfail or permissive hash set.

## Dependency evidence and test boundary

Run 43310879444 reports PyMuPDF **2.1**, Python **3.11.18** and wheel
`pymupdf-2.1-cp311-abi3-manylinux_2_28_x86_64.whl`. It did not retain a wheel
hash receipt. The identically named public PyPI wheel was downloaded and
measured as SHA-256
`a9efa2e9e5f469d3b5749199329739cfef1ff1d1846538ced4885c544eecbcd9`.
This is the future install pin, not fabricated historical byte attestation.
PyMuPDF 2.1 requires Python >=3.11; the existing Python 3.10 job pins remain,
using observed compatible PyMuPDF 1.28.2. New tests inspect the installed
version, loaded module and pip hash receipt and rasterize a synthetic PDF.

Local verification uses model-free tests (`-m "not integration"`), separate
main/integration worktrees, scrubbed environments and TMPDIR under
`/ai-work/copilot/_tmp`. Known original NAS admission and Python JSON-depth
failures are compared by exact test identity, not skipped or weakened.
The Draft PR body records the final Python-specific results. Only a branch
with no newly failing related case is pushed. Actions checks are automatic;
no workflow dispatch or paid/model call is part of this publication task.
