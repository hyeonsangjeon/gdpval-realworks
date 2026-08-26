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
the pinned names. It reuses `classify_endpoint` from `core/azure_ai_clients.py`
rather than matching text itself, so the two agree on what an address means.

> **Correction, recorded in section 13.** This section first said that
> reusing `classify_endpoint` made a plan checked here "checked against exactly
> the rules the real run applies". That was not true, and reusing one function
> was never enough to make it true. Seven of seventeen settings were measured
> to disagree, six of them in the direction that costs money. Section 13 has
> the measurement and what was changed. The claim now holds for sixteen of the
> seventeen, and the seventeenth is a deliberate refusal stated in writing.


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

---

## 13. 이 문서의 주장을 실제로 재어 봤습니다 (2026-08-26)

### 13.1 무엇이 틀렸나

6절에 이렇게 적혀 있었습니다.

> `classify_endpoint`를 그대로 쓰기 때문에, 여기서 검사한 계획은 **실제 실행이
> 적용하는 규칙 그대로** 검사된 것이다.

주소를 해석하는 함수 하나를 같이 쓴다는 사실만으로 "규칙 그대로"라고 적은
문장입니다. 확인한 사람은 없었습니다.

Azure 설정 17개를 **한 번에 하나씩** 바꿔 놓고, 무료 검사와 실제 실행에게
따로 물어서 답이 같은지 세어 봤습니다.

| | 답이 같은 경우 | 답이 다른 경우 |
|---|---|---|
| 고치기 전 | 10 / 17 | **7 / 17** |
| 고친 뒤 | **16 / 17** | 1 / 17 |

다른 7개 중 **6개는 위험한 방향**이었습니다. 무료 검사는 "문제 없음"이라고
말하고, 실제 실행은 시작을 거부하는 조합입니다.

### 13.2 위험한 방향으로 어긋난 6개

모두 **어느 계정·어느 프로젝트에 접속해도 되는지 못 박는 설정**입니다.

| 설정 | 실제 실행 | 고치기 전 무료 검사 |
|---|---|---|
| `AZURE_AI_EXPECTED_DIRECT_ACCOUNT` 없음 | 거부 | 문제 없음 |
| `AZURE_AI_EXPECTED_PROJECT_ACCOUNT` 없음 | 거부 | 문제 없음 |
| `AZURE_AI_EXPECTED_PROJECT_NAME` 없음 | 거부 | 문제 없음 |
| `AZURE_AI_EXPECTED_DIRECT_ACCOUNT`가 다른 계정 | 거부 | 문제 없음 |
| `AZURE_AI_EXPECTED_PROJECT_ACCOUNT`가 다른 계정 | 거부 | 문제 없음 |
| `AZURE_AI_EXPECTED_PROJECT_NAME`이 다른 프로젝트 | 거부 | 문제 없음 |

`.github/workflows/batch-run.yml`은 돈이 나가는 모든 단계에서
`AZURE_AI_REQUIRE_EXPECTED_IDENTITIES`를 `'1'`로 **고정해서** 넘깁니다. 즉 실제
실행은 저 세 이름을 **항상** 요구합니다. 그런데 363.59달러를 쓸지 말지 정하는
무료 검사는 저 세 이름을 **한 번도 쳐다보지 않았습니다.**

### 13.3 손으로 다시 옮겨 적은 목록이 또 있었습니다

`core/execution_envelope_azure.py`에 고정 자격증명 10개 이름이 **다시 타이핑되어**
있었습니다. 같은 저장소의 `scripts/azure_ai_route_preflight.py`는 같은 목록을
**가져다 쓰고** 있었는데, 이 파일만 옮겨 적었습니다.

실제로 해 봤습니다. 진짜 목록에 이름을 **하나 추가**하고 그 설정을 켜 두었더니:

```
  실제 실행:  거부 (static Azure credential environment variables are forbidden)
  무료 검사:  문제 없음 — 깨끗함
```

주소 설정 이름 4개에도 "core/azure_ai_clients.py가 읽는 이름과 같다"는 **주석이
붙어 있었지만**, 그쪽은 함수 안에 글자로 박혀 있어서 **같은지 확인할 방법 자체가
없었습니다.**

### 13.4 지금은 어떻게 하나

| 전 | 후 |
|---|---|
| 금지 자격증명 10개를 옮겨 적음 | 실행 쪽 목록을 **읽어 옴** |
| 설정 이름 4개를 옮겨 적음 | 실행 쪽에서 이름을 **읽어 옴** |
| 신원 고정 규칙 없음 | 실행 쪽 표를 **읽어서 그대로 적용** |
| 계획에 적힌 계정·프로젝트와 저장소 설정을 비교하지 않음 | **비교함** |

실행 쪽(`core/azure_ai_clients.py`)에도 손을 댔습니다. 함수 안에 글자로 박혀
있던 설정 이름들을 **파일 맨 위 한 곳으로** 꺼냈습니다. 무료 검사가 이제 그
한 곳을 읽습니다. 동작은 바뀌지 않았고, 기존 테스트 323개가 그대로 통과합니다.

### 13.5 일부러 더 엄격하게 둔 곳 하나

17개 중 마지막 하나는 여전히 답이 다릅니다.

`AZURE_AI_ROUTE_PROFILE`이 `direct-v1`이면 실제 실행은 **잘 돌아갑니다.** 무료
검사는 **거부합니다.** 이 비교는 `project-ci`로 못 박혀 있기 때문입니다.

이건 결함이 아니라 못 박은 것의 목적이고, **돈이 안 드는 방향으로** 어긋납니다.
테스트로 적어 두었습니다.

신원 이름 요구도 같은 이유로 일부러 더 엄격합니다. 실제 실행은 스위치가 켜져
있을 때만 요구하지만, 무료 검사는 스위치와 무관하게 요구합니다. **돈을 쓸 수 있는
실행 자리는 전부 그 스위치를 켜기 때문입니다.** 그 문장이 맞는지도 테스트가
워크플로 파일을 열어서 확인합니다 — 나중에 누가 워크플로를 바꾸면 문장이 조용히
낡는 대신 테스트가 실패합니다.

### 13.6 검사 결과

- 신규 테스트 41개 (이 파일에는 테스트가 **한 개도 없었습니다**)
- 그중 **20개는 고치기 전 코드에서 실제로 실패**합니다
- 아무것도 켜지 않았습니다. 승인한 금액 없음, 부른 모델 없음, 로그인 없음
- 무료 검사는 **더 많이 거부하게** 됐을 뿐, 더 허용하게 되지 않았습니다

### 13.7 고치고 나서 기존 테스트 6개가 깨졌습니다

전체 테스트를 돌렸더니 기존 파일
`tests/test_execution_envelope_advance_check.py`에서 6개가 실패했습니다.
원인은 하나였습니다. 그 파일에는 **"이제 고칠 게 하나도 없는 상태"** 라고 이름
붙인 설정 묶음이 있고 테스트 여러 개가 그걸 같이 씁니다. 그런데 그 묶음에
신원 이름 세 개가 **빠져 있었습니다.**

즉 그 파일이 "완전히 준비됨"이라고 부르던 상태는, 실제 실행이라면 **시작을
거부했을 상태**입니다. 무료 검사가 그 세 이름을 안 봤으니 테스트도 안 넣었고,
아무도 몰랐습니다. 같은 결함이 테스트 쪽에도 한 번 더 있던 셈입니다. 세 이름을
넣었고 100개 전부 통과합니다.

한 가지는 짚어 둘 만합니다. `batch-runner/README.md`와
`docs/first-experiment.md`에는 저 세 이름이 **처음부터 정확하게 적혀
있었습니다.** 사람이 읽는 설명은 맞았고, 코드가 틀렸던 겁니다.

### 13.8 바뀐 파일

| 파일 | 무엇이 바뀌었나 |
|---|---|
| `batch-runner/core/azure_ai_clients.py` | 함수 안에 글자로 박혀 있던 설정 이름 10개를 파일 맨 위 한 곳으로 꺼냄. 동작 변화 없음 |
| `batch-runner/core/execution_envelope_azure.py` | 옮겨 적은 목록 두 개를 지우고 실행 쪽에서 읽어 옴. 신원 고정 규칙을 적용함 |
| `batch-runner/tests/test_envelope_azure_applies_the_run_rules.py` | 신규. 테스트 41개 |
| `tasks/0822_saturday/TASK_PIN_AZURE_RESOURCE_IDENTITY.md` | 6절의 틀린 문장을 고치고, 이 13절을 추가 |
| `batch-runner/experiments/execution_envelope/advance_check_plan.yaml` | 계획 옆 설명을 실제 동작에 맞게 고침 |
| `batch-runner/tests/test_execution_envelope_advance_check.py` | "완전히 준비됨" 설정 묶음에 빠져 있던 신원 이름 세 개를 넣음 |
