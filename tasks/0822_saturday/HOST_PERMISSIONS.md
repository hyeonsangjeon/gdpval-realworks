# The host permissions, in one place

The V2 backend cannot run anything until a Firecracker host exists, and the
host cannot be created because the identity that would create it holds no
control-plane write anywhere. That sentence has been true since stage D. What
it lacked was the detail an owner would need to act on it: which action, at
which scope, for which principal, and what the smallest change is.

This file is that detail. It is a **report**. The change is named here and
left undone, because access belongs to whoever owns the subscription.

Everything below was read. No write was attempted, no role was requested, and
no model was called. Cost: nothing.

---

## The short answer

| | |
|---|---|
| **Principal** | the app registration behind `secrets.AZURE_CLIENT_ID` / `vars.AZURE_AI_EXPECTED_CLIENT_ID` — the same identity the paid inference runs authenticate with |
| **What it holds** | 2 role assignments, both **Cognitive Services OpenAI User**, both scoped to the Foundry account |
| **Why that blocks** | that is a data-plane inference role. It carries no `Microsoft.Compute`, `Microsoft.Network` or `Microsoft.Resources` write at all, so every host action is denied for the same single reason |
| **Smallest change** | **Virtual Machine Contributor + Network Contributor**, both at **resource-group scope**, on a resource group the owner creates first |
| **Not the change** | nothing at subscription scope, no Owner, no `Microsoft.Authorization` write, no new subscription |

The two roles are not a guess. They were evaluated against the real built-in
role definitions, and the evaluation is pinned in
`tests/test_azure_boot_host_survey.py::TestTheMinimalChangeIsCheckedNotAsserted`
so it fails if either definition is described wrongly later.

---

## What is measured, and when

The survey is `.github/workflows/azure-boot-host-survey.yml`, five reads over
the ARM control plane. It runs only on `main`, because it authenticates by
OIDC and a local `az` session reaches a different tenant — which is why a
local run reports `not_measured` rather than a wrong answer.

It has been run three times over two days, and the three agree exactly.

| | 2026-09-11 · `34549220652` | 2026-09-12 · `34683287478` | 2026-09-12 · `34684908054` |
|---|---|---|---|
| right subscription | yes, Enabled | yes, Enabled | yes, Enabled |
| `Microsoft.Compute` | Registered | Registered | Registered |
| existing VMs | 0 | 0 | 0 |
| `Standard_D8as_v5` quota, eastus2 | 100 limit / 0 in use / **100 free** (8 needed) | 100 / 0 / **100 free** | 100 / 0 / **100 free** |
| role assignments held | 2 | 2 | 2 |
| actions asked about | 3 | 3 | **12** |
| actions permitted | **0 of 3** | **0 of 3** | **0 of 12** |
| verdict | `blocked_and_the_change_is_named` | `blocked_and_the_change_is_named` | `blocked_and_the_change_is_named` |

Four of the five reads are favourable. **The block is permissions and nothing
else.** There is room, there is registration, there is no clutter.

Both artifacts are committed: `boot_host_survey.json` (`1.0`, three actions)
and `boot_host_survey_widened.json` (`1.1`, twelve). The narrower one is kept
because it is the record the earlier write-ups cite; the three actions it
measured are `false` in both, so the wider run extends it rather than
correcting it.

### Where the two assignments come from

The survey reports the *count* of assignments, never their names or scopes.
The names are in a different read — the Foundry RBAC diagnostic, run
`34347345143` (2026-09-09), which reports both assignments as `role_name:
"Cognitive Services OpenAI User"` at `scope_shape: "foundry-account"`.

That is the whole explanation for the twelve `false`s. It is not a partial
grant that needs topping up, and it is not a scope mismatch. The identity has
inference rights on one AI resource and no control-plane rights on anything.

---

## Every action the deployment would take

`infra/dev-host/main.bicep` declares six resources unconditionally and one
conditionally, and each needs its own write. The survey now asks about all of
them (`scripts/azure_boot_host_survey.py`, `artifact_version: 1.1`, merged as
PR #559); the list is derived from the template and a test re-parses the
template to prove nothing was missed.

Run `34684908054` measured all twelve against the live identity. **Every one
came back `false`.**

**Always performed — all at resource-group scope:**

| action | why |
|---|---|
| `Microsoft.Resources/deployments/write` | submit the template at all; a deployment is itself a resource |
| `Microsoft.Network/networkSecurityGroups/write` | the security group that closes the host to the internet |
| `Microsoft.Network/virtualNetworks/write` | the network and the subnet the host sits on |
| `Microsoft.Network/networkInterfaces/write` | the interface |
| `Microsoft.Compute/disks/write` | the data disk the guest images live on |
| `Microsoft.Compute/virtualMachines/write` | the machine |
| `Microsoft.DevTestLab/schedules/write` | the auto-shutdown that stops it billing overnight |
| `Microsoft.Network/virtualNetworks/subnets/join/action` | put the interface on the subnet |
| `Microsoft.Network/networkSecurityGroups/join/action` | apply the security group to the subnet |
| `Microsoft.Network/networkInterfaces/join/action` | attach the interface to the machine |

**Conditional — measured, but not part of the block:**

| action | scope | only if |
|---|---|---|
| `Microsoft.Network/publicIPAddresses/write` | resource group | `attachPublicIp` is set, and the template defaults it to `false` |
| `Microsoft.Resources/subscriptions/resourceGroups/write` | **subscription** | the resource group does not already exist |

Twelve actions measured; ten of them block. The two conditionals are reported
separately and never drive the verdict — a denial on an action the deployment
does not perform is not a block.

Two things the template does **not** need, worth stating so nobody grants them
defensively: the image is `Canonical / ubuntu-24_04-lts / server / latest`, a
free image with no Marketplace plan action, and the VM identity is
`SystemAssigned`, so no `Microsoft.Authorization/roleAssignments/write` is
involved.

---

## The minimal change

### Option A — two built-in roles at resource-group scope *(recommended)*

1. The owner creates the resource group. One action, done once, by someone who
   already has it.
2. Assign **Virtual Machine Contributor** on that resource group.
3. Assign **Network Contributor** on that resource group.

Why both. Virtual Machine Contributor covers `virtualMachines/*`,
`disks/write`, `DevTestLab/schedules/*`, `networkInterfaces/*`,
`deployments/*` and all three `join/action`s — but on network security groups
and virtual networks it grants only `read` and `join`, not `write`. Those two
writes are exactly what Network Contributor's `Microsoft.Network/*` closes.

Checked, not assumed: against the real definitions, VM Contributor alone
leaves precisely `Microsoft.Network/networkSecurityGroups/write` and
`Microsoft.Network/virtualNetworks/write` unpermitted, and the pair covers
every blocking action.

Step 1 is what keeps this off the subscription. **Neither role grants
`resourceGroups/write`**, so pre-creating the group is not a convenience — it
is the thing that removes the only subscription-scope item on the list.

### Option B — a custom role

A custom role with exactly the ten blocking actions above, at resource-group
scope, is strictly smaller than Option A: it excludes the `delete`,
`powerOff`, `restart` and extension actions the two built-ins carry. It costs
a role definition to author and maintain. Option A is recommended only because
it uses definitions that already exist.

Either way the scope is one resource group, and the grant can be removed by
deleting the assignment.

---

## What this is not

- Not a role request, and not a step toward one. Nothing here should be read
  as authorisation to run `az role assignment create`.
- Not a claim that a host in this subscription would boot a guest. That is a
  different question, answered separately on a different machine
  (`c2_first_boot.json`); it says the hardware can, not that this one will.
- Not a cost question. The existing experiment approval is unaffected — this
  changes access, not spend.
- **Not the only thing in the way.** See immediately below.
- Not urgent in the sense of blocking everything. See further below.

## The grant is the first of four gates, not the last

Reading this file and granting the two roles would not produce a real V2 run.
Three further gates sit after it, each deliberately built to require a visible
change rather than a flag:

1. **The roles**, above. Blocked, and reported here.
2. **Admission.** `AgenticV2ScriptedRunner` admits exactly one backend
   identity and defaults to the fixture's. No module outside that file is even
   allowed to mention the argument —
   `test_nothing_in_this_repository_declares_a_non_default_identity` reads
   every other module's source to enforce it, and the wiring layer documents
   that it deliberately does not forward the parameter. That test is the line
   that changes when a guest is admitted for real.
3. **Activation.** The substrate, supply-chain and microVM manifests all
   declare `production_activation: "disabled"`, and three separate validators
   reject a document that says anything else. Flipping it is a reviewable edit
   to the declarations, not a setting.
4. **`browser_run`.** The real backend refuses it entirely, including the
   local read the fixture serves. In trial_30 that same tool ended twelve of
   thirty tasks, and on the real backend its refusal is wider, not narrower.
   `TURN_LIMIT_COMPARISON_DESIGN.md` carries the measurement.

Gates 2 and 3 are intentional and cost nothing to pass when the time comes.
Gate 4 needs no access change at all and is the one piece of this that can be
worked on today.

Gate 4 is also larger than its name. The instruction text the model reads
names three tools as refusing, and that list fits neither backend: on the
fixture only two tools have no working call, and on the microVM backend
`exec_run` — one of the three the text says is shut — is the capability the
whole host exists to provide. Granting the roles and booting a host would
produce a machine that runs commands and a model that has been told it
cannot. Correcting the text is therefore on the critical path rather than
beside it, and it needs no access change.

A second item sits beside it, also needing no access change: the model is
shown a paraphrase of its own previous turns rather than the turns, with the
arguments dropped, and completing that paraphrase as text ended five more of
trial_30's thirty tasks. That one is a defect rather than a description, and
it is backend-independent — it will follow the run onto a real host unchanged.
`TURN_LIMIT_COMPARISON_DESIGN.md` §4 carries both.

## What continues without it

Everything on the code side, which is most of the remaining work: the microVM
backend's second verification standard, the ledger and retry wiring, the
offline integration and isolation tests, and the run preparation. None of it
needs a host or an access change.

What it does block is the real execution backend. Until that exists, the V2
stages run against the fixture backend, and a fixture result must never be
reported as an isolation result. When a real backend does exist, the sequence
is 5 → 30 → 220 on the verified path, with no implicit fall-back to the
fixture.

## Open, and honest about it

The ten-action list is no longer derived. Run `34684908054` read all twelve
against the live identity and every one is `false`, which closes the gap this
section used to describe. It cost nothing, and it can be re-read any time from
`main`.

What remains genuinely open is the sentence that was never a permissions
question: **nobody has measured that a machine in this subscription boots a
guest.** The survey says a host could be created if the roles existed. It does
not say the host would work. `c2_first_boot.json` answers that for different
hardware in a different subscription, which is evidence about the hardware
class and not about this one. The order is roles → host → boot test → backend,
and only the first is currently named.

`TASK_AGENTIC_SANDBOX_V2_ACTIVATION.md` still says "none of the three writes
permitted". That was true of the measurement it describes and remains true;
it is narrower than what this file reports, not in conflict with it.
