# Latest task result

## Direct-account CI correction; live Sol execution remains blocked

Review of PR #785 at `fbdac81a462e0328f3c015d8a89be0b689a4ea7d`
found **9 successful and 2 failed checks**, with no recorded owner review.
The two failures exposed test integration defects: a new filename entered a
reserved CI partition, and another exact source-refusal list omitted the four
changed pilot modules. The correction renames the regression without changing
its bytes and adds those four required refusals. The workflow, partition guard,
production code and historical pins are unchanged by this follow-up.

The new local invocation reported **1 failed, 1 passed**, not a complete pass.
The source-boundary node passed. The partition node passed its original failing
assertion but failed during nested collection because the selected local
Python lacks `openai_codex`. No dependency was installed and no previously
passing selector was rerun. Final-HEAD CI and owner review remain required.

The requested live Sol experiment was not started. Its existing registration
still refuses this source, and `launch_allowed` remains false. A separately
approved source binding and the existing live evidence/unused-right checks
are required; this is not missing child-project information or a renewed
payment-approval request. No runtime admission or live result is claimed.

### Source and scope

- Base HEAD: `6efe99cbd40bb839037e7a20711a734e0a4ce002`.
- Base tree: `4b80f235ab1627584e1a6c1f66849c3ead6b1a3d`.
- CI-reviewed HEAD: `fbdac81a462e0328f3c015d8a89be0b689a4ea7d`.
- CI-reviewed tree: `72b46dd81e6e19b0e20955b32949a1d2151cc25f`.
- Current tested correction HEAD: `077b3e37cc9116503c143ad58b5f7427d1eeab03`.
- Current tested tree: `c73f32e97c762e1e4163d7d82bc882f517f23557`.
- Earlier integration test HEAD: `6dab6b151b7b70127ab35a0e96b324bc6e005116`.
- Earlier integration tree: `229b128b871c084314a78a9da6d6e5095cdb7ccd`.
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
The earlier six-file integration patch is **28248 bytes**, SHA256
`1119ab34ae2e3d77c1b283f5be1656676664667b8081caf2e6b790ee4aaed663`,
at `/tmp/p5-direct-account-integration.XnuxcB/reviewed-code.patch`.

Changed code paths are:

- `batch-runner/gpt56_foundry_evidence_intake.py`
- `batch-runner/gpt56_pilot_deployment_binding.py`
- `batch-runner/gpt56_pilot_input_capture.py`
- `batch-runner/gpt56_sol_codex_pilot_preflight.py`
- `batch-runner/tests/test_direct_account_pilot_binding.py` (new regression, renamed without byte changes)
- `batch-runner/tests/test_gpt56_sol_codex_pilot_preflight.py` (four assertions added)
- `batch-runner/tests/test_gpt54_disposable_checkout.py` (four assertions added in this follow-up)

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

### Current CI findings and bounded correction proof

CI run `39772172623` evaluated the CI-reviewed HEAD above. These are separate
pytest summaries, not full job durations or independent model outcomes:

- `pytest`, job `119802154544`: **1 failed, 13396 passed, 64 skipped,
  46 deselected, 1 warning in 1753.62s**. The partition test expected
  **9** `test_gpt56_*.py` files but found **10**. Its later checks also require
  the exact workflow file lists, so changing only the count would be wrong.
- `comparison-contracts`, job `119802154502`: **1 failed, 1462 passed in
  1797.48s**. Its pilot source-refusal assertion omitted four changed modules.

The regression moved from `test_gpt56_direct_account_binding.py` to
`test_direct_account_pilot_binding.py`. Its SHA256 is unchanged:
`8ee774413be4ab5bb945872c0ba66c18d35e5397683597789561ff4ba3f4076b`.
It stays in the default pytest job that already executed it. The existing
**12 comparison / 9 pilot / 7 general-pilot** count assertions, exact workflow
lists and partition checks remain intact. The source-refusal test now requires
all eleven refusals and still requires both launch flags to be false.
The **1500-byte** correction patch is SHA256
`b29235a3943e21d6b672bee002de1bd79d0025f1d05550a5c2adb0a2b178b819`.

Collection found **3 selectors in 2.90s**, exit **0**, outer wall **3.32s**:
the two failed CI nodes plus the renamed regression. Only the two failed CI
nodes ran; the renamed regression was collected, not executed again.

- `tests/test_a_test_file_nobody_runs_is_not_a_test.py::test_backend_jobs_partition_the_comparison_contracts`
  failed at nested collection with `ModuleNotFoundError: openai_codex`.
  It reached line **790**, beyond the original failing line **689** and the
  exact partition assertions. The nested collection reported **445 collected,
  3 errors**; those are not additional outer test failures or executed bodies.
- `tests/test_gpt54_disposable_checkout.py::test_comparison_runtime_launch_boundary_current_source_bindings`
  passed with real current-source refusal and immutable frozen-source checks.

The one body invocation reported **1 failed, 1 passed in 28.69s**, exit **1**,
outer wall **29.17s**; JUnit duration is **28.677s**. It used Python **3.10.12**,
pytest **9.1.1**, **TERM120s/KILL5s**, an empty inherited environment, offline
Hub/dataset settings and no plugin autoload or pytest cache. Existing bounded
Git fixture reads and runtime traps were retained. No test was retried, and
no package, stub or altered assertion replaced the missing local SDK. The
declared dependencies still pin `openai-codex==0.147.0` and
`openai-codex-cli-bin==0.147.0`.

Exact collection/body commands are in
`/tmp/p5-pr785-review.M21C8U/invocation.txt`. Artifacts in that directory:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `pytest-failed.log` | 274845 | `7480c1fbba93b2d3b5afc82265e71e4460ee7c550e73a8cc05cb28bb2f6bfff0` |
| `comparison-failed.log` | 187648 | `208970c6c5d63ba949ccbd4731627f20fb77929b46552c50712831060c91575d` |
| `collection.log` | 765 | `8efb98b6b0c1700cff7eba49128d1ceba4195659b33bad9f4bd17df0c24162fa` |
| `test.log` | 209127 | `6d7b07a8e8d14ee398b87a6a40a7c8049fe258bfe88a06abe47c433b2c68c6b9` |
| `junit.xml` | 210275 | `a3899d6c0ec5fa679ef6d7cc25c55b88e745d8aeab90d08a447b0364b8bb26c7` |
| `timing.txt` | 31 | `f3c0c21fb3a274a46c34b4607d690c2f291b211f85127d9e1874ab30776e8e70` |

### Earlier verification, not rerun or pooled

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

The earlier integration invocation selected only the two affected variants of
`tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight`:
`[current]` and `[stale_expected_hash]`. Collection found **2 tests in 1.69s**,
exit **0**, outer wall **2.15s**. One body invocation reported **2 passed in
3.04s**, exit **0**, outer wall **3.36s**; JUnit records **3.039 seconds**.
Python **3.10.12** and pytest **9.1.1** used the existing environment with
**TERM 120s / KILL 5s**, no installation and no old-suite replay.

These results are separate observations, not a pooled test suite,
GitHub job durations, model latency or a performance comparison. The earlier
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
are not removed by the current two-node check.

The earlier command and artifacts are retained under
`/tmp/p5-direct-account-integration.XnuxcB/`:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| `invocation.txt` | 1140 | `115d14487f9937ff4887ae1654ef57921e30224a60a4c3e0ba1731be43b75070` |
| `collection.log` | 633 | `2ac40da4bbe3269dc40cec89de58c0ec0062f72e2d9035b8b014013dd193bae3` |
| `test.log` | 1215 | `2914b195382d2a38c82a767a878fe0e061304262028a0668d667f078d7a7851e` |
| `junit.xml` | 562 | `a8e4bc1b9a660a7785c889b04d8c8745f2afad420a4951f2a34ab623ae6c905f` |
| `timing.txt` | 29 | `6160299f877231e24361e5de837a09c4c7a98b09548d86a48986ef76e1c45dc5` |

The [immutable integration record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/fbdac81a462e0328f3c015d8a89be0b689a4ea7d/tasks/LATEST_TASK_RESULT/README.md)
preserves the complete earlier command and source/proof boundaries.

### Remaining conditions and retained history

The new final HEAD has no passing-CI claim in this record; the local partition
proof is still unresolved in the selected environment. Owner review and
fixed-HEAD CI must precede integration approval. A separately
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
