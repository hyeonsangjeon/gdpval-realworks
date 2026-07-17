# Agentic Sandbox Experiment Plan

- Date: 2026-07-17
- Status: `PLAN_APPROVED_PENDING_MERGE`
- Plan base: `main@71902db3904a358e6f832caf8f39e807047f9bdf`
- Experiment family: task-solving / sandbox execution
- Comparison baseline: current `sandbox` execution mode
- Proposed treatment: new `agentic_sandbox` execution mode
- Paid execution: prohibited until the approval gate in this document is signed

## Why This Work Exists

The current sandbox can classify a failed attempt, feed bounded evidence back to
the model, and regenerate a complete solution. That recovery is useful, but the
orchestrator still decides the sequence: generate code, execute it, verify the
artifacts, then optionally ask for a replacement.

This experiment asks a narrower engineering question: can the model choose the
next safe action itself while the harness retains control of permissions, cost,
time, persistence, and final verification? The proposed solver may inspect the
workspace, inspect installed capabilities, execute Python or ffmpeg, inspect its
artifacts, and request deterministic finalization. It may not install packages,
open the network, become root, invoke a shell, or bypass artifact verification.

The plan is also the evidence ledger for the later retrospective. Design
changes, validation results, incidents, run IDs, cost decisions, and final
promotion decisions must be added here with immutable commit or run identity.

## Research Questions

1. Can a bounded model-directed tool loop improve verified task completion over
   the current generate-once-then-regenerate-once sandbox?
2. Does the loop reduce time to the first valid artifact, or only add model and
   tool overhead?
3. Which tool trajectories recover compile, schema, API, media, and artifact
   contract failures?
4. Can the system prove that no tool call escapes the task workspace, network
   boundary, resource limits, or approved cost budget?
5. Does external grading remain non-inferior on an identical paired task set?
6. Which capabilities are genuinely missing from the image and would justify a
   separate offline package-broker experiment?

## Baseline Facts

- The current `sandbox` defaults remain unchanged. The paired baseline keeps
   its current bounded full-regeneration semantics and opts into the
   experiment's common hardened execution substrate. It fixes
   `repair.enabled: true` and `repair.max_attempts: 1`: one initial generation,
   then at most one complete regeneration with bounded reflection when
   deterministic blocking failures remain.
- exp026 completed 200/220 tasks with average Self-QA 6.24, but historical
  comparisons include model, prompt, runtime, and task-selection confounds.
- Job performance metrics are opt-in through
  `execution.metrics.enabled: true`; legacy experiments omit those keys.
- Existing sandbox execution uses Docker isolation, target-Python compile
  preflight, deterministic artifact verification, render QA, bounded repair,
  no network, non-root UID:GID, memory/swap/PID/CPU limits, and
  `no-new-privileges`.
- The grading `ToolCallingJudge` demonstrates a Responses API function-call
  loop, but it remains a grading component. The task solver will not import or
  mutate grading semantics.

## Architecture Decisions

### ADR-1: New Mode, Stable Baseline

Add `agentic_sandbox` as a separate execution mode. Do not turn the existing
`sandbox` mode into an agentic loop and do not change its defaults. Implement a
common hardened container supervisor that can run either the existing
generate-once-then-regenerate-once sandbox logic or the agentic loop. Every live comparison
runs a fresh sandbox-logic baseline and agentic treatment through the same
supervisor, image digest, UID, mounts, cgroups, outer seccomp, verifier, and
budget authority. Generated Python in both conditions uses the same launcher,
in-process syscall policy, and binary mediation. Only solver control flow,
tool exposure, tool prompt, and treatment's required `finalize` call differ.

### ADR-2: Provider Scope

The MVP supports Azure/OpenAI Responses API function calls only. Anthropic and
text-emulated tool calls are deferred because their continuation contracts and
accounting differ.

### ADR-3: Preinstalled Capabilities Only

The MVP does not execute `pip install`, `apt`, `sudo`, package-manager commands,
or network downloads. `inspect_environment` reports a checked-in capability
manifest derived from the pinned image. Missing capability requests are counted
and returned as bounded errors.

A future offline package broker is a separate experiment and requires a
checked-in allowlist, preloaded wheelhouse, hashes, non-root target directory,
package/count/size/time limits, and disabled dependency-index access.

### ADR-4: Persistent Workspace in One Disposable Task Container

One disposable container persists for exactly one solver invocation. Its
`/work` is a size-limited tmpfs, so generated state survives `docker exec`
calls without relying on an unbounded host bind mount. Reference files are
staged with read-only permissions and mounted under `/inputs:ro`.

Solver state, generated source, tool arguments, request history, and best
artifact snapshots remain in host-owned directories that are never mounted
into the container. Python source is streamed over stdin to a trusted launcher
baked into the read-only image. Verified artifacts are copied out to a
host-owned snapshot after inspection; the snapshot is never visible to later
model code. The task container is removed on every terminal path.

### ADR-4A: Split Credential and Compute Planes

The credentialed API control plane owns Responses requests, the transactional
budget ledger, and bounded solver state. It has no Docker socket, task-container
namespace, raw artifact mount, or artifact parser. A separate disposable
compute runner owns input staging, the task container, ffmpeg dispatch,
snapshot copying, and verifier containers. It has no model, cloud, HF, or
control-plane credentials and runs no concurrent workload. The two planes
exchange only versioned bounded command/result envelopes over an authenticated
channel. Model-originated values are schema-validated data, never host commands.
The compute runner may hold only a run-scoped, single-purpose, short-lived
mutual-authentication identity for that channel; it grants no provider, cloud,
HF, repository, artifact-store, or budget-ledger access and expires when the
runner is destroyed.

Every command envelope binds protocol version, paired run ID, condition,
task ID, monotonically increasing sequence, unpredictable one-use command
nonce, expiry, operation, and canonical payload digest. The result binds the
same fields plus the command-envelope digest and canonical result digest. Both
are authenticated by the run identity. The control plane accepts exactly the
next outstanding result once. Stale, duplicate, replayed, out-of-order,
unsolicited, expired, cross-run, cross-condition, cross-task, or digest-mismatched
envelopes fail closed without changing solver state or the budget ledger and
without permitting another model request.

If this split is unavailable, all non-paid tests may run with fakes but no live
request is permitted.

### ADR-5: Deterministic Completion

Plain assistant text cannot mark a task successful. The model must call
`finalize`, name its deliverables, and provide a concise summary. The harness
accepts completion only after contract validation, openability checks, render
QA, path checks, and artifact selection pass.

### ADR-6: Privacy-Preserving Observability

Persist counts, durations, hashes, stable error categories, usage, and bounded
status. Agentic observability stores artifact counts and aggregate hashes, not
generated filenames. Relative names appear only in the final deliverable list
required by the existing submission contract and are not copied into the
agentic metrics block. Do not persist model reasoning, raw code, raw tool
arguments, process output, image/base64 data, credentials, or absolute paths in
checkpoints, reports, or dashboard JSON.

## Security Invariants

Every tool and every test must preserve these invariants:

1. Container network is `none`; URL and network protocols are rejected.
2. The image declares a fixed unprivileged UID:GID (`65532:65532`). The
   launcher verifies the effective UID is nonzero; UID 0 is a pre-tool
   fail-closed error. Host UID propagation is not used for this mode.
3. Docker uses `--read-only`, `--cap-drop ALL`,
   `--security-opt no-new-privileges`, `--ipc=none`, a pinned seccomp profile,
   a private PID namespace, pinned procfs masks/read-only paths, two CPUs,
   8 GiB memory/swap, 128 PIDs, and `nofile=256:256`. Host PID mode is forbidden.
   No writable tmpfs is added except the quota-backed `/work` mount. Live use
   requires a patched ephemeral runner with enforce-mode AppArmor or SELinux
   and rootless Docker or user-namespace remapping; a model task never shares
   its compute runner with credentials, a Docker socket mount, or another
   workload.
4. `/work` is a 512 MiB tmpfs owned by UID 65532 with `nosuid,nodev,noexec`;
   `size=512m,nr_inodes=1024` is kernel-enforced. `HOME`, `TMPDIR`, XDG caches,
   fontconfig, matplotlib, Java, GDAL, and LibreOffice temp paths are private
   hidden subdirectories inside `/work`. Compute-runner swap must be disabled
   or encrypted. The root filesystem has no writable persistent location.
   Kernel pseudo-devices are nonpersistent and cannot become deliverables.
5. Inputs are copied into a dedicated staging tree containing regular files
   only. Symlinks, hardlinks, magic links, nested mounts, FIFOs, sockets, and
   device nodes are rejected before launch. The mount is `readonly,rprivate`;
   recursive read-only is required when supported. At most 256 files, 2 GiB
   total logical bytes, 512 MiB per file, depth 16, and 240 UTF-8 bytes per
   relative path are staged; an over-limit selected task fails eligibility
   before a model call. Inputs cannot be renamed, removed, or replaced.
   Absolute paths, `..`, symlink escape, other-task paths, and hidden workspace
   paths are rejected by compute-runner path validation.
   Each source and staged file is opened without following links and is bound
   to canonical relative path, regular-file type, link count one, logical and
   allocated size, SHA-256, and provider-specific transmission classification.
   A Merkle root over the exact sorted file records is fixed in selection,
   approval, staging, and command identities. Any source race, missing/extra
   file, type/link/size/hash drift, or unapproved classification aborts before
   credential release or model-client construction.
6. The dedicated image removes package-manager executables and Python package
   manager modules, download clients, compilers, SSH clients, and unneeded
   shells. Image construction fails if the forbidden executable/module audit
   finds any survivor.
7. The outer container seccomp permits only the process startup required by
   `docker exec`. `run_python` starts a trusted baked launcher with all imports
   and file descriptors prepared, sets `PR_SET_NO_NEW_PRIVS`, verifies the
   supported architecture, and applies a TSYNC in-process libseccomp filter
   before `exec(compile(source))`. Filter installation, architecture mismatch,
   or thread synchronization failure exits before one generated line runs. The
   filter denies `execve/execveat`, process-form `fork/vfork/clone/clone3`,
   signals to other processes, pidfd signaling, network sockets/connect,
   mount/namespace APIs, ptrace/process_vm, keyring, BPF, perf, userfaultfd, and
   io_uring. Only required thread-form clone flags are allowed. Python import
   hooks are defense in depth, not the security boundary.
8. ffmpeg runs only through the separate `run_ffmpeg` tool. The credentialed
   control plane validates the closed operation schema; the uncredentialed
   compute supervisor maps it to an argv list and invokes the pinned binary
   inside the task container. No shell parses model content, and no media parser
   executes in the credentialed control plane.
9. API/HF/cloud credentials and host environment variables are never mounted
   or inherited by tool containers.
10. Trusted startup probes verify the private PID namespace and pinned procfs
    policy, and prove PID 1 and each generated-code launcher have exactly file
    descriptors `0,1,2` with no inherited socket before generated code runs.
    After every tool call the compute supervisor verifies only PID 1 remains.
    Wall time, API calls, tokens, USD, process count, memory, CPU, output bytes,
    workspace bytes, file count, code size, argv size, tool-result size,
    summary size, stdout, and stderr are bounded before execution or request.
11. Before snapshot, all tool descendants must exit and the container is
   paused. The host copies to a new private staging tree, then uses `lstat`,
   mode/type/depth/count/logical-size/block-use/hash checks. The exact copied
   bytes are verified and submitted; `/work` is never recopied after
   verification. A failed later action cannot read or delete the host-owned
   best snapshot.
12. PDF, Office, image, and media parsing never occurs in a credentialed host
   process. A separate no-network, read-only, resource-limited verifier
   container parses the private snapshot and returns only bounded results. Its
   image digest, SBOM, seccomp, mandatory-access-control profile, UID, cgroups,
   mounts, and ulimits are pinned in the common substrate manifest.
13. Budget exhaustion, malformed calls, unexpected tools, missing usage, and
    verification uncertainty fail closed.
14. The solver and external grader use separate prompts, schemas, results, and
    budgets.

## MVP Tool Contract

All tool results use one of these envelopes:

```json
{"ok": true, "data": {}}
```

```json
{"ok": false, "error_type": "stable_category", "retryable": false}
```

### `inspect_workspace`

Returns bounded relative name, kind, and size metadata for `/inputs` and
`/work`. It excludes internal files and never returns file content by default.

### `inspect_environment`

Returns Python version, ffmpeg/LibreOffice/tool availability, and a checked-in
allowlisted package/capability manifest. It does not run package managers or
return host environment variables.

### `run_python`

Accepts Python source and a per-call timeout not exceeding the task limit. The
harness streams source to the read-only trusted launcher, which compiles with
the target Python, installs the irreversible syscall filter, and evaluates it
in `/work` with `/inputs` available read-only. Source and control state are not
written under `/work`. Returned stdout and stderr are redacted, truncated, and
represented by status plus bounded tails only inside the live loop; persisted
records retain hashes, counts, and categories.

### `run_ffmpeg`

Accepts exactly one of the following `additionalProperties: false` schemas,
never arbitrary ffmpeg argv or a shell string:

- `probe`: `input` only; emits bounded metadata and writes nothing;
- `extract_audio`: `input`, one new `output`, `format` in `wav|flac`,
  `sample_rate` in `8000|16000|22050|44100|48000`, `channels` in `1|2`,
  `start_seconds` in `[0,3600]`, and `duration_seconds` in `[0.1,600]`;
- `transcode_audio`: the same closed fields and ranges as `extract_audio`;
- `transcode_video`: `input`, one new `output`, `container` in `mp4|webm`,
  `video_codec` in `h264|vp9`, `audio_codec` in `aac|opus`, width and height
  integers in `[64,1920]`, fps in `1|5|10|15|24|25|30`, start in `[0,3600]`,
  and duration in `[0.1,600]`;
- `sample_frames`: `input`, one new PNG `output`, frame count in `[1,16]`,
  width in `[64,1920]`, start in `[0,3600]`, and duration in `[0.1,600]`;
  the harness builds one contact sheet, not a filename expansion.

The compute harness maps fields to an absolute pinned binary, closes stdin,
forces `-nostdin -n`, and constructs argv itself. Inputs resolve under `/inputs`
or `/work`; the sole output resolves under `/work` and must not exist. Only
local file protocols are allowed. Pipe, data, concat, subfile, crypto, HTTP,
TCP, UDP, response files, filter scripts, embedded-path filters such as
movie/amovie/subtitles, overwrite, multi-output expansion, and every unlisted
option or field are rejected.

### `inspect_artifacts`

Runs current deliverable contract inference, artifact selection, openability
verification, and render/output QA. Returns bounded artifact metadata, warnings,
and blocking categories. It does not return rendered image bytes.

### `finalize`

Accepts an ordered deliverable list and concise summary. It rejects copied
inputs, internal files, missing paths, unverified files, contract mismatch,
blank/corrupt output, and files outside `/work`. A successful finalization ends
the loop and snapshots the verified artifact set.

## State Machine

```text
INIT
   -> start one hardened task container with quota-backed /work
   -> mount inputs read-only; retain control state and snapshots on host only
  -> send stable solver instructions + task + bounded file inventory
MODEL_TURN
   -> preflight remaining HTTP/token/USD/wall budgets
   -> Responses API call with SDK retries disabled and parallel_tool_calls=false
  -> account latency, calls, tokens, cache, usage completeness
DISPATCH
  -> validate ordered function calls
  -> enforce global and per-tool budgets
  -> execute sequentially and append function_call_output
  -> snapshot verified artifacts when inspection/finalization improves them
FINAL_MESSAGE
  -> one bounded finalize-required correction if finalize was not called
FINALIZE
  -> deterministic verification
  -> success, or bounded verification feedback and next MODEL_TURN
STOP
  -> success, or fail-closed on API/tool/time/iteration/repetition/security cap
```

Responses output items are preserved in original order. Tool calls are never
parallel. Unknown or unexpected calls are rejected before dispatch.

## Hard Budgets

MVP defaults and absolute maxima are identical unless a lower experiment value
is supplied:

| Budget | Default / maximum |
|---|---:|
| Upstream HTTP attempts, including all corrections/retries | 6 |
| SDK/transport automatic retries | 0 |
| Model iterations | 6 |
| Output tokens per response | 8,192 |
| Cumulative input tokens per task | 300,000 |
| Cumulative output tokens per task | 32,768 |
| Solver wall time per task | 1,200 s |
| Raw model cost per task | USD 1.25 |
| Total dispatched tools | 8 |
| `run_python` | 4 |
| `run_ffmpeg` | 2 |
| Artifact inspections | 4 |
| Finalize feedback | 1 |
| Identical error fingerprint | 2 |
| Python source / tool arguments | 128 KiB |
| ffmpeg argv | 64 entries, 16 KiB total, 1 KiB each |
| Serialized tool result returned to model | 32 KiB |
| Finalize summary | 2 KiB |
| Workspace files | 64 |
| Workspace total bytes | 512 MiB |
| Workspace tmpfs inodes | 1,024 |
| Single artifact | 256 MiB |
| Staged input files / total / single file | 256 / 2 GiB / 512 MiB |
| Input depth / relative-path UTF-8 bytes | 16 / 240 |
| Captured stdout/stderr | 32 KiB each |
| Container CPU / memory / swap / PIDs | 2 / 8 GiB / 8 GiB / 128 |
| Open files | 256 |

The solver uses a dedicated Responses client with transport retries disabled.
Every actual request, including transient recovery and finalize-required
correction, consumes one HTTP attempt and one model iteration. Before each
request, the harness estimates input tokens from the complete serialized UTF-8
request using a pinned tokenizer when available and the UTF-8 byte count as a
conservative fallback. It adds the full remaining per-response output ceiling
and the pinned model price table to compute worst-case next-call cost. The call
is rejected when actual accumulated usage plus that worst case exceeds the
task or run USD/token cap.

The five-task canary has an absolute raw model-cost cap of USD 6.25. Each
twenty-task condition has an absolute cap of USD 25, and the paired inference
cap is USD 50. The paid gate may only lower these values. Cumulative run spend
is checked before each task and before each request, not after the cap has been
crossed. Missing or nonfinite usage makes the task fail closed and blocks the
next request.

A crash-safe transactional budget ledger is keyed by `(paired_run_id,
condition, task_id)`. Preprocessing, solver calls, finalization corrections,
Self-QA, resume rounds, and transport attempts all reserve from the same task,
condition, and paired-run authority. Before a request, the harness atomically
debits one HTTP attempt and reserves uncached input plus the full output ceiling
using `Decimal` and a pinned price table. Timeout, connection loss,
cancellation, or missing usage remain fully reserved because the provider may
have billed the call. Only finite provider usage can reconcile a reservation
downward. Separate baseline and treatment workflows may run only under a
shared transactional budget service; otherwise they run sequentially.

Per-tool timeout cannot exceed the remaining task wall time. Invalid
configuration is rejected or clamped before a model call. Container startup,
tool execution, verification, and model wait all consume the same 1,200-second
task wall budget.

## Planned Code Surface

### New files

- `batch-runner/core/agentic_tools.py`
- `batch-runner/core/agentic_sandbox_runner.py`
- `batch-runner/core/agentic_python_launcher.py`
- `batch-runner/prompts/agentic_sandbox_solver.yaml`
- `batch-runner/sandbox/agentic.Dockerfile`
- `batch-runner/sandbox/agentic-seccomp.json`
- `batch-runner/sandbox/agentic-capabilities.json`
- `batch-runner/tests/test_agentic_tools.py`
- `batch-runner/tests/test_agentic_sandbox_runner.py`
- `batch-runner/tests/test_agentic_sandbox_security.py`

### Existing integration points

- `batch-runner/core/experiment_config.py`
- `batch-runner/core/executor.py`
- `batch-runner/step1_prepare_tasks.py`
- `batch-runner/step2_run_inference.py`
- `batch-runner/step3_format_results.py`
- `batch-runner/step6_report.py`
- `scripts/aggregate-experiments.mjs`
- `src/types/report.ts`
- `src/pages/ExperimentDetail.tsx`
- `src/lib/officialExperimentScope.js`

### Reused without changing semantics

- `batch-runner/core/sandbox_runner.py`
- `batch-runner/core/subprocess_runner.py`
- `batch-runner/core/deliverable_contract.py`
- `batch-runner/core/artifact_verifier.py`
- `batch-runner/core/output_qa.py`
- `batch-runner/core/execution_metrics.py`
- `batch-runner/core/tool_calling_judge.py` (grading only)

## Optional Agentic Metrics

`observability.agentic_metrics` schema v1 appears only for agentic runs:

- model API calls and iterations;
- tool calls by name and status;
- per-tool duration totals;
- execution and finalization attempts;
- repeated-error rejections and deduplication hits;
- capability misses;
- time to first verified artifact;
- input, output, and cached tokens;
- usage completeness;
- stable terminal error category.

Step 6 aggregates measured coverage, calls by tool, tool error rate, recovery
rate, finalize attempts, p50/p95 tool time, and capability misses. Existing
execution metrics remain the source for task wall, model, tool, verification,
dependency, Self-QA, and orchestration time. Legacy reports omit agentic keys
entirely.

## Non-Paid Validation Plan

No live model/API call is allowed in these phases.

1. Unit tests with scripted Responses objects:
   - inspect -> Python -> inspect -> finalize success;
   - compile/runtime error recovery;
   - malformed/unknown tool arguments;
   - duplicate request and repeated-error limits;
   - missing usage and API failure;
   - final text without finalize;
   - finalize verification failure and recovery;
   - budget exhaustion and best-artifact preservation.
2. Tool security tests:
   - traversal, absolute path, symlink escape, URL/protocol, shell injection;
   - read-only inputs, internal files, copied inputs, output/file/size caps;
   - Python timeout/output truncation;
   - ffmpeg argv and path allowlist;
   - capability manifest and missing capability.
   - image audit for `pip`, `ensurepip`, package-manager modules, compilers,
     linkers, debuggers, shells, download/SSH clients, SUID/SGID files, file
     capabilities, and world-writable executables;
   - pinned base image, OS packages, wheels, ffmpeg hashes, and generated SBOM.
3. Docker integration with a fake client and synthetic inputs:
   - real Python 3.11 image;
   - persistent `/work` across disposable executions;
   - `/inputs:ro` enforcement;
   - fixed UID 65532 and UID 0 startup refusal;
   - read-only rootfs and kernel-enforced `/work` quota exhaustion;
   - forbidden package manager, download client, compiler, SSH, and shell audit;
   - generated Python attempts to use `os.system`, `subprocess`, direct
     `execve/execveat` including memfd, sockets for every address family,
     fork/vfork/process clone, mount/namespaces, ptrace/process_vm, keyring,
     BPF, perf, io_uring, package modules, writes outside `/work`, kill, and
     symlink escape all fail closed;
   - supplementary groups, inherited file descriptors/sockets, `/proc/1/root`,
     `/proc/*/fd`, and environment/metadata credential probes reveal nothing;
   - block and inode quota, input count/byte/depth/path limits, sparse files,
     hardlink/symlink replacement, FIFO/device/socket, long names,
     memory/PID/FD/CPU/output floods, pipe deadlock, timeout children/threads,
     and PID 1 signals fail closed and leave no process before the next tool;
   - ffmpeg protocol, concat, embedded-path, stdin/pipe, overwrite,
     multi-output, extra-field, range, and parser-crash cases are rejected or
     contained;
   - repeated inspect/snapshot rename-write races always produce identical
     verifier and submitted hashes;
   - no network, credentials, host control-state access, snapshot access, or
     task-container leak;
   - malicious artifacts are parsed only in the isolated verifier container;
   - deterministic artifact verification.
4. Budget integration tests:
   - pre-call cap boundary and one-unit-over rejection;
   - SDK hidden retry remains disabled;
   - timeout/connection loss/missing usage keeps the reservation consumed;
   - unknown model or price fails before request;
   - crash/resume, Self-QA rerun, and two-condition concurrent reservations use
     one crash-safe transactional ledger and cannot exceed the paired cap.
5. Regression:
   - sandbox, executor, config, Step 1/2/3/6, report, grading loop;
   - broad non-integration Python suite;
   - Node aggregation, TypeScript, Vite build;
   - desktop/mobile agentic fixture and legacy experiment with zero new UI.
6. Gate falsification:
    - independently corrupt each runtime-inspect claim for UID/GID, groups,
       capabilities, no-new-privileges, network, IPC, private PID namespace,
       procfs masks/read-only paths, exact PID 1/launcher FD and socket set,
       seccomp, MAC, rootfs, mounts, byte/inode quota, cgroups, ulimits, digests,
       SBOM, and manifest; every case stops before credential release,
       model-client construction, or request;
    - mutate a source during staging and independently alter path, file type,
       link count, logical/allocated size, SHA-256, classification, Merkle root,
       or add/remove a file; every case stops before credential release;
    - reject stale, duplicate, replayed, out-of-order, unsolicited, expired,
       cross-run, cross-condition, cross-task, wrong-nonce, and digest-mismatched
       channel envelopes without changing solver state or ledger balances;
    - compare baseline and treatment substrate manifests byte-for-byte, including
       generated-code launcher/filter, binary mapper, task/verifier images, and
       runtime profiles; any mismatch aborts both conditions;
    - prove canary, baseline, and treatment IDs are all excluded from official
       aggregates before their first artifact can be published.

If the local GDPVal parquet fixture is unavailable, only its selector module may
be excluded, with the exact path and test count recorded.

## Hypotheses

- H1: Agentic verified completion is no worse than baseline by more than 5
  percentage points on the paired diagnostic set.
- H2: Across all twenty diagnostic tasks, agentic p95 time to first verified
   artifact is no more than 1.5x baseline. A task with no verified artifact is
   assigned the preregistered 1,200-second wall cap.
- H3: The fixed-denominator task-macro external grade is non-inferior by 5
   points while treatment completion is not below baseline.
- H4: Agentic fixed-denominator conservative raw model cost remains at or below
   1.5x baseline; hard abort is 2x.
- H5: No security, scope, usage-completeness, silent-corruption, or dashboard
  contamination gate is violated.

Groups defined after execution by retry, failure, recovery, or tool trajectory
are descriptive only. They cannot define a primary endpoint or promotion gate.
These hypotheses are diagnostic, not population-level claims.

## Preregistered Selection Contract

The literal selection seed is `20260717`. The eligible frame is every unique
task in `<DATASET_REPO>@<DATASET_SHA>` with a non-empty canonical task ID,
sector, occupation, prompt, parseable reference-file metadata, and a matching
rubric at `<RUBRIC_SHA>`. A structural violation aborts selection; it never
silently drops one task. Historical completion, grades, retries, repair paths,
costs, human labels, and prior run membership are forbidden eligibility or
ranking inputs.

For task `i`, define stratum `h(i) = (sector, input_class)`. `input_class` is:

- `none`: no reference files;
- `tabular`: all suffixes in `csv, tsv, xls, xlsx, xlsm, ods, parquet`;
- `document`: all suffixes in `pdf, doc, docx, ppt, pptx, txt, md, rtf`;
- `media`: all suffixes in `png, jpg, jpeg, gif, webp, tif, tiff, bmp, svg,
   wav, mp3, m4a, flac, ogg, mp4, mov, avi, mkv, webm`;
- `mixed_or_other`: every other combination.

Allocate 25 seats proportionally by largest remainder. For each stratum, define
the floor quota and remainder:

```text
a_h = floor(25 * N_h / |F|)
r_h = 25 * N_h / |F| - a_h
R = 25 - sum_h(a_h)
s_h = a_h + 1{h is among the first R strata by (-r_h, UTF8(h))}
```

Here `UTF8(h)` is the bytewise ascending encoding of the length-prefixed tuple
`(sector, input_class)`, and `sum_h(s_h)=25`. Within stratum `h`, select the first
`s_h` tasks by ascending digest `d_select(i)`, breaking digest ties by ascending
UTF-8 canonical task ID:

```text
d_select(i) = SHA256(UTF8(
   "agentic-select-v1\0" + "20260717\0" + DATASET_SHA + "\0" + task_id
))
```

Let `S_h` be those selected tasks. Allocate five canary seats from the final
25-seat quotas, not the floor quotas:

```text
b_h = floor(5 * s_h / 25)
u_h = 5 * s_h / 25 - b_h
U = 5 - sum_h(b_h)
c_h = b_h + 1{h is among the first U strata by (-u_h, UTF8(h))}
```

Thus `sum_h(c_h)=5`. In each `S_h`, choose the first `c_h` tasks by ascending
`d_canary(i)`, then ascending UTF-8 task ID on a digest tie:

```text
d_canary(i) = SHA256(UTF8(
   "agentic-canary-v1\0" + "20260717\0" + DATASET_SHA + "\0" + task_id
))
```

Their union is canary set `C`; diagnostic set `D` is the other twenty selected
tasks. Emit ordered lists by ascending corresponding digest, then ascending
UTF-8 task ID on a digest tie:

```text
d_order_canary(i) = SHA256(UTF8(
   "agentic-order-canary-v1\0" + "20260717\0" + DATASET_SHA + "\0" + task_id
))
d_order_diagnostic(i) = SHA256(UTF8(
   "agentic-order-diagnostic-v1\0" + "20260717\0" + DATASET_SHA + "\0" + task_id
))
```

One selector invocation emits both lists atomically before any canary outcome:
`|C|=5`, `|D|=20`, and `C intersect D` is empty. Run it from an outcome-free
checkout that cannot read `data/grades`, `batch-runner/results`,
`batch-runner/workspace`, prior HF inference repositories, or run logs.

Store selection provenance in
`tasks/0717_friday/data/agentic_task_subset.json`:

- dataset repository and full immutable revision;
- rubric repository and revision;
- selector path, source commit, and SHA-256;
- seed, eligible-frame count, stratum counts, quotas, and tie-break rules;
- exact ordered canary and diagnostic IDs;
- sector, occupation, input class, reference suffixes and sizes;
- inclusion/exclusion validation and selected-before-outcomes attestation;
- deterministic recomputation hash.

The selector, tests, exact lists, and manifest are committed after non-paid
implementation validation but before the first canary call. Canary outcomes
never redraw the diagnostic set.

## Separate Experiment Identities

`execution.mode` is top-level, so the paired comparison uses three separate
single-condition experiment YAMLs and repositories:

1. `<CANARY_EXP_ID>`: five tasks, `agentic_sandbox`;
2. `<BASELINE_EXP_ID>`: twenty diagnostic tasks, current `sandbox`;
3. `<TREATMENT_EXP_ID>`: the same twenty tasks, `agentic_sandbox`.

Baseline and treatment fix the full implementation Git SHA, dataset and rubric
SHAs, ordered task IDs, model deployment, API version, reasoning effort, token
limits, prompt suffix, Self-QA, preprocessors, timeout, CPU, memory, verifier,
capability-manifest hash, and full Docker image digest. The baseline additionally
fixes `repair.enabled: true` and `repair.max_attempts: 1`; one initial generation
plus at most one full regeneration is the preregistered baseline solver. Both set
`use_docker: always`; Docker absence, pull failure, tag-only resolution, digest
mismatch, or attempted local/subprocess fallback aborts before a model call.

Both conditions install the identical syscall filter inside every generated
Python process and use the identical closed ffmpeg mapper. A byte-identical
common substrate manifest pins the generated-code launcher/filter, binary
mapper, task and verifier image digests and SBOMs, runtime profiles, UID,
mounts, cgroups, ulimits, and verifier contract. Any parity mismatch aborts
both conditions before model-client construction. Output roots, HF
repositories, experiment IDs, checkpoints, reports, and grades are distinct.
Placeholders such as `<DATASET_SHA>`, `<IMAGE_DIGEST>`, and experiment IDs are
forbidden at the paid gate and must be replaced by full immutable values.

Retained run output is rooted at
`batch-output/agentic-sandbox/<experiment_id>/<github_run_id>-<run_attempt>/`
with identity, prepared tasks, progress, final inference, and deliverables as
separate children. Shared `batch-runner/workspace` files are staging only and
cannot be the comparison source. Formatted inference, self-report, and grade
files remain keyed by their experiment and full source/config identities.

## Preregistered Endpoints

Let `D` be the fixed diagnostic set and `N=20`. For condition `c`, define
`C_ic=1` only when the registered terminal-success predicate and the common
condition-blind artifact verifier both pass. Treatment also requires an
accepted `finalize` call. Missing, pending, aborted, API-error, QA-failed, and
verification-failed tasks have `C_ic=0`.

```text
Completion_c = sum(C_ic) / 20
DeltaCompletion = 100 * (Completion_treatment - Completion_baseline)
```

For each expected rubric item, classify in precedence order as `missing`,
`judge_error`, `score_excluded`, or `scored`. Every item-state rate uses the
same frozen expected-item denominator. Missing task grades and non-null task
errors are reported separately over denominator 20.

For task `i`, let `P_i` be the sum of positive maximum rubric scores. A selected
task with `P_i=0` invalidates the frozen design. Awarded score contributes only
when the task completed and the item is `scored`; every other state contributes
zero while retaining its denominator. Clamp task score to `[0, 100]`.

```text
q_ic = 100 * clamp(sum(eligible awarded score) / P_i, 0, 1)
Q_task_c = sum(q_ic) / 20
```

`Q_task` is the primary quality endpoint. A secondary rubric-weighted endpoint
uses the sum of eligible awarded scores divided by the fixed sum of all
positive maxima. A paired complete-case score is sensitivity analysis only and
must print its denominator. No endpoint may silently use the intersection of
available task IDs.

For timing, `T*_ic` is time from first model dispatch to first commonly
verified artifact, or 1,200 seconds when none exists. Report all twenty paired
values. Sort each condition's twenty values ascending and define nearest-rank
`P95T_c` as element `ceil(0.95 * 20) = 19`; the timing gate uses only
`P95T_treatment / P95T_baseline`. Repair/retry trajectory subgroups are
exploratory only.

Let `K_ic` be settled finite provider raw cost plus every unreconciled
worst-case reservation retained after timeout, connection loss, cancellation,
crash, or missing usage. Tasks with no request contribute zero; failed and
missing tasks retain incurred or reserved cost. Define fixed-denominator cost:

```text
MeanCost_c = sum(K_ic) / 20
CostRatio = MeanCost_treatment / MeanCost_baseline
```

A zero baseline with positive treatment cost gives an infinite ratio; both
zero gives ratio 1. The cost gate uses this conservative raw ratio. Effective
provider cost and latency are descriptive only.

Canary, baseline, and treatment experiment IDs are registered in the
official-scope exclusion registry before the first artifact from any of them.
Direct detail and `?debug=1` remain available.

## Paid Approval Gate

Before any live or paid workflow or real model call, create
`tasks/0717_friday/AGENTIC_SANDBOX_PAID_GATE.md` containing:

- exact plan and implementation merge SHAs;
- exact five and twenty task IDs;
- selector, manifest, dataset, rubric, image, and capability hashes;
- each input's canonical relative path, type/link constraints, logical and
   allocated size, SHA-256, provider-specific transmission classification, and
   the complete input-manifest Merkle root;
- workflow names and all inputs;
- expected model calls and token ranges;
- projected raw/effective cost and per-task/per-run hard caps;
- wall-clock/relay policy;
- abort and cancellation procedure;
- acceptance gates;
- explicit owner approval and timestamp.

The Markdown record is human evidence, not runtime authority. Before each
approved phase, it references a canonical signed approval envelope containing
the plan and implementation SHAs, exact run and condition scope, task IDs,
input-manifest Merkle roots and provider classifications, model/deployment/API
version, workflow SHA and canonical input digest, token/USD/time caps, issue and
expiry times, and an unpredictable single-use approval nonce. A checked-in
owner public key verifies the signature. The nonce is atomically consumed in
the crash-safe ledger for exactly that phase and cannot authorize a rerun,
resume under a new run identity, canary expansion, paired run, or grading run.
Changed scope requires a newly signed envelope.

The live job contains no static provider secret. A separate credential broker
verifies signature, expiry, all bound identities and caps, unconsumed nonce,
input-byte identity, official-scope exclusions, and runtime/substrate preflight,
then issues a run-scoped short-lived provider credential to the control plane.
Any missing, unsigned, malformed, expired, replayed, already-consumed, or
identity-mismatched approval fails before credential release and model-client
construction. Non-paid tests independently corrupt every field and signature,
simulate concurrent nonce claims and crash/restart, and prove exactly one claim
can succeed without permitting a model request in every rejection case.

The gate also requires a disposable dedicated runner identity with a patched
kernel and OCI runtime, enforce-mode AppArmor or SELinux, rootless Docker or
user-namespace remapping, disabled or encrypted swap, and no mounted Docker
socket, cloud/API/HF credentials, or concurrent workload. The credentialed API
control plane is a separate identity with no Docker or artifact access.
Runtime preflight
must inspect the started container and prove UID/GID, supplementary groups,
capability set, no-new-privileges, network/IPC/private-PID mode, procfs
masks/read-only paths, exact PID 1 and launcher FD/socket allowlists, seccomp
and mandatory-access-control enforcement, read-only rootfs, mounts, tmpfs
byte/inode quota, cgroups, ulimits, image digest, SBOM, and capability manifest
before credential release or model-client construction.

Only inputs explicitly classified as permissible for transmission to the
selected model provider may enter a live agentic run. The canary and diagnostic
sets use approved public and pinned GDPVal material only. Inputs with secrets,
personal data, customer data, or provider-prohibited content are ineligible,
because generated code can intentionally summarize readable input to the model
through bounded tool output even when container network access is disabled.

Without that approval, stop after implementation PR merge. No live smoke is
implicitly authorized by this plan.

## Paid Execution Sequence After Approval

1. Run only the five-task agentic canary.
2. Audit exact task set, tool budgets, usage completeness, security categories,
   verification, cost, and absence of child/full-run dispatch.
3. Stop on any violation. Do not auto-start A/B.
4. With renewed approval, run fresh twenty-task current-sandbox baseline and
   agentic treatment on identical task IDs.
5. With separate grading approval, grade both conditions with the same current
   Track 2 config.
6. Compare only paired task IDs and label all findings diagnostic.

## Acceptance and Abort Rules

Immediate abort:

- network/root/path/secret boundary violation;
- copied input or unverified artifact accepted;
- silent corruption or incomplete usage;
- task-set or image/config identity drift;
- tool/API/cost/time hard-cap violation;
- automatic expansion outside approved scope.

Iterate or abort:

- completion or external grade more than 5 percentage points below baseline;
- `P95T` ratio or fixed-denominator conservative raw `CostRatio` above 2x;
- repeated error loops or capability misses dominate recoveries.

Promotion candidate:

- no safety violation;
- external grade within 5 percentage points of baseline;
- verified completion improves or is equal;
- `CostRatio` and `P95T` ratio remain within 1.5x baseline;
- recovery evidence is attributable to bounded tool decisions.

## Evidence Ledger

| UTC time | Phase | Commit / run / artifact | Evidence | Decision |
|---|---|---|---|---|
| 2026-07-17 | Plan | `main@6bdcfcf9` | Initial plan drafted; no code or paid run | Revise after review |
| 2026-07-18 | Plan | `main@71902db3` | Docs validation passed; `first-reviewer` and `extreme-reasoner` found no mandatory blocker | Approved for docs merge and non-paid implementation |

## Cost Ledger

| UTC time | Run | Scope | Raw | Effective | Cumulative | Gate |
|---|---|---|---:|---:|---:|---|
| 2026-07-17 | none | Planning only | USD 0 | USD 0 | USD 0 | Pass |

## Incident Log

| UTC time | Phase | Category | Evidence | Containment | Follow-up |
|---|---|---|---|---|---|
| 2026-07-17 | Plan | None | No execution performed | N/A | Begin non-paid implementation after plan merge |

## Retrospective Template

Create `tasks/0717_friday/AGENTIC_SANDBOX_RETROSPECTIVE.md` after experimental
execution with these sections:

1. Original question and preregistered hypotheses
2. Architecture actually shipped
3. Timeline and decision changes
4. Expected versus observed tool trajectories
5. Completion, quality, time, calls, usage, and cost
6. Security and privacy evidence
7. Incidents and failed assumptions
8. Confounds and limits
9. What to keep, remove, and redesign
10. `promote`, `iterate`, or `abort` decision
11. Next experiment and unresolved package-broker question

Do not quote raw reasoning, code, tool arguments, process output, or sensitive
file contents in the retrospective. Use bounded metrics, categories, relative
paths, hashes, and carefully selected non-sensitive artifact descriptions.

## Current Decision

`PLAN_APPROVED_NON_PAID_ONLY` — merge this plan first. Then implement through
non-paid validation. Stop before any live model/API run until the signed,
single-use paid authorization gate is explicitly approved and consumed.
