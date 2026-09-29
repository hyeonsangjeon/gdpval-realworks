# Latest task result

## PROJECT5-RETENTION-CI-CAS-INTEGRATION

The single authorized offline invocation failed during guarded historical
archive preparation, before the integration assertions were reached. The
implementation remains unvalidated. No correction, rerun, push or new PR
followed. The implementation is pinned at
`6038eb0cf01b372c874e0c824a3750e118f9ac35`; these two completion-record updates
remain uncommitted.

Branch `b/codex-retention-ci-cas-20260929` starts at exact base
`6aa34a2f393f877da7b8f95e1dcd7bb00077a3fb`, tree
`d571030bbb04fe82726d39d6876982e0ca97bcc8`. The leader reported 10 passing
checks at reviewed `71b3a8274bc6282e8cbc6842303cdb76df54cadb` /
[review 5349547201](https://github.com/hyeonsangjeon/gdpval-realworks/pull/701#pullrequestreview-5349547201).
That review covers the base, not this adapter. The prior 26.20s and 6.62s
observations remain separate in the
[immutable controller handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/6aa34a2f393f877da7b8f95e1dcd7bb00077a3fb/tasks/LATEST_TASK_RESULT/README.md).
Neither selector was replayed.

### Scope

Only `3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r1`,
ordinal 0 of the unchanged eight-cell registration, is supported. The new
adapter and workflow connect the existing first-cell controller to same-run
owner environment review, signed GitHub job-origin evidence and the existing
one-use serial CAS branch. The request binds source, plan, cell, current
input/staging/config/grader identities, hosted job and finite scope. The host
witness relies on GitHub's job-scoped issuance credential, not hardware
attestation. Default planning and preparation request no execution authority.

The separate retention prefix uses existing branch
`pilot-inference-20260925-04`. The historical observer uses immutable source
`8ac891e3e0e4752fe15a00139a2691ddf9df7dce` for input serialization and the
last old producer's metadata, never its Step2 runtime. Admission requires
verification of the last old terminal at one captured HEAD and a claim with
that exact CAS parent. No old claim, registration, result or setup receipt is
reinterpreted. The code has no parent refresh, replay, grading, scheduler or
cross-runner native-state migration. Unresolved ownership and acknowledgments
remain blocking.

The mandatory bounded extreme-reasoner decision preceded workflow editing.
Its conditions included deterministic input lineage, a closed historical
source namespace, signed job-origin evidence and exclusive execution-job
OIDC issuance. Static syntax, fixture/guard ownership and workflow-permission
checks passed; they are not integration results. Experiment-design retained
the registered study without adding an axis.

### Validation

| Tested source | Invocation | Actual result |
| --- | --- | --- |
| `6038eb0cf01b372c874e0c824a3750e118f9ac35` | The exact single selector below | 1 collected, 1 failed in 2.65s; exit 1 |

Run from `batch-runner` with the existing isolated environment. Only the
private handoff value is redacted below; the known locator was present.

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  GDPVAL_RETENTION_PREPARED_HANDOFF='<known private handoff>' \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -p no:cacheprovider --tb=short -s \
  tests/test_codex_retention_ci.py::test_retention_ci_grant_cas_and_owned_runtime_are_bound
```

The exact safe diagnostic was:

```text
dispatcher regression crossed a live boundary
immutable_historical_archive: AssertionError at test_codex_budget_pilot.py:52:forbidden
```

The existing offline guard produced the failure. This diagnostic identifies
the archive-preparation phase and guard, but not which guarded operation
triggered it. No root cause beyond that boundary is established. The preserved
local log has SHA256
`62003b2fa5da67e9fd66121a79f5a250c2f896ae2dc7739c6367a04325827a10`.

The run reached neither real packet/staging verification nor the simulated
approval, CAS, clock, cleanup or publication cases. The planned test-owned
Python `pass` payload was not reached. No new prepared-input or materialized
grader identity was verified, and no model, live provider, claim or inference
was invoked. Prior input evidence is not a result of this invocation.

### Remaining gates

The guarded archive failure needs a separately authorized diagnosis before
validation can resume. The adapter, workflow and test remain unvalidated and
need full new-head review and CI. Existing runtime, registration, compiler,
preparer, grader and old-workflow bytes remain equal to the base; only the
first-cell controller, new adapter/helper/test/workflow and two records differ.

The leader must separately bind the reviewed source, intended host, actual
inputs and first cell before launch. This turn grants no workflow dispatch,
environment review, token exchange, HF write/setup, inference, grade or paid
call. The same-branch protocol needs no new storage ref or setup, but live
target access, predecessor state and provider token interfaces remain
unverified. Protected im-not-ai-en was applied only to the current English
records, preserving the failed result and these limits.
