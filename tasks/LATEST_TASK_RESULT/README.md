# Latest task result

## PROJECT5-ARCHIVE-GUARD-ROOT-FIX

The authorized follow-up selector failed at
`3be7160b08969689035aa886f975c43b89a1dbe6`: 1 collected, 1 failed in 60.80s,
exit 1. Code work stopped after that invocation. There was no further retry,
push or new PR. These two completion-record updates remain uncommitted.

Branch `b/codex-retention-ci-cas-20260929` starts at exact base
`6aa34a2f393f877da7b8f95e1dcd7bb00077a3fb`, tree
`d571030bbb04fe82726d39d6876982e0ca97bcc8`. The leader reported 10 passing
checks at reviewed `71b3a8274bc6282e8cbc6842303cdb76df54cadb` /
[review 5349547201](https://github.com/hyeonsangjeon/gdpval-realworks/pull/701#pullrequestreview-5349547201).
That review covers the base, not this adapter or fixture correction. The prior
26.20s and 6.62s observations remain separate in the
[immutable controller handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/6aa34a2f393f877da7b8f95e1dcd7bb00077a3fb/tasks/LATEST_TASK_RESULT/README.md).
Neither selector was replayed.

### Cause and test-only correction

The original log identified only `immutable_historical_archive` and the shared
guard at `test_codex_budget_pilot.py:52:forbidden`. Static inspection narrowed
the call chain, then the one authorized archive-only probe identified guarded
`time.sleep` at `subprocess.py:1953:_wait`. Its callers were
`gpt54_disposable_checkout.py:97:_git`,
`codex_retention_historical.py:115:archive_bytes` and
`codex_retention_historical.py:123:materialize_archive`; the executable was
`git`. The guard raised before sleeping. This separate diagnostic used no
private inputs and was not a validation pass or a GitHub CI result.

Only `tests/test_codex_retention_ci.py` changed beyond the two records. An
explicit fixture dependency constructs both genuine immutable
`8ac891e3e0e4752fe15a00139a2691ddf9df7dce` archives before installing the
unchanged shared offline guard. Later production verifiers still read the
real archives through Git. Because those reads also use a timed reap, the
already-allowlisted metadata transport now uses a bounded pidfd wait. It does
not restore `time.sleep` or change the real owned supervisor. The correction
remains unvalidated because the fresh invocation failed in this guarded
re-verification path.

Static checks confirmed the selector/import/guard owners and preserved all
93 original assert/refusal nodes. No validator verdict, source identity,
signature, rematerialization, CAS ambiguity or cleanup assertion was replaced.
Production adapter/controller/runtime, workflow, HF/auth code, registrations,
frozen 30-cell pins and old validators remain byte-identical to `6038eb0c`.
The earlier conditional shared-branch/OIDC design decision was not reopened.

### Separate observations

| Source | Operation | Actual result |
| --- | --- | --- |
| `6038eb0cf01b372c874e0c824a3750e118f9ac35` | Original single selector | 1 collected, 1 failed in 2.65s; exit 1. Later integration assertions were not reached. |
| `6038eb0cf01b372c874e0c824a3750e118f9ac35` plus a diagnostic guard wrapper | One archive-only probe, not pytest | First refusal was `time.sleep` in `_wait`; exit 2. No input verification or integration result. |
| `3be7160b08969689035aa886f975c43b89a1dbe6` | Authorized fresh single selector | 1 collected, 1 failed in 60.80s; exit 1. Guarded archive re-verification failed. |

The previously uncommitted stopped-integration record is preserved in local
commit `3be7160b08969689035aa886f975c43b89a1dbe6` at this same record path.
It preserves the original failure log identity and the limits known then.

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

The fresh invocation reported:

```text
[Errno 38] Function not implemented
bounded local Git command failed
guarded_immutable_historical_archive: DisposableCheckoutRefused at test_codex_retention_ci.py:68:positive -> test_codex_retention_ci.py:374:<lambda> -> codex_retention_historical.py:145:verify_archive -> codex_retention_historical.py:115:archive_bytes -> gpt54_disposable_checkout.py:102:_git
```

The test-only `MetadataProcess._wait` calls `os.pidfd_open` at line 57; the new
path encountered `ENOSYS`. No second probe, fallback or guard relaxation was
attempted. The diagnostic log has SHA256
`c34f505382f5a3a27cb75907965854ce849f62a08f16a56caeeeaec5d5f42b94`;
the fresh pytest log has SHA256
`4a0dd8930e599c3f15a56100ad5534f8619759fdea03be59ce63173be1835d43`.

Both immutable archive fixtures were constructed. Real packet/staging/input
attestation and materialized-grader verification were not reached. Neither
were the simulated approval/CAS/clock/cleanup/publication cases or the planned
test-owned Python `pass` payload. Prior input evidence is not a new result.

### Remaining gates

The test-only metadata reaping boundary needs a bounded compatibility repair
before integration validation can resume. Full new-source review and CI remain
required; neither prior base review nor the diagnostic probe approves this
adapter. The leader must separately bind reviewed source, host/runtime, inputs,
spend scope and the registered ordinal-0 cell before any launch.

No workflow dispatch, external environment approval, live CAS, HF/OIDC/Azure,
model, grade or paid operation occurred. The same-branch protocol and unchanged
eight-cell design remain unvalidated for live use. Protected im-not-ai-en was
applied only to the current English records, preserving the distinct failed
observations, diagnostic status and limits.
