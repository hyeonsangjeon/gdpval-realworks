# Latest task result

## V2 failure-code loss reproduced; correction blocked by its source pin

The base-source reproduction confirmed a deterministic loss of a valid V2
failure code in the consumer. It also confirmed typed write/finalize success
and faithful second-request construction. The proposed correction has **no
behavioral pass**: its one selector reported **2 failed in 6.35s**, stopping
at the unchanged registration's compiler pin before either response path ran.
No retry or source-pin bypass followed. This candidate is not ready to run.

### Exact source and authority

Accepted main `d7aad7abc1e1626e72178f9e8d85090a63825cd2`, tree
`749155e1f967699036f887bbf58a6bddbde2aa0c`, was checked against origin/main
once before creating the independent worktree. The leader directed this
narrow returned-result investigation and conditional correction. That is not
acceptance of the new source or live authority. No unavailable reviewer
harness was invoked or claimed successful.

Tested correction `7e6e441fa64dcca804b23383b43bd90830844247`, tree
`12117a30c37d53a38c7cf407f1fc60b8e27f4b4b`, changes only
`batch-runner/gpt54_time_budget_comparison.py` and adds
`batch-runner/tests/test_time_budget_v2_returned_result_boundary.py`.
Only CHANGELOG, this record and direct V2 README usage change after the
failed selector. Exact final HEAD/tree and draft PR identity are in local
`/tmp/v2-real-voice-boundary-proof.TnBlJliY/handoff.json`.

### Leader-verified actual Task3 readout

Readout run `37546159098`, attempt 1, succeeded. Artifact `11450457583`
contains a 2597-byte projection, SHA256
`53570348019f1fcfcdccbfb11beb63470b495223b6e23366db60ca54fe666331`;
ZIP SHA256 is
`c989af75b4588d38f519ea35c1c2b1b5a4208eab7b7077c2745989fd29cc19a1`.
These are leader-supplied verified facts, not a read repeated in this task.

Controller C is the accepted main above. Original result R remains
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

### What the reproduction established

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

### Candidate correction and failed selector

The proposed consumer change keeps the original code only when the existing
`verify_agentic_v2_failure_result` accepts the complete V2 receipt, terminal
reason is `failed` and cleanup is complete. It never sets success true.
Timeout, unconfirmed cleanup, invalid receipts and native results keep the
previous control override. Core provenance/capture validators are unchanged.
The new test also asserts malformed-audit/success-flag rejection and permanent
duplicate refusal, but those assertions were not reached in this invocation.

From `batch-runner`, the only correction selector was:

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
The unchanged runtime registration pins compiler SHA256
`2766e58f769e2bf617c26c15cc124329c8c9bd5f17bf03fb88a3066f78140f96`,
while the tested compiler bytes hash to
`f4e41540a089e4ed164063bec60ce124a901eb5195065e456502e902814cd3a2`.
This is a source-binding failure, not a behavioral pass, provider failure or
supported-host refusal. The guard, registration, assertions and bounds were
left intact; no repeat or untested follow-up code edit was made.

Both invocations used Python 3.10.12, OpenAI SDK 2.46.0, pytest 9.1.1 and
pytest-timeout 2.4.0. Each had one 300-second outer bound plus 5 seconds grace,
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

Source-pin reconciliation is required before a corrected-source behavioral
proof, final review/CI and accepted-source delivery. No runtime source may be
treated as accepted merely because this change has a plausible local fix.
Genuine input/host/controller checks and any future live request remain
leader-owned; no live authority is issued here.

The twenty-cell registration, model/prompt, V2 9-turn/8192 settings, 1200+20,
one attempt, frozen F and history are unchanged. No workflow, HF upload,
provider/runner core or readout code changed. Task1/Task2 remain consumed and
uncertain; Task3 remains consumed with its immutable canonical error. No
result was adopted, mutated, replayed or relabeled as a zero score. PR764 at
`787ed5cfed40b8c7bd6d90e6760ba0ab8f912c97` and all preserved worktrees are
untouched. [The prior accepted-main record][prior] retains earlier proofs
separately; no aggregate pass claim is made.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/d7aad7abc1e1626e72178f9e8d85090a63825cd2/tasks/LATEST_TASK_RESULT/README.md
