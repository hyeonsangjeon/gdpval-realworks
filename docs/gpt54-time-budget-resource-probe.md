# Time-budget Ubuntu 24.04 resource and cleanup probe

This is a **model-free host check**, not one of the registered 20 observations.
It is prepared for Actions only; local tests do not establish that the hosted
image, AppArmor or kernel actually passed. Publishing needs owner approval and
the new dispatch-only workflow must be available on the default branch before
GitHub will accept a dispatch. No dispatch is performed by this change.

## Scope and stopping rule

The probe asks whether the standard GitHub-hosted Ubuntu 24.04 image admits the
pinned Codex sandbox and the actual time-budget ownership/cleanup machinery.
It refuses an unreviewed source, non-hosted runner, Ubuntu 22.04, missing
sandbox evidence, unknown inventory, unexpected network/process work, missing
worker report, cleanup uncertainty or any residue. It does not repair or remove
unrelated host processes, directories or Docker containers.

| Check | What is real | What is synthetic / not proved |
| --- | --- | --- |
| Before/after resources | `df -B1`, `free --bytes`, `nproc`, runner OS/image/run attempt; Docker container IDs | Small fixtures do not establish capacity for the original reference files or model workloads |
| Sandbox preparation | Existing `prepare_codex_sandbox_host.py`: `/usr/bin/bwrap`-scoped AppArmor profile if needed, userns/netns and pinned Codex `sandbox` marker | No Codex `exec`, model request, login or provider proof; no global sysctl weakening |
| V2 observation | Actual same-host `AgenticV2FixtureBackend`, conversation runner and tool write | Scripted voice, synthetic text, no original inputs or provider |
| Codex observation | Actual runner, SDK request/stream facade, workspace, collection and cleanup | Scripted app-server client; no app-server model turn or HTTP server is started |
| Deadline/cleanup | Real monotonic clock, SIGALRM, exclusive subreaper, pidfd/waitid, 1,200s then the same 20s cleanup end | Remote cancellation, model/judge behavior and billing are not proved |

The V2 and Codex checks run **serially in one job**, each in a fresh
network/PID namespace. Each writes the same small synthetic file, creates an
owned `setsid` orphan that ignores SIGTERM, and stalls until the **real 1,200s**
generation deadline. Production cleanup must kill/reap it before the unchanged
20s cleanup deadline. This deliberately spends about **40 minutes plus setup**;
the 90-minute job includes dependencies, sandbox checks and artifact headroom.
It is not a shortened timer demonstration. Offline tests alone substitute the
clock, kernel and process transport so NAS never performs the host check.
Each synthetic observation is expected to time out: a green probe means its
timeout/cleanup was verified, not that a task was successfully solved.

## Isolation, authentication and artifacts

The workflow has only `contents: read`, no secret/environment/OIDC binding, and
checkout does not persist credentials. Workers receive only an explicit public
metadata allowlist and empty fixture-owned home/tmp/native roots. Bubblewrap
denies external networking and hides `/run` (including the Docker socket).
A Python audit hook additionally rejects sockets and any child command except
the fixed orphan helper; an accidentally restored live SDK transport fails.
The Codex fixture uses the existing **loopback-only provider type**, no listening
server and a fixed non-credential placeholder. The normal live provider's
authentication preflight stays enabled and unchanged; a separate negative unit
test checks refusal before runtime startup when its auth response is empty.

The `time-budget-resource-cleanup-<run>-<attempt>` artifact contains JSON only:
`source.json`, `resources-before.json`, `sandbox-preflight.json`, `sandbox_v2.json`,
`codex.json`, `resources-after.json`, `summary.json` (or an explicit refusal).
Worker JSON records synthetic status, original budgets, observed elapsed time,
runner evidence, orphan identity/residues, temporary residues, cleanup status
and forbidden-attempt counters. It never contains an auth response or raw child
stderr. Unavailable inventories are `null` and fail, never an empty success.

No Docker container is used by these same-host fixtures. Before/after IDs detect
unexpected newly remaining containers; this is **not** a Docker teardown test.
Runtime temporary trees must be empty before their known fixture wrappers can
be removed with `rmdir`; remaining files are
listed and cause failure, not force-deleted. Diagnostic receipts and JSON are
intentionally retained separately. New `codex-sandbox-preflight-*` scratch
directories are also compared with the pre-setup baseline. If a worker crashes, the PID namespace is a
secondary containment boundary, not evidence that production cleanup succeeded:
missing/failed inner evidence always fails the job and blocks the next fixture.

## Registration and future command (draft only)

The original comparison and 42-pin registration, source-only successor, paid
workflows, model/effort, input/grader contracts and 1,200s/20s budgets are
byte-for-byte unchanged. These new independent probe files are not replacements
for registered study sources; no hash expectation needs to advance. Successful
host evidence cannot authorize a paid run or be ingested as a study capture.

After publication approval, default-branch workflow availability and review of
the exact branch HEAD, the owner can use this **unexecuted draft**:

```bash
gh workflow run gpt54-time-budget-resource-cleanup.yml --repo hyeonsangjeon/gdpval-realworks --ref leader/time-budget-2404-guard-20261030 -f expected_source_sha=<reviewed-full-HEAD>
```

Blocker ① remains: wire the deterministic serial 20-ID schedule to actual
dispatch/capture, then feed each captured observation once into the frozen
grader and pair `(task, repeat)` without filling missing sides with zero.
Develop/test that orchestration with fake dispatch/storage/judge transports
before seeking a separate paid-run approval.
