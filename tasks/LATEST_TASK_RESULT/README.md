# Latest task result

## PR750 owned-host usage alignment — 2026-10-05

The time-budget usage paragraph now matches the leader's source-reviewed
implementation at `67f2ef7c94665fbe5d302040a757402873790cfc`, tree
`cd34fd6cd3e3d74e3b927eb8732ae72fd3d0331d`. The remaining incremental source/test
review found no additional blocking code finding in that scope. This is source
approval, not delivery or live authorization. This task changes documentation
only; it does not reread the implementation or repeat a software proof.

### Usage correction

The README now requires exclusive Linux child-subreaper ownership, one kernel
thread, no existing children, default `SIGCHLD` handling and the required
`/proc`, pidfd and `waitid` interfaces. Main-thread execution and the absence of
an existing real-time alarm remain requirements. Unsupported or occupied hosts
refuse admission. Owned-child termination uses kernel-confirmed child pidfds,
not bare PID or process-group signalling.

Unconfirmed cleanup cannot produce clean-host success. Admission history and
process ownership prevent reuse even if the lease was unlinked before expiry.
Successful reuse requires confirmation in the same process before the cleanup
deadline. The 1200-second generation budget, shared 20-second cleanup remainder
and 1220-second maximum planned host lifecycle remain unchanged. These are not
claims about remote cancellation, billing or live execution.

The prior real-host case refused admission with
`time_budget_owned_process_host_required`, caused by `FileNotFoundError`, errno 2.
Standard proc paths are used, but a missing interface is not orphan-cleanup
success. Cleanup on a real supported kernel remains unproved; controlled
ownership cases do not establish it.

### Bounded documentation check

The existing `im-not-ai-en` brief preserved technical terms, numbers and evidence
limits. One invocation of its `verify_fidelity.py` compared the accurately
corrected draft with the copyedited README passage, under a 30-second bound plus
5-second termination grace. It exited 0 with status `pass`, no failures, no
warnings and no configuration errors. This is a changed-passage literal/structure
check, not a runtime test or proof of real-kernel cleanup. The leader's supplied
implementation facts define the intentional semantic corrections.

No pytest, Node, HF, build or CI command ran. No experiment-design review or new
readiness investigation was performed.

### Prior software evidence, unchanged

The [source-reviewed record][reviewed-record] retains the exact node list,
redacted public command and private evidence identities for the prior invocation:

| Identity or result | Value |
| --- | --- |
| Tested correction | `00997e75f6c72e3bfa0541be1bb1c6e47867c401` |
| Tested tree | `a3d4e355260c87ed7555d9db2cde1420955596ff` |
| Result | 23 passed in 136.55s; exit 0 |
| Environment and bound | Python 3.10.12; one offline invocation, 300 seconds plus 5-second grace, without `-x` |
| Exact private command SHA256 | `a480936099b18cc75a2a241bcac5bd66d5babfc7de7063e92f3c972b3e18d7aa` |
| Log SHA256 | `eeebc45da1491ee35e8613fbc41cd0e5b6113e80ed4ee96a92689e2593f5a91c` |
| Receipt SHA256 | `aaf6910b2200c97394610a428d5edb981316c60851253172976a73763b375b29` |

These identities are retained from that record, not newly read or rerun evidence.
The command hash identifies the private script, not its redacted public display.
The original 46-pass/5-fail invocation, five-target continuation, 21-case
finalization proof and 30-case ownership proof remain separate observations in
the [earlier immutable record][prior-record]. They are not an aggregate pass or
a global all-tests-pass claim. The real-kernel admission refusal remains separate
from every passing synthetic proof.

### Exact scope and remaining gates

The extra post-proof delta from source-reviewed `67f2ef7c` contains exactly:

- `batch-runner/README.md`
- `CHANGELOG.md`
- `tasks/LATEST_TASK_RESULT/README.md`

The cumulative changed-path set after the `00997e75` proof is those same three
files. No source, test, workflow, manifest, pin, historical evidence, study policy
or launch guard changed. The user checkout, previous worktrees and consumed
preparation remain untouched.

The leader supplied an initial CI snapshot of 14 successes, one native-host
check in progress and one PR-only deploy skip. It was not queried or refreshed
in this task and is not final CI acceptance for this documentation HEAD.
Applicable CI and final delivery acceptance remain pending. Supported-host
cleanup, dispatcher/capture selection, verified credentialed inputs, F-derived
grading execution and a separately reviewed source-bound live direction remain
open work. All launch refusals and execution flags stay closed.

No private original, receipt or consumed artifact was accessed. No preparation,
provider/model/grader/HF/Azure operation, CI query/poll/dispatch/rerun, Project edit
or merge occurred.

[reviewed-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/67f2ef7c94665fbe5d302040a757402873790cfc/tasks/LATEST_TASK_RESULT/README.md
[prior-record]: https://github.com/hyeonsangjeon/gdpval-realworks/blob/513a443f361106300f9be425f8b12c2c48a2540f/tasks/LATEST_TASK_RESULT/README.md
