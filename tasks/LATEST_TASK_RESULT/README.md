# Latest task result

## Two voice cases pass after the duplicate-guard test correction

The test-only continuation reported **2 passed in 10.64s**, exit 0, wrapper
**11.238067s**. Each case now verifies two separate refusals: the original
destination raises `result_destination_exists`; changing only the destination
to an unused sibling reaches `direction_observation_already_consumed`.
After each refusal, effects, permanent consumed/claimed bytes and original
result/deliverable bytes are unchanged. The alternate destination and its
reservation remain absent. No production guard or independently issued
direction was changed.

The preceding combined invocation remains **2 failed, 5 passed in 13.79s**,
exit 1, wrapper **14.574513s**, not seven passes. Its four historical-R cases
and workflow check were not repeated. The base reproduction and preparation
failure also remain separate observations below; none establishes Task3's
historical first error.

### Exact source and authority

This continuation began in the clean existing PR765 worktree at leader-reviewed
`67602c50fd1add61956bd767d0f568ae072df0bd`, tree
`5bb1a3f3191d15ec42c7a6eb3e6ef50402a6d0f4`. The leader inspected the two-pin
delta, historical-R loader and bounds, coupled tests and record, and identified
no additional blocking source issue in that scope. The authorization here was
only to correct the duplicate test and rerun its two voice cases once.
The accepted-main basis remains
`d7aad7abc1e1626e72178f9e8d85090a63825cd2`, tree
`749155e1f967699036f887bbf58a6bddbde2aa0c`; no new origin/main check or branch
integration was performed.

The earlier source-binding decision followed inspection of
`93c5cbb931ea0a3db1cb63f9bd0e89bea72132a1`, tree
`ee85d1c5771012fec362823da61268997df2f53e`. The leader verified compiler blob
`f6fe26b40310f3ca72347a6133abe43316de97f2` and authorized the two prospective
runtime bindings plus historical-readout compatibility. This is runtime
provenance, not a new study condition or live authority. The required reviewer
invocation failed before execution on the unavailable legacy Opus preference;
no successful spawned review is claimed and no new harness invocation occurred.

Tested correction `be92f1f399934ece7ba4aee3887d4d7fe052139a`, tree
`94124a3a8a42af45e3c8f3a6be0ade3944378581`, changes only the duplicate
section of `tests/test_time_budget_v2_returned_result_boundary.py`: 24 added
lines and 3 removed lines. All preceding typed-replay, success/failure,
forged-receipt, cleanup and one-claim assertions remain byte-identical, as
does the final safe receipt writer. Production, compiler, registration,
readout helper and workflow bytes are unchanged from the reviewed source.
Only CHANGELOG, this record and the direct README evidence paragraph change
after this proof. Exact final HEAD/tree and PR identity are recorded in
`/tmp/pr765-duplicate-guards-proof.sHfFVypx/handoff.json`.

### One two-node continuation

From `batch-runner`, the wrapper ran exactly:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout \
  'tests/test_time_budget_v2_returned_result_boundary.py::test_time_budget_v2_real_voice_returned_result[finalize]' \
  'tests/test_time_budget_v2_returned_result_boundary.py::test_time_budget_v2_real_voice_returned_result[refused_finalize]' \
  -m 'not integration' --tb=short -ra \
  --basetemp=/tmp/pr765-duplicate-guards-proof.sHfFVypx/pytest-tmp \
  --junitxml=/tmp/pr765-duplicate-guards-proof.sHfFVypx/junit.xml
```

The two cases use the real typed `AzureFoundryVoice`, consumer, runner,
backend, source/input/direction validators and canonical capture, with the
existing synthetic transport and kernel fixtures. The valid `workspace_apply`
and `finalize` sequence produces canonical success. The controlled finalize
refusal preserves its verified `artifact_not_openable` code through capture;
it remains an error with no deliverables. Forged-audit and forged-success
receipts remain rejected. Neither outcome is a historical Task3 diagnosis.

Each duplicate call checks an exact, separately anchored refusal code. The
second call changes only `destination`; it keeps the same direction,
preparation, observation identity and store. After each refusal the test
compares provider/admission/runner/typed-response/capture effects, requires
the original single claim, compares permanent consumed/claimed bytes and
the complete original result/deliverable file inventory and bytes, and
checks absence of the alternate destination and reservation. The existing
network/credential/native/grading sentinels remain active. Both final
`safe-boundary.json` receipts were reached.

Python 3.10.12, pytest 9.1.1, pytest-timeout 2.4.0 and OpenAI SDK 2.46.0 were
used under one 300-second outer bound plus 5-second grace, no `-x`, Python
timing and the unchanged 30-second fixture Git bounds. The existing named
Git/Bash fixture allowances were reused without a new audit hook. No real-host
kernel probe, model/provider call, private read, old selector or full suite ran; the
synthetic kernel is not evidence of NAS or Actions host readiness. There
was no repeat or post-outcome test/code change.

Artifacts are in `/tmp/pr765-duplicate-guards-proof.sHfFVypx/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `2c59a49ded9852cd5b00136f7f10a86f0791c7a79ca0b27497e7de125c3cdbc3` |
| `command.json` | `c1703355b9a5ae662a10606195138dd16f2d406aae6ef446e7f1a6b2524940e9` |
| `source.json` | `81afb6076f401585e71c6f44f06b075d398d2b7cb2ad2e7631339eb95fb4d39b` |
| `pytest.log` | `e1b3e62c650976c4fe0a4f4b6fc7720fbfd9b1ef2a0653fc4e9e3b256ba93eba` |
| `junit.xml` | `29d45d3b7120e3882f16a73623a8136497bca4f99d42d093dd2ed3ce9e17fe79` |
| `outcome.json` | `564b8236216540dd726d40233a31a06525bf4ca482c3624159c12dde7dfbc4d6` |
| `pytest-tmp/test_time_budget_v2_real_voice0/safe-boundary.json` (`finalize`) | `674128fb465bfe094c655c9090b6ff5d62379dafc7ec1690ede40c8eb8c6e81c` |
| `pytest-tmp/test_time_budget_v2_real_voice1/safe-boundary.json` (`refused_finalize`) | `15a5216a089db571bbf2965bac0d35a8c7829902c19029bdce2c0852302acd2a` |

### Prospective registration and historical R

The earlier continuation advanced only `source_basis.registration_compiler.sha256`
and `source_pins["batch-runner/gpt54_time_budget_comparison.py"]` from
`2766e58f769e2bf617c26c15cc124329c8c9bd5f17bf03fb88a3066f78140f96` to
`f4e41540a089e4ed164063bec60ce124a901eb5195065e456502e902814cd3a2`.
Its bounded wrapper verified exact byte replacement and parsed-YAML identity
for every other field. The resulting full seals are:

| Registration | Full seal |
| --- | --- |
| Historical observations, unchanged | `f3337bd80a168cf42b37314b425f5f5b221049fa87c1c15e2338de3441e0ae05` |
| New prospective registration | `3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f` |

The new registration file SHA256 is
`e1d16d350aeb21af34104cede0d3acc0f6dc8db134338708e70168fbd9642699`.
Frozen F `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`, TEMPLATE
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`, and
the old local-source profile and its 37 pins remain unchanged. No observation
or consumed receipt is relabeled with the new seal.

Readout first validates C's existing source/workflow/bootstrap context and the
independently supplied completion envelope. It verifies the envelope's exact
R commit/tree with the existing local read-only Git guards, reads only the
constant `REGISTRATION_PATH` blob within the existing manifest-size bound,
applies the existing duplicate-key rejecting YAML loader, and compares the
trusted request seal to that R plan.
Selection and result validation use R's plan. Missing R or a mismatched
tree/blob/seal refuses before the credentialed read step; there is no fallback
to C, legacy-seal allowlist, historical checkout or old-code execution.

The workflow's only change is checkout `fetch-depth: 1` to `0`, making the
historical objects available while keeping the reviewed C checkout and linked
source layout. Parsed YAML and exact bytes confirm that single workflow delta.
Permissions, credentials, steps, timeouts, canonical-result/fingerprint checks
and the two-GET/60-second private projection contract are unchanged.

### Prior combined continuation (failed, not repeated)

Tested continuation `e3ad928bf02b99e080a6a5924a4ebda75b156adf`, tree
`fe3d097ca4d6632478494e67d57f0f9be48e52b8`, changed only the prospective
registration, readout helper, readout checkout depth and coupled readout tests.
The consumer correction and then-188-line voice test were unchanged. Its
record-only completion was `67602c50fd1add61956bd767d0f568ae072df0bd`, tree
`5bb1a3f3191d15ec42c7a6eb3e6ef50402a6d0f4`, with final identities retained
in `/tmp/pr765-registration-readout-proof.HFBa6hyS/handoff.json`.
From `batch-runner`, that bounded wrapper ran exactly:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout \
  'tests/test_time_budget_v2_returned_result_boundary.py::test_time_budget_v2_real_voice_returned_result[finalize]' \
  'tests/test_time_budget_v2_returned_result_boundary.py::test_time_budget_v2_real_voice_returned_result[refused_finalize]' \
  tests/test_time_budget_result_readout.py::test_time_budget_result_readout_historical_registration \
  tests/test_time_budget_result_readout.py::test_time_budget_result_readout_workflow_binding \
  -m 'not integration' --tb=short -ra \
  --basetemp=/tmp/pr765-registration-readout-proof.HFBa6hyS/pytest-tmp \
  --junitxml=/tmp/pr765-registration-readout-proof.HFBa6hyS/junit.xml
```

The four compatibility cases cover a historical R whose registration differs
from C only in legitimate compiler/runtime bindings, wrong R tree, a trusted
request incorrectly supplying C's seal, and missing R. They use real
source/request/canonical-result validators and the existing synthetic HTTP
transport. The positive read keeps the exact result identity/fingerprint and
safe projection; the three refusals occur before `_read_result`, with zero
credential-step entries, HTTP calls or public artifact writes. The workflow
case parses the real command and reaches request validation and Bash guards.

Both real-voice cases reached line 175 of the unchanged test. Before that
point, their real typed `workspace_apply`/`finalize`, faithful replay,
canonical success or verified `artifact_not_openable` capture, provenance,
cleanup and one-claim assertions had completed. The duplicate call then
raised `FirstV2ObservationRefused("result_destination_exists")`, not the
expected `direction_observation_already_consumed`. The first actual refusing
operation is `run_first_v2_observation` → `absent(before_generation=True)` →
the existing destination/reservation existence guard at
`gpt54_time_budget_v2_observation.py:384`, before its consumed-state guard.
The post-refusal effects/byte assertions at test lines 177–179 and the final
`safe-boundary.json` write were not reached. No complete duplicate-preservation
proof is claimed. The full invocation remains failed; there was no retry,
assertion relaxation or speculative production edit.

Python was 3.10.12, pytest 9.1.1, pytest-timeout 2.4.0, OpenAI SDK 2.46.0 and
PyYAML 6.0.3. One 300-second outer bound plus 5-second grace, no `-x`, Python
timing and the existing 30-second fixture Git bounds were preserved. Kernel
state in the voice cases is explicitly synthetic, not a NAS/Actions host proof.
No base reproduction, old 21/3 selector, full suite or real kernel probe ran.

Artifacts are in `/tmp/pr765-registration-readout-proof.HFBa6hyS/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `9624bd41bf168d09782450cdf0d06e442f8dcdd3c60f650ad3b8008209766966` |
| `command.json` | `91b512c1bf2488daacd88d34b5a6014a2c49e48f7b4e6bddb4df817f0a2dc66c` |
| `source.json` | `7c90c17814dd0205af27fe22b5a011e29b45a5b4f25ae007fd248633a6ca0756` |
| `pytest.log` | `374b5eb1eb80b05a2cc9745164e5c3ec3e320e3c22f54978bb35e5b9e3fe8da6` |
| `junit.xml` | `bd6ab8d4b74e529ddc864d454c18c7ca3b3e961074eeffe555972d92d0174550` |
| `outcome.json` | `3e0f4d826660471af5f601995c27cbde14947eb59284d6f6ed5b5fe8c14db44e` |
| `first-failure.json` | `350d87f2fea3f440af8a18b07df62a2cd29fe8a03fa10b145bc5d0d3fbdb8cfa` |

### Leader-verified actual Task3 readout

Readout run `37546159098`, attempt 1, succeeded. Artifact `11450457583`
contains a 2597-byte projection, SHA256
`53570348019f1fcfcdccbfb11beb63470b495223b6e23366db60ca54fe666331`;
ZIP SHA256 is
`c989af75b4588d38f519ea35c1c2b1b5a4208eab7b7077c2745989fd29cc19a1`.
These are leader-supplied verified facts, not a read repeated in this task.

For that real readout, controller C was the accepted main above. Original
result R remains
`f2eaccf1b3973a6fc683f169b38f6caddb5a1953`, tree
`72a9d2fa2c22b1409a8b19e01d6a24ac5f29f9cf`, for
`gpt54_time_budget_v1_v2_r1` / `sandbox_v2` / repeat 1 /
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d`. The readout matched:

| Original binding | Verified value |
| --- | --- |
| Execution request SHA256 | `6748374c1b4ad0bbcbafb47117c6c641976d85ece836486eb8ce553c65719c1a` |
| Output commit | `2460c45c3896371b011624f13fc7817d5f670969` |
| Result byte identity | 6632 bytes / `a2f21666eb53542ead8b780404fd241056d3cc129167f6e7b1be36c6b64160f7` |
| Result fingerprint | `0374270431f6352211715da432d886f8557514324c89d60c230f81f65a2a5b61` |

The safe projection reports `status: error`,
`error: time_budget_observation_non_success`, `runner_success: false`,
`runner_result_verified: false`, `runner_error: null` and
`required_deliverable_missing: true`. Deliverable count and bytes are both
0. Control reports admitted true, terminal `failed`, cleanup complete true,
cleanup expired false, owned processes stopped true, host reusable true and
interruption attempted false.

Reported usage is complete: 2913 input and 326 output tokens. Cached input
0 and reasoning output 302 are subsets, not additional tokens. Client
construction attempts, Responses create invocations and completed responses
are each 1; response model binding is `matched`. Native model attempts,
repeated-request count and written tokens remain null; money hard cap is
false. This excludes a missing response or model-binding mismatch in that
retained invocation. It does not establish price, score, native model-call
count or every possible historical cause. No raw model/tool reply or raw
exception survives in the projection, so Task3's first error is not recovered.

### Separate prior base-source reproduction

One bounded temporary reproduction ran against clean accepted main, using
real `AzureFoundryVoice`, typed SDK `Response` / `ResponseFunctionToolCall`,
the actual consumer, runner, backend and capture. Existing synthetic source,
input and direction fixtures kept the real validators. Only Responses and
credential transport seams were synthetic; the existing local kernel fixture
was explicitly synthetic, not a new host proof. No model, real auth, private
input, network or grading operation occurred.

The valid case made a declared `workspace_apply` write followed by `finalize`.
It verified exact call arguments, call/output pairing and actual backend data
in the second request's faithful replay, then canonical success. The controlled
refusal case asked `finalize` for a missing synthetic artifact. The real runner
returned a valid `artifact_not_openable` failure receipt. The consumer changed
its error to control reason `failed`; the unchanged failure verifier rejected
that receipt, and capture emitted the generic unverified error row.

This identifies the first demonstrated information-loss operation, not
Task3's underlying failure. In particular, it does not establish that Task3
asked for a missing artifact. The normal typed response/replay path was valid
in this reproduction.

Pytest reported **2 passed in 14.34s**, exit 0; wrapper **14.933481s**. Those
assertions deliberately confirm the base-source defect as well as success;
they are not a corrected-source pass. Artifacts are under
`/tmp/v2-real-voice-boundary-repro.nWLuBtNR/`:

| Artifact | SHA256 |
| --- | --- |
| `test_reproduction.py` | `eefc56e955fadf41d25e8346ad77a409096b087910407c693ff8ac141f0325b8` |
| `run-reproduction.py` | `37c09d98a06d3544f589e8524c08e70e60c8e9812608a75fcb1e7050d1800304` |
| `command.json` | `1f6511ed75d6e2f99ed1aa246d030024e598b3e6545406fd62b2ab07c0471014` |
| `source.json` | `970a3484dcbfdee5918c60a6af871dab2293adf8ef1f3e2517d725a96bd88e95` |
| `pytest.log` | `2eec46a7710252e8abdf9eb401aa5daee5dea0ba8fe7e7492143205179c94c36` |
| `junit.xml` | `7f5894fc7241a6e9315f65e4e890e81054021d96f79e53aae6653f9cb77ffc96` |
| `outcome.json` | `b5cd69d492a7721f3c4bd4a13a14e90c079f551f7cd9fbadbe887b4879096a8c` |
| `finalize.json` | `cde5a33bcfe70a1ee0e710ca59479d98593fb7e8b38d3ef9878ce3a3455e5774` |
| `refused_finalize.json` | `a3e0c4842906af50b701e9d9d3d4801415f92ced407f1873496ae6649f20069c` |

### Separate prior source-pin failure

The unchanged consumer correction keeps the original code only when the
existing
`verify_agentic_v2_failure_result` accepts the complete V2 receipt, terminal
reason is `failed` and cleanup is complete. It never sets success true.
Timeout, unconfirmed cleanup, invalid receipts and native results keep the
previous control override. Core provenance/capture validators are unchanged.
That earlier invocation did not reach the malformed-audit/success-flag or
duplicate-refusal assertions. Its tested source was
`7e6e441fa64dcca804b23383b43bd90830844247`, tree
`12117a30c37d53a38c7cf407f1fc60b8e27f4b4b`.

From `batch-runner`, that earlier correction selector was:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout \
  tests/test_time_budget_v2_returned_result_boundary.py::test_time_budget_v2_real_voice_returned_result \
  -m 'not integration' --tb=short -ra \
  --basetemp=/tmp/v2-real-voice-boundary-proof.TnBlJliY/pytest-tmp \
  --junitxml=/tmp/v2-real-voice-boundary-proof.TnBlJliY/junit.xml
```

It reported **2 failed in 6.35s**, exit 1; wrapper **6.956347s**. The first
failure arose during `_case` → `prepare_observation_handoff` → `_compile_registration`
→ `_dual_root_sources` → `_expect("runtime_source_roles", ...)`. Both cases
refused before admission, Responses, the proposed correction or capture.
At that tested source the registration still pinned compiler SHA256
`2766e58f769e2bf617c26c15cc124329c8c9bd5f17bf03fb88a3066f78140f96`,
while the tested compiler bytes hash to
`f4e41540a089e4ed164063bec60ce124a901eb5195065e456502e902814cd3a2`.
This is a source-binding failure, not a behavioral pass, provider failure or
supported-host refusal. At that stage the guard, registration, assertions and
bounds were left intact; no repeat or untested follow-up code edit was made.

Those two prior invocations used Python 3.10.12, OpenAI SDK 2.46.0, pytest
9.1.1 and pytest-timeout 2.4.0. Each had one 300-second outer bound plus 5 seconds grace,
no `-x`, Python timing and unchanged 30-second fixture Git bounds. No old
selector, whole suite, kernel probe or CI query was run. Failed-proof
artifacts are under `/tmp/v2-real-voice-boundary-proof.TnBlJliY/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `5ca07213289b94d8db554fcc7bd101586630632fcd219ead801491764d378891` |
| `command.json` | `50a881359267a9b4252af9f6bc109f90a7cad523800c1e1a43f3a67de47625e2` |
| `source.json` | `031b3e7f6fb917bc17d3e480952e78eb4894f9c95f9d9833d3ac98a5868ca74d` |
| `pytest.log` | `32482584c0b156772222d8c7e0f74a29fb916a8250b7ccc7a4619a17ea86eeb2` |
| `junit.xml` | `d8a32793dac515371e1d57031440deeded93c854160b61fb7968b7cb34c6b05e` |
| `outcome.json` | `94d15260e9cb41a3acf0d2896c9396200b9dfcc2091e973b3a825bf1bd7b204d` |

### Remaining gates and preserved state

The source-pin blocker was resolved under the explicit prospective-binding
decision. This authorized test-only continuation completes the two voice
cases, including both duplicate guards and byte-preservation assertions.
The prior combined invocation remains failed; its five passing cases are
not aggregated with this proof. Final review/CI and accepted-source delivery
remain gates. Genuine input/host/controller checks, a real readout request
and any future live request remain leader-owned; no live authority is issued
here. No CI query, dispatch, retry or poll was performed.

The twenty-cell study scope, model/prompt, V2 9-turn/8192 settings, 1200+20,
one attempt, frozen F and history are unchanged. The two prospective compiler
bindings and readout source/depth changes belong to the earlier continuation;
only the duplicate test section changed before this proof. No HF upload or
provider/runner core code changed. Task1/Task2 remain
consumed and uncertain; Task3 remains consumed with its immutable canonical error. No
result was adopted, mutated, replayed or relabeled as a zero score. PR764 at
`787ed5cfed40b8c7bd6d90e6760ba0ab8f912c97` and all preserved worktrees are
untouched. [The preceding failed-continuation record][continuation],
[earlier PR765 record][previous] and
[prior accepted-main record][prior] retain earlier evidence separately; no
aggregate pass claim or historical-error diagnosis is made.

[continuation]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/67602c50fd1add61956bd767d0f568ae072df0bd/tasks/LATEST_TASK_RESULT/README.md
[previous]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/93c5cbb931ea0a3db1cb63f9bd0e89bea72132a1/tasks/LATEST_TASK_RESULT/README.md
[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/d7aad7abc1e1626e72178f9e8d85090a63825cd2/tasks/LATEST_TASK_RESULT/README.md
