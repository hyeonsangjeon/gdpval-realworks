# Latest task result

## Native Step0 identity bound corrected; one offline selector passed

The native callable now checks Step0 against the existing original Step0
size, 218405 bytes, rather than the 65536-byte preparation metadata cap.
Preparation and direction keep their 65536-byte limits. One new selector
reported **7 passed in 68.90s**, exit 0; wrapper **69.565234s**. The positive
case used an actual full-length synthetic file and reached canonical capture
and retention over synthetic auth/RPC/kernel/storage fixtures. It did not
verify private originals or establish real-host readiness.

This is an implementation-only correction. Native Task1 and Task2 are
consumed and must never be replayed. No next cell or ABBA advance is authorized.

## Leader-verified Task2 and the demonstrated source mismatch

The leader verified native r1 Task2, task
`0112fc9b-c3b2-4084-8993-5a4abb1f54f1`, run `37619469416`, run number 4,
attempt 1, job `112785799708`. Original inputs/full Step0, permanent private
claim, login and identity checks succeeded. Execute failed; retention,
envelope and artifact succeeded. Exactly one safe native event reported
`stage=observation_callable`, `category=observation_refused`,
`reason=independent_identity_size_bound`.

Completion remained uncertain with null result identity, fingerprint, usage,
terminal, cleanup and host-reuse fields; retry and grading were false.
Those nulls are not zero model calls, zero cost, a cleanup verdict or a score.
This task did not fetch private data, rerun the observation or read its result.

| Retained evidence supplied by the leader | Identity |
|---|---|
| Permanent claim | `70b6ac9412576680d831249b051fff14b99a99d2` |
| Output commit | `0a718b45b96bf340cb2e4a71206d81cebe0f7abc` |
| Artifact | `11482090159` |
| ZIP SHA256 | `3985575a15f9baf080a53497d3da8d0c14f5c3d98403736e52d4f2ac4aee0bc6` |
| Completion SHA256 | `dea0d86d7db262480e07bb64fcfae604e503a7f98a20b0998a86e70c80f7fe7f` |
| Log | 199452 bytes; SHA256 `fd61a5ffdf9cad1c02c5457f879d1ca6e70f7aa9fe7b54e218e99ae1faeb1ee6` |

At the accepted base, native callable blob
`21f592472ad78991d69e6d11af58cf88e1de615e` applied
`registration.MAX_MANIFEST_BYTES == 65536` to both independently expected
identities before provider/consumer construction. The original-input helper,
blob `65bec6ffb3468b2ac9758dfde303a72824e0e04a`, pins the whole original
Step0 to 218405 bytes / SHA256
`463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512`.
The trusted Task2 request used that identity. A 218405-byte original cannot
pass a 65536-byte limit; this is a deterministic source mismatch, not a guess
from a generic error category.

The role-aware helper now uses `STEP0_PIN["size"]` only for Step0, retaining
the preparation default. It does not derive the cap from the caller, change
the original pin, truncate/split/reserialize originals or bypass exact byte,
digest, whole-Step0 semantic, source, host, direction or provenance checks.
No-clobber publication, permanent claims and all native/V2 controls are intact.

Task1's earlier retained classification remains `observation_callable` /
`validation_refused` / `execution_refused_or_uncertain`. Its original first
guard, model calls, cost and cleanup remain unknown. This Task2 correction
does not retrospectively establish Task1's cause. All five V2 r1 cells also
remain consumed and retained: two uncertain and three canonical errors,
not successes or zero quality scores.

## Exact source and unchanged study bindings

| Role | Commit / tree or blob |
|---|---|
| Accepted base; origin/main checked once | `f081f470a03b205bfdaf567050bbc1d123b6d7b3` / `6a3d0c8c18b8f4ac345bfe06f2429136b9642b15` |
| Tested correction and new test | `45350d204967553d96a9ed809320542733cb2994` / `bb45022865949ed7e871255254bbafc05bebc103` |
| Corrected callable blob | `389b141af28b2235767f95b8639ac9110dd84489` |
| New regression blob | `c2b86c98709fb13674a9a1867587689dccc3bf3f` |
| Unchanged compiler blob | `f6fe26b40310f3ca72347a6133abe43316de97f2` |
| Frozen F | `882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2` / `45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca` |

The full registration seal remains
`3dde5f2f62e8ada29c883e1ef0eb555c969987f710b437af50c513ac9b52d22f`.
Compiler SHA256 remains
`f4e41540a089e4ed164063bec60ce124a901eb5195065e456502e902814cd3a2`;
frozen TEMPLATE SHA256 remains
`37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce`.
The callable is not a registration `source_pins` member. Its existing
`ENTRYPOINT` byte check binds it to the independently reviewed runtime
commit, so no registration/source-pin update is needed. All other tracked
bytes were unchanged at the tested commit. Only this record, CHANGELOG and
the direct README evidence change after the proof.

The existing twenty cells, model GPT-5.4/direct-v1/xhigh, native null context
override, zero configured provider request/stream retries, one external
attempt, shared concurrency 1, nonrenewable 1200-second generation/shared
20-second cleanup and 45-minute job ceiling stay fixed. This is input
compatibility, not a new study condition, money hard cap or timing-equivalence
claim. The original Step0 revision remains
`6c7e07ee7365f145dfcf898263365b5c8c97b224`; private bytes were not read here.

## The one bounded proof

Only
`tests/test_time_budget_codex_step0_identity.py::test_time_budget_native_step0_identity_bound`
ran, under Python 3.10.12, pytest 9.1.1 and pytest-timeout 2.4.0, with no `-x`,
one 300s TERM + 5s KILL bound and existing 30s Git limits. The wrapper checked
syntax, the `change` parameter and exact two-file scope before collection.
It used Python timing and the existing named Git/bootstrap Bash allowances,
not `/usr/bin/time` or a broad audit hook. No old selector or full suite ran.

| New case | Actual outcome |
|---|---|
| `full_step0` | Passed: valid 218405-byte synthetic Step0 stayed byte-identical through actual controller/callable/consumer/capture and synthetic private retention/envelope checks |
| `step0_bytes` | Passed: a changed final whitespace byte beyond the old cap refused on the real full-file digest check |
| `step0_digest` | Passed: wrong independently expected digest refused on the real hash check |
| `step0_size` | Passed: expected size 218404 refused on the real byte-size check |
| `step0_over_bound` | Passed: expected size 218406 refused with `independent_identity_size_bound` |
| `preparation_over_bound` | Passed: metadata identity bound accepts 65536; 65537 refuses with `independent_identity_size_bound` |
| `direction_over_bound` | Passed: actual 65537-byte valid JSON direction with a coherent digest refuses with `direction_size_bound` |

The synthetic Step0 SHA256 is
`11afd4cb6e0d41141c6ff203108c7b66d4f1a00eb8fa876651d8cdd096c8ff52`.
It is the existing valid six-task synthetic schema4 document with JSON
whitespace added before input pins were established, not private original
data or inflated size metadata. Existing real validators consumed its whole
file. Ordinary synthetic auth/RPC and stateful kernel fixtures are explicit;
no successful native constructor or validator was substituted. Refusal cases
left provider/admission/native effects absent and permanent claim/preparation
bytes unchanged. This does not prove actual Actions ownership or login.

Artifacts are retained under `/tmp/native-step0-identity-bound.Kuhetw/`:

| Artifact | SHA256 |
|---|---|
| `run-proof.py` | `b647e1f4cdc9b15df18365aad2f76b16e23ad5b0f310acc210327707e4f1f7f1` |
| `command.json` | `02255457caeb302f031827f653e233dccb7a09c7aaa845288f714d15f29a318d` |
| `source.json` | `f7ade42a26ca7469f1da91636954701c69dad1b4139d73f95fbb3d5cdfcea6be` |
| `pytest.log` | `e573fbdeb7c0bbf17e5d4e33711814ab2643cba253bf5765db63cac771cacd9b` |
| `junit.xml` | `8eac02edfcbdd7f1df35eb24c71d9626f311cef279175c4d38a30d7786ebcb68` |
| `cases.json` | `2fef76f0df6f9c8fed9a04859c9ce9177ced20670eab2d558f9894963b87bfa4` |
| `outcome.json` | `1eb1bb361d3fc8bc87bae7d8806eba0add0a485186eaf11c6191dbf180216a55` |
| `synthetic-step0.json` | `7d7a04d790087bb530926b4fa9afbe73a44c5367235bbd270a6865c02785695f` |

The directory's `handoff.json` records the exact final documentation-bearing
HEAD/tree after the records commit and verifies that the tested callable/test
blobs are unchanged. It is not another test invocation. `records/` retains
bounded before/structural/final checkpoints, the protected-claim ledger and
copyediting checks. The [accepted prior record][prior] preserves earlier
selection review/CI and its separate failed/passed proofs; none was rerun or
aggregated into these seven cases.

## Remaining gates and authority

The leader's exact source finding authorized this minimal correction. No
independent review or CI pass of this candidate is claimed. The agent catalog
was read once; experiment-design held the study fixed, and experiment-report-en
then im-not-ai-en kept historical uncertainty separate from fixture evidence.
No unavailable reviewer harness was retried.

Fixed-HEAD review, ordinary final CI, leader-owned integration and independently
authorized next-cell source/request/input/full-Step0/auth/host/direction/CAS
checks remain required. No private input or output was fetched; no real model,
provider, kernel-positive, grading, readout, workflow dispatch or CI query ran.
Prior worktrees and consumed claims are untouched. Neither native Task1/Task2
nor any consumed V2 cell may be replayed; no native Task3 or ABBA advance follows.

[prior]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/f081f470a03b205bfdaf567050bbc1d123b6d7b3/tasks/LATEST_TASK_RESULT/README.md
