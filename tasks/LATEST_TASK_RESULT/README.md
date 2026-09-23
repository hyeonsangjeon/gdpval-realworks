# Latest task result

## Private draft-asset intake before single-cell CI admission

The single-cell workflow now has an explicit input-intake path that verifies
one selected same-repository draft release asset and imports the registered
original roles before Azure OIDC or model admission. Plan-only remains the
default. The focused offline selection at
`f4a984d8bed0f6845e405c5b6d9f82b3b96757e0` reported
`67 passed, 18 deselected in 4.66s`, exit 0. No real asset was transferred or
imported. Whether the existing `contents:read` token can access the private
draft remains unproven; the permission declaration is not access evidence.

### Intake and privacy boundary

`batch-runner/codex_ci_input_intake.py --input-check` requires explicit positive
numeric release and asset IDs, an external expected SHA256, a new absent
private staging file and a new absent private input root. It accepts only
`hyeonsangjeon/gdpval-realworks` and the registered candidate expectation:
2,519,040 bytes, SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
That size/digest comes from the earlier private packaging observation, not a
new read, rehash, import or transfer in this task. An asset's metadata or inner
manifest is not its own trust anchor.

The intake uses only the existing process-local `GITHUB_TOKEN` and constructs
the API paths for the supplied IDs locally. It requires matching repository
and release identities, literal `draft=true`, unique selected-asset membership,
uploaded state, a bounded regular filename/type and the exact registered size.
It does not enumerate releases or use `browser_download_url`. A 401/403/404
returns `github_draft_or_asset_inaccessible`, without diagnosing whether the
cause is token validity, permission or absence. There is no published-release
fallback, alternate repository, new credential or permission widening. Draft
status is checked at metadata-read time; it cannot guarantee that a maintainer
will never publish the release later.

Metadata is limited to 256 KiB and 100 asset records. Automatic redirects and
ambient proxies are disabled. Metadata redirects are refused. An asset may
return bytes directly or use one validated HTTPS redirect to the genuine
`release-assets.githubusercontent.com/github-production-release-asset/` path.
The redirected request has fresh headers without authorization, cookies,
Referer or GitHub auth headers. Other hosts, malformed targets and additional
redirects refuse. Response types, encoding, declared and actual lengths are
bounded; the full external digest is checked before payload bytes are staged.
Network operations have at most 30 seconds within a shared 120-second transfer
deadline. The workflow sends TERM at 120 seconds and KILL after another
5 seconds; the intake/check step has a 3-minute ceiling.

Existing no-clobber helpers hold destination parents and retain reservations
and partials after refusal or interruption. A later invocation cannot adopt
them. The unchanged `codex_ci_input_bundle.import_bundle` validates the archive,
publishes `original.parquet`, the two references under `reference-only/...`,
and `step0-manifest.json`, then runs the genuine installed-original reader
before its ready record is written. Step 0 is not regenerated, references are
not substituted and canonical bytes are not edited. Controlled refusal codes
do not print raw response bodies, signed URLs, tokens, file contents or private
host paths. The existing completion-envelope-only upload remains unchanged;
the bundle and private imported state are not added to public artifacts.

The workflow first binds the reviewed main source and canonical cell and
materializes its plan. Only explicit `input_check` or `execute` requests reach
intake; the two flags are mutually exclusive. `verified=true` is emitted only
after both intake and the existing adapter's `--resume --check-inputs` succeed.
Native prerequisites, Azure login, session-identity verification and execution
require that verified result plus explicit execution. Input-check does not
request Azure OIDC or invoke native/model work. The existing job-wide
`id-token: write` declaration remains; this is a control-flow restriction,
not a claim that the job lacks OIDC permission. Missing or rejected inputs
still stop before those execution steps.

### Focused offline evidence

One invocation used the following command from the repository root.
`CI_INTAKE_PYTHON` denotes the existing isolated interpreter retained in the
private handoff; its absolute locator is not republished here. Installed
versions were Python 3.10.12, `openai-codex==0.147.0` and
`openai-codex-cli-bin==0.147.0`. Nothing was installed.

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$CI_INTAKE_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_ci_input_intake.py batch-runner/tests/test_codex_budget_pilot_ci.py -k 'ci_input_intake or ci_registered_cell_workflow_invocation_contract'
```

The result is 66 new intake cases plus one directly affected workflow contract,
not 67 pilot cells. The tests use tiny synthetic originals with explicit
fixture-only provenance/anchor substitutions and fake GitHub metadata/download
responses. The CLI, request construction, importer, archive validation,
current-byte hashing, reference-tree and canonical Step 0 readers, reservations
and publication guards remain real. Cases cover missing IDs/hash,
ownership/draft/access refusals, metadata and payload limits, redirect/auth
isolation, digest failure,
no-transfer plan mode, input-check without OIDC, correct roles and retained
partial-state refusal. Offline guards forbid live sockets, auth, native,
provider and grader construction.

Controlled shell checks exercise the workflow's early refusals and verified
output with fake commands. Static YAML contracts check ordering, gates,
permissions, timeouts and publication. These are not a GitHub Actions run or
proof of private draft access. No prior bundle, dispatcher or diagnostic
family was rerun. Pytest wall time is not transfer latency, recovery quality,
model consumption or an invoice. No real release API, upload/download, auth,
native/model, grading or original-data operation occurred.

### Source and prior review scopes

This independent branch starts from
`266ef7a05335d900304214da0c0d680331fb346c`. The tested implementation is
`f4a984d8bed0f6845e405c5b6d9f82b3b96757e0`; the subsequent completion-record
commit does not change those tested workflow/source/test bytes. The adapter,
dispatcher, bundle implementation, core, experiments and dependencies are
unchanged. The new intake module is outside the active full-grader source
closure, so no coupled hashes need updating. Exact source-set guards remain
37/58 and were not rerun.

Before this implementation, one normal non-squash merge integrated exact main
`266ef7a05335d900304214da0c0d680331fb346c` into the owned #657 branch. Its
pushed integration HEAD is `2e89f411efc4294a47831a1b58cb8b0c99c90418`. The
only conflict was this completion page. Both substantive changelog entries
were retained and native-only remained latest on that branch. The reviewed
native-only workflow/tests and incoming #656 bundle source/test were verified
byte-identical. #657 is frozen again; no tests, packaging, diagnostic or CI
query accompanied the merge, and no integration-head approval is claimed.

- #655 review `5285590451` at
  `4d3c4b4f895da35e3db07b413f66c8066dfa5ad1` covers the one-cell entry only.
  Its original result is `19 passed in 93.52s (0:01:33)` at
  `cb3e5dd308f769812809249f1c60ed2fdf2ade58`.
- #656 review `5285752981` at
  `df3e3f24404a90f47789051ef99318fb6af2dd20` covers the local bundle and
  private candidate only. Its original result is `39 passed in 3.19s` at
  `3c20adb08e1db62d81855a5184963ad1bf342061`. It is not transfer or public
  redistribution approval. The earlier bounded sensitive-field screen is
  not publication clearance.
- #657 review `5286077604` at
  `0f291f4041bb321817ce93e6d8b4bfe0c4f2cfb0` covers native-only diagnostic
  mode only. Its original result is `42 passed, 155 deselected in 4.92s` at
  `f09ffb62b717f9818dedd4e59a9a45c483ca4f42`, not a live diagnostic.

None of those reviews approves this intake change. The earlier bundle failure,
correction, member identities, packaging observation and privacy-screen limits
remain in the [immutable bundle completion record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/266ef7a05335d900304214da0c0d680331fb346c/tasks/LATEST_TASK_RESULT/README.md)
and unchanged historical changelog entries. No replacement receipt or new
candidate observation was created.

### Controls and remaining work

The sealed NAS campaign `budget_pilot_20260923_01`, source
`0d6ed6d806fc0360434952792d5ab82327290570`, original inputs and all 30 pending
cells remain untouched. `budget_pilot_ci_20260923_01` remains reserved, not
materialized or run. The five `advance_check_5` tasks retain per-task
A1/B1/C1/C2/B2/A2 order, the GPT-5.4/direct-v1/xhigh target, context, tools,
fixed grader and common CI host policy. A keeps at most four fresh attempts;
B/C share retained workspace/native-thread continuation and backoff, with
only C receiving host error feedback. The 180-minute cumulative deadline and
30-minute attempt bound are unchanged. The 240-minute job ceiling remains
setup/cleanup headroom, not a larger model budget. Input transport and native
diagnostics are separate from the A/B/C treatment and from graded quality.

Immutable review/CI, an explicitly directed private-draft-access and source
transfer observation, current CI OIDC/native connectivity, ordered 30-cell
scheduling/deduplication/aggregation, paid execution and grading remain
unfinished. Standing spend authority is unchanged; private access is an
unresolved technical boundary, not a new owner-approval wait. No release/tag,
upload, workflow dispatch or campaign execution is authorized by this change.

The intended later no-model input-check invocation is below; it was not run.
The leader must supply an exact reviewed main SHA, an explicit canonical cell
and the selected positive draft release/asset IDs. The feature HEAD cannot
replace the reviewed main identity, and no IDs are invented here.

```bash
gh workflow run codex-budget-pilot-ci-cell.yml \
  --repo hyeonsangjeon/gdpval-realworks --ref main \
  -f reviewed_source_sha="$REVIEWED_MAIN_SHA" \
  -f cell_id="$CANONICAL_CELL_ID" \
  -f execute=false -f input_check=true \
  -f input_release_id="$PRIVATE_DRAFT_RELEASE_ID" \
  -f input_asset_id="$PRIVATE_DRAFT_ASSET_ID" \
  -f input_bundle_sha256=757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3
```

Experiment-design kept the input/host/budget boundaries fixed. Backend guidance
kept intake on the existing importer and publication helpers. The required
pre-edit CI/cost decision covered implementation only and retained the
unproven read-token/draft-access condition. Experiment-report-en and
im-not-ai-en kept offline evidence, historical review scopes and live-access
unknowns distinct. No new dependency, identity, permission or experiment
parameter was introduced.
