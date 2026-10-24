# Latest task result

## Archived native-pilot deployment comparison, local only (2026-10-24)

Scope: retrieve and hash-check the existing connection diagnostic, compare all
five-task native-pilot deployment references, and trace the historical
`gpt-5.4` baseline without Azure/model calls, dispatch, grading or push.
Worktree: `/ai-work/copilot/_tmp_worktrees/gpt56-native-pilot-caps-20261024`;
branch: `codex/gpt56-native-pilot-caps-20261024`; starting head:
`a49496afe`. Tested evidence/test commit:
`9a31015526c0577b69f6f56e7704fd379a31e270`.
This is an inspected/tested head, not independently reviewed execution source.
No new reviewed head or launch approval is established.

### Artifact and comparison

GitHub artifact metadata confirms artifact `12257312458`
(`codex-foundry-connection`) belongs to run `39407062120`.
The downloaded ZIP SHA256 matches the required
`5d1a2540f0ba1291093b231d0e12e489ca197c32683aee521fb1622893600841`.
The archive and extracted JSON remain in scratch directory
`/ai-work/copilot/_tmp/p5-conn-artifact-12257312458`, not Git.

Both archived JSON files request deployment `gpt-5.6-sol`; the connection
result is `connected`, with 9,444 input / 5 output tokens. Pinned and installed
SDK/CLI versions are all `0.147.0`. The route is `direct-v1`, provider
`gdpval-foundry`, path `/openai/v1/`, host fingerprint
`sha256:69057d59166a82e3`. Raw host, account/project/deployment resource IDs
and served-model/version are not recorded. In particular, a successful reply
does not establish the served model; the archived `served_model` is null.

| Reference | Comparison with archived requested deployment |
| --- | --- |
| Cap requested name | Match: `gpt-5.6-sol` |
| Source registration and preflight model labels | Match: `gpt-5.6-sol`; SDK/CLI also match |
| Registration/preflight actual deployment | Unbound: null, not a confirmed live match |
| Generated runtime template | Unbound: deployment/execution null, not runnable |
| Diagnostic workflow | Required explicit input, no default; archived settings match the requested name |
| Generic batch workflow | Required selected experiment; reads its Azure deployment, no pilot/default deployment |
| Historical baseline, both deployment fields | Mismatch: `gpt-5.4`; not inherited by the pilot |

### Baseline reachability

**No baseline-deployment fallback reaches the registered native pilot.**
The cap YAML records the full file:line trace:

- `experiments/exp035_codex_foundry_full220.yaml:584,622` under `batch-runner/`
  contains the historical values. Preflight reads that baseline at
  `gpt56_sol_codex_pilot_preflight.py:381`, but constructs model/identity
  separately at `403-445`; only prompt, limits and output are taken from it
  at `471-504`.
- `gpt56_pilot_config_bundle.py:90-114` requires an inert null-deployment,
  null-execution template. The unchanged parser rejects it before setup.
- `gpt56_sol_codex_pilot_preflight.py:795-811` retains the deployment blocker
  when the binding is omitted and refuses incomplete explicit arguments.
- `gpt56_pilot_deployment_binding.py:184-236` requires explicit resource
  files matched to identity-evidence hashes. Its fresh candidate writes that
  resource's deployment suffix into both model fields at `126-165`;
  it does not copy the baseline or substitute its deployment on omission.
- `.github/workflows/batch-run.yml:8-11,605-622` requires an explicitly
  selected experiment and nonempty Azure deployment. Manually selecting the
  historical baseline would run that baseline, not materialize the pilot.
  The diagnostic input/forwarding is explicit at
  `codex-foundry-connection-diagnostic.yml:82-85,251-255`.

No new production guard is needed for this residue. The cap findings and
regression assertions were updated; sealed plans, source pins, historical
baseline, runtime, workflows, grader and execution rights are unchanged.
Deployment names are resource labels, not proof of a served model.

### Verification

At clean head `9a31015526c0577b69f6f56e7704fd379a31e270`, **408 passed,
0 failed (177.19s)** with an empty inherited environment, explicit
PATH/HOME/user-package PYTHONPATH, offline Hub/dataset settings, disabled
plugin autoload and no pytest cache:

```text
python3 -m pytest -m "not integration" -o addopts= -p no:cacheprovider --tb=short -q
  tests/test_gpt56_pilot_caps_draft.py
  tests/test_sol_source_registration.py
  tests/test_gpt56_sol_codex_pilot_preflight.py::test_active_grader_template_source_foundry_preflight
  tests/test_gpt56_sol_codex_pilot_preflight.py::test_gpt56_sol_foundry_pilot_is_pinned_and_fails_closed
  tests/test_gpt56_pilot_config_bundle.py
  tests/test_gpt56_pilot_deployment_binding.py
```

The real source-registration guard passed without weakening its clean-worktree
check. Existing tests cover inert-template parser/entrypoint rejection,
omitted/partial binding refusal and explicit candidate deployment equality.
A separate direct comparison checked both archived JSON hashes, settings,
versions, null served identity and connection usage against the cap record.
The first broader invocation was interrupted during unrelated runtime-cap
tests, with no failure reported; only the completed focused run is counted.
The completion-record commit follows this validation and changes only records.

### Remaining work and boundary

Owner approval of provisional noncurrency caps and a USD cap; independently
verified account/deployment resource binding, served-model/version and Max/Long
evidence; native request counting and cumulative hard enforcement; frozen-grader,
prepared-input and live wire/host/usage gates; independent final-source review.
Archived settings do not clear these requirements. This step used only free
GitHub artifact reads and local operations. No Azure/model call, workflow
dispatch, grading, push, merge or execution approval occurred.
