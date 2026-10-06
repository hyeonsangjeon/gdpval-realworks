# Registered Codex time-budget observation callable

## Outcome and source basis

The new offline selector reported **9 passed in 22.91s**, exit 0. The callable
and CLI now connect one registered Codex handoff to the existing real consumer,
provider settings, runner and canonical result/deliverable capture. This is
implementation and synthetic verification only, not a live observation or
permission to execute one.

This independent branch started from accepted main
`86bf684706bdbfc641f10c2774b7e4884d8fc7cd`, tree
`0165ff4f9f7d226a4cac8f34803d6134f53ba693`. One ordinary fetch verified that
exact `origin/main` before creating the clean worktree. No previous worktree
was changed. PR760 source `ca84a224fe565d255194a33e1f2ea18340af70a7`, tree
`1cdfddb4b3335366e418d18a36fc3417a9076a42`, remains a separate leader-reviewed
candidate (review `5429965072`, conditional on final CI). Its source and pending
integration were not copied, stacked or queried. That review does not cover
this new callable; new-source review and final-HEAD CI remain pending.

## Implemented scope

`batch-runner/gpt54_time_budget_codex_observation.py` exposes
`run_codex_observation` and a CLI. One invocation selects one task from the five
already registered tasks in `gpt54_time_budget_v1_codex_r1` or
`gpt54_time_budget_v1_codex_r2`, with the matching repeat and `codex` condition.
`ObservationIdentity` and the verified registration enforce that selection.
The fixed 20-observation ABBA design, GPT-5.4/direct-v1/xhigh, null requested
context-window override, concurrency 1, one external attempt, 1200-second
generation and shared 20-second cleanup remain unchanged. A native turn is not
a model-call count, and the elapsed-time bound is not a money cap. Orchestrator
settings do not change the experimental model.

The caller supplies the expected direction digest, observation tuple,
preparation and Step0 digest/size, reviewed R commit/tree, F and input-source
anchors, host digest and canonical paths independently. The concrete direction
checker binds those values, resolved provider/config-override hashes and a
finite admission window. The actual Foundry account and direct-v1 route are
checked through the existing resolver. `CodexProviderSettings`, the pinned
0.147.0 SDK/runtime checks and isolated auth/environment remain on the real
runner path; no loopback provider, personal API key or fallback endpoint is
selected by production code.

Only `consume_observation_handoff` consumes the preparation and installs the
real `CodexAgentRunner` with the same `TimeBudgetObservation`. Its permanent
claim is keyed by the registered observation in the independently named local
store. A changed preparation or destination cannot authorize another attempt
there. This does not claim distributed/global once-only protection or permit
an operator to replace the store. No claim, partial output or cleanup state is
adopted or reset.

Capture writes the returned terminal Step2 row and its
fingerprint, exact deliverable records/bytes, preparation/source/input/config
bindings and actual deadline/cleanup record. The canonical JSON is written
last to a new destination, after held-directory and source/input/member
rereads. A returned failure can retain partial deliverables as an error row;
construction or interruption without a returned terminal record cannot
fabricate a row. Partial publication remains non-reusable.

The consumer does not export the runner's token-usage diagnostics. The row's
`usage`, native counters and cost therefore remain null, with an explicit
availability reason, even if an underlying native notification reported usage.
Returned safe item/status/rate-limit diagnostics are retained; raw provider
error text is not printed or copied into the row. No inference publication
`source_repo_id` or `source_revision` is invented. The callable neither uploads
nor grades.

V2, core runners, common registration/consumer, workflows, frozen F, templates,
historical profiles and launch guards are unchanged. F remains
`882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2`, tree
`45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca`; the whole original TEMPLATE hash
remains `37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
The original 30-cell pilot, eight retention observations and #649 stay closed.

## Exact proof

- Tested HEAD: `c6c8b2135f7e363d6c3371f023187641dbc0802f`.
- Tested tree: `4f14c866b6b05def538e05ca9296b75837e78e73`.
- Pinned implementation: the new callable and focused test module only,
  882 inserted lines; no existing production/test/workflow file changed.
- Selector: `tests/test_time_budget_codex_observation.py`.
- Python 3.10.12, one offline invocation, 300 seconds plus 5 seconds termination
  grace, no `-x`, unchanged 30-second temporary Git setup limits:
  **9 passed in 22.91s**, exit 0. No previous selector or suite was rerun.

The proof covers two synthetic successes (r1/task 1 and r2/task 2),
one returned native failure with retained partial bytes (r1/task 3), and six
refusals: wrong direction digest, stale window, direction-observation mismatch,
invalid/mismatched selection, Step0 digest mismatch and a different provider
account. One positive case reaches the actual CLI. Duplicate calls, including
a copied handoff and changed destination with a newly bound synthetic direction,
leave the permanent original observation claim and result bytes unchanged and
perform no second auth/native attempt.

The tests use real temporary Git and registered linked R/F, explicitly synthetic
parquet/references/Step0, actual source/registration/input/direction validators,
the real consumer/provider/runner and the installed SDK facade, typed RPC
responses and result collector. Ordinary auth-process and app-server I/O seams
return synthetic data. The existing controlled kernel fixture exercises local
ownership/cleanup semantics; it is not evidence of real host support. Network,
credential, external-process and grader sentinels remain enabled except for
read-only Git and the scripted auth transport. The SDK/CLI version guard runs,
but no native binary, actual auth request or provider is launched. The fixture's
token notification does not become available usage in the consumer envelope.

Artifacts remain at `/tmp/codex-time-budget-native-proof.0X57Ez/`.
`command.sh` contains the complete invocation and clean HEAD/tree guards.

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| `command.sh` | 1388 | `b57bc6472218fc519b55e7de04379479859d5fff83156853532544ced9671af0` |
| `pytest.log` | 1529 | `5edc111eebd46ff05e2c16758ff8e9b2e78c862abc0addb68bc833ecf63113d8` |
| `junit.xml` | 2065 | `c64b454b461e08c95b26bb3183c47d19a7df74e02f6c0657d987c31f36c48e94` |
| `exit.txt` | 14 | `a589fb135cc49e1dd1462a45e1394bfa71fa20ffca282d444ae7f7d857ad39a3` |

## Evidence boundaries and remaining gates

The [accepted diagnostic source record][diagnostics] retains the separate
**5 passed in 95.25s** private-receipt proof and **8 passed in 162.87s** event
proof, plus earlier evidence through immutable links. [PR760's record][pr760]
retains its separate **1 passed in 19.36s** and preceding failed and continuation
proofs. None was rerun or added to the new nine-case result.

The first real V2 observation, run `37456739936`, attempt 1, Task
`02aa1805-c658-4069-8a6a-02dec146063a`, remains permanently consumed/uncertain.
Its claim `e53fe8d4c47ef2a05aea8ffcc0fe1745a9b3c288` and private output
`f602355f945471963a338ccf79783a6f802ac6dd` remain untouched. Its first throw,
model-call count and cost cannot be recovered from the retained evidence or
inferred from this proof. It remains an uncertain planned cell, not a zero
score, excluded datum or retry opportunity.

After the proof, only `CHANGELOG.md`, this LATEST record and the directly
related `batch-runner/README.md` usage section changed. Callable and test bytes
remain exactly those tested. The final record-bearing HEAD/tree are supplied
in the handoff, without a claim about this PR's future merge. The catalog and
existing source guidance were checked once. `experiment-design` kept the
registered axes and denominator fixed; `im-not-ai-en` was applied only to changed
English records. No reviewer-model harness was invoked.

Remaining work is final-source review and ordinary CI; a trusted controller
that selects accepted R and issues an independent live direction; genuine
registered local originals/references/Step0 and preparation identities; the
approved auth/route values, canonical persistent store/native/output paths and
actual supported host. The existing direction window and digest must be issued
for those exact values. A live observation, later inference intake/publication
and separately authorized F-derived grading remain gates, not actions granted
by this implementation. No live Codex or Task2 direction is issued here.

No CI query/dispatch/retry/poll, private HF/input/result read or write, Azure
management, provider/model/grader operation, infrastructure change, Project
edit or merge was performed.

[diagnostics]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/86bf684706bdbfc641f10c2774b7e4884d8fc7cd/tasks/LATEST_TASK_RESULT/README.md
[pr760]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/ca84a224fe565d255194a33e1f2ea18340af70a7/tasks/LATEST_TASK_RESULT/README.md
