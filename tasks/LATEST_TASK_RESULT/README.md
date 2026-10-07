# Latest task result

## Read-only native uncertainty projection

The existing result reader now supports one explicit native uncertainty
manifest purpose. Its single offline selector reported **17 passed in 5.92s**,
exit 0, with a **6.351552-second** wrapper. It used real source, registration,
manifest and receipt validators with synthetic HTTP. No private object,
provider, model or grader was called. The actual native failure cause,
model-call count and cost remain unknown.

### Leader-verified consumed native observation

The leader supplied these facts; this implementation did not query CI or
private storage. Native run `37574558224`, run number 3, attempt 1, job
`112640438630` passed source/caller/linked R-F, dependencies, full request,
original inputs/full Step0, permanent claim, approved login and identity
checks. Execute ran `05:07:26..05:07:30Z`, returned 2 and printed only
`refused_or_uncertain`. Retention, envelope and artifact succeeded. No safe
native failure event was printed; the validated private execution receipt
was retained inside the output manifest.

The completion format is `gpt54-time-budget-first-codex-ci-completion-v1`.
Its cell is `gpt54_time_budget_v1_codex_r1` / `codex` / repeat 1 /
`02aa1805-c658-4069-8a6a-02dec146063a`; status is `uncertain` and retention
is `acknowledged`. Result identity/fingerprint, terminal reason, usage,
cleanup and host reuse are null. Retry and grading are false; other cells
executed are 0. Null usage does not establish zero model calls or cost.

| Leader-supplied binding or artifact | Exact identity |
| --- | --- |
| Permanent claim commit | `4ca4fd9c86fe1253059fffc66f6e4397c34c3c4e` |
| Acknowledged output commit | `d443e8045f58b6f7b4b35ed7f1888182b62296e0` |
| Original execution request | 2369 bytes; SHA256 `c78a581c482baf495b09efad70899e0067293752f3cc7320f54f2af0079fa062` |
| Host SHA256 | `37d71d11f30432cdd046980f111a7225202905becdba0891172d95988473dc79` |
| Completion artifact | `11461284645` |
| Artifact ZIP SHA256 | `61b911574cda4744ec3f65c839e54bf3901f01c57ad031f6a5a5db67a7f27c39` |
| Completion SHA256 | `bc2fdfce6279748e61a7a69dd3bde1d12e8869302d58b05f40948c001a0233e9` |
| Job log | 197979 bytes; SHA256 `ff4f6bd3d3682660e05e285407a1a335919197124111b36be03bce70a3fe618f` |

The five V2 r1 cells remain consumed: Task1/Task2 uncertain and
Task3/Task4/Task5 canonical errors. Native r1/Task1 is also consumed and must
never be replayed. These outcomes are not successes or zero quality scores.
The [prior accepted record][prior] preserves the earlier grading compatibility,
Task5 readout and input provenance. Its native authorization has already
been consumed and supplies no new permission.

### Trusted bindings and observed identity

The new request format is
`gpt54-time-budget-native-uncertainty-readout-request-v1`, with purpose
`read_one_retained_native_uncertainty_manifest`. Alongside the existing
controller/CI/cell/registration/completion fields, it requires independently
supplied `execution_request_identity` size/hash. The completion must be the
validated, acknowledged uncertainty for this one fixed native cell.

Controller C still requires exact source/workflow/bootstrap bindings. The
reader resolves the original registration only from the independently verified
completion's R commit/tree and constant registration blob, not C or the
downloaded object. R's full identity must come from that completion in the
later trusted request; this record does not substitute the implementation
base for R. Missing or conflicting R refuses before credentials.

At the trusted output commit, the reader derives the one manifest member
from `gpt54_time_budget_codex_ci.MANIFEST`. It checks exact producer format
`gpt54-time-budget-first-codex-private-output-v1`, canonical producer bytes,
observation/cell/R/registration, execution request identity and claim commit.
It requires the no-result/no-grade/empty-files shape and validates the receipt
with the existing private execution-failure schema. The claim identity is
checked for shape and bounds, not against a reread claim.

The public completion supplies **no independently expected manifest hash or
size**. Immutable output commit, fixed member and trusted known fields bind
the read. Any downloaded manifest size/hash is labeled
`observed_not_independently_expected`; the claim and original request objects
are `not_reread`. No result identity or fingerprint is fabricated.

The separate output format is
`gpt54-time-budget-native-uncertainty-readout-v1`. It projects only validated
static `stage`/`category`/`reason`, binding identities, observed manifest
identity and explicit absent/unavailable classifications. Raw error text,
class names, private prose, filenames, paths, headers, credentials and the
full manifest are excluded. Missing/malformed receipts, missing static
codes and extra private fields refuse with a null summary; they do not
become a successful diagnostic or a runtime cause.

The unchanged workflow retains its inputs, permissions, only secret-bearing
read step and timeout. Both GETs request identity encoding, with no redirects,
decompression or retries. At most private-identity metadata and one exact
raw Git object share 60 cumulative seconds. No HEAD lookup, HF write, OIDC,
claim acquisition, native execution, model call or grading is added. Existing
canonical V2 reads and their historical R registration checks remain intact.

### Pinned source and one offline proof

| Source role | Commit | Tree |
| --- | --- | --- |
| Accepted base | `b0bba8c71369605fd4261c59259e3cc3924de981` | `f9bb914a717d3fc1326ac8e1e925119cfaee307f` |
| Tested implementation | `ca8cacc0a7b9f9de1edd441bf0a337c1a9b5bee6` | `87f9f769addfaeb98019340bd3052414a99cdc71` |

Only `gpt54_time_budget_result_readout.py` and its focused test changed before
the proof. Their SHA256 values are, respectively,
`46e84a0c07b2ae06bfed3642ca32030af126a7519121110698ca803be4a5dfec` and
`b0277358a92bf6eaa4ee2f9b3fd8df16f910b1812a09a160e6f3233e9705a669`.
The unchanged readout workflow SHA256 is
`5dc57a9ccaeabc086e230df060b88e4fd23283e0d8b2e8d26bd498abeb66cfe6`.

The one invocation used offline Python 3.10.12, pytest 9.1.1,
pytest-timeout 2.4.0, 300s+5s, no `-x` and existing 30s Git bounds. Named
read-only fixture Git/Bash operations remained permitted. Timing used Python
`perf_counter`, not `/usr/bin/time`. From `batch-runner`, the command was:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout \
  tests/test_time_budget_result_readout.py::test_time_budget_native_uncertainty_readout \
  -m 'not integration' --tb=short -ra \
  --basetemp=/tmp/native-uncertainty-readout-proof.ygvebVCU/pytest-tmp \
  --junitxml=/tmp/native-uncertainty-readout-proof.ygvebVCU/junit.xml
```

The outer command was:

```bash
timeout --signal=TERM --kill-after=5s 300s \
  /ai-work/venvs/gdpval-realworks-py310/bin/python \
  /tmp/native-uncertainty-readout-proof.ygvebVCU/run-proof.py
```

All 17 cases passed: native uncertainty; wrong manifest source, cell,
registration, request hash, request size or claim; refused receipt, missing
receipt or missing static failure codes; extra manifest or failure fields;
wrong R tree or execution-request binding; noncanonical manifest encoding;
the cumulative bound; and one canonical V2 compatibility case. Write,
credential, native/model and unexpected-network effects were guarded.
The synthetic receipt's error category is test data, not the historical
native cause. No kernel-positive claim is made. No earlier selector or
suite was rerun; earlier proofs and failures remain separate.

Artifacts are in `/tmp/native-uncertainty-readout-proof.ygvebVCU/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `1db8e9eb855ce87172e36a38ce288c939ca705f7d2b27c070c0e2d1affdd6d13` |
| `command.json` | `da7095fe6ff782a51e24f1a9d31e97f3d093fcc940acb8bdac850c9e3c7b4c18` |
| `source.json` | `e3c36b279ea1da2f975f4c9fcb84ab18fa21028424c28285b2a27e23c614e0d0` |
| `pytest.log` | `581a5a06df26618e75983378cafe24225ea8cad1b2a71e216341a5c27aafbe70` |
| `junit.xml` | `764c4981c3133a06ee5cfd7d730db6311bea2f7a2bb067ce356f058bcdcfed1a` |
| `cases.json` | `81dd7050146fdfef970c35739491215cbe0c750c788ba54dbb28ecd310e45ff5` |
| `outcome.json` | `5487d25028e5bd14f67799a34615eeeb17f10c74d79099724f2022660db1df59` |

### Fixed study and remaining gates

Registration seal
`3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`, frozen F
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, F tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca` and TEMPLATE
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce` are unchanged.
The twenty planned observations, cohort/ABBA order, GPT-5.4/direct-v1/xhigh,
null native context override, zero provider request/stream retries, one
external attempt, concurrency 1, 1200-second generation, shared 20-second
cleanup and 45-minute job ceiling stay fixed. None is a money cap.

Only CHANGELOG, this record and direct README usage change after the proof.
Final commit/tree and draft PR are recorded after that documentation commit
in `/tmp/native-uncertainty-readout-proof.ygvebVCU/handoff.json`; they are not
future merge claims. Final source review, ordinary CI, accepted readout C and
one separately directed real read remain gates. No CI query/dispatch/retry,
private fetch or unavailable-reviewer loop was used. The actual native
receipt is still unread here. No replay, next cell, grade or live read is
authorized by this implementation.

The catalog and retained source/CI guidance were used once. `experiment-design`
held the existing study boundaries; `experiment-report-en` and `im-not-ai-en`
kept leader observations, synthetic evidence and unavailable facts separate.
No independent spawned review is claimed.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/b0bba8c71369605fd4261c59259e3cc3924de981/tasks/LATEST_TASK_RESULT/README.md
