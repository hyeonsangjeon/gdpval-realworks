# Latest task result

## One-observation time-budget handoff — 2026-10-05

The leader completed source review at
`865c37fe662af11850cc2681f53bf136fdc65444`, tree
`ae71f34e1d3787e584c05220de5b7780da19bab2`, with no blocking source finding.
All 11 applicable checks at that HEAD succeeded; PR-only deploy was skipped.
The supplied corrected-HEAD comparison CI covers the nine repaired cases and
two added reference-payload positives. They were not rerun locally.

The original local result remains **38 passed, 9 failed, 177 deselected in
19.00s**, exit 1. It is a failed observation, not an aggregate local pass. This
update reconciles only CHANGELOG and LATEST with the supplied review and CI
evidence. Final docs-HEAD review and applicable CI acceptance remain pending.

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
reservation blocks adoption after partial publication. The corrected
final-reread/quarantine cases are covered by the supplied successful CI below,
not by a local rerun.

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
- Locally tested implementation: `ccf6e880caa8e5b3dfccea5139fe2c114baa4602`, tree
  `407f36bb0848811191cbabe0a45469356a09949b`.
- Test-only correction, not rerun locally and covered by the later supplied CI:
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

### Local proof and corrected-HEAD CI

The original Python 3.10.12 / pytest 9.1.1 invocation selected 47 nodes without
`-x`, under a 300-second bound plus 5-second termination grace. All completed:
**38 passed, 9 failed, 177 deselected in 19.00s**, exit 1. All nine failures were
fixture `IndexError`s before the API call: the first selected task has no
references. These failures are not successful refusal evidence. The test-only
correction selects a declared reference-bearing task and adds two positive
reference-payload cases; the four original passing handoffs had no references.
None of these repaired or new cases was rerun locally.

The [immutable local-proof record] retains the redacted command display, exact
private command/log/receipt hashes, all nine failed node IDs and the original
scope/review details. The command hash identifies the exact private script,
including private paths and log capture; it is not a digest of the redacted
public display. No old evidence file was reopened or changed for this update.

The leader supplied the completed [PR752 comparison CI] result at reviewed HEAD
`865c37fe662af11850cc2681f53bf136fdc65444`, tree
`ae71f34e1d3787e584c05220de5b7780da19bab2`: run `37345048041`, job
`111881404006`, attempt 1, **1410 passed in 1008.64s**, with no failed, skipped
or deselected cases in the final result. The existing command selects
`tests/test_gpt54_time_budget_comparison.py`, including all nine repaired cases
and both added reference-payload positives. The completed log SHA256 is
`da26d6a2768d32eeefe073ea451cb35e4f67d566e71a4f5e76a889c19d19a2d1`.
This supplied CI result is separate from the failed local invocation; no
aggregate local pass is claimed. CI was not queried, polled or rerun here.

That job also emitted a positive model-free owned-host receipt at source commit
`55ee47386c97058863a5ceefb6c1e358f7f41940`, tree
`ae71f34e1d3787e584c05220de5b7780da19bab2`. The receipt's source commit is not
the reviewed PR HEAD; their supplied trees are equal. This is CI host evidence
for that source/job, not a study observation, support for another host or live
authority. No receipt or private input was read locally.

From the local proof through reviewed HEAD `865c37fe662af11850cc2681f53bf136fdc65444`,
the repository delta contained only the fixture correction and two new cases in
`batch-runner/tests/test_gpt54_time_budget_comparison.py`, plus CHANGELOG and LATEST.
Production, the prospective manifest and usage README still matched the locally
tested implementation. This reconciliation adds only `CHANGELOG.md` and
`tasks/LATEST_TASK_RESULT/README.md` changes. Every source/test/config/pin and
usage README byte remains unchanged from the reviewed HEAD.

### Remaining work and evidence boundary

Source review and the supplied successful checks apply to `865c37fe662af11850cc2681f53bf136fdc65444`.
Final docs-HEAD review and applicable CI acceptance remain pending after this
records-only commit. Earlier software proofs, the distinct NAS refusal and
PR751's exact-source/host evidence remain separate in the [immutable prior
record]. Neither that evidence nor the new PR752 host receipt authorizes a live
study observation. No platform probe was run locally.

The single next execution wiring gap is a consumer that revalidates this
one-observation handoff and supplies the required control to the existing V2 or
Codex factory under a separately reviewed source-bound execution direction.
That future work must still bind a usable host, verified credentialed originals,
provider identity, live dispatch/capture and eventual F-derived grading. None
is selected or enabled here; no spending-approval question is reopened.

This records-only update uses `im-not-ai-en` for one bounded changed-passage
fidelity check, which passed with no failures or warnings. It preserves counts,
source identities, provenance and the local/CI distinction without scanning the
historical changelog. Experiment
design and the earlier source review were not reopened. No pytest/Node/HF/build,
platform probe, CI query/poll/dispatch/rerun, private input/receipt/preparation,
provider/model/grader/Azure call, Project edit or merge occurred in this update.

[PR752 comparison CI]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37345048041/job/111881404006
[immutable local-proof record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/865c37fe662af11850cc2681f53bf136fdc65444/tasks/LATEST_TASK_RESULT/README.md
[immutable prior record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/e0e270b67b3c7f63b8f94f945c4839b778c7572b/tasks/LATEST_TASK_RESULT/README.md
