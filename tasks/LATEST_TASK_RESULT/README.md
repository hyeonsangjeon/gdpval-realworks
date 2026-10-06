# Latest task result

## First-V2 static stderr event for a freshly reserved failure

The new event-focused selector reported **8 passed in 162.87s**, exit 0.
The controller now exposes the existing validated failure codes in one
non-authoritative stderr event after this invocation reserves execution and
successfully writes its failure receipt. Generic CLI stdout, refusal exit 2,
the public completion envelope and canonical result schemas are unchanged.

The accepted private-receipt proof remains **5 passed in 95.25s**, exit 0,
as a separate observation. Neither proof recovers the historical first throw,
model-call count or cost. The real first cell remains consumed and uncertain;
no replay, resume, regrade, state adoption or new cell is authorized.

### Reviewed basis and actual failed attempt

This continuation began in PR759's existing clean worktree at
`b98fc7e5eca79d55a4925ff1aa6bd78463e25814`, tree
`065c50a6be73db07fdca2464a28307ca9dc93f98`. The leader accepted the private
receipt/retention change within the inspected scope and separately approved
this tightly scoped public static event in an actual read-only review. That
review was leader-executed, not a successful spawned-model review. No reviewer
harness, design review or experiment was started. Final-HEAD review and
ordinary CI remain gates.

The leader read [run 37456739936, attempt 1][live-run], job `112246098370`,
from accepted source `7f4daa09944f6d9635e9bff3d945c224cfc76392`, tree
`9bc2b0bb655c4cd69fb3b59162776743b5a9278a`. Source/caller/ref/attempt guards,
ordinary bootstrap
and linked R/F setup, full request validation, genuine V2 originals and
preparation, permanent claim, Azure Login and existing OIDC identity checks
succeeded. The execute step alone returned exit 2 with only
`{"outcome":"refused_or_uncertain"}`. Retain, verify-envelope and artifact
publication succeeded. These are supplied leader-verified facts, not new local
reads of logs, private data, credentials or remote storage.

| Evidence | Exact identity |
| --- | --- |
| Completion artifact | `11409044632` |
| Completion artifact SHA256 | `06eb9a0c78858da29089cbd9d162e690320e45e40e3f8837de5bfaf11ef9e468` |
| Job log SHA256 | `3e606025e66106575a472cb20073ec705ff60fd0cd532d972b589faf710f9a83` |
| Permanent claim commit | `e53fe8d4c47ef2a05aea8ffcc0fe1745a9b3c288` |
| Private output commit | `f602355f945471963a338ccf79783a6f802ac6dd` |
| Host hash | `a84bfb9c4e87bd9911654714c629c00ca32466c381376b4f3f07416721ef1c87` |
| Request SHA256 | `6425b2b65ad94b6d7e1455df2d1717eccae18f937bf632f68222b80bf75f79bf` |

The bound cell is `gpt54_time_budget_v1_v2_r1` / `sandbox_v2` / repeat 1 /
task `02aa1805-c658-4069-8a6a-02dec146063a`. The verified completion has
`status=uncertain`, `retention=acknowledged`, `retry_allowed=false`,
`grading_performed=false` and `other_cells_executed=0`. Its result identity,
result fingerprint, terminal reason, usage, cleanup completion and host reuse
are all null. This proves acknowledged retention of uncertainty, not zero
provider calls, zero cost, successful kernel admission or confirmed cleanup.
No old claim, output or other consumed artifact was read, changed or adopted.

### Bounded visibility correction

The [accepted private-receipt record][private-proof] preserves the earlier
source trace. The historical controller discarded its exception data and
retention discarded its generic failure receipt. The first throw, model-call
count and cost cannot be recovered. No deterministic production mismatch,
kernel, quota or model cause was established, and this patch does not invent one.

Production changes are confined to `batch-runner/gpt54_time_budget_v2_ci.py`.
The controller uses the current failure object in memory, validates it with
the existing exact receipt schema and emits exactly four fields:

```json
{"category":"unexpected_error","format":"gpt54-time-budget-first-v2-ci-failure-v1","reason":"execution_refused_or_uncertain","stage":"observation_callable"}
```

This is the event verified for a synthetic construction error, not an event
recovered from the historical run. `stage`, `category` and `reason` use the
unchanged static code/class allowlists. The stage names an entered controller
boundary, not an internal traceback or inferred admission/model/cleanup fact.
The event is diagnostic data, never a study row or execution authority.

Emission is attempted only after this invocation acknowledges its own execution
reservation and successfully writes the failure receipt. The execute path does
not read, annotate or print a prior partial receipt. Absent or malformed metadata
produces no event. Pre-reservation failure, lost reservation acknowledgement or
failed receipt I/O can still leave no diagnostic. A failed stderr write is not
retried and cannot change a refusal into success. Receipt-writing failures after
a returned outcome retain their existing uncertainty limits; no new metadata is
invented for that path. No deadline or cleanup allowance is extended.

The existing private manifest retains the validated receipt independently of
stderr availability. Generic CLI stdout stays `{"outcome":"refused_or_uncertain"}`
with exit 2. Public completion and canonical result schemas are unchanged.
No raw exception, traceback, dynamic type name, provider message, filename,
token, header or body is formatted or emitted. No new service, workflow,
permission, provider, source-pin sweep, manifest, core, F or grading-policy
change was made.
Existing source/input/direction/CAS/host guards, one attempt, concurrency 1,
GPT-5.4/direct-v1/xhigh, the fixed 20-observation study, 1200-second generation,
shared 20-second cleanup and 45-minute job ceiling remain unchanged. Receipt
metadata does not restart or extend cleanup. The ceiling is not a money cap.

### Pinned implementation and one offline event proof

- Tested HEAD: `2bd14c256992d7a47e4f297f81fa28a729b05755`.
- Tested tree: `5b77ac3550461e8331bd3de8854b98abc99513d2`.
- Implementation delta from reviewed `b98fc7e5eca79d55a4925ff1aa6bd78463e25814`:
  controller and test module only, 173 insertions and 2 deletions.
- Selector: `tests/test_time_budget_first_v2_ci.py::test_time_budget_first_v2_ci_failure_stderr_event`.
- Python 3.10.12, one offline invocation bounded by 300 seconds plus 5 seconds
  termination grace, no `-x`: **8 passed in 162.87s**, exit 0. No old five-case,
  layout, platform, study or whole-suite selector was rerun.

The eight new cases were `allowlisted_refusal`, `secret_exception`,
`missing_metadata`, `malformed_metadata`, `prior_partial`, `reservation_io`,
`receipt_io` and `stderr_io`. Full routes use actual temporary Git/linked R/F,
source/request/input/direction validation, synthetic originals, the existing
controlled kernel fixture, and ordinary construction, file-I/O, stderr and
private-storage transport seams. The malformed/absent metadata cases call the
real event/schema helper. No successful validator verdict is substituted;
socket and external-effect sentinels remain enabled.

The proof checks the exact event shape and static refusal code, a secret-bearing
exception whose text must never be formatted, no event from prior/partial or
unavailable metadata, and one failed stderr write without a retry. Duplicate
synthetic execution refuses without reading or modifying the earlier receipt
or permanent claim. Private retention acknowledges uncertainty through real
CAS/readback validators on the synthetic transport, with an exact unchanged
completion envelope and no result or deliverable fabrication. This is not real
host, original-input, provider or private-publication evidence.

Artifacts remain at `/tmp/pr759-v2-failure-event-proof.UREWou/`.
`command.sh` contains the complete invocation and exact clean HEAD/tree guards;
its digest is not a hash of shortened or redacted command text.

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| `command.sh` | 1333 | `7f3aea8af6a147116c0177e5ccac5ce4d1cc4647641b163204b48501b5f24601` |
| `pytest.log` | 1468 | `fc6c80f9ac2508ecbfde18496bdbb9f782ca96a8b1a62bcaf648c6e8405429f0` |
| `junit.xml` | 1871 | `ee8d2019b599ae990ff3fad00c9fd48b8360701f3222cb5ad20b058a634016a8` |
| `exit.txt` | 14 | `a589fb135cc49e1dd1462a45e1394bfa71fa20ffca282d444ae7f7d857ad39a3` |

### Separate prior evidence and remaining gates

The [accepted private-receipt record][private-proof] preserves its separate
five-case result, original command and artifact hashes. Its tested HEAD was
`1b21fe4d635b5d3934cfcd06699f6ca9c7c725ca`, tree
`6b2b049ef9551766b00876fa59d37dedfcbc23e1`: **5 passed in 95.25s**, exit 0.
Its record-bearing reviewed HEAD was
`b98fc7e5eca79d55a4925ff1aa6bd78463e25814`, tree
`065c50a6be73db07fdca2464a28307ca9dc93f98`. That result was not rerun or
combined with the new public-event proof.

The [prior source/evidence record][prior] preserves the real metadata
observation and earlier software proofs through immutable links. The original
14-pass/11-fail/11-teardown-error invocation, separate 10-pass/1-fail continuation,
1-pass missing-usage proof, 6-pass/1-fail layout proof and isolated 1-pass CLI
proof retain their original scopes and outcomes. Earlier grading, ownership
and CI host evidence remain linked there; none is blended with this new
eight-case proof or the actual uncertain attempt. No aggregate pass result is
claimed.

The exact post-proof repository delta is only `CHANGELOG.md`, this LATEST
record and the directly related usage passages in `batch-runner/README.md`.
Controller and test bytes remain identical to the tested implementation.
The final record-bearing HEAD/tree are reported in the task handoff after
committing these records. Retained source/CI guidance and a bounded
`im-not-ai-en` changed-passage check preserve exact evidence, scope and
uncertainty; no new study design or reviewer-harness attempt was needed.

Final-HEAD review and ordinary CI remain pending. The first cell stays consumed
and uncertain; this patch neither repairs historical remote evidence nor grants
replay, resume, regrade, alternate-destination adoption or another cell. The
leader owns any future live decision and its independent source/host/input and
direction bindings. No valid canonical result is reported for this attempt, and
the private uncertainty output is not an inference-publication/intake locator
for grading. Do not invent `source_repo_id` or `source_revision`. A genuine
result/input/deliverable association and independent live grading direction
remain required for any later grading route.

No CI query/dispatch/retry/poll, Azure management, credential search, private
HF/input/result read or write, model/grader operation, Project edit or merge
was performed in this task.

[live-run]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37456739936/attempts/1
[private-proof]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/b98fc7e5eca79d55a4925ff1aa6bd78463e25814/tasks/LATEST_TASK_RESULT/README.md
[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/7f4daa09944f6d9635e9bff3d945c224cfc76392/tasks/LATEST_TASK_RESULT/README.md
