# Latest task result

## PROJECT5-PR703-MALFORMED-URL-FIX

The one authorized locator selector passed at tested HEAD
`b6415a2066fd341ea913cadaa7422b029ca21c60`: 1 collected, 1 passed in 2.22s,
exit 0. This follow-up changes one synthetic test value and the two completion
records on `b/codex-retention-first-locator-20260929`. Production authentication
and all test assertions are unchanged.

The correction addresses leader [review 5356074537](https://github.com/hyeonsangjeon/gdpval-realworks/pull/703#pullrequestreview-5356074537)
at prior PR703 HEAD `b19d7a0d218ce1bd1d18307f77b0346b68016f94`.
Only the `malformed-url` value in
`batch-runner/tests/test_codex_retention_ci_locator.py` changes:

```diff
-        ("malformed-url", "https://[" + private + "]/" + private, "url_parsed"),
+        ("malformed-url", "https://[" + private, "url_parsed"),
```

The unmatched opening bracket replaces the balanced non-IP bracketed host.
Exact `url_parsed=False`, an empty route skeleton, redaction, the primary
refusal and all no-effects assertions remain required. No parser or acceptance
predicate changed, and no new production-auth review was needed.

### Separate observations

| Source | Observation | Actual result |
| --- | --- | --- |
| `d4011844a0ee1efacd56304718f66c9bc038c32f` | Prior local locator selector | 1 collected, 1 passed in 2.17s; exit 0. Preserved, not replayed unchanged. |
| `b19d7a0d218ce1bd1d18307f77b0346b68016f94` | Leader-supplied [CI run 36599503878 / job 109512928743](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/36599503878/job/109512928743), CPython 3.10.12 | 1 failed, 13292 passed, 64 skipped, 46 deselected in 1471.63s. The malformed-URL flag assertion failed at line 108. |
| `b6415a2066fd341ea913cadaa7422b029ca21c60` | Fresh local selector with the one-value correction | 1 collected, 1 passed in 2.22s; exit 0. All unchanged assertions completed. |

In the CI failure, `url_parsed` was `True` where the malformed-URL case expected
`False`. The primary refusal and no-opener/HTTP assertions passed before that
failure; later assertions for that case were not reached. No version cause is
inferred, and no CI query, rerun or environment investigation was performed.

### Exact fresh validation

The command ran once from `batch-runner` in the existing isolated environment,
without a private-input locator or real credential:

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -p no:cacheprovider --tb=short -s \
  tests/test_codex_retention_ci_locator.py::test_retention_job_issuance_locator_diagnostics_are_closed
```

The log SHA256 is
`21e3d2f9e6e8cef4081815106b957e5538f5633047063808c47fdc904863265c`.
The real parser, predicates and closed diagnostic formatter ran with simulated
HTTP only. All 23 refusal cases and both previously accepted synthetic forms
remain within one pytest test, not separate test totals or real provider URLs.
The shared offline guards and fail-before-effects assertions remained active.
No private preparation, child, model, grade or live authority operation ran.

The [immutable prior handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/b19d7a0d218ce1bd1d18307f77b0346b68016f94/tasks/LATEST_TASK_RESULT/README.md)
preserves the original diagnostic implementation, authoritative source links,
live pre-admission refusal, source/input identities and earlier observations.
The genuine private `da0fb6bea28826c9287adaff95e6d4daf8996642` result remains
1 passed in 295.37s, not skipped, repeated or combined with this validation.

### Byte scope and remaining gates

Only the one test line and these two records differ from
`b19d7a0d218ce1bd1d18307f77b0346b68016f94`. All production, workflows,
shared fixtures, runtime, registrations/pins, grading and original private
integration/wait-registry bytes are unchanged. The adapter file SHA256 remains
`ed5dbc4e7140ff5899c17b4f13bfc3a9871119bf7c994b43777b25ca333f3713`.
The unrelated changelog tail is preserved. Protected im-not-ai-en copyediting
retains the separate results, literals and limits.

New-head delta review and CI remain required; review 5356074537 is not approval
of this follow-up. The actual provider locator and failed live constraint remain
unknown. The production patch is still diagnostic-only, not a proven provider
compatibility fix. A model-free observation requires separate leader
authorization. No token exchange, workflow rerun/dispatch, environment approval,
live CAS/HF/OIDC/Azure/model/grade or paid operation occurred. Existing source,
cell, host, runtime, input, spend, serial-admission and cleanup gates remain in
force; no new launch authority is granted.
