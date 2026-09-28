# Latest task result

## PROJECT5-LAST-TWO-FIXTURE-BOUNDARIES

The single three-node invocation passed at fixture HEAD
`93e96b342386482cb9e7f60805781f0009620629`: 3 passed in 16.55s, exit 0.
Only the two authorized test boundaries changed, followed by these two
completion records on `b/codex-retention-runtime-20260928`. The passing result
permits one ordinary push to existing draft
[PR698](https://github.com/hyeonsangjeon/gdpval-realworks/pull/698).
New-HEAD CI and delta review remain required.

### Fixture scope

The leader reported 12 passing and 2 failing checks at
`5d35dc440cdf7cdf2b53cc61ebd6a55ff9549350` in CI run
[36479015855](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36479015855).
The supplied inventory isolated pilot job `109119784479` to ledger-note host
allocation and all 44 failures in readout job `109119784689` to lazy archive
setup. The pilot log was read only to confirm the selected failed node IDs.
No other failure investigation or passing-check rerun was performed.

- `batch-runner/tests/test_codex_budget_pilot_ledger_notes.py::produce` now
  allocates its owned temporary host directory under
  `Path(__file__).resolve().parents[3]`, following the existing test pattern.
  Mutable `pilot.ROOT` can point to the historical archive under `/tmp`; it
  no longer determines host placement. Real run-root and state-ownership guards,
  temporary-directory cleanup, reference bytes and assertions remain unchanged.
- `batch-runner/tests/test_codex_budget_pilot_task2_final_readout.py::test_task2_final_grade_readout`
  explicitly requests the existing module-scoped `historical_budget_source`
  through `pytest.mark.usefixtures`. Its genuine immutable
  `8ac891e3e0e4752fe15a00139a2691ddf9df7dce` archive is ready before the
  function-scoped subprocess guard. Dynamic `request.getfixturevalue("case")`
  remains unchanged, and the guard stays active for writer/verifier execution.

Production, source pins, validators, images, workflows, registrations and
guard/assertion bodies are unchanged from `5d35dc440cdf7cdf2b53cc61ebd6a55ff9549350`.
Production and the grading-image guard still match the frozen
`de3e0401b9c0ae9d2d142c25e14d1f4dab768383` baseline. No skip or timeout changed.

### Exact invocation and result

Both ledger IDs were confirmed against the failed log and their local owning
definitions and parameters. The Task2 selector also matches its local parameter.
From `batch-runner`, the sole invocation was:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest -p no:cacheprovider --tb=short \
  'tests/test_codex_budget_pilot_ledger_notes.py::test_real_producer_notes_publish_original_bytes_and_preserve_outcome[success-settled-one Codex turn; the model requests inside it are not individually reported]' \
  'tests/test_codex_budget_pilot_ledger_notes.py::test_export_identity_and_recorded_accounting_still_refuse_changes[bytes]' \
  'tests/test_codex_budget_pilot_task2_final_readout.py::test_task2_final_grade_readout[C_r1-graded]'
```

```text
collected 3 items
============================== 3 passed in 16.55s ==============================
pytest exit status: 0
```

The log, exact selector list and pilot failure log remain in
`/tmp/project5-last-two-fixtures.ubu9Da/`. These three selected cases passed;
this is not a full-family or CI result. No other pytest invocation ran.

### Separate local validation observations

These are distinct PR698 invocations, not combined totals or a claim that a
single full selector passed. Earlier stops without an invocation add no result.

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

The [49-file fixture scope and both selector attempts](https://github.com/hyeonsangjeon/gdpval-realworks/blob/5d35dc440cdf7cdf2b53cc61ebd6a55ff9549350/tasks/LATEST_TASK_RESULT/README.md),
[complete prior handoffs](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/tasks/LATEST_TASK_RESULT/README.md),
[54-module inventory and prior CI results](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/tasks/LATEST_TASK_RESULT/README.md#project5-final-legacy-fixtures)
and [prior changelog](https://github.com/hyeonsangjeon/gdpval-realworks/blob/de3e0401b9c0ae9d2d142c25e14d1f4dab768383/CHANGELOG.md)
remain immutable Git evidence. Session artifacts, including
`/tmp/project5-final-legacy-fixtures.S8DFVq/failed-nodes.tsv`, were preserved.
Historical handoffs are linked here rather than copied into this current record.

### Remaining gates

The three selected cases passed locally; no new CI result is claimed.
Leader [review 5344462942](https://github.com/hyeonsangjeon/gdpval-realworks/pull/698#pullrequestreview-5344462942)
at `5d35dc440cdf7cdf2b53cc61ebd6a55ff9549350` is conditional on all CI;
it is not a waiver, approval of this new fixture delta,
authorization of modified runtime for the old campaign, or launch authority.
New-HEAD delta review and CI remain required. The capability remains
unregistered and live-unverified. No model, live readout, Azure, OIDC, HF
credential or paid operation, new campaign, CI rerun/poll or merge occurred.
