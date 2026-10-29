# Native workflows: guarded Ubuntu 24.04 migration

Local change on `leader/runner-receipt-20261029`, based on
`3f31968e5482a17d66e9b1b23c90815c0c79dda5` (parent `cf1401e1c`). The owner chose
GitHub-hosted Ubuntu 24.04 on 2026-10-29 at 09:20; NAS is development/dry-run only.
This change migrates the connection diagnostic and **Codex mode only** in
`batch-run.yml`. Other batch modes retain their existing runner expression.
No model, Azure request, credential lookup, dispatch, push or PR was performed
for this branch. Publication and the pilot-specific Actions connection remain
separate decisions/work.

## Why unprepared 24.04 failed

`docs/codex_sandbox_hosts.json` records the actual unprepared survey from
run **34202380505**: Ubuntu 24.04 had
`kernel.apparmor_restrict_unprivileged_userns=1`; bubblewrap failed with
`Failed RTM_NEWADDR: Operation not permitted`. That is an AppArmor policy wall,
not the NAS's different kernel-without-user-namespaces wall. The original
`hosts` object is preserved exactly: its sorted JSON SHA256 before and after
is `577a14c8f796b3ab9f18bea126520a6be4dcb039f9dab2130945b57e4dcebb9a`.
The new `execution_policy` object is prospective, with
`prepared_host_observation=not_yet_measured_on_Actions`; it does not relabel
the old failure as a newly measured success. The old 22.04 survey control stays.

Sources fetched without authentication on 2026-10-29:

- [Ubuntu 24.04 release notes, unprivileged user namespace restrictions](https://discourse.ubuntu.com/t/ubuntu-24-04-lts-noble-numbat-release-notes/39890): unconfined unprivileged programs can create a namespace but lose capabilities inside it; the documented targeted option is an AppArmor `flags=(unconfined)` profile granting `userns,`. The notes also describe the broader system-wide sysctl option; **this implementation does not use it**.
- [Ubuntu AppArmor documentation, common commands](https://ubuntu.com/server/docs/how-to/security/apparmor/#common-commands): `apparmor_parser -a` adds a profile from standard input; `-r` replaces one. This implementation uses add only, never replacement or a persistent `/etc` file.
- [Official OpenAI CLI documentation, Linux sandbox](https://learn.chatgpt.com/docs/developer-commands?surface=cli#linux-sandbox), reached via `https://developers.openai.com/codex/cli/reference/`: the local `sandbox` command executes a supplied program through bubblewrap/seccomp, with the program after `--`. Current documentation is not proof that the pinned binary succeeds on a particular image; the same-job marker check below is required.

The installed `openai-codex` and `openai-codex-cli-bin` packages remain
**0.147.0**. `--version` returned `codex-cli 0.147.0`. A local, empty-environment
`sandbox linux --help` inspection attempted namespace setup and returned the
NAS kernel refusal rather than help. It was not a model or benchmark call and
changed no host permission. No successful sandbox execution is claimed from
NAS, and no real sudo/profile loader is run by the new fixtures.

## Pre-call order and refusal contract

1. Require the existing real-OS/metadata admission, **GitHub-hosted 24.04**,
   an unprivileged UID and an existing runner temporary directory. Native
   receipt fields/schema stay `native-runner-evidence-v1`. The separate,
   explicitly approved Azure VM admission remains unchanged (Ubuntu 22.04 or
   24.04 plus matching Microsoft DMI); this hosted-only preparer refuses Azure.
2. Require SDK/CLI 0.147.0, check the binary's version, and require the selected
   system `/usr/bin/bwrap` to be root-owned, executable, not group/world-writable
   and not setuid/setgid. Record its SHA256.
3. Run the existing namespace geometry (`--unshare-user --unshare-net
   --ro-bind / / /bin/true`). If it already succeeds, add no profile. If it fails
   and the recorded restriction is `1`, add only the fixed
   `gdpval_codex_bwrap /usr/bin/bwrap` profile granting `userns,`. A loader error
   refuses the job; it never falls back to clearing a sysctl, replacing a
   profile, adding capabilities, disabling isolation or legacy Landlock.
4. Require the full bubblewrap probe and the pinned CLI's local sandbox command
   to succeed. The latter runs `/usr/bin/printf CODEX_SANDBOX_PREFLIGHT_OK` in
   fresh HOME/config/cache/state directories with a credential-free environment;
   exact marker output is mandatory. Exit zero or help text alone is not proof.
   Each subprocess has a 20-second timeout; temporary CLI state is removed.
5. Recheck unchanged restriction value, bwrap selection/hash and runner identity.
   Write the pre-call report, then run the existing host diagnostic again.
   Both workflows place these checks **before their first Azure identity/login
   step**. Failure, unknown state or an unwritable report exits nonzero and
   cannot reach a model request.

The report is `native-sandbox-preflight-v1`, with top-level refusal code
`codex_sandbox_preflight_refused`, a fixed stage-specific detail, runner receipt,
probe exits, marker verification, profile/binary hashes and before/after policy
observations. Raw subprocess output and exception messages are not published.
Unread policy change stays null, not false. The dedicated artifact step runs
on failure too, requires the file, and retains it for seven days. These are
**sandbox admission facts**, not served-model, Max, 1M or billing evidence.

## Design boundary

The `experiment-design` check treats the OS plus targeted AppArmor setup as one
new execution condition, not an OS-only performance comparison. A workflow
setting is intent; only the same-job probes can establish sandbox readiness.
The OpenAI Docs check supports the sandbox-command purpose, not a claim of
version/image compatibility. SDK/model/effort/context, all token/request/time
limits, **USD 200**, prompts, rubrics and score denominators are unchanged.
Fixtures are synthetic and cannot establish any five-task score or cost parity.

Existing sealed plans, registrations, cap/price records and grade/cost schema
files are untouched. The preceding branch already had source-pin mismatches;
these workflow changes and the new preparer need reviewed source inclusion.
No hash validation or preflight refusal is weakened to clear that pending work.

## Verification and handoff

The complete selected related invocation and development diagnostics are under
`/tmp/p5-native-ubuntu24.zLRltk/`; `verified.log` and `verified.xml` are the final
invocation: **428 passed / 0 failed / 0 errors / 0 skipped**, **22.02 seconds**,
exit **0**, not a sum of repeated runs. It covers the new preparer, existing
host classification and workflow contracts, runner admission/receipts,
connection diagnostics, grader guard parity, workflow step references, model
control bytes and workspace rules. Integration/model cases are not selected.

Preliminary runs are retained separately: 48 passes before the marker check;
then 412 passes/16 failures (ignored new script, a missing synthetic runner
fixture, and env-i without a run root), then 427 passes/1 tracking failure
before the script was staged. The fixes are an explicit ignore exception,
the existing fake-host fixture and isolated test directories; assertions and
production refusals are not weakened.

The final invocation used the existing isolated Python environment, `env -i`,
offline HF flags, an explicit `GDPVAL_CODEX_RUN_ROOT` outside its own isolated
`TMPDIR`, and a 600-second command timeout. It selected these files together:

```text
test_codex_ubuntu24_preflight.py
test_codex_sandbox_host_diagnosis.py
test_the_codex_batch_lands_on_a_host_that_can_isolate.py
test_gpt56_runner_environment.py
test_codex_foundry_connection_probe.py
test_gpt56_grader_guard_scope.py
test_a_step_reference_that_names_nothing.py
test_codex_requested_model_controls.py
test_codex_run_root.py
test_an_experiment_can_ask_for_the_codex_run_place.py
```

Actions must still confirm that its installed AppArmor parser/profile attachment,
system bwrap and **pinned** CLI marker path work together on the current image.
A conflicting pre-existing profile, missing parser, changed namespace policy,
or CLI/helper-path incompatibility stays fail-closed. No Actions run was
dispatched and no hosted sandbox success is claimed by this local commit.

Changed-file inventory (16 files):

- `.github/workflows/batch-run.yml`
- `.github/workflows/codex-foundry-connection-diagnostic.yml`
- `.gitignore`
- `batch-runner/core/runner_environment.py`
- `batch-runner/docs/codex_sandbox_hosts.json`
- `batch-runner/docs/native_ubuntu24_migration_20261029.md`
- `batch-runner/scripts/prepare_codex_sandbox_host.py`
- `batch-runner/tests/conftest.py`
- `batch-runner/tests/grader_guard_scope_probe.py`
- `batch-runner/tests/test_codex_foundry_connection_probe.py`
- `batch-runner/tests/test_codex_requested_model_controls.py`
- `batch-runner/tests/test_codex_ubuntu24_preflight.py`
- `batch-runner/tests/test_gpt56_runner_environment.py`
- `batch-runner/tests/test_the_codex_batch_lands_on_a_host_that_can_isolate.py`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`
