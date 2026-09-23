# Latest task result

## Sweep contract correction and stopped private input staging

The stale transmission-sweep workflow test now requires the reviewed
native-only exclusion. Its single offline invocation at
`e6445a0544e0e6c0bb3d5ef6bee4a232be96ccff` reported
`1 passed in 0.25s`, exit 0. No workflow or runtime code changed.

Separately, one authorized private staging transaction verified the existing
candidate and created draft release `394272629`. The single asset upload
attempt returned HTTP 400 (`gh` exit 1); no asset ID was captured. The transaction
stopped without retry. This is partial staging, not a completed input transfer
or proof that CI's `contents:read` token can access the draft.

### One corrected static contract

The leader supplied failed CI run `35809373961`, job `107017506054`, at
`2e89f411efc4294a47831a1b58cb8b0c99c90418`. Its
`tests/test_codex_transmission_sweep.py:625` assertion required
`"if" not in step`, although the reviewed workflow intentionally uses
`${{ !inputs.native_only }}`. REQUEST-CHANGES review `5286466233` records that
test-contract defect. It is not a native/runtime failure; CI logs and status
were not queried here.

The corrected test is
`test_native_only_skips_the_sweep_and_legacy_cannot_buy_a_turn`. Its name and
docstring now distinguish native-only exclusion from legacy dispatches. It
requires the exact condition, following the discriminator counterpart, while
retaining both `--transmission-sweep` presence and `--send-request` absence
assertions. No skip, weaker condition or diagnostic/settings change was added.

The test correction was committed before this one invocation from the source
root. `NATIVE_CI_PYTHON` denotes the existing isolated Python 3.10.12 interpreter
with `openai-codex==0.147.0` and `openai-codex-cli-bin==0.147.0`; its private
locator is not republished. Nothing was installed.

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=batch-runner "$NATIVE_CI_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short batch-runner/tests/test_codex_transmission_sweep.py::test_native_only_skips_the_sweep_and_legacy_cannot_buy_a_turn
```

The result checks the real YAML step and command contract, not live workflow
execution or model behavior. Neither the earlier 42-case selection nor #658's
67-case selection was rerun. The 0.25 seconds are pytest wall time, not native
latency, recovery quality or consumption. Subsequent completion-record edits
do not change the tested bytes. Active source sets and hashes are unchanged.

### Separately authorized private staging observation

Only the exact named private handoff was resolved, through focused named-path
checks without a directory inventory. Its existing archive passed a current
private-owned regular-file/single-link check and byte verification:
2,519,040 bytes, SHA256
`757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3`.
That is the previously reviewed bundle of four originals plus its logical
manifest. No source was rematerialized, imported, repackaged or replaced.
Only those verified bytes were supplied to the upload invocation.

The local observer used the existing `gh`/REST client and verified the existing
`hyeonsangjeon` account. An exclusive private one-use reservation preceded
release creation, and the returned release ID was saved immediately. The
release's repository, ID, label, exact target and unpublished draft status were
verified before upload. The observed stages are:

| Boundary | Observation |
| --- | --- |
| Release creation | ID `394272629`, label `project5-ci-inputs-20260923-01`, target `266ef7a05335d900304214da0c0d680331fb346c` |
| Pre-upload release check | `draft=true`, `published_at=null`, no existing assets; `make_latest=false` was requested at creation |
| Named tag ref | Absent before and after draft creation; no tag/ref mutation API was called |
| Single upload attempt | `budget-pilot-originals-20260923-01.tar`, `application/x-tar`; HTTP 400, `gh` exit 1 |
| Asset receipt | No asset ID captured; uploaded state, remote size and provider digest remain unobserved |
| Post-upload metadata | Not reached after the failed response; asset existence is unresolved, not proven absent |
| CI read-token access | Not observed; owner-account draft access is not that capability |

The observer exited 2 after 2.506628 seconds. It made six `gh api` invocations,
including the selected metadata checks, one create and one upload attempt;
this is not a measured HTTP-request count or a billing statement. Calls were
bounded to 30 seconds, or 60 seconds for upload, within a shared 240-second
transaction deadline. Those limits are separate from model and CI job budgets.

HTTP 400 is the observed upload blocker. Its underlying cause was not diagnosed;
no account, permission or authentication explanation is inferred. No retry,
clobber, fallback, asset retrieval, publication or deletion followed. The
external SHA remains authoritative; no provider digest was observed. The
private reservation, immediate release receipt and stopped observation are
retained with the original handoff. Their absolute locators, tokens, signed
URLs, file contents and raw responses are not published. The incomplete upload
must not be silently replayed or treated as a usable input asset.

### Original native-only evidence remains scoped to its tested SHA

The original result remains `42 passed, 155 deselected in 4.92s`, exit 0, at
`f09ffb62b717f9818dedd4e59a9a45c483ca4f42`. It is not a new result at the
correction SHA. That invocation ran from `batch-runner` with the same isolated
interpreter:

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. "$NATIVE_CI_PYTHON" -m pytest -q -o addopts= -p no:cacheprovider --tb=short tests/test_codex_foundry_connection_probe.py tests/test_codex_auth_discriminator.py 'tests/test_a_step_reference_that_names_nothing.py::test_each_workflow_on_its_own[codex-foundry-connection-diagnostic.yml]' -k 'native_only or test_each_workflow_on_its_own'
```

Its 42 cases cover the 16 flag combinations, local command/reporting paths with
synthetic auth and SDK-shaped transport, and static workflow guards. They are
not a live Actions run, current connectivity or owned-process cleanup proof.
The newly corrected transmission-sweep case was outside that selection.

The reviewed native-only implementation remains unchanged. Default false keeps
legacy behavior; enabled mode rejects incompatible paid flags and skips all
five obsolete listing/discrimination/sweep/urllib probes. Native-only plan mode
sends no model turn but would still perform OIDC and auth preflight in a later
dispatch. Sending retains the reviewed-main, identity, endpoint-fingerprint,
runtime/retry, redaction and seven-file evidence-upload guards. The job ceiling
remains 20 minutes and the script timeout argument remains 120 seconds; this
correction adds no hard live stream deadline. Diagnostic runtime defaults are
not the pilot's `xhigh` control. One native turn is not an exactly-one-HTTP or
invoice-completeness claim: a 401 can trigger token refresh and resend despite
zero provider retry pins. Missing send evidence does not become the plan's
`turn_sent=false`, and missing usage is not zero cost.

For a later separately authorized native send on reviewed main, the unchanged
intended inputs are below. No diagnostic was dispatched here.

```yaml
deployment: gpt-5.4
native_only: true
send_request: true
send_valid_request: false
send_closing_sweep: false
```

### Review boundaries and remaining work

This correction continues the existing #657 branch from integrated
`2e89f411efc4294a47831a1b58cb8b0c99c90418`; main remains
`266ef7a05335d900304214da0c0d680331fb346c`. The only non-record change is the
single transmission-sweep test. The workflow, diagnostic/runtime, bundle and
experiment settings remain unchanged.

The leader cites prior #657 review `5286254682` for the native-only change.
Earlier review `5286077604` at
`0f291f4041bb321817ce93e6d8b4bfe0c4f2cfb0` retains its original scope.
Neither is approval of this test correction. #658 FINAL-APPROVE review
`5286466150` at `e5d5fcb647129e86d9faf742fc19df1e1e800c15` covers the private
intake implementation, not live transfer/access. Its
`67 passed, 18 deselected in 4.66s` evidence remains at
`f4a984d8bed0f6845e405c5b6d9f82b3b96757e0`. #658 was left frozen.

Prior #655 review `5285590451` covers the one-cell entry; #656 review
`5285752981` covers the local bundle/private candidate, not public distribution.
The detailed 19/39-case evidence, bundle failure/correction and member identities,
bounded sensitive-field screen, and prior integration history remain in the
[immutable pre-correction record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/2e89f411efc4294a47831a1b58cb8b0c99c90418/tasks/LATEST_TASK_RESULT/README.md)
and unchanged changelog entries. The earlier screen is not publication clearance.

The NAS campaign `budget_pilot_20260923_01`, its sealed source
`0d6ed6d806fc0360434952792d5ab82327290570`, original inputs and all 30 pending
cells remain untouched. `budget_pilot_ci_20260923_01` remains reserved, not
materialized or run. The five `advance_check_5` tasks, per-task
A1/B1/C1/C2/B2/A2 order, GPT-5.4/direct-v1/xhigh target, tools/context/grader and
common CI host policy remain fixed. A keeps at most four fresh attempts; B/C
share retained continuation/backoff, with only C receiving host error feedback.
The 180-minute cumulative and 30-minute attempt budgets, and 240-minute cell
job setup/cleanup ceiling, are unchanged. Failed/missing outcomes and accounting
are not converted to success, zero charges or grades.

New immutable-HEAD review/checks, the unresolved upload and selected-asset
receipt, a separately directed CI read-token `input_check`, current CI native
connectivity, ordered 30-cell scheduling/deduplication/aggregation, execution
and fixed grading remain unfinished. No CI query, workflow dispatch, live
intake, OIDC, NAS Azure auth retry, native/model or grader call occurred.
Standing spend authority is unchanged; the upload failure is a technical
boundary, not a new owner-approval wait. No automatic staging replay or live
diagnostic follows this record.

Experiment-design kept the contract correction, private transfer observation
and A/B/C treatment separate. Reporting and English copyediting preserved the
original test/review scopes and the difference between an observed draft and
an unobserved asset outcome.
