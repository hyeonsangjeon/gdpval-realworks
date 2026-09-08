# The development and test host

A declarative definition of the Azure VM the Xenology card gates on, plus the
scripts that create it, install it, measure it and take it away again.

| File | What it is |
|------|------------|
| `main.bicep` | The machine, its network, its disks, its identity and its automatic shutdown. Everything the card fixes is a parameter whose default is the card's value. |
| `deploy.sh` | `plan`, `deploy`, `bootstrap`, `status`, `deallocate`, `start`, `delete`. Reads the running deployment; refuses the wrong subscription. |
| `bootstrap.sh` | What gets installed on the machine, and what gets measured once it is there. Runs through `az vm run-command invoke`, so it needs no inbound port. |
| `../../batch-runner/scripts/check_dev_host_definition.py` | Reads this directory offline and holds it to the card. 22 checks, run in CI. |
| `../../batch-runner/dev_host_boundary.py` | Refuses to start a benchmark run on this machine. |

## Why it exists

The card allows the VM once one of five conditions reproduces. Two have, and
they are recorded rather than asserted:

1. **Kernel.** The development box runs 3.10.102. This repository's seccomp and
   user-namespace verifications do not run there — they *skip*, which is worse
   than failing, because a regression in the agentic launcher's deny-exec and
   deny-socket behaviour would pass unnoticed. `batch-runner/scripts/check_dev_host_migration_triggers.py`
   is what measures this.
5. **Codex's sandbox.** `bwrap` cannot start on a 3.10 kernel at all, so the two
   end-to-end checks in `batch-runner/tests/test_codex_runtime_end_to_end.py`
   have no host to run on. The measured verdicts for every host tried so far are
   in `batch-runner/docs/codex_sandbox_hosts.json`.

## What it will not do

These are absences on purpose, and the checker fails if any of them is filled
in:

- **No inbound SSH rule** unless somebody names a source prefix. The default is
  a security group whose only inbound rule is a deny and a network interface
  with no public address. `az vm run-command` reaches the machine through the
  Azure agent, which is enough to install it and to run the diagnostics. A
  wildcard source is refused twice: by the offline checker, and by an assertion
  inside the template that fails the deployment.
- **No role assignment.** The machine gets a system-assigned identity, because
  the card forbids storing long-lived Azure keys on it. An identity with no role
  can do nothing. Granting it one is a permission change and belongs in a
  request.
- **No password path.** Not a strong password — `disablePasswordAuthentication`
  is true and `adminPublicKey` has no default, so a deployment without a key
  fails rather than falling back.
- **No benchmark role.** See *The boundary* below.

## Using it

```bash
export GDPVAL_DEV_HOST_SUBSCRIPTION='<the external subscription>'   # ME-MngEnvMCAP756842-hjeon-1
export GDPVAL_DEV_HOST_SSH_PUBLIC_KEY="$(cat ~/.ssh/id_ed25519.pub)"

./deploy.sh plan        # what-if, changes nothing
./deploy.sh deploy      # creates it, and writes the provenance of what was created
./deploy.sh bootstrap   # installs and measures, through the Azure agent
./deploy.sh status      # what is actually running, as opposed to what this directory says
./deploy.sh deallocate  # stop paying for compute
./deploy.sh start       # bring it back up
./deploy.sh delete      # needs GDPVAL_DEV_HOST_CONFIRM_DELETE to equal the resource group name
```

`deploy.sh` refuses to run against the subscription that carries the Foundry
permissions. The two are different subscriptions and the whole point of the
external one is that this machine is not inside the other.

The machine deallocates itself at 21:00 Korea time every day. That is a ceiling,
not an idle policy — deallocating the moment work stops would need the machine to
call Azure about itself, which needs a role on its identity.

## The boundary

This VM is for development and test. It is **not** a pre-registered GDPVal
benchmark execution environment, and `bootstrap.sh` writes `/etc/gdpval-dev-host`
saying so in its first section, before anything else is installed.

`batch-runner/dev_host_boundary.py` reads that file and refuses to start an
inference run on a machine carrying it. The escape is not a flag meaning "ignore
this" — it is the card's own condition: register the machine as its own arm,
with the kernel, image, VM size, region and task manifest hash all pinned in the
marker. A partial registration is refused and names what is missing, and a run
on a kernel other than the pinned one is refused too.

The module sits at the batch-runner root rather than in `core/` because
`step8_grade.compute_grader_source_hash` hashes every `core/**/*.py`; a file
there would move the grader's source fingerprint, and invalidate the smoke run
that a paid grading run is gated on, for a module grading never calls.

## The open question this does not answer

The card fixes **Ubuntu 24.04 LTS**. That is exactly the image measured
`user_namespaces_restricted_by_security_policy` on GitHub's runners: Ubuntu has
shipped `kernel.apparmor_restrict_unprivileged_userns=1` since 23.10, and under
it Codex's sandbox creates its namespace and is then denied the capability to
bring up the loopback interface of the network it unshares.

`bootstrap.sh` **reads that sysctl and does not write it.** Setting it to 0 would
remove the restriction from every process on the machine, which is not a fix but
the absence of one, and it is one of the four shortcuts refused in
`tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md` §3b. Three tests in
`batch-runner/tests/test_dev_host_definition.py` fail if a future edit adds it.

So the bootstrap measures and reports, and the decision that follows belongs to
a person:

- **A targeted AppArmor profile** granting `userns create` to one binary. The
  sysctl stays at 1 and every other process on the machine stays restricted.
  This is a security-policy change and has to be asked for with the exact target
  and permission named.
- **An Ubuntu 22.04 image**, which needs no security change and is measured
  `ready`, but deviates from the card. A test catches exactly this substitution,
  because doing it quietly is how the host stops being the host the card
  approved.

Neither is applied here. What is recorded is what the machine reports.

## What none of this can tell you

Everything the checker reads is in this directory. A template that says
`disablePasswordAuthentication: true` and a machine with password authentication
off are two different facts, and only the first is readable from a checkout.
`./deploy.sh status` reads the other one.
