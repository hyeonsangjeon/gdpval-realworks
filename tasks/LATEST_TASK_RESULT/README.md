# Latest task result

## Direct-account pilot correction prepared for review

The direct-account correction has been placed on a dedicated review branch.
Its four production modules and new regression are byte-identical to the
previously tested isolated candidate. Local review found one coupled test
expectation to update: the current-source refusal list must include those four
changed modules. The exact-list assertion now does so, and both affected
variants passed. No historical source pin was changed to admit the candidate.

This is code integration and offline verification, not permission to launch
the Sol experiment. Fixed-HEAD CI and owner review remain required. No CI
success, independent review endorsement, runtime admission or live result is
claimed by this record.

### Source and scope

- Base HEAD: `6efe99cbd40bb839037e7a20711a734e0a4ce002`.
- Base tree: `4b80f235ab1627584e1a6c1f66849c3ead6b1a3d`.
- Locally reviewed and tested code HEAD: `6dab6b151b7b70127ab35a0e96b324bc6e005116`.
- Tested tree: `229b128b871c084314a78a9da6d6e5095cdb7ccd`.
- Branch: `codex/gpt56-direct-account-contract-20261022`.
- Worktree: `/ai-work/copilot/_tmp_worktrees/gdpval-realworks-direct-account-integration-20261022`.

The final delivery adds only these completion records to the tested code.
Its full HEAD/tree are reported in the external handoff; the code identity
above is not an approved runtime source binding. The preserved WIP checkout,
accepted-source worktree and earlier isolated candidate were not edited.
The existing Git author and committer identity is unchanged, with no trailers.

The original five-file candidate is sealed by a **25287-byte** patch, SHA256
`5d17c6916b25630bc124c657f2ddd2dc6f601f783e322b0c38fa4b999b49bf3e`.
Its source manifest SHA256 is
`64180870e49a050ab1be649e8102d6e1485b10def3c26045998f01f77a6cb56e`.
Both remain at `/tmp/p5-direct-account-contract.bhnYUP/evidence/`.
The six-file integration patch is **28248 bytes**, SHA256
`1119ab34ae2e3d77c1b283f5be1656676664667b8081caf2e6b790ee4aaed663`,
at `/tmp/p5-direct-account-integration.XnuxcB/reviewed-code.patch`.

Changed code paths are:

- `batch-runner/gpt56_foundry_evidence_intake.py`
- `batch-runner/gpt56_pilot_deployment_binding.py`
- `batch-runner/gpt56_pilot_input_capture.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/tests/test_gpt56_direct_account_binding.py` (new)
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py` (four assertions added)

Only the validated `direct-v1` route can omit the child-project ID file.
Explicit `project: null` remains in the evidence; only that exact inapplicable
leaf stops blocking readiness. Non-null project evidence still requires its
exact project-ID file. Account/deployment hierarchy, hashes, source checks,
upstream rereads, capture path checks and launch restrictions remain intact.
The connection does not require a child project. `allow_project_management`
is a resource capability, not project-existence evidence or Azure management
query permission.

No core, schema, registration, historical pin, plan, model/host setting,
budget, grader, workflow or dependency changed. The shared Git helper remains
SHA256 `77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62`.
The exact current-source guard now requires all eleven refusals: the seven
already expected plus the four changed pilot modules. The frozen positive
source and stale-grader-hash refusal are still checked independently.

### Verification, with separate evidence scopes

The prior isolated regression was not rerun. Its observations remain:

| Prior stage | Actual result | pytest elapsed | Outer wall time |
| --- | --- | ---: | ---: |
| Launcher | Exit 127; `/usr/bin/time` absent; no body or JUnit | Not run | Not measured |
| First body | Exit 1; 1 failed at `pilot_step1_refused` | 16.86s | 17.39s |
| Corrected unresolved selector | Exit 0; 1 passed | 42.07s | 42.61s |

That failure identified the capture workspace treating the optional project
path as a required path. The preserved correction skips only that absent
path; real route and upstream verification still precede capture writes.
The failed **24757-byte** patch remains SHA256
`d45ae73cea2acde71d549152d7a8b6602c7dd16f8361a80624a93a8173457f24`.
The prior passing log is SHA256
`5e40beea08bf29d79ab3f8399c3b4762c8f7ead238f0e6e2713616aeec396c59`;
its JUnit is SHA256
`0f02127176942c1c8c73944764a9dd555cf90c2a5dee3c0388d32d6d28dc2086`.
The [prior isolated record](/tmp/p5-direct-account-contract.bhnYUP/completion-records/tasks/LATEST_TASK_RESULT/README.md)
preserves the original command, failure artifacts and detailed test limits.

The new integration invocation selected only the two affected variants of
`tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight`:
`[current]` and `[stale_expected_hash]`. Collection found **2 tests in 1.69s**,
exit **0**, outer wall **2.15s**. One body invocation reported **2 passed in
3.04s**, exit **0**, outer wall **3.36s**; JUnit records **3.039 seconds**.
Python **3.10.12** and pytest **9.1.1** used the existing environment with
**TERM 120s / KILL 5s**, no installation and no old-suite replay.

These results are separate observations, not a pooled three-test suite,
GitHub job durations, model latency or a performance comparison. The new
checks exercise real current-source refusals and immutable local frozen
source/grader verification. The existing process, network and credential
traps apply after the fixture's bounded local Git archive extraction.

The earlier direct-account proof used real local evidence, identity, config,
input, deployment, Step 1 and capture validators with synthetic IDs and tiny
inputs. Test-owned source copies renewed four digests only for that fixture;
no historical registration was edited. Existing reference, manifest,
publication-generation and unrelated connection-flag seams remain synthetic.
No successful validator verdict was stubbed. Provider, credential, process,
network, executor and grader construction were trapped. These limitations
are not removed by the new two-node source check.

The exact new command and artifacts are retained under
`/tmp/p5-direct-account-integration.XnuxcB/`:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `invocation.txt` | 1140 | `115d14487f9937ff4887ae1654ef57921e30224a60a4c3e0ba1731be43b75070` |
| `collection.log` | 633 | `2ac40da4bbe3269dc40cec89de58c0ec0062f72e2d9035b8b014013dd193bae3` |
| `test.log` | 1215 | `2914b195382d2a38c82a767a878fe0e061304262028a0668d667f078d7a7851e` |
| `junit.xml` | 562 | `a8e4bc1b9a660a7785c889b04d8c8745f2afad420a4951f2a34ab623ae6c905f` |
| `timing.txt` | 29 | `6160299f877231e24361e5de837a09c4c7a98b09548d86a48986ef76e1c45dc5` |

The body command runs from the integration worktree's `batch-runner` directory:

```bash
set -o pipefail
test ! -e /tmp/p5-direct-account-integration.XnuxcB/pytest-coupled || exit 90
{ time -p timeout -s TERM -k 5s 120s env -i PATH=/usr/bin:/bin:/usr/local/bin LANG=C.UTF-8 PYTHONPATH=/ai-work/copilot/_tmp_worktrees/gdpval-realworks-direct-account-integration-20261022/batch-runner PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 python3.10 -B -u -m pytest -p no:cacheprovider -v -ra --tb=short --durations=3 --basetemp=/tmp/p5-direct-account-integration.XnuxcB/pytest-coupled --junitxml=/tmp/p5-direct-account-integration.XnuxcB/junit.xml 'tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight[current]' 'tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight[stale_expected_hash]' 2>&1 | tee /tmp/p5-direct-account-integration.XnuxcB/test.log; } 2> /tmp/p5-direct-account-integration.XnuxcB/timing.txt
p5_proof_exit=$?
printf 'proof_exit=%s\n' "$p5_proof_exit"
exit "$p5_proof_exit"
```

### Remaining conditions and retained history

Owner review and fixed-HEAD CI must precede integration approval. A separately
approved source binding and the applicable live evidence/rights gates are
still needed before any Sol experiment. Historical pins deliberately refuse
the new source. `launch_allowed` and `full_220_allowed` remain false. No
five-task experiment, private-input preparation, workflow dispatch, Azure
management, credential discovery, model/judge/grade call or Project edit
occurred. This change does not reset any finite right or consumed attempt.

Retained diagnostic `39407062120`, number **16**, attempt **1**, remains
`connected`, with SDK-reported **9444 input / 5 output tokens**. Served model
identity and cleanup confirmation remain `null`. Context **258400** is
reported metadata, not tested capacity. Max/Long1M, five-task performance and
billing remain unverified. This is earlier evidence, not a new read or call;
see the [corrected connection record](/tmp/p5-sol-native-20261020.PnrI5A/completion-records/tasks/LATEST_TASK_RESULT/README.md).

Native Task3 preparation run `37859270679`, number **6**, attempt **1**, remains
the earlier model-free preparation success with no grading, handle-reuse or
retry authority. Grading run `37756891578` remains uncertain, spent and
nonretryable. Metadata absence remains limited to the two fixed objects at
its inspected immutable parent. The complete earlier history remains in the
[immutable prior LATEST](https://github.com/hyeonsangjeon/gdpval-realworks/blob/6efe99cbd40bb839037e7a20711a734e0a4ce002/tasks/LATEST_TASK_RESULT/README.md).
No discarded historical exception, live fix, score or absent-effects claim
is inferred from this code correction.

The complete skill catalog was consulted. `experiment-report-en` preserves
measurement units, separate proof outcomes and synthetic limits;
`im-not-ai-en` preserves those facts while copyediting the English record.
No experiment redesign, UI work, specialist retry or model/account setting
change was applicable or performed.
