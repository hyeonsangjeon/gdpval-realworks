# Latest task result

## PROJECT5-ALLOWLISTED-CHILD-WAIT-COVERAGE

The one authorized selector failed at
`6c33c2bd960574d827bb4983c2b904ff049f6210`: 1 collected, 1 failed in 168.90s,
exit 1. Code work stopped after that invocation. There was no diagnostic
rerun, retry, push or new PR. These two completion-record updates remain
uncommitted.

Branch `b/codex-retention-ci-cas-20260929` starts at exact base
`6aa34a2f393f877da7b8f95e1dcd7bb00077a3fb`, tree
`d571030bbb04fe82726d39d6876982e0ca97bcc8`. The leader reported 10 passing
checks at reviewed `71b3a8274bc6282e8cbc6842303cdb76df54cadb` /
[review 5349547201](https://github.com/hyeonsangjeon/gdpval-realworks/pull/701#pullrequestreview-5349547201).
That review covers the base, not this adapter or fixture correction. The prior
26.20s and 6.62s observations remain separate in the
[immutable controller handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/6aa34a2f393f877da7b8f95e1dcd7bb00077a3fb/tasks/LATEST_TASK_RESULT/README.md).
Neither selector was replayed.

### Test-only correction and observed boundary

Only `tests/test_codex_retention_ci.py` changed beyond the two records. The
existing sleep guard now uses one child-registration path for the complete
previously allowlisted catalog. The catalog and its constructor, communicate,
wait, context-manager and timeout-cleanup paths were inspected before editing.

| Existing command category | Unchanged bound and wait path |
| --- | --- |
| Seven exact local Git metadata/archive forms | 60 seconds; `run → communicate → wait/_wait` |
| `SAFE_ERROR + OBSERVE` and `SAFE_ERROR + MATERIALIZE`, with the original input roles and exact immutable archive cwd | 90 seconds; the same stdlib paths, including communicate's second wait |
| Exact owned-supervisor argv carrying only `[sys.executable, "-c", "pass"]` | Direct `Popen`; the actual `LocalTransport.process` frame and its 10,860-second lifecycle deadline, with the existing control-channel/poll/wakeup cleanup unchanged |

Captured real sleep is available only from the actual stdlib `_wait` code for
the matching tracked `Popen`, active owner frame, argv, cwd and original
deadline. Requested sleep is capped at the remaining bound. The supervisor
and its fixed payload use existing owned reaping, not a new stdlib-wait path.
Normal subprocess failure/timeout cleanup is unchanged. There is no pidfd,
custom reaper, new command or timeout extension, and `time.sleep` is never
globally restored. Other threads and untracked processes remain outside the
exception.

The guard refused direct sleep, bare Python, an altered historical script,
a forged supervisor call and a direct Step2 command before any tracked child
was created.
Explicit fixture ordering still constructs both genuine immutable
`8ac891e3e0e4752fe15a00139a2691ddf9df7dce` archives before the unchanged
shared offline guard; production verifiers still reread them.

Static checks confirmed the selector/import/guard owners and preserved all
93 original assert/refusal nodes; this is not a claim that all ran. No validator
verdict, source identity, signature, rematerialization, CAS ambiguity or cleanup
assertion was replaced. Production adapter/controller/runtime, workflow,
HF/auth code, registrations,
frozen 30-cell pins and old validators remain byte-identical to `6038eb0c`.
The earlier conditional shared-branch/OIDC design decision was not reopened.

### Separate observations

| Source | Operation | Actual result |
| --- | --- | --- |
| `6038eb0cf01b372c874e0c824a3750e118f9ac35` | Original single selector | 1 collected, 1 failed in 2.65s; exit 1. Later integration assertions were not reached. |
| `6038eb0cf01b372c874e0c824a3750e118f9ac35` plus a diagnostic guard wrapper | One archive-only probe, not pytest | First refusal was `time.sleep` in `_wait`; exit 2. No input verification or integration result. |
| `3be7160b08969689035aa886f975c43b89a1dbe6` | Authorized fresh single selector | 1 collected, 1 failed in 60.80s; exit 1. Guarded archive re-verification failed. |
| `933d07573d997af43ba6427ce323a329ebe40dc7` | Metadata-reap compatibility selector | 1 collected, 1 failed in 64.15s; exit 1. Git re-verification completed; the historical Python serializer's timed reap hit the retained sleep guard. |
| `6c33c2bd960574d827bb4983c2b904ff049f6210` | Complete allowlisted-wait selector | 1 collected, 1 failed in 168.90s; exit 1. Preparation/staging completed; an authority-response refusal was converted to a different exception category. |

The prior stopped handoffs remain at this same record path in local commits
`3be7160b08969689035aa886f975c43b89a1dbe6`,
`933d07573d997af43ba6427ce323a329ebe40dc7` and
`6c33c2bd960574d827bb4983c2b904ff049f6210`. Their log identities and session
artifacts are preserved. All three earlier pytest invocations stopped before
packet/staging, approval, CAS or owned-child assertions. The cause of the prior
`ENOSYS` beyond the pidfd call remains undetermined; no kernel or container
investigation was performed. The separate archive-only probe identified
`time.sleep` in `subprocess.py:1953:_wait` through `_git`, `archive_bytes` and
`materialize_archive`; it raised before sleeping and was not a validation pass.

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

The new invocation stopped in the approval/OIDC refusal loop at
`test_codex_retention_ci.py:566`. Its safe traceback ends with:

```text
codex_retention_ci.py:700:execute -> codex_retention_ci.py:333:verify_approval -> codex_retention_ci.py:207:github -> codex_retention_ci.py:188:_authority_json -> contextlib.py:153:__exit__ -> codex_ci_input_intake.py:117:_response
codex_ci_input_intake.InputIntakeRefused: private_input_verification_or_transport_failed
```

Static tracing identifies the `redirect` negative. The fixture at line 225
returns HTTP 302, including for the GitHub metadata response. The real
`_authority_json` predicate at lines 190–191 requires the same URL and status
200, and raises `RetentionCIRefused("github_authority_origin_or_status_refused")`.
That class inherits `ValueError`; the enclosing `_response` context catches
it at lines 112–117 and converts it to the generic `InputIntakeRefused` above.
The test expects the original adapter category. This is a different boundary
from child reaping; no production change or assertion relaxation was made.
The new pytest log has SHA256
`a106b811aa3a63ac9aab7c9fbb025171347504647f476b27aafd115bf9c4ba78`.

Real archive verification, original-input serialization, schema4 packet and
materialized-grader verification, Step2 staging, independent rematerialization
and request equality checks completed. The input-role fingerprint assertion
matched `40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38`.
No final materialized-grader digest was emitted by this failed invocation.
Missing/wrong authority, source/cell/input/staging and preceding
approval/job-origin negative checks completed using real validators and
simulated service responses.

Later issuance-credential/origin checks, CAS conflicts/ambiguity, deadline and
replay checks, terminal reconciliation, cleanup and the harmless owned child
were not reached. Neither were the final child-category/reaped assertions or
legacy-refusal checks. Supervisor wait coverage is therefore static only.
No first-cell inference slot was reserved or durable cell clock started. No
post-failure output cleanup or reuse was attempted.

### Remaining gates

The authority-response exception-category boundary needs separate direction;
production remains frozen at `6038eb0c`. Full integration validation, new-source
review and CI remain required. Neither prior base review nor the diagnostic
probe approves this adapter. The leader must separately bind reviewed source,
host/runtime, inputs, spend scope and the registered ordinal-0 cell before any
launch.

No workflow dispatch, external environment approval, live CAS, HF/OIDC/Azure,
model, grade or paid operation occurred. The same-branch protocol and unchanged
eight-cell design remain unvalidated for live use. Protected im-not-ai-en was
applied only to the current English records, preserving the separate failed
observations, diagnostic status and limits.
