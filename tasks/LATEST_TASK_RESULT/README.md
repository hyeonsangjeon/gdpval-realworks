# Latest task result

## Native-only mode for the existing CI connection diagnostic

The existing workflow now has an opt-in `native_only` mode. Its focused offline
selection at `f09ffb62b717f9818dedd4e59a9a45c483ca4f42` reported
`42 passed, 155 deselected in 4.92s`, exit 0. This checks local command/reporting
behavior and the workflow's static contract, not current CI connectivity or
benchmark performance. No diagnostic was dispatched.

### Implemented boundary

`native_only` defaults to false, preserving the legacy commands, order and
behavior, including unservable probes when all send flags are false. With
native-only enabled, the first local step rejects `send_valid_request` or
`send_closing_sweep` before checkout, setup, OIDC or native work. All five legacy
probe steps are skipped: models listing, bearer discrimination,
transmission/header sweep, plain-urllib servable request and closing sweep.
The unchanged legacy summary is gated off; the native-only summary labels these
probes intentionally skipped, not measured.

Native-only plan mode sends no model turn. A later dispatch would still perform
the existing OIDC and plan auth preflight; plan-only is not network-free.
Sending retains the existing plan, endpoint-fingerprint confirmation and sole
native send path. The main-only guard, existing OIDC scope/expected identity,
Ubuntu 22.04, Python 3.10.12, SDK/companion 0.147.0, prompt, provider retry pins,
runtime, redaction and cleanup paths remain unchanged. Both provider retry
counters remain 0, but the runtime can refresh a token after a 401 and resend.
One native turn is not a measured HTTP-request count or a complete invoice.

The workflow ceiling remains 20 minutes. The script still defaults its timeout
argument to 120 seconds and forwards it to the runner. This unit does not add
timeout enforcement or establish a hard live stream deadline. Its tests check
existing close/workspace-cleanup calls, not a live owned-process tree. The
diagnostic sets no reasoning-effort or context-window override; those runtime
defaults are not the pilot's `xhigh` control. No prompt or runtime setting was
changed to make the diagnostic match the benchmark.

The summary distinguishes requested sending from observed `turn_sent`, and
provider replies from successful connectivity. Failed or unobserved auth,
completed turns and final-response presence keep their separate meanings. If a
requested send has no valid record, its observations remain unknown rather
than falling back to the plan's `turn_sent=false`. Only controlled fields are
rendered after a successful redaction check. Known thread-total and
most-recent-request usage stay separate; missing usage is not zero cost.
Evidence upload still requires that check to succeed and retains the same
seven explicit JSON paths. No token, raw error, endpoint, answer, native state
or private locator is added to the summary or upload allowlist.

### Focused offline evidence

One invocation used the existing isolated Python 3.10.12 interpreter, named
`NATIVE_CI_PYTHON` below, with SDK and companion 0.147.0, from `batch-runner`:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. "$NATIVE_CI_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short tests/test_codex_foundry_connection_probe.py tests/test_codex_auth_discriminator.py 'tests/test_a_step_reference_that_names_nothing.py::test_each_workflow_on_its_own[codex-foundry-connection-diagnostic.yml]' -k 'native_only or test_each_workflow_on_its_own'
```

The 42 cases cover all 16 input combinations, early contradictory-flag refusal,
native-only plan/send and unchanged legacy routing, the actual fingerprint and
send shell, missing-output refusal, safe summaries and existing redaction.
The real `main`, plan/probe, record and output paths run with synthetic auth
observations and SDK-shaped native transport. Live subprocess, credential
discovery and socket boundaries are forbidden in those entry tests. Action
pins, permissions, ref/identity gates, timeouts, step references and publication
conditions are checked statically; no GitHub Actions execution occurred.
The 4.92 seconds are pytest wall time, not model latency. Before the upstream
integration below, only completion records changed after the tested SHA.
The reviewed workflow/test bytes remain unchanged through integration; this is
not a fresh test run on the integration HEAD. Earlier selections and packaging
were not rerun.

### Source, prior reviews and remaining work

This branch starts from exact main
`ea81fefc7dae1297dee7d68e78327a0f05fb6958`, independently of #656. The mandatory
extreme-reasoner decision preceded the workflow edits and covered only this
bounded implementation/offline check, with conditions. It used the available
inherited agent, not the charter's unavailable named preset.

Prior #655 review `5285590451` at
`4d3c4b4f895da35e3db07b413f66c8066dfa5ad1` covers the one-cell CI entry and its
19-case offline evidence. Prior #656 review `5285752981` at
`df3e3f24404a90f47789051ef99318fb6af2dd20` covers the 39-case local bundle
evidence and private 2519040-byte candidate, not external publication or live
readiness. Its separate, normal integration commit
`ca41664cf36f7b2183ef8bdd02df8cd0f822eb04` preserved the reviewed bundle source
and tests byte-for-byte and retained both completion histories. That integration
did not rerun the 39 cases or obtain a new final-head approval; #656 is frozen
again at that handoff. Neither earlier review approves this native-only change.

The leader subsequently supplied #657 FINAL-APPROVE review `5286077604` at
`0f291f4041bb321817ce93e6d8b4bfe0c4f2cfb0` and new main
`266ef7a05335d900304214da0c0d680331fb346c` after #656's nine applicable checks.
One normal upstream merge integrates that exact main. Its only conflict was
this completion record. Both substantive changelog entries are retained, with
native-only remaining the latest result. The three reviewed native-only
workflow/test blobs match `0f291f4041bb321817ce93e6d8b4bfe0c4f2cfb0` exactly;
the two incoming bundle implementation/test blobs match main exactly. No test,
packaging, diagnostic or CI query was repeated. The prior review covers its
named HEAD, not a new final-head approval of this integration.

Current CI connectivity, approved input transport, whole-pilot ordered CI
scheduling, deduplication/aggregation, execution and fixed grading remain
unfinished. Review/CI for the integration HEAD remain required. Both
campaigns, original inputs and the private candidate remain untouched. No SDK,
credential, permission, source-fingerprint or experiment-control change, live
auth/model call, CI query or bundle operation occurred. Standing owner budget
authority is unchanged; this implementation authorizes no dispatch.

For a later leader-authorized native send on reviewed main, the intended
`workflow_dispatch` inputs are:

```yaml
deployment: gpt-5.4
native_only: true
send_request: true
send_valid_request: false
send_closing_sweep: false
```

Experiment-design kept the diagnostic separate from benchmark evidence.
Backend guidance preserved the existing command, identity and cleanup seams.
Reporting/copyediting preserved the test units, unknowns and review boundaries.

## Prior local input-bundle record

The following record retains its original source/test/review scope. Its
outstanding-review statements describe that earlier bundle handoff, not the
later leader-supplied #656 integration or this native-only change.

## Local transfer bundle for pinned CI originals

The local producer/importer now preserves and verifies the four registered
original files without implementing transport or execution. The focused
offline family passed at `3c20adb08e1db62d81855a5184963ad1bf342061`:
`39 passed in 3.19s`, exit 0. One authorized producer call also created a
private candidate from the real named original-source handoff. No real
import, external transfer or pilot execution ran.

### Format and publication boundary

`batch-runner/codex_ci_input_bundle.py produce` uses the existing genuine
original-input reader, source snapshot, reference-only tree checks and
canonical schema-4 `deliverable_only` Step 0 validator. It preserves the
normalized original parquet, the exact two declared references and canonical
Step 0 bytes. The deterministic, uncompressed USTAR archive adds only
`input-bundle-manifest.json`, which records dataset revision and ordered
logical paths, roles, sizes and SHA256 values. Headers have fixed order,
permissions and timestamps, with no host ownership or locator metadata.
No Step 0 classification is regenerated.

`import --bundle <local-file> --expected-sha256 <external-sha256> --out
<new-private-root>` requires an externally supplied digest; the manifest is
not its own trust anchor. Before publication, the importer validates the
whole archive and exact allowlisted member count, names, order, regular-file
types, canonical headers, bounded sizes and immutable content. It refuses
links, traversal/absolute paths, duplicate/extra members, compression,
oversized/truncated data, noncanonical padding and mismatched digests. It
never calls `extractall`. Both the destination and its sibling reservation
must be absent. Once reserved, an interrupted or refused publication keeps
its reservation and any partial files; a later invocation cannot adopt them.
Published roles are `original.parquet`, `reference-only/...` and
`step0-manifest.json`. The real original-input verifier reads the installed
roles before `input-bundle-ready.json` is written last. The private import
root uses mode 0700 and published files use mode 0600.

### Focused offline evidence

The first invocation at `ed70d862ed98a8645a38691f65f714cc1c82e78d` returned
`33 failed, 6 passed in 2.97s`, exit 1. `_safe_path()` returned the result of
`core.inference_manifest._assert_no_symlink_ancestors()`, but that validator
returns `None`, causing an early `AttributeError` before publication. Five
source-negative passes occurred at that wrong earlier boundary and are not
treated as source-verifier evidence. The correction returns the validated
absolute path and strengthens those tests to require a source-reader call.
The same selection then returned `39 passed in 3.19s`, exit 0, at
`3c20adb08e1db62d81855a5184963ad1bf342061`.

Both invocations used this command from the repository root, with
`CI_BUNDLE_PYTHON` bound to the existing isolated interpreter recorded in the
private handoff. Its installed runtime is Python 3.10.12,
`openai-codex==0.147.0` and `openai-codex-cli-bin==0.147.0`; nothing was
installed for this task.

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$CI_BUNDLE_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_ci_input_bundle.py -k ci_input_bundle
```

The tests traverse real CLI producer/importer entry points with tiny synthetic
files. Original parquet provenance and fixture-only Step 0 digest pins are
explicit synthetic boundaries; archive handling, current-byte hashing,
reference-tree and canonical-manifest readers, no-clobber publication and
refusal paths remain real. The family checks deterministic bytes across
different paths/timestamps, exact role mapping and byte preservation, external
SHA requirements, archive attacks, source drift/missing/linked/extra inputs,
retained reservations and refusal of corrupt installed partials. One case
reads the actual registered contract without opening original payloads.
Offline guards forbid subprocess, network, auth, Codex/provider and grader
construction. No prior suite or #655 selection was rerun. Test durations are
pytest wall times, not task latency, recovery quality or invoice evidence.

### One private real candidate

After the passing selection, one authorized local observer called
`codex_ci_input_bundle.main(["produce", ...])` at the corrected SHA, using
only the three original-source locators from the existing named private
handoff. It did not spawn a CLI process. The genuine reader verified dataset
revision `11e7900cdcac61bc4daf59e65feb238acda98fbf` and all four approved
source roles. Exit was 0; the producer call took 0.591994 seconds, excluding
interpreter startup. Process/network attempts were 0. No real-input importer
operation occurred.

| Candidate or member role | Bytes | SHA256 |
| --- | ---: | --- |
| Whole uncompressed bundle | 2,519,040 | `757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3` |
| Logical-role manifest | 844 | `d5e77412993344e6a8510113d9969cb72157643e9cde63e27e51107b624fb0df` |
| Normalized original parquet | 1,913,489 | `f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202` |
| Declared PDF reference | 47,850 | `901e943a97328a661f9e704ae43eeea167e7805385a99322f1c24f8e159125c4` |
| Declared XLSX reference | 329,418 | `bb09ca2a9999b404d7fced9202b42949cd9f142f39554e254bac77b3686dae9e` |
| Canonical Step 0 manifest | 218,405 | `463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512` |

The observed `canonical_step0_publication_sensitive_fields_found=false`
means only that the bounded structured-field-name/absolute-string-path
screen found no match. It is not a comprehensive sensitive-content audit or
a safe-to-publish determination. Canonical bytes were not edited. The
candidate, observation and exact input/output/interpreter locators remain in
the private handoff; external publication is not authorized. No credentials,
auth stores, native workspaces/transcripts, ledgers or generated model results
are added to the bundle. No task or reference content is printed in these
records.

### Controls, review boundary and remaining work

This branch started independently at
`42c7b8f2f6457463333e386432baceed96182c72`. One later source fetch and normal
non-squash merge integrated exact main
`ea81fefc7dae1297dee7d68e78327a0f05fb6958`. The actual conflict was confined
to this latest-result page; both substantive changelog entries were retained,
with the bundle kept as the latest result. The bundle source and test files
compare byte-for-byte equal to reviewed
`df3e3f24404a90f47789051ef99318fb6af2dd20`. The leader's FINAL-APPROVE
review `5285752981` covers that earlier head and its original 39-case/private
candidate evidence, not a new run or approval of the integrated head.

#655 review `5285590451` at `4d3c4b4f895da35e3db07b413f66c8066dfa5ad1`
and its 19-case offline evidence cover the one-cell entry only. The leader
reported all 10 applicable checks passed before integration; CI was not
queried here. No tests or packaging were repeated for this merge. The
`39 passed in 3.19s` result remains tied to
`3c20adb08e1db62d81855a5184963ad1bf342061`; only completion records followed
that SHA before this upstream integration. Source counts remain 37/58, with
no new grader-source or active-hash edits. Prior results and review scopes
remain in the preserved changelog entries and immutable Git history.

The sealed `budget_pilot_20260923_01` campaign, its source
`0d6ed6d806fc0360434952792d5ab82327290570`, original inputs and all 30 pending
cells remain untouched. Neither that campaign nor
`budget_pilot_ci_20260923_01` was rematerialized. The fixed five-task cohort,
30-cell order, GPT-5.4/direct-v1/xhigh settings and grader remain unchanged.
A keeps four fresh attempts; B/C retain the same workspace/native-thread and
backoff policy, with C's host error feedback as their only intervention.
The 180-minute cumulative and 30-minute attempt limits are unchanged.
Packaging bytes is not execution evidence, consumption, readiness or graded
quality. No model call, authentication retry, preparation or Step 1/Step 2
execution occurred.

The integrated head still needs immutable review and CI. Approved transport and
workflow integration, ordered 30-cell scheduling/aggregation, live CI
OIDC/current connectivity, separately directed paid execution and grading
remain unfinished. #655's missing-input refusal is not bypassed by a local
candidate. Standing owner budget authority is unchanged; this is not a new
approval wait or an execution authorization.

Experiment-design kept inputs and experimental controls fixed and separated
transport from execution. Backend guidance kept validation and publication
on the existing helpers. Experiment-report-en and im-not-ai-en preserved the
synthetic/real evidence boundary, failure history and privacy-screen limits.
The bundle implementation adds no workflow, dependency, UI, pricing, upload
or QA changes. This merge retains #655's reviewed workflow and adapter bytes
without modifying them.
