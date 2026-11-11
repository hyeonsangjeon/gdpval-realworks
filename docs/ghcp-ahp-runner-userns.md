# Authenticated zero-turn: native failure and runner user namespaces

Scope: one GitHub-hosted Ubuntu 24.04 dispatch, no model turns, no inference,
no paid calls. NAS execution of bwrap, the SDK or the host is prohibited.
The immutable SDK, two VS Code patches, patch-set/bundle hashes, and all
admission/network/privilege guards remain unchanged.

## Evidence and hypothesis before execution

Run 42931848815 returned native `thread/start` error -32603:
`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`.
Authentication and a logical AHP session succeeded, but no native thread did.
The observer recorded no new RPC refusal. All applied fields were not_reported.
The old workflow was green because a matching JSON-RPC error counted as a reply.

AppArmor's unprivileged userns restriction is a hypothesis, not a measured cause.
The new runner receipt records both relevant sysctls, aa-status counts, the
resolved bwrap path/version/hash, and an isolated namespace canary before any
change. The canary reuses the broker's exact outer mount/net/PID namespace,
empty capability bounding/inheritable/ambient sets and no-new-privs boundary.
It adds bwrap read-only root and user/net/PID namespaces and checks those facts.
It performs no authentication or external network access and is not a native
thread result or model-admission proof.

If the baseline passes, change nothing and report that the failure was not
reproduced. Otherwise, when the recorded restriction is 1, first load a profile
attached to exactly the selected bwrap executable, granting `userns`. The
profile uses the Ubuntu documented `flags=(unconfined)` form; it does not change
Codex's sandbox policy, outer netns, no-new-privs, seccomp or capability guards.
Only if that profile fails may this ephemeral job set
`kernel.apparmor_restrict_unprivileged_userns=0`. Remove our profile before that
fallback so the second intervention is distinguishable. Never change
`kernel.unprivileged_userns_clone`, skip netns, allow network, or use full access.

The one preparation run may contain baseline/A/B local namespace canaries;
these are not authentication retries or extra workflow dispatches. Native
authentication/session is attempted once, only after preparation verifies.
Always restore this job's own profile/scalar setting and record cleanup;
cleanup failure is a workflow failure. No permanent `/etc` profile is installed.

## Source-grounded launcher selection

- SDK 0.163.0, source commit
  `83086188ae0614bd882818ff1aa23f3194962012`:
  [launcher.rs:135](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/linux-sandbox/src/launcher.rs#L135)
  prefers a PATH bwrap whose help contains `--as-pid-1` and `--perms`
  ([line 200](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/linux-sandbox/src/launcher.rs#L200)).
  Otherwise it uses the SDK's bundled resource, not an assumed `/usr/bin/bwrap`.
- [bundled_bwrap.rs:65](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/linux-sandbox/src/bundled_bwrap.rs#L65)
  verifies the digest and executes an open file through `/proc/self/fd`;
  [line 104](https://github.com/openai/codex/blob/83086188ae0614bd882818ff1aa23f3194962012/codex-rs/linux-sandbox/src/bundled_bwrap.rs#L104)
  resolves `codex-resources/bwrap`. The unchanged SDK archive contains bwrap
  SHA256 `77360cb751ccedc5971391444ac86a8a33c15b04d6b4a6fe45f5d25496e62c4c`.
  The canary preserves that exec form when the bundled path is selected.
- [Official OpenAI sandbox guidance](https://developers.openai.com/codex/sandboxing/)
  recommends the bwrap-specific AppArmor userns profile first on Ubuntu 24.04,
  and the sysctl fallback only if the profile is unavailable/ineffective.
  Current documentation does not override the pinned source or prove this run's cause.

## Acceptance, receipts, and stop conditions

`await_native_thread` now counts only successful result objects with a nonempty
thread ID. Error/invalid/uncorrelated/incomplete responses cannot establish a
thread. Error and invalid counts remain distinct. The exported wire response
preserves the original redacted error; cleanup and export still run on failure.

Authenticated zero-turn additionally requires the existing policy assessment
to report admission_allowed exactly true. False/missing/non-boolean admission
fails exit 2. This does not relax admission: native configured model is not a
served model; absent thread context/web-search/server evidence stays unknown.
Thus sandbox preparation or native creation may succeed while the workflow
correctly remains FAILURE because admission cannot be established at zero turns.

`runner-userns.json` is the final preparation receipt (original and effective
sysctls, profile text/hash, command outcomes and canary proofs).
`runner-userns-use.json` binds its SHA256 and selected binary hash immediately
before credential use; altered/missing/rolled-back preparation refuses auth.
`runner-userns-cleanup.json` binds the same receipt and records restoration.
They are retained by the existing JSON artifact glob without credentials.

Offline fixtures test the judge as well as A/B/no-change/failure/cleanup paths.
They do not estimate the success rate on hosted kernels. Fixed axes are the
SDK, host bytes, policies, prompt count (zero), and isolation. The intervention
is only the runner's userns permission, and the reported unit is a correlated
native thread result, not a protocol response or a billing assertion.
One fresh dispatch only after green push CI; stop on HTTP 401/403 or any new
error. No post-result workaround or second dispatch is authorized in this task.
