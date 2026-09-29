# Latest task result

## PROJECT5-REGISTRATION-COMPILE-REFUSAL

The config-assembly repair is pinned at
`510bb8246f40e999c3c1f603dc94bd67051e5141`. The sole authorized pytest invocation
reported 1 passed in 5.01s, exit 0. It checked the closed eight-cell offline
plan, drift refusals, legacy-campaign refusal and inert CLI. This is one contract
test, not eight experiment executions or live-runtime validation. These records
precede the authorized push and new draft PR; no source approval or merge is claimed.

### Scope and reviewed base

Branch `b/codex-retention-registration-20260929` continues in the same worktree
`/ai-work/copilot/worktrees/codex-retention-registration-20260929`, created from
exact main `18bc942b97114cca3b9f6ed913b9841dda3a5874`. Its tree is
`062d668f967bb9e772f0de353dbef27e99987479`, matching reviewed
`610d39c2744be8b8879f884fa0a43abb053ecd44` and
[review 5345799305](https://github.com/hyeonsangjeon/gdpval-realworks/pull/698#pullrequestreview-5345799305).
The leader reported all 14 checks passing and delivery of PR698. Those are
reviewed-base facts, not approval or validation of this new compiler. Old
branches, checkouts and WIP are preserved; no PR698 test or check was replayed.

The draft adds only the [registration](../../batch-runner/experiments/execution_envelope/codex_retention_diagnostic.yaml),
[offline compiler](../../batch-runner/codex_retention_diagnostic.py) and
[focused test](../../batch-runner/tests/test_codex_retention_diagnostic.py), plus
these two current records. Existing runtime, grader, workflow, source-pin and
original 30-cell registration/outcome bytes are unchanged from the base.

The bounded pre-test diagnosis captured the real validator's sole error:
`experiment.id must be a safe identifier`. The first keep ID was a string of
102 characters; `core.repository_identity.validate_experiment_id` permits at
most 100. The old assembly redundantly included the policy label after the
campaign namespace. The field-by-field template comparison found no other
validation error; deadline controls were not the cause.

The compiler now uses the existing identifier validator for
`<campaign>__<task>_<keep|fresh>_r<repeat>`, while preserving all eight full cell
IDs and their controls. The test verifies unique valid experiment IDs and the
real validator's refusal of the original 102/103-character forms. Compilation
refusals now include the validator's structural errors. Only the new compiler,
its actual registration source hash and the focused test changed in this fix.
The compiler SHA-256 is
`c8ac9d0ec3eca0d4251c345f733009f506d366d312c5357836e6c67332a76c53`;
it is a byte binding, not approval. The earlier relative-import correction and
the existing offline guards remain intact; no validator or runtime was changed.

The prospective scope is eight new Task4/Task5 cells: keep/fresh, two repeats,
with Task4 ordered keep1/fresh1/fresh2/keep2 and Task5 fresh1/keep1/keep2/fresh2.
Both modes use `retention_bundle_v1`, B recovery, one global inference slot,
one durable 10,800-second budget, no fixed admission cap and no C feedback.
The 1,800-second native-turn wait is not an all-in attempt ceiling. The draft
separates reviewed runtime pins, unreviewed compiler bytes and the actual
grader-template closure; no future materialized grader fingerprint is claimed.
It binds public input provenance for dataset revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf`, without fetching private payloads.
It contains no scheduler or dispatch path and explicitly denies launch authority.

### Exact invocation and result

After the bounded diagnosis and static comparison with the canonical config
helpers, at `510bb8246f40e999c3c1f603dc94bd67051e5141`, from `batch-runner`,
the sole pytest invocation was:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p no:cacheprovider --tb=short \
  tests/test_codex_retention_diagnostic.py::test_retention_registration_is_exact_closed_and_inert
```

```text
collected 1 item
tests/test_codex_retention_diagnostic.py::test_retention_registration_is_exact_closed_and_inert PASSED [100%]
============================== 1 passed in 5.01s ===============================
pytest exit status: 0
```

The complete log is `/tmp/project5-registration-compile-refusal.I4pDWM/pytest.log`.
No second pytest invocation, old suite, CI replay or CI polling ran in this follow-up.
All tracked files outside the three new registration-unit files and these two
records were byte-compared with the reviewed base and are unchanged. This includes
runtime, validators, frozen 30-cell registrations/pins, graders and workflows.

The import-corrected attempt at `38e4a4b5422641a16e61209fc741a44621c06732`
remains separate: 1 collected, 1 failed in 2.47s, exit 1, at the first
`compile_plan` call with `RetentionRegistrationRefused: compiled_config_refused`,
before contract assertions. Its log is
`/tmp/project5-registration-fixture-import.CEPTWc/pytest.log`; that invocation
did not expose the underlying identifier error diagnosed in this follow-up.

The earlier attempt at `0fe972e2814b3eb5f256ecf8516d6f531583f3f3` remains separate:
`ModuleNotFoundError: No module named 'test_codex_budget_pilot'`, 1 collection
error in 1.21s, exit 4, with 0 tests collected or executed. Its preserved log is
`/tmp/project5-retention-registration.bxAJKE/pytest.log`.

### Separate local validation observations

The historical PR698 runs and these registration attempts are separate
observations, not combined totals. Stops without an invocation add no result.

| Tested SHA | Actual result | Exit |
| --- | --- | --- |
| `b1854e5b50eda9c25c9db5bc2627acf35022e70d` | 5 failed, 42 passed in 334.92s | 1 |
| `91ffae589b240dd9d31978af0dd2cf19532e96c7` | 5 passed in 24.02s | 0 |
| `6710299c5776c30ccf3927a1f8a54c6ee4ffab09` | 3 passed, 1 setup error in 93.52s | 1 |
| `6665c183c215aa6594622eb9fe92ca55633c7013` | 1 setup error in 8.44s | 1 |
| `7bbe61f7880ce0bdb3a130fbf8f89856cb8efc27` | 3 passed in 49.11s | 0 |
| `88b8a62b4b5f4802f6fc22c25b9348d78a931f65` | 3 passed in 9.04s | 0 |
| `3fdc5a95853619135d4165063392144eb6fea540` | 8 passed in 26.06s | 0 |
| `1fa84f2b2cff4d51a323aabd2051130fd8b119c8` | 3 passed in 61.92s | 0 |
| `3188e27a2eac24fd7ed3f3e074c9a088ad7d79e0` | No tests ran; selector not found; 7 collected; 5.49s | 4 |
| `3188e27a2eac24fd7ed3f3e074c9a088ad7d79e0` | Corrected owner: 8 passed in 139.10s | 0 |
| `93e96b342386482cb9e7f60805781f0009620629` | 3 passed in 16.55s | 0 |
| `dac0421ca5b05d35eae85a9b666eb351a9f84744` | Unchanged node, read-only diagnostic profiling: 1 passed in 0.67s | 0 |
| `eb9971b1b8ce94e559481d56dd6cdbe1ca854c61` | Deterministic edge and fixed paths: 4 passed in 1.02s | 0 |
| `0fe972e2814b3eb5f256ecf8516d6f531583f3f3` | Registration test: 0 collected, 0 executed; 1 collection/import error in 1.21s | 4 |
| `38e4a4b5422641a16e61209fc741a44621c06732` | Relative-import correction: 1 collected, 1 failed in 2.47s; `compiled_config_refused` before contract assertions | 1 |
| `510bb8246f40e999c3c1f603dc94bd67051e5141` | Bounded experiment-ID assembly and offline plan contract: 1 passed in 5.01s | 0 |

The [final PR698 handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/610d39c2744be8b8879f884fa0a43abb053ecd44/tasks/LATEST_TASK_RESULT/README.md)
preserves the prior deterministic reproduction, original CI-cause uncertainty
and unchanged local diagnostic separately.

The [two-boundary fixture result and preceding CI evidence](https://github.com/hyeonsangjeon/gdpval-realworks/blob/dac0421ca5b05d35eae85a9b666eb351a9f84744/tasks/LATEST_TASK_RESULT/README.md),
[49-file fixture scope and both selector attempts](https://github.com/hyeonsangjeon/gdpval-realworks/blob/5d35dc440cdf7cdf2b53cc61ebd6a55ff9549350/tasks/LATEST_TASK_RESULT/README.md),
[complete prior handoffs](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/tasks/LATEST_TASK_RESULT/README.md),
[54-module inventory and prior CI results](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/tasks/LATEST_TASK_RESULT/README.md#project5-final-legacy-fixtures)
and [prior changelog](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/CHANGELOG.md)
remain immutable Git evidence. Session artifacts, including
`/tmp/project5-final-legacy-fixtures.S8DFVq/failed-nodes.tsv`, were preserved.
Historical handoffs are linked here rather than copied into this current record.

### Remaining gates

New compiler/source review and new-HEAD CI remain required. The reviewed runtime
base and this offline pass do not approve the new compiler/controller or authorize
launch or the modified runtime for the original campaign. Input staging and byte verification,
the serial execution/reservation controller, any materialized grader identity,
live-runtime verification and explicit paid-run direction remain outside this unit.

The decision remains whether to consider a larger bundle-retention study, with
only a preliminary within-task signal from two keep-only pair advantages and
no reverse pair. Otherwise benefit is not established. No-recovery cells stay
in the denominator of eight but are uninformative about retention. Post-selection,
two repeats, service variation and an uncalibrated judge limit the claim; no
thread-versus-files attribution, model superiority or complete bill is established.
There are no forced faults, extra repeats or automatic monetary cap. Known
usage, partial costs, missing prices and NG/null grades must stay distinct.
No live execution, private payload fetch, storage setup, credentials,
infrastructure change, Azure/OIDC/HF/model call, paid run or merge occurred.
