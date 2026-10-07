# Latest task result

## Native canonical readout fixture corrected; 18-node proof passed

The test-only continuation reported **18 passed in 7.20s**, exit 0; wrapper
**7.740273s**. It copies the real native template before the fixture seals
its synthetic source commits. Production code, workflows and all assertions
are unchanged. Fixed-HEAD review and final CI remain pending.

The original local invocation remains **18 failed, 2 passed in 4.52s**, exit 1;
wrapper **5.107217s**. The leader-read CI failure and the two prior compatibility
passes are separate evidence below. Those two passes were not rerun or combined
with this 18-node result. No live/private read or observation execution occurred.

### Scope and source identities

PR774 originated from accepted main
`33e24e9c1402ec0b7c92a71222998d1407646a92`, tree
`6e67da4e12169b41a837d92eaf946db15e71010e`; its original origin/main check matched.
The original tested implementation is `974f5f33713a17b7e9fa0de90f646cd59814139c`,
tree `b42b31e39599b4b81261aa2df56dab4c53a57baa`. Its helper/test implementation
and failed proof are retained in the original record and
`/tmp/native-canonical-readout.YqBcYa/handoff.json`.

This continuation uses the existing clean worktree at
`94368d8b16353758cfb7fa115d0f3459a1d3c47b`, tree
`8617a94b6d61055b9734e1295a6cedcffa00bfb7`. The test-only correction is pinned
and tested at `102dee649002366b3fa95b4ddccd81354f2e881c`, tree
`696f5c745a98663dfbd2c4fa7fcc9958dfdc617f`. Only this record, CHANGELOG and the
direct README evidence change after that invocation. The final HEAD/tree,
existing PR774 and unchanged tested blob identities are recorded after the
evidence commit in `/tmp/native-canonical-readout-fixture.5nJnSc/handoff.json`.
No new branch, worktree or main integration is part of this continuation.

The sole fixture change adds `subject.registration.CODEX_TEMPLATE` to its
copied-role set before creating either synthetic R or C commit. It copies
`batch-runner/experiments/exp033_codex_foundry_fixed5.yaml` from the reviewed
repository: blob `fd54aeb9305624ee480ca34c38ad6c2139c104ec`, SHA256
`5af7bd64ec00c6ac45c6d2a2f472833b90c4920221fd61dfdc9bbc324c745763`.
No template bytes were invented or injected after source sealing. Production
`SOURCE_ROLES`, validators and every existing test assertion remain unchanged.

The new explicit purpose is `read_one_retained_native_canonical_result`, with
request format `gpt54-time-budget-native-canonical-readout-request-v1` and
public format `gpt54-time-budget-native-canonical-readout-v1`. One trusted
success/error completion selects one registered native-r1 task. Controller C
is the readout source; R is the retained observation's source. Original R's
verified registration, native completion, canonical bytes/fingerprint, cell,
source, control and producer shape are checked without V2 runner aliases.
The helper validates native template and SDK/CLI bindings against R's plan.
It does not fetch deliverable contents, claim/request objects or grading inputs.

The public native shape preserves unknown usage, counters, served-model identity
and cost as null. Aggregate deliverable count/bytes are explicitly declared
from verified result metadata; contents were not fetched or verified. Only
allowlisted static native diagnostics, control and binding identities are
eligible for projection. Private prose, filenames/paths, raw errors, traces,
credentials/headers and unknown fields are not passed through. This is readout
validation, not a grader verdict, score or inference-publication association.

Existing V2 canonical and fixed-Task1 native uncertainty semantics remain.
Workflow bytes, inputs, permissions, secret step and timeout are unchanged,
as are historical R lookup, two GETs/60 cumulative seconds, identity encoding,
no retries/redirects/HEAD lookup and no HF writes. No compiler/registration pin
change is needed: the reader is bound through reviewed controller C's source
roles. Registration seal remains
`3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`.
Frozen F remains `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, TEMPLATE SHA256
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.

### Actual native Task3, verified by the leader

This is separate from the synthetic proof. The leader verified run
`37631184801`, run number 5, attempt 1, job `112825568457`, at the accepted
source/tree above, for `gpt54_time_budget_v1_codex_r1` / `codex` / repeat 1 /
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d`. All steps succeeded. Execute ran
13:49:12–13:54:09Z, **297 seconds for the workflow step**, not measured pure
generation or model time. Retention was acknowledged. Completion reports
status success, terminal completed, cleanup complete and host reusable true,
usage null, retry false, grading false and other cells 0. No failure event
was observed. Native model counters, cost and quality score are not established.

| Leader-supplied identity | Exact value |
| --- | --- |
| Claim commit | `08e485281f25ea06311305e7a4add721a68ba9ea` |
| Output commit | `d5aeecec1394fb44d4b1da33b1be38a39acdb89a` |
| Result | 8518 bytes; SHA256 `4ae3ea3d0dbe6ee540b86e3db17085e3a4d6f73afaf035c7f6f659f99b4601a4` |
| Result fingerprint | `4a62be1df3e21eae52bd7814359887c5f774200948ba67fc15ca62bf2f4b2967` |
| Execution request SHA256 | `3d2bbe5f55f0f0558f8e38bf53ebaa22f722b60b55b2338df465196b278ffc98` |
| Artifact | `11486512100`; ZIP SHA256 `39242db9f7ebdf05f232990159a090ccc960650e3a7403a58fc8861b88c819f7` |
| Completion | 1102 bytes; SHA256 `0f2f8fec804785518c236d334d501cb8a7f9e567814bda58cdf97678b152c702` |
| Log | 198873 bytes; SHA256 `006c6a3a11046153d8d0d6836de3813eec2e58b34bd895a1b5d5acb985ba13ef` |

These are independently supplied result/completion bindings, not hashes
derived here from a private download. The same supplied facts are retained in
`/tmp/native-canonical-readout.YqBcYa/leader-task3.json`. Native Task1/Task2
remain consumed uncertain; Task3 is consumed canonical success. None may be
replayed. Canonical success is not quality or evidence that the study is complete.
The [prior record][prior] retains the accepted Step0 correction, earlier failed
observations and pre-attempt direction; it is not rewritten as a Task3 outcome.

### Original local invocation (failed)

The original invocation selected only
`tests/test_time_budget_result_readout.py::test_time_budget_native_canonical_readout`,
once, using Python 3.10.12, pytest 9.1.1 and pytest-timeout 2.4.0,
an outer 300s TERM bound plus 5s KILL grace, no `-x`, and existing 30s Git
fixture bounds. Python `perf_counter` measured the wrapper; `/usr/bin/time`
was not used. AST checks confirmed the function accepts `scenario` and all
pre-existing test/fixture definitions were unchanged. Source syntax, clean
HEAD/tree and two-file scope checks passed before collection of 20 cases.

The first failed operation was `_native_capture_payload` calling
`Path.read_bytes()` on
`batch-runner/experiments/exp033_codex_foundry_fixed5.yaml` inside the synthetic
linked source. That file was absent from the fixture's copied source roles,
so it raised `FileNotFoundError` before calling the real native `_capture`.
All 18 native scenarios reached this same operation. This is a test-body
fixture failure, not zero-body collection failure or native validation refusal.

The failed scenarios were `native_success`, `native_error`, `cell`, `R`,
`digest`, `fingerprint`, `mode`, `unsafe_field`, `unsafe_error`,
`unsafe_diagnostics`, `counter`, `wrong_R_tree`, `registration`, `r2`,
`unregistered_task`, `cumulative_bound`, `gzip_metadata` and `gzip_result`.
Their intended native validations were unreached in that invocation. Only
`canonical_v2` and `fixed_uncertainty` passed through real request/source/schema/transport guards
with synthetic data. The overall invocation remains failed, not a 20-case pass.

The unchanged fixtures forbid actual network, HF writes, Azure/model/native
execution, kernel admission and grading, with only the existing named fixture
Git/Bash seams allowed. Synthetic Step0/direction/control declarations do not
verify private originals or runtime readiness. No old selector, full suite,
host probe, private read, provider/model/grader operation or consumed cell ran.

Artifacts remain under `/tmp/native-canonical-readout.YqBcYa/`:

| Artifact | SHA256 |
| --- | --- |
| `pytest.log` | `034e8a1996c7b0baa337e6f0b063db52ef2eb53406c36a25e37a993f51a68352` |
| `junit.xml` | `c5f784b4be84a01a17c21687fe98cc44d4ae9bc73c51fd872470ac7f30f4fb38` |
| `cases.json` | `c24dcec65afdf705b3cfab5d0623bafd8368dccb427f5dfc7aa6d54d9dd81927` |
| `outcome.json` | `02567677d221996e77ac77bad22e666b0a5ffa8ef45649e0bac019bc241f17a9` |
| `source.json` | `89273ea54e2558e5576c38b580d0e2c5e63e31048e23208665c5c692f2b95d40` |
| `command.json` | `78942edca00a7c133a52fd81d152e39b2613cdac21ea58f7a133afd799e2bbd5` |
| `run-proof.py` | `3bdee2808728850957e53a3bd7288bec6e0cb3172a84c7de006d81e3ddc541ff` |

`proof-hashes.sha256` inventories those immutable proof artifacts. The original
checkpoints, literal inventories, condition/claim ledger and handoff remain
untouched in that directory.

### Leader-read CI fixture failure (separate evidence)

Actual CI run `37639736598`, job `112855194221`, failed with the same 18
`FileNotFoundError` cases. The leader read its 143123-byte log, SHA256
`5fbbef1ed8c1fede56d41fd7c23344c4be036f7d181e5da246f88222d77030fb`.
The absent member was
`/runner-temp/time-budget-readout-source/batch-runner/experiments/exp033_codex_foundry_fixed5.yaml`.
It failed at the fixture's template read, before native capture/readout
validation. No CI query, download or retry was made in this continuation;
total CI counts and duration were not supplied and are not inferred.
`/tmp/native-canonical-readout-fixture.5nJnSc/leader-ci.json` preserves those
supplied facts. This CI failure is not relabeled by the local proof below.

### One bounded 18-node continuation

At the test-only commit above, exactly the 18 authorized full node IDs were
passed to pytest together once. Before launch, AST and argv checks confirmed
the `scenario` parameter, the 18 unique selections and the exclusion of
`canonical_v2` and `fixed_uncertainty`. The wrapper also verified the exact
one-line fixture delta, real template identity, clean source/tree and unchanged
production/workflow/registration bytes.

Every selected scenario passed: `native_success`, `native_error`, `cell`, `R`,
`digest`, `fingerprint`, `mode`, `unsafe_field`, `unsafe_error`,
`unsafe_diagnostics`, `counter`, `wrong_R_tree`, `registration`, `r2`,
`unregistered_task`, `cumulative_bound`, `gzip_metadata` and `gzip_result`.
Pytest reported **18 passed in 7.20s**, exit 0; Python `perf_counter` recorded
**7.740273s** for the wrapper. Python 3.10.12, pytest 9.1.1, pytest-timeout
2.4.0, 300s TERM plus 5s KILL grace, no `-x`, existing 30s Git bounds and the
named local Git/Bash allowances were retained. No other selector ran.

These cases exercise real capture/readout validators with synthetic data and
HTTP transport. The existing effect sentinels stayed in place. They are not
a private read, native execution, kernel/host positive, quality score or
grading-intake association. The two prior compatibility passes remain separate;
there is no aggregate 20-case pass claim.

New proof artifacts are in `/tmp/native-canonical-readout-fixture.5nJnSc/`:

| Artifact | SHA256 |
| --- | --- |
| `pytest.log` | `780ca975f5c319a0e88903a5dd5809024520e33a92ea1c589598c8545b859644` |
| `junit.xml` | `4c6ac2bc5575d8fdd6cd3836aa6c8efcbd39807abab421bd61419faa2f5bc9de` |
| `cases.json` | `76d4dbeb5f7396ed0421e6fa8333700a0bdddaf7283831bf4e8e6ebc44d64d59` |
| `outcome.json` | `05bdd6a04fbabfebdf1ebcb192b8bd97f0cf49c960b2269fda8889611bab6f30` |
| `source.json` | `d834e3888f4733f78e7ab05027c1c53572a2c291a8916c5ec8eb1fc3bda1656f` |
| `selection.json` | `1c092154c3262fc576e4f87648df4dd01e0b3b8dfdb3e87693209f62079c80af` |
| `command.json` | `1a009bf72d8229dd7b5e5d19e5943d7b55fc1bf28d6ccdf4067906f965f2f69f` |
| `run-proof.py` | `53d9c8f56307b4197c38f030e843a8ff412f9663eb5e4be623304c7b364f46bf` |

`proof-hashes.sha256` inventories the new proof. The bounded evidence checkpoints
and protection/change ledger are in `records/`. Final commit/tree and existing
PR774 are in the external handoff, avoiding a self-referential commit hash in
these committed records.

### Remaining gates

The fixture correction has the bounded local proof above; fixed-HEAD source
review and final CI remain gates. One real read requires an accepted controller
and an independently bound request under separate direction. Genuine retained
bytes and frozen F
must govern any later once-only grading intake; no publication/intake
association, score, exact native call count or cost is inferred here.

GPT-5.4/direct-v1/xhigh, null native context override, zero configured provider
request/stream retries, concurrency 1, one external attempt, 1200-second
generation, shared 20-second cleanup and the 45-minute job ceiling remain
fixed. None is a money cap or remote cancellation guarantee. All five V2 r1
cells and the consumed native cells remain immutable; no previous outcome is
relabeled as a quality score.

The catalog was read once. `experiment-design` preserves the existing
20-cell cohort/model/budget/F design; this is visibility only.
`experiment-report-en` and `im-not-ai-en` keep leader-supplied measurements,
the failed local and CI observations, prior compatibility passes, the new
18-node proof and unavailable quantities separate. No new reviewer
invocation or CI query is claimed. No Project edit, merge, manual dispatch,
retry, Azure/private-HF operation, readout execution, Task4 or ABBA advance
was performed or authorized. The helper and all production/workflow bytes
stay unchanged throughout this continuation; the corrected test stays unchanged
after its one invocation. Earlier worktrees remain untouched.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/33e24e9c1402ec0b7c92a71222998d1407646a92/tasks/LATEST_TASK_RESULT/README.md
