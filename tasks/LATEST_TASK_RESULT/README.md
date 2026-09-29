# Latest task result

## PROJECT5-AUTHORITY-REFUSAL-BOUNDARY

The single authorized offline selector passed at
`da0fb6bea28826c9287adaff95e6d4daf8996642`: 1 collected, 1 passed in 295.37s,
exit 0. No retry, additional selector or live authority request was run. This is local
integration evidence, not external source approval or launch authority.

Branch `b/codex-retention-ci-cas-20260929` starts at exact base
`6aa34a2f393f877da7b8f95e1dcd7bb00077a3fb`, tree
`d571030bbb04fe82726d39d6876982e0ca97bcc8`. The leader reported 10 passing
checks at reviewed `71b3a8274bc6282e8cbc6842303cdb76df54cadb` /
[review 5349547201](https://github.com/hyeonsangjeon/gdpval-realworks/pull/701#pullrequestreview-5349547201).
That review covers the base, not this adapter. The prior
26.20s and 6.62s observations remain separate in the
[immutable controller handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/6aa34a2f393f877da7b8f95e1dcd7bb00077a3fb/tasks/LATEST_TASK_RESULT/README.md).
Neither selector was replayed.

### Correction and retained guards

A bounded auth review approved the exception-lifetime correction with
conditions before editing. It did not reopen the architecture or approve a
live source. Only `LocalTransport._authority_json` changed in production.
It now records the existing origin/status or pagination refusal inside the
transport context, leaves the refused body unread, and raises
`RetentionCIRefused` after successful closure. Acquisition, header, bounded-read
and close failures still pass through the unchanged intake privacy guard.
JSON parsing remains outside the context.

The original HTTP 302 negative now preserves
`github_authority_origin_or_status_refused` before claim, clock or child creation.
The focused regression also checks closure without reads for foreign-origin
and pagination refusals, closure on success and malformed JSON, and exact
`private_input_verification_or_transport_failed` refusals for acquisition,
read and close failures. A close failure on a refused redirect remains a
transport failure; no domain decision masks it.

The shared intake helper, all legacy callers/validators, workflow, runtime,
compiler/preparer, registrations and frozen 30-cell pins remain byte-identical
to `6038eb0cf01b372c874e0c824a3750e118f9ac35`. The completed exact-command
wait registry and guard bodies remain unchanged from `6c33c2bd`. Static
comparison preserves all 93 original assertion/refusal nodes and all 115
nodes from the preceding test version; these are not runtime pass counts.
The existing eight-cell study and ordinal-0-only execution scope are unchanged.

### Validation and separate observations

| Tested source | Operation | Actual result |
| --- | --- | --- |
| `6038eb0cf01b372c874e0c824a3750e118f9ac35` | Original single selector | 1 collected, 1 failed in 2.65s; exit 1. Archive guard failure; later integration assertions not reached. |
| `6038eb0cf01b372c874e0c824a3750e118f9ac35` plus a diagnostic guard wrapper | One archive-only probe, not pytest | Exit 2. Identified `time.sleep` in `subprocess.py:1953:_wait` through `_git`, `archive_bytes` and `materialize_archive`; raised before sleeping. No validation pass. |
| `3be7160b08969689035aa886f975c43b89a1dbe6` | Fresh single selector | 1 collected, 1 failed in 60.80s; exit 1. Introduced pidfd path raised `ENOSYS` during archive re-verification. Later integration assertions not reached. |
| `933d07573d997af43ba6427ce323a329ebe40dc7` | Metadata-reap compatibility selector | 1 collected, 1 failed in 64.15s; exit 1. Git verification and unexpected-module refusal completed; historical serialization hit the then-Git-only sleep guard. Packet and later assertions not reached. |
| `6c33c2bd960574d827bb4983c2b904ff049f6210` | Allowlisted-wait selector | 1 collected, 1 failed in 168.90s; exit 1. Real preparation, staging, independent rematerialization and preceding approval/job-origin negatives completed. The 302 domain refusal became an intake transport refusal. CAS, deadline/replay, terminal cleanup and harmless owned child not reached. |
| `da0fb6bea28826c9287adaff95e6d4daf8996642` | Authority-response boundary selector | 1 collected, 1 passed in 295.37s; exit 0. New closure/refusal regressions and the later integration assertions completed. |

The five prior observations, log identities and reached/unreached boundaries
remain in the
[immutable preceding handoff](https://github.com/hyeonsangjeon/gdpval-realworks/blob/da0fb6bea28826c9287adaff95e6d4daf8996642/tasks/LATEST_TASK_RESULT/README.md)
and its earlier commit references. No historical result was reclassified. The
cause of `ENOSYS` beyond the pidfd call remains undetermined; no infrastructure
investigation was performed. Session artifacts remain intact. The six exact
ignored output roles left by the preceding test were moved to private session
storage before the fresh no-clobber run; nothing was deleted or reused as new
verification evidence.

Run once from `batch-runner` in the existing isolated environment. Only the
private handoff value is redacted; it was present and the test did not skip.

```bash
env -i PATH=/ai-work/venvs/gdpval-realworks-py310/bin:/usr/bin:/bin \
  LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  GDPVAL_RETENTION_PREPARED_HANDOFF='<known private handoff>' \
  /ai-work/venvs/gdpval-realworks-py310/bin/python -m pytest \
  -p no:cacheprovider --tb=short -s \
  tests/test_codex_retention_ci.py::test_retention_ci_grant_cas_and_owned_runtime_are_bound
```

### Real evidence and simulated boundaries

Real archive/source verification, original-input serialization, schema4
attestation, packet/config/grader readback, Step2 staging and independent
rematerialization completed. The run and retained log have these identities:

```text
original_input_roles_sha256=40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38
materialized_grader_source_sha256=c391424e7ff45f375c6bb17135440aab85b29748fa0c52215805594a1517a320
adapter_source_sha256=3490cb63af1cf078965768d93b972f3218353e78574175a837afe248e2a47e03
request_sha256=30ebe664643bd180fe9f46a4e3a5d8a052d6f774d2b6422f2b597b118da9b5df
pytest_log_sha256=b218de2e44bd421409805cb0a715009c669832fea4d6c87427fa03d7104a90dc
```

GitHub/Azure/HF responses, RSA provider keys and remote CAS were simulated;
the signature, source, approval, claim/history and cleanup validators were real.
CAS conflict/unknown-ack, duplicate/replay, ambiguous-start, unconfirmed-cleanup,
output/terminal-ack and terminal-reconciliation checks completed. Durable clock
restart behavior used the real store with an injected test clock. The real
owned supervisor launched only the fixed test-owned Python `pass` payload.
Its missing result remained failed with a null grade, and model invocations
were 0. These facts do not attest a live provider or reserve a live cell.
The final assertions also checked legacy refusals, retained general-sleep and
command guards, and reaping of every registered local child.

### Remaining gates

The new source and records delta still need leader review and CI. The adapter
identity above is a byte identity, not approval. Before any launch, the leader
must separately bind reviewed source, host/runtime/deployment, verified inputs,
finite time/spend scope and the registered ordinal-0 cell. Real protected-job
approval, same-deployment serial CAS consumption and live cleanup/terminal
reconciliation remain unverified. Original inputs and outcomes remain untouched.

No workflow dispatch, external environment approval, live CAS, HF/OIDC/Azure
request, credential operation, model, grade or paid operation occurred. Protected
im-not-ai-en applies only to the current English records and preserves every
separate observation and limitation.
