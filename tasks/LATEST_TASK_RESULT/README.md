# Latest task result

## Native pilot guard review and combined offline verification

For the **2026-10-25 15:10 KST order**, the complete related CI-derived
selection reported **6002 passed, 0 failed, 0 errors, 0 skipped, 3 warnings**.
Pytest took **15178.96 seconds**; the outer command took **15180.42 seconds**,
exit **0**. JUnit contains **6002 unique cases**, including the final real
source-registration test. No production code, test, assertion or expected
value needed correction. This task changes only this record and CHANGELOG.

The requested changed-line review found no weakened or deleted validation
condition. This is bounded self-review and offline verification, not independent
approval, a pilot result or execution authority. All **11** launch blockers remain.

The first full-selection command hit its verification watchdog at **3600.02
seconds**, exit **124**, without a final pytest summary or JUnit. Its log is
retained separately; partial progress is not pooled with the completed run.

### Source and scope

Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`.
Branch: `codex/gpt56-native-pilot-caps-20261024`.

| Role | Identity |
| --- | --- |
| Before the registration work | `9511b3d70719be2503d779b3fd17dcb07f49e312` |
| Reviewed and tested HEAD | `e0fa32ef30dea02da3ee918b40ae08e744d67e14` |
| Reviewed and tested tree | `b67cd5e4d4b956b07850addbfbd1954330d341a0` |
| Before and after both body invocations | Clean; same HEAD/tree |

The final local child changes completion records only. Its exact HEAD/tree and
record hashes are in the evidence directory's `final-source.txt`. Runtime,
test, registration and workflow bytes remain those of the tested HEAD. The
documentation commit is not relabeled as a tested or independently approved
source revision. Other worktrees were not changed by this task.

The full two-file diff `9511b3d70..e0fa32ef3` was reviewed in
`batch-runner/gpt56_sol_codex_pilot_preflight.py` and
`batch-runner/gpt56_pilot_wire_receipt.py`:

| Changed function or condition | Verdict | Evidence |
| --- | --- | --- |
| `wire._native_caps`, line 95 | Maintained | `SOURCE_PROFILE_PREVIOUS` preserves the exact 10-23 path. The 7343-byte read, fixed SHA256, positive-integer checks and cap values are unchanged. |
| Preflight constants, line 49 | Maintained | Select the authorized source-only successor while retaining finite refresh/role sets, digest syntax and non-source field checks. |
| `source_plan_snapshot`, line 295 | Strengthened | Require the predecessor's exact SHA256 and at most 65536 bytes; failures remain closed refusals. |
| `source_plan_snapshot`, line 313 | Strengthened | Require exactly five changed roles against the predecessor, in addition to the existing exact refresh-set comparison. |
| Held roles/rereads, lines 319 and 344 | Strengthened | Add predecessor bytes to archive membership/equality and the existing held-path, clean HEAD/tree, imported-file, admission and final rereads. |
| Safe source report, line 364 | Maintained | Add fixed predecessor/reason metadata; launch/retry authority remains false and exceptions remain sanitized. |
| `main`, line 932 | Strengthened | Explicit old-profile selection enters source verification and refuses at the changed source rather than bypassing those checks. |

The review has **3 maintained / 4 strengthened / 0 weakened rows**. No source
correction was justified. It covers changed lines in these two files, not all
pre-existing execution paths. The **6640-byte** full-index review patch is
SHA256 `cfb49ddad5b4ca09a47fb6422923aaf09068a4f984ce63771fa5270351a5d262`.

### Complete offline selection and command

The selection recombines `.github/workflows/backend-tests.yml` targets at
lines 444, 451-458, 518, 577, 635, 693, 752 and 814, plus the related caps,
provider, remaining-caps and source-registration modules in the general
non-integration job. Complementary preflight/wire partitions are combined
without a `-k` filter. This is the whole related selection, not the whole repo.

Collection found **67 modules / 6002 nodes / 0 duplicates**: **122** caps/provider/
remaining-caps, **917** pilot-contract, **341** preflight, **155** wire,
**1537** budget non-readout, **2929** budget readout and **1** source-registration
case. Collection took **11.53 seconds** in pytest, **12.13 seconds** outside,
exit **0**. Collection is separate from body execution and pass counts.

Evidence directory: `/ai-work/copilot/_tmp/p5-native-combined-review.gCP39k/`.
The completed command, from this worktree's `batch-runner/` directory, was:

```bash
timeout --signal=TERM --kill-after=5s 22500s env -i \
  PATH=/usr/local/bin:/usr/bin:/bin HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_LAZY_FETCH=1 \
  /ai-work/copilot/_tmp/ghcp-sol-gate-ci-20261024-venv/bin/python \
  -m pytest -q -ra --tb=short --durations=20 -o addopts= -p no:cacheprovider \
  -m 'not integration' \
  --junitxml=/ai-work/copilot/_tmp/p5-native-combined-review.gCP39k/junit-combined.xml \
  tests/test_gpt56*.py tests/test_codex_budget_pilot*.py \
  tests/test_sol_source_registration.py
```

The existing Python **3.10.12** environment was reused. No dependency was
installed or HOME/CODEX_HOME override declared. Fixtures use synthetic inputs,
mocked providers and local transports/children, not live study execution.

| Invocation at the same clean HEAD | Outcome | Pytest seconds | Wrapper seconds | Exit |
| --- | --- | ---: | ---: | ---: |
| TERM3600s/KILL5s | Watchdog timeout; complete counts unknown; no JUnit | unknown | 3600.02 | 124 |
| TERM22500s/KILL5s | 6002 passed, 0 failed, 0 errors, 0 skipped, 3 warnings | 15178.96 | 15180.42 | 0 |

The first watchdog used one CI job's ceiling, which was too short for this
combined selection. The corrected **22500-second (375-minute)** ceiling reflects
seven **45-minute** jobs and one **60-minute** job; it bounds local verification
only. No production deadline, cap, assertion or test membership changed.
`--durations=20` adds reporting only. No separate collect-only command reran.

JUnit reports **15178.701 seconds** for its suite and **6.411 seconds** for the
final `test_sol_source_registration` case. These are distinct from pytest's
displayed elapsed time and the shell wrapper's wall time. No known test/wrapper
process-group member remained after completion.

There were no assertion failures to classify as stale expectations or actual
regressions. The earlier exit **124** is a verification-watchdog outcome, not
such an assertion failure. All three `record_property`/xunit2 warnings remain:
two parametrizations at `tests/test_codex_budget_pilot_grading.py:611` and one
node at `tests/test_codex_budget_pilot_grading_source.py:115`. No warning was
suppressed and no unrelated fixture or report format was changed.

### Retained proof and unchanged bytes

| Evidence file | Bytes | SHA256 |
| --- | ---: | --- |
| First `test.log` | 1529 | `6a6839310bdb801398d16e62261cf47eb1375ef3fa12d37301035874c90a88de` |
| First `timing.txt` | 46 | `8ac2858493a4c579756d1e83f8837d36aeef049221004f1311c79507f4f69e40` |
| `test-combined.log` | 10908 | `b405c81641e13481397a2d92ef70223e7cb60143c57f1e5dd0b54507f38cf580` |
| `junit-combined.xml` | 945098 | `5d73d3cb35be4b8c27cd23b3420c80dbe437dca7291cad61465deeb24da521ea` |
| `timing-combined.txt` | 46 | `6c2fb860cdfefb0c1031ada37d7a16686642b98d39c9e026e52256deba1b987d` |
| `reviewed-source.patch` | 6640 | `cfb49ddad5b4ca09a47fb6422923aaf09068a4f984ce63771fa5270351a5d262` |

`invocation.txt` retains collection and the interrupted command, SHA256
`2d808b89b819e9089891f761c4817861356ee1a3ac26fae044b50f146c36e460`.
`invocation-combined.txt` records the completed command/result, SHA256
`20074bfb8c559f0f9be06f66b541cd7803984deb32f8985540bea4f6a30ad8f8`.
`source-hashes.sha256` is SHA256
`ea5e228e3462e479dbf177fd16160cd26053326276efb0b13d8d55439b9d3d47`;
all seven recorded runtime/test/registration/workflow hashes still match.
The 10-23 registration remains
`506de35370ffe6d54e6decb2459a4f4abda47136d550c010086b0fffd5c1e482`;
the 10-25 successor remains
`f88c850558674a4c3a89ae0840f23dc27402aefafe56f7323ba3d3b8ad33a3b2`.
The **7343-byte** caps draft remains
`7c3c139bb96333e939b4dc43939c05c2f848313d907c8cade052afde18855fb6`.
No plan, cap, source registration, hash algorithm, shared helper, workflow,
dependency, model, host, frozen grader or permission was changed.

### Remaining gates and history

No standalone plan-only preflight reran and no new launch evidence was added.
The previously recorded **11** blockers remain: **0 cleared / 11 retained /
0 new**. Passing this selection does not close them:

```text
foundry_account_project_deployment_identity_unverified
foundry_served_model_version_unverified
max_and_long_1m_capability_unverified
native_call_and_token_limits_unresolved
prepared_input_bytes_unverified
live_inference_identity_and_wire_unverified
pilot_dispatch_and_grading_identity_not_wired
foundry_usage_and_tariff_mapping_unverified
native_sandbox_and_result_bundle_host_unverified
actual_pilot_deployment_not_prepared
prepared_request_capture_unverified
```

The legacy account/project name does not require a child-project ID for
`direct-v1`. Caps remain **32/attempt, 128/task, 640/pilot**, **1800 seconds**,
and **300000 input / 10000 output tokens**. Reported token-overrun stops are
not hard provider token ceilings; the monetary cap remains null. Owner review
of the final HEAD, CI and separate live evidence/authorization gates remain
outstanding. No publication or live execution is authorized by these results.

The [immutable prior record](https://github.com/hyeonsangjeon/gdpval-realworks/blob/e0fa32ef30dea02da3ee918b40ae08e744d67e14/tasks/LATEST_TASK_RESULT/README.md)
retains the separate **4-pass/1-fail** registration proof, its **one-node pass**,
the **58-hash** plan-only refusal and the link to the earlier **165-case** caps
proof. These results are not pooled with each other or the new complete
invocation. Task3 run `37756891578` remains uncertain, spent and nonretryable;
no finite right was consumed, restored or retried.

`experiment-report-en` kept test populations, timing units, observations and
live limits separate; `im-not-ai-en` preserved protected facts and hedges. The
protection brief/reconciliation are retained with the evidence. No experiment
redesign, UI work or specialist endorsement applies. Existing Git identity was
retained without attribution trailers. No live provider/auth/external-network
call, model run, grading, dispatch, push or PR occurred.
