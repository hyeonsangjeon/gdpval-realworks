# Latest task result

## Project5 first registered local comparison preparation — 2026-10-04

One model-free local preparation succeeded for the first registered comparison
row, `gpt54_v2_codex_v1_v2_r1`: `sandbox_v2`, repeat 1, five registered tasks.
The unchanged preparer returned after its built-in final verification, exit 0.
This created one private, source-bound checkout with verified config and input
bundles. It did not execute the comparison or establish launch readiness.

### Reviewed source and fixed selection

The operation used a fresh clean source worktree at accepted main
`14d7579c2578cb2a09397b5d42f41e7b5daaf2d7`, tree
`b3988e0f794866abc44007d22d632e2691485b1b`. The missing commit was obtained by
one ordinary origin fetch of that exact SHA. No existing worktree was reused,
reset or modified.

The leader supplied PR744 delivery evidence: reviewed HEAD
`fd903b96dc8d4622470b6971fde820334c16396b`, owner
[review5408616238][first-preparation-source-review], all 11 applicable checks
successful and PR-only deploy skipped. These are prior source-review facts,
not review or CI results for this new records HEAD. No CI query or proof rerun
was performed here.

The selected [prospective manifest][first-preparation-manifest] retains raw-file
SHA256 `51a1788d37b7eba3aa134dccff13fdb27eeb5be1ba9a00896e6f2b97fe6509d5`.
The real `compile_grading_plan(load_plan(...))` produced the combined plan;
`plan.dispatch.runs[0]` supplied the exact typed first row, checked against its
run ID, condition, repeat and task count. Only that row was passed once to
`prepare_disposable_checkout`, with `combined_plan=plan.as_dict()`, the exact
reviewed source SHA and explicit `manifest_path`. No other row was prepared.
Model, effort, task order, ABBA20, run IDs, limits, source pins and launch flags
were not changed.

### Observed preparation and safe identities

The preparer itself performed its normal original-parquet, cohort, prompt and
reference checks. The previously read 6679-byte input metadata receipt, SHA256
`b5b3b95b7da05f7a0af868196ef8bc7df5cdd40c03c6a5c83971eb088589a965`, supplied
locators only; it was not treated as fresh input verification or reopened here.
The archive was not opened or rehashed, and the importer was not rerun. This
SandboxV2 call supplied no Step0 argument and did not read the Codex-only
canonical Step0 file.

The destination was new and absent before the attempt, outside all source and
input trees, under a private mode-0700 parent with umask 0077. The existing
exclusive reservation, no-clobber publication and quarantine rules remained
active. The reservation was retained; no destination was adopted, overwritten,
retried or cleaned up. No separate marker/input verification or runtime-verifier
probe followed the preparer's own final check.

The operation ran in the existing Python 3.10 environment with `env -i`, no
provider credentials and offline input settings. Its 300-second timeout and
5-second termination grace bounded this local software operation only, not a
model budget or CI job. Captured UTC timestamps were 23:25:55Z–23:26:05Z on
2026-10-04. Preparation and both capture processes exited 0. Each output stream
had an enforced 65536-byte capture cap; neither reached it. Stdout contained
1767 bytes of metadata, and stderr was empty.

The returned marker records ABBA index 0 and task count 5. Its semantic manifest
SHA256 is `43db7cb37aa814750640a2e5d0837b390c607a63e8a70ff6fd6c3c62600aa4b3`,
distinct from the raw-file digest above. Combined-plan SHA256 is
`31dccc9293498eba760088687c150441fda4d233481b4983ec958cffb47f0c4a`.

| Generated marker | Bytes | SHA256 |
| --- | ---: | --- |
| Checkout ready | 5831 | `567c71e73cce0ee8c65bf1fecb12d59cb938ab62585cc369a3cc9a1e6d7f679a` |
| Config bundle | 11214 | `b63e1170a0b4e203fcf6cad852b6a89679ab377fa128fcc5c173212224abcf98` |
| Input bundle | 4716 | `1458a08dde78ecd3ac52aa0862eacc67a9271e33bdacccdbd9f19c8206b4f077` |

These identities come from the marker returned by built-in final verification.
The checkout-ready digest is computed from that marker's canonical bytes; the
config/input identities are its existing verified bundle entries. No generated
marker or original input was reopened to obtain this record.

The exact command and all local locators remain private. The 3685-byte command
has SHA256 `b42ab417335691d61b0cc9a5ed98037821e65511d048e64b9e0c4316bbe3145c`.
Stdout SHA256 is
`210a54806d204ad83c7ef2959669207997c9b13ff9c84f42b78896ca20e02a1b`;
empty-stderr SHA256 is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The private 5509-byte preparation receipt has SHA256
`f76b5cf42ca05ce8ce94d81080a3d728ebd2bacf178a079cf496e913561e2d84`.
Evidence files are mode 0600. No archive, original body, local path or raw
marker content is published in this record.

### Prior evidence and remaining work

<a name="project5-prospective-local-preparation-source-profile--2026-10-04"></a>

The prior source-profile implementation, 60-case/2-case/5-case proofs, CURRENT
observer correction, incomplete invocation and 14-case continuation remain in
the [immutable prior task record][first-preparation-prior-record]. That record
also preserves earlier failure and local-input provenance. Those proofs were
not rerun and are not evidence of this new real-input preparation. This page
replaces the stale task status rather than appending its full history.

Only CHANGELOG and this single current task record change after the operation.
The source worktree was clean at the reviewed HEAD before and after preparation.
Final records-HEAD review, applicable CI and leader acceptance remain pending.
No carrying-PR future delivery state is asserted.

The runtime and workflows still do not select this prospective profile. Native
call/token caps, the dispatcher and credentialed-CI input authority remain
unresolved, and all existing launch refusals remain in force. The credentialed
comparison-workflow intake proposal remains REJECTED; local verification does
not establish CI-read authority. Any execution
requires separate direction; this artifact proves no served model identity,
input wire consumption, inference, grade, model success or cost measurement.
No Step1, Step2 or Step8 entrypoint, model client, provider/input-network request,
workflow dispatch or consumed-study operation was run. The registered
20-observation comparison remains unexecuted; the separate 30-cell pilot and
8-cell retention study remain closed and unchanged.

The catalog was inspected once. experiment-design preserved the registered
configuration-bundle scope and stop-after-one-result boundary; im-not-ai-en was
used only for bounded English records. No runtime selector or new experiment
was used to validate this documentation. Bounded English fidelity, captured
metadata/literal/link checks and `git diff --check` passed without another input
read or preparation call.

[first-preparation-source-review]: https://github.com/hyeonsangjeon/gdpval-realworks/pull/744#pullrequestreview-5408616238
[first-preparation-manifest]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/14d7579c2578cb2a09397b5d42f41e7b5daaf2d7/batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_comparison_local_source.yaml
[first-preparation-prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/fd903b96dc8d4622470b6971fde820334c16396b/tasks/LATEST_TASK_RESULT/README.md
