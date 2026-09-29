# Latest task result

## PROJECT5-METADATA-REAP-COMPAT

The one authorized selector failed at
`933d07573d997af43ba6427ce323a329ebe40dc7`: 1 collected, 1 failed in 64.15s,
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

The earlier archive-only probe identified `time.sleep` at
`subprocess.py:1953:_wait`, reached through
`gpt54_disposable_checkout.py:97:_git`,
`codex_retention_historical.py:115:archive_bytes` and
`codex_retention_historical.py:123:materialize_archive`. It raised before
sleeping and used no private inputs. That diagnostic was not pytest, a
validation pass or a GitHub CI result; it was not repeated here.

Only `tests/test_codex_retention_ci.py` changed beyond the two records. The
pidfd override was removed. All children use normal bounded
`subprocess.run` / `communicate` / `wait`, including their existing failure
and timeout cleanup. Explicit fixture ordering still constructs both genuine
immutable `8ac891e3e0e4752fe15a00139a2691ddf9df7dce` archives before the
unchanged shared offline guard; production verifiers still reread them.

The test-local sleep exception checks exact stdlib code frames, the active
`run` frame, owned `Popen` identity, full argv and cwd binding, and the original
60-second Git timeout. The requested sleep duration is capped at the time
remaining before the original communicate deadline. The same active frame
requirement excludes other threads and later waits on the object. The guard
refused both a direct sleep and a nonallowlisted bare Python command before
either could sleep or start a child. Historical Python metadata scripts and
the owned supervisor receive no sleep exception; `time.sleep` is never
globally restored.

Static checks confirmed the selector/import/guard owners and preserved all
93 original assert/refusal nodes; this is not a claim that all ran. No validator
verdict, source identity, signature, rematerialization, CAS ambiguity or cleanup
assertion was replaced.
Production adapter/controller/runtime, workflow, HF/auth code, registrations,
frozen 30-cell pins and old validators remain byte-identical to `6038eb0c`.
The earlier conditional shared-branch/OIDC design decision was not reopened.

### Separate observations

| Source | Operation | Actual result |
| --- | --- | --- |
| `6038eb0cf01b372c874e0c824a3750e118f9ac35` | Original single selector | 1 collected, 1 failed in 2.65s; exit 1. Later integration assertions were not reached. |
| `6038eb0cf01b372c874e0c824a3750e118f9ac35` plus a diagnostic guard wrapper | One archive-only probe, not pytest | First refusal was `time.sleep` in `_wait`; exit 2. No input verification or integration result. |
| `3be7160b08969689035aa886f975c43b89a1dbe6` | Authorized fresh single selector | 1 collected, 1 failed in 60.80s; exit 1. Guarded archive re-verification failed. |
| `933d07573d997af43ba6427ce323a329ebe40dc7` | Metadata-reap compatibility selector | 1 collected, 1 failed in 64.15s; exit 1. Git re-verification completed; the historical Python serializer's timed reap hit the retained sleep guard. |

The prior stopped handoffs remain at this same record path in local commits
`3be7160b08969689035aa886f975c43b89a1dbe6` and
`933d07573d997af43ba6427ce323a329ebe40dc7`. Their log identities and session
artifacts are preserved. Neither earlier pytest invocation reached
packet/staging, approval, CAS or owned-child assertions. The cause of the prior
`ENOSYS` beyond the pidfd call remains undetermined; no kernel or container
investigation was performed.

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

The new invocation reported the following safe diagnostic:

```text
dispatcher regression crossed a live boundary
genuine_offline_original_five_serializer: AssertionError at test_codex_retention_ci.py:52:positive -> test_codex_retention_ci.py:418:<lambda> -> codex_retention_historical.py:228:materialize_originals -> codex_retention_historical.py:183:_command -> subprocess.py:505:run -> subprocess.py:1154:communicate -> subprocess.py:2047:_communicate -> subprocess.py:1209:wait -> subprocess.py:1953:_wait -> test_codex_retention_ci.py:311:metadata_wait_sleep -> test_codex_budget_pilot.py:52:forbidden
```

The guarded symbol was `time.sleep`, immediately called by stdlib
`Popen._wait` for the fixed historical Python serializer, not a tracked Git
child. The exception was not broadened. The new pytest log has SHA256
`c867ebce2dfeb87967d34d53b2af19d2c5a1b7fc6fe5bfa47eac24ee632779c0`.

Both immutable archive fixtures were constructed. Guarded Git archive
verification and the unexpected-module refusal completed. The real historical
Python metadata child started but its call did not return a verified result.
Packet/staging/input attestation and materialized-grader verification were
not reached. Neither were the simulated approval/CAS/clock/cleanup/publication
cases or the test-owned Python `pass` payload. Prior input evidence is not a
new result; no materialized identity is claimed for this invocation.

### Remaining gates

The historical Python serializer's bounded reap is outside the authorized
Git-only sleep exception. Further work on that offline boundary needs separate
authorization. Full new-source review and CI remain required; neither prior
base review nor the diagnostic probe approves this
adapter. The leader must separately bind reviewed source, host/runtime, inputs,
spend scope and the registered ordinal-0 cell before any launch.

No workflow dispatch, external environment approval, live CAS, HF/OIDC/Azure,
model, grade or paid operation occurred. The same-branch protocol and unchanged
eight-cell design remain unvalidated for live use. Protected im-not-ai-en was
applied only to the current English records, preserving the separate failed
observations, diagnostic status and limits.
