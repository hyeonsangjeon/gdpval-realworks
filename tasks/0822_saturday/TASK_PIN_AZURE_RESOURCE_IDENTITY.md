# Pin the Azure resource, not just the deployment name

- Written: 2026-08-25
- Status: **done and merged.** This document records why the work was needed and
  what it changed.
- Related GitHub Project: hyeonsangjeon/projects/5 — card
  "같은 GPT 모델의 실행 환경별 성능 비교"

## 1. The problem a person actually hits

The run-place comparison asks one question: when the same model does the same
work, does the place it runs in change the result? Everything except the run
place has to be held still, and a written plan lists fifteen things that must
match everywhere. One of them is the deployment name.

**A deployment name does not identify a deployment.**

Two different Azure AI Foundry accounts in the same Azure tenant can each hold a
deployment named `gpt-5.4`. They can sit in different regions, be pointed at
different versions of the model, and apply different content filters. Nothing
about the name distinguishes them.

So the comparison could have run one place against one account's `gpt-5.4` and
another place against a different account's `gpt-5.4`, and every check would
have reported that all three places used the same deployment. The resulting
table would have looked like a clean measurement of run places while actually
measuring two different Azure resources. Nobody reading the table afterwards
could have told.

## 2. This is not hypothetical

While preparing the five-task advance check, the Azure tenant available at the
time was listed. It held:

- one account with a deployment named exactly `gpt-5.4`
- a second, different account with a deployment named exactly `gpt-5.4`
- a third account holding the same underlying model under a different
  deployment name

Two accounts, same deployment name, different resources. The hole was open and
reachable, not theoretical.

## 3. What the code said before this change

- `batch-runner/experiments/execution_envelope/advance_check_plan.yaml` pinned
  `provider`, `deployment`, `resolved_model`, and `api_version`. It said nothing
  about which Azure account or project held that deployment.
- `batch-runner/core/execution_envelope_preflight.py` took exactly one piece of
  Azure information: the route profile, a single word. It compared that word to
  `project-ci` and stopped there.
- When the route profile was absent, the check reported
  `evidence_insufficient` with the sentence "the Azure route profile was not
  measured, so it is unknown whether this environment could start."

That last sentence is the second half of the problem. It is the same message
whether nobody had configured Azure at all, or Azure was configured and pointing
at the wrong account, or the account was in a tenant this machine cannot reach.
Those three have completely different fixes, and the reader was sent looking in
the wrong place. Working out which one was actually true took a manual
investigation with the Azure command-line tool.

## 4. Goals

1. Make the plan pin the Azure account and project, so the deployment is
   identified exactly rather than by a name that is not unique.
2. Make the free check read the endpoint settings that the run itself will use,
   and refuse when they name any other account or project.
3. Make the refusal say which specific thing is wrong and what the correct value
   looks like, so no manual investigation is needed.

## 5. What this change deliberately does not do

- **It does not contact Azure.** The check stays free and offline. It reads
  settings and compares them. It never signs in, never asks for a token, and
  never spends anything. It can therefore say "the settings name the intended
  resource", which is a different and weaker claim than "the resource can be
  reached", and it says only the weaker one.
- **It does not create credentials, relax a security rule, or invent an
  address.** Where information was missing, the run stays blocked.
- **It does not switch to a reachable account.** Substituting a different
  account is exactly the failure this work exists to prevent.

## 6. The design, in plain terms

A new block in the plan names the Azure resource:

```yaml
azure_connection:
  account: "hjeon-fdpo-foundry-eus2"
  project: "gdpval-realworks"
  route_profile: "project-ci"
```

These two names are not new information and are not secrets. This repository
already records them for its own automated runs, as the repository settings
`AZURE_AI_EXPECTED_PROJECT_ACCOUNT` and `AZURE_AI_EXPECTED_PROJECT_NAME`.
Repository settings, unlike repository secrets, are readable by design.

A new module reads the endpoint settings from the environment, classifies them
using this repository's own endpoint rules, and compares what it finds against
the pinned names. Because it reuses `classify_endpoint` from
`core/azure_ai_clients.py` rather than matching text itself, a plan checked here
is checked against exactly the rules the real run applies.

## 7. Files and how information flows

| File | Role |
|---|---|
| `batch-runner/core/execution_envelope_azure.py` | New. Holds the pinned resource and works out what is wrong with the settings. |
| `batch-runner/core/execution_envelope_preflight.py` | Calls the new module when the Azure run place takes part, and adds anything it finds to the list of problems. |
| `batch-runner/scripts/check_execution_envelope_advance_check.py` | Prints which account and project the settings name. |
| `batch-runner/experiments/execution_envelope/advance_check_plan.yaml` | Gains the `azure_connection` block. |
| `batch-runner/tests/test_execution_envelope_advance_check.py` | Gains the tests below. |

The flow: plan file → pinned account and project → compared against the
environment settings → problems added to the one list the tool prints and the
exit code is built from.

## 8. Safety, cost, and no-silent-substitution conditions

- Every check reads settings only. Nothing is spent and no model is called.
- No secret is printed. The account and project are settings; the endpoint
  addresses are compared, and only the account and project names are shown back.
- Fixed credentials that this repository refuses to run with — an interface key,
  a client secret, a stored password — are reported during the free check rather
  than after a run has been scheduled.
- The deprecated combined endpoint setting is reported, because this repository
  refuses to start while it is set.
- If the Azure run place does not take part in a plan, the check is skipped
  entirely: there is then no Azure resource for the comparison to get wrong.
- Nothing here removes a blocked run place from the comparison. That still
  requires a person to edit the plan.

## 9. Order the work was done in

1. Confirm the hole is real by listing the deployments actually present.
2. Confirm the plan pins no account and the check takes no account.
3. Add the module that compares settings against the pinned resource.
4. Add the plan block, with the evidence written beside it.
5. Wire it into the check and the printed output.
6. Add tests, including one that changes only the account and nothing else.
7. Run the repository's whole test suite.

## 10. How this was checked

Automated, in `batch-runner/tests/test_execution_envelope_advance_check.py`:

- a correctly pointed setup is accepted, and the account and project it found
  are reported back
- **the same deployment name on a different account is refused** — the settings
  are well formed, the route is right, the deployment name is unchanged, and
  only the account differs; this is the case that used to pass
- a different project on the right account is refused
- a missing project address is refused, and the message contains the address it
  should have held
- "the route profile is not set" is told apart from "the route profile is set to
  the wrong thing"
- the deprecated combined endpoint setting is refused
- each fixed credential is refused up front
- a direct address on another account is refused
- a plan that forgets to pin the account is refused
- a plan without the Azure run place skips the check and raises nothing

By hand: run the check with the Azure settings unset and confirm it names both
missing settings and prints the exact address that should be supplied.

## 11. Done when

- [x] The plan pins the Azure account and project.
- [x] The check refuses any other account or project.
- [x] The refusal names the specific setting and the value it should hold.
- [x] A test exists that changes only the account and requires a refusal.
- [x] The whole repository test suite passes.

## 12. Known blockers and the next decision

This change makes the Azure run place's requirements checkable. It does not
make the resource reachable.

At the time of writing, the Azure AI Foundry account this comparison is pinned
to sits in a different Azure tenant and a different subscription from the one
signed in on the machine the work was done on. A request for access to the
pinned tenant is rejected by a Conditional Access policy, and the only remaining
path is an interactive sign-in through a web browser.

That is an access decision belonging to whoever administers the tenant, not
something this repository can settle. Until it is settled, the Azure run place
stays blocked and the comparison does not start, because dropping it and running
the other two would produce a different comparison from the one that was agreed.
