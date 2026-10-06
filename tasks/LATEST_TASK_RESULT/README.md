# Latest task result

## Bounded readout of one retained canonical result

The new read-only helper and manual workflow passed their single offline
selector: **21 passed in 7.95s**, exit 0. The wrapper took **8.412420 seconds**.
This validates synthetic transport and result projection, not a private HF
read, a live readout, host admission, input verification or grading.

The fresh branch started from accepted main
`f2eaccf1b3973a6fc683f169b38f6caddb5a1953`, tree
`72a9d2fa2c22b1409a8b19e01d6a24ac5f29f9cf`; origin/main was verified once.
The leader performed the source-grounded read-only pre-edit readout/CI
decision. The mandatory reviewer invocation failed before execution on the
unavailable legacy Opus preference. It was not retried and is not a successful
spawned review. The implementation still needs its own final source review.
PR761 and all prior worktrees were left untouched.

### Implementation and evidence boundary

`batch-runner/gpt54_time_budget_result_readout.py` and
`.github/workflows/gpt54-time-budget-result-readout.yml` read one already
retained observation from the existing private target. Controller source C
is independently checked against its commit/tree, the ordinary Actions
bootstrap and a detached registered worktree at
`RUNNER_TEMP/time-budget-readout-source`. Original result source R is bound
by the leader's independently verified completion envelope inside the exact
digest-bound request; it is not replaced by C.

The request binds the owner, repository, workflow, main ref, readout run
number and attempt 1, source-verified registration, selected cell, original
execution request hash, immutable output commit, result size/hash and
fingerprint. Existing completion, observation, canonical-result and
fingerprint validators remain real. Only the current V2 capture schema is
supported; the selection must be a V2 row of the unchanged registration.
The original request hash and claim association come from the trusted
completion envelope. The result does not embed that request hash, and this
route does not download or independently reverify the original request or claim.

Only `contents: read` is granted. Only one bounded step receives the existing
Actions `HF_TOKEN`; setup, source checks and artifact verification do not.
Private-identity metadata at the requested output commit and one exact raw
Git-object GET share 60 cumulative seconds. There is no HEAD lookup, retry,
redirect, cache/LFS follow-up, unrelated listing or deliverable download.
An LFS pointer, inaccessible object, missing credential, byte/hash/fingerprint
disagreement or unsupported schema refuses explicitly. No private result is
written locally; only the validated safe projection becomes an artifact.

The projection contains existing static result/runner error enums, flags,
reported usage, typed availability counters and model-binding categories,
route fingerprint, and aggregate deliverable count/bytes. Deliverable totals
come from authenticated records, not a new check of deliverable bodies.
Private prose, filenames, raw exceptions, tokens, headers and full result JSON
are excluded. Unknown projected fields refuse; nothing passes through by
default. No served-model string, unavailable counter, invoice, grade or
model-call count is reconstructed. Neither the completion nor canonical
result schema changed. No observation, input, claim, core, grader, frozen F,
registration or existing workflow bytes changed.

### One offline proof

Tested implementation HEAD:
`2fa134ba2deeefe4cdc9e0098cb0c5117a6f51a5`

Tested tree:
`4be69ae48d1502e669c962110016ca0218e1e686`

The only test invocation, from `batch-runner`, was:

```bash
/ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p pytest_timeout \
  tests/test_time_budget_result_readout.py -m 'not integration' --tb=short -ra \
  --junitxml=/tmp/time-budget-result-readout.YTwR9r/junit.xml
```

The retained wrapper was invoked once with
`timeout --signal=TERM --kill-after=5s 300s`, without `-x`. It checked the
clean source/tree, exact three-file implementation scope and Python syntax
before the selector. Python was 3.10.12, pytest 9.1.1, pytest-timeout 2.4.0
and huggingface-hub 1.24.0. Temporary Git setup kept its 30-second bound.

The 21 cases exercised reported and unavailable usage, exact projection,
request/actor/source/task/attempt refusals, wrong bytes/canonical encoding/
fingerprint/result source/result task, added private fields, missing token,
nonprivate/wrong target, access and timeout refusal, the cumulative bound,
final source reread, no-clobber output and actual workflow/CLI binding.
The source fixtures used ordinary bootstrap checkouts and genuine detached
linked worktrees. Named sentinels allowed only validated local Git and the
workflow's exact credential-free Bash guard; they rejected network, HF writes,
admission, inference and grading. A secret-bearing transport exception was
not formatted. No prior selector, kernel probe or complete suite ran.

Artifacts are retained in `/tmp/time-budget-result-readout.YTwR9r/`:

| Artifact | SHA256 |
| --- | --- |
| `run-proof.py` | `d87bcca5af4b1e55c270e81253a076216b5846422c6a39a4ae9e1a68c5e2eda9` |
| `command.json` | `14cb573ae1b152106b0ec156eb00578127adbe20e531a2651fa5efe3f2a92a16` |
| `source.json` | `b18d600fde7034f394a9c3f4f2215ceab3b4cfb99adf7f16c8bd370a88414dd2` |
| `pytest.log` | `821675614ef942e47244da0c15f6683d4732e28546541f2f64c451f90536ee3d` |
| `junit.xml` | `7941e9ca1aff36a4296b4b36610f3ebc391cffe656fc0bafe2deb415b0053775` |
| `outcome.json` | `e2549bf96dbffabdc2d0bcd1f6119c42a176f54dcd7cb599a6e7d72acfa99090` |

### Actual Task3 outcome, supplied by the leader

The leader verified [run `37524773961`, job `112478881979`][task3], run number
3, attempt 1, at R `f2eaccf1b3973a6fc683f169b38f6caddb5a1953`, tree
`72a9d2fa2c22b1409a8b19e01d6a24ac5f29f9cf`. Input/preparation, permanent
claim and login succeeded. Execution ran from 20:15:44 to 20:15:57Z and
returned 1; retention, envelope verification and artifact publication succeeded.

For `gpt54_time_budget_v1_v2_r1` / `sandbox_v2` / repeat 1 /
`2ea2e5b5-257f-42e6-a7dc-93763f28b19d`, the canonical result is `error` with
terminal reason `failed`, `cleanup_complete=true`, `host_reusable=true`,
reported `input_tokens=2913` and `output_tokens=326`, and acknowledged
retention. The completion records `retry_allowed=false`,
`grading_performed=false` and `other_cells_executed=0`. This is a canonical
ERROR result, not an uncertainty-only output. No bill, score or model-call
count is inferred. The private structured error fields have not been read
by this implementation task.

| Immutable evidence | Identity |
| --- | --- |
| Result byte size | `6632` |
| Result SHA256 | `a2f21666eb53542ead8b780404fd241056d3cc129167f6e7b1be36c6b64160f7` |
| Result fingerprint | `0374270431f6352211715da432d886f8557514324c89d60c230f81f65a2a5b61` |
| Output commit | `2460c45c3896371b011624f13fc7817d5f670969` |
| Permanent claim commit | `e5571e85eb10ed7450c4dda02b66363f7e5d0dc4` |
| Original request SHA256 | `6748374c1b4ad0bbcbafb47117c6c641976d85ece836486eb8ce553c65719c1a` |
| Completion artifact | `11441448261` |
| Artifact ZIP SHA256 | `59983e3c6a9a2e900653f0c8f0373400162d7126dce960884c850b3f78b8f4eb` |
| Envelope SHA256 | `200b555b8659b0e04ba7be6f722a2c7dd2e6a0f12bb05392c101b268de2a5648` |
| Log byte size | `186528` |
| Log SHA256 | `6c95b70770625435976c1cf1e2033401890187977c122150c39d68d6f97a41ba` |

Those are leader-supplied immutable observations, not new CI/private-storage
queries. Task1 and Task2 remain consumed/uncertain, and Task3 remains
consumed/error. None may be replayed, adopted, deleted, scored as zero or
removed from the planned denominator. The [prior accepted record][prior]
retains the earlier separate proofs, failed checks and immutable evidence.
Today's 21-case proof is not aggregated with any of them.

### Post-proof delta and remaining gates

After the proof, only `CHANGELOG.md`, this record and the directly related
`batch-runner/README.md` passages changed. The final documentary HEAD/tree
are recorded in the PR handoff and local
`/tmp/time-budget-result-readout.YTwR9r/handoff.json`; helper, workflow and
test bytes remain exactly those at the tested HEAD above.

Final source review, ordinary CI, delivery to accepted main, and a separately
issued immutable leader request for the real readout remain required. That
request must refresh C/tree and the actual readout run number; it must retain
Task3's independently verified R/cell/request/output/result identities.
No dispatch, private fetch, credential search, Azure operation, provider or
grader call was performed. A readout grants no input, grading or execution
authority. Any later intake or grading has its own source/input/publication
and frozen-F gates. No Task4 or Task1–3 replay is authorized here.

The unchanged study has 20 planned observations, the same five tasks and
ABBA order, GPT-5.4/direct-v1/xhigh, V2 nine-turn/8192-output settings,
concurrency 1, one external attempt, 1200 seconds of generation and shared
20-second cleanup. The observation workflow keeps its 45-minute ceiling;
the read-only workflow has a separate 10-minute setup/read/artifact ceiling.
Experiment-design was used only to preserve those boundaries. The English
report and copyediting checks preserve the distinction between live evidence,
synthetic proof, reported usage and unmeasured billing/quality.

[task3]: https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/37524773961/job/112478881979
[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/f2eaccf1b3973a6fc683f169b38f6caddb5a1953/tasks/LATEST_TASK_RESULT/README.md
