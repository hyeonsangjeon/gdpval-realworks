# GHCP 고정 5문제: 선택지 1·3의 첫 턴 실행 계획서 — 미실행

작성 기준: 2026-11-11, 브랜치 `leader/ghcp-patched-runtime-receipt-20261106`,
조사 HEAD `4735721587dc5d455c2a260d91e7287ec8247464`.
소유자는 아직 **1(패치된 GHCP)** / **3(미패치 기본 정책)** 중 고르지 않았다.
이 문서는 후속 구현·승인에 필요한 계획이지 실행 승인이나 실행 가능한 명령이 아니다.
`execution_allowed=false`와 기존 잠금을 유지한다. 최초 계획서 커밋은
`5c385bdc1549e52c3a79591aa794b2cdcc0ab552`다. 아래 수집 순서 상태는 후속
오프라인 구현으로 갱신했다. §6은 `e9de3a5188a5`를 기준으로 공개 과금 문서·핀 소스·
기존 zero-turn 카탈로그를 재조사한 내용이다. dispatch·인증·모델 턴·유료 실행·채점은 하지 않는다.

23:2x 후속 지시에서는 `a40b44056557`을 기준으로 두 선택지 공통의 토큰 장부
**soft guard**를 추가했다. 하드 비용 상한이나 소유자 예산 승인으로 승격하지 않는다.

## 1. 이번에는 나 경로: zero-turn 추가 실행 없음

제어면 연결과 경로 정보는 이미 확인됐다. 남은 것은 **실제 과제 컨트롤러의
턴/스트림/수집 연결**과 **네이티브 도구가 쓴 출력의 회수**다. 전자의 성공을
후자의 성공으로 대신할 수 없다.

| 검증 대상 | 현 가드 안에서 zero-turn 가능 여부 | 근거와 남은 범위 |
| --- | --- | --- |
| WebSocket·인증·세션/native thread·구독/종료 | 가능, 선택지 1 run `42964958467`에 기존 증거 있음 | `ghcp_ahp_probe.py:705,734`, `ghcp_ahp_thread_policy.py:70,110-118` |
| job TMPDIR의 실제 경로·소유자·정규화·보고된 쓰기 범위 | 가능, 같은 run에서 측정됨 | `ghcp_ahp_wire_preload.cjs:242,260`; 경로 정보이지 실제 쓰기 성공은 아님 |
| 과제 첫 턴 응답·스트림·capture 종단간 연결 | 불가, 현 경로에서는 턴 필요 | `ghcp_ahp_connection.py:163-170,276-308`; 별도 과제 경로는 `ghcp_sol_paid_gate.py:219-229`에서 잠김 |
| 네이티브 도구의 출력 쓰기와 최종 회수 | 불가, 현 zero-turn 허용 목록으로 실행할 수 없음 | `ghcp_ahp_wire_preload.cjs:14-18,374-375,414`: `command/exec`, 턴·도구 실행은 허용하지 않음 |

공식 [Codex app-server 문서](https://developers.openai.com/codex/app-server/)의
`command/exec`는 턴 없이 sandbox 안에서 명령을 실행하는 API다. 그러나 이 저장소의
zero-turn 가드는 그 메서드를 허용하지 않는다. 이를 새로 허용하거나 러너에서
직접 파일을 써서 네이티브 쓰기 증거로 바꾸는 것은 이번 범위가 아니다.
별도 승인된 model-free canary라면 파일 접근만 검증할 수 있고, 모델 출력은 증명하지 못한다.

핀 소스 `codexAgent.ts:2687-2690`은 자식용 TMPDIR를 만들고, `:2703-2706`은
자식 `close` 때 비동기 삭제를 예약한다. 이 제품 동작은 패치하지 않는다.
과거 `SessionClient.capture()`의 종료 후 원본 읽기만으로는 수명이 맞지 않았으므로,
공통 컨트롤러의 **정상 dispose/terminate보다 앞**에 수집·봉인을 연결했다.

| 수집 항목 | 상태 | 확인 범위 / 남은 조건 |
| --- | --- | --- |
| 선택지 1 job TMPDIR → 수집·봉인 → 삭제 | 해결됨 — 코드·fixture | `OutputCollection(profile=choice1_job_tmpdir)`, 실제 임시 파일 bytes와 해시·목록 대조; native 모델 쓰기 증거 아님 |
| 선택지 3 workspace → 수집·봉인 → TMPDIR/workspace 삭제 | 해결됨 — 코드·fixture | `profile=default_policy_unpatched`, 선택지 1 판정과 분리; 빈 writableRoots를 read-only로 해석하지 않음 |
| 선행 삭제·부분 수집·링크/특수 파일·크기 상한 초과 | 해결됨 — 오프라인 거부 경로 | 과제/gate 실패, 성공 산출물·grader 입력 발행 금지; 실패 확정 뒤 강제 정리는 허용 |
| 실제 호스트의 writer/cleanup hold 및 관측 root 연결 | 남음 | 현재 live 과제 port가 미구현. hold 부재/실패는 거부하며, fixture 성공을 native 정지 증거로 바꾸지 않음 |
| 실제 모델 출력의 생성·회수 실측 | 남음 | 소유자 선택·별도 실행 승인이 필요한 최초 실제 과제/도구 턴; 이번에는 실행하지 않음 |

새 코드 위치: `ghcp_ahp_client.py:216`이 admission을 닫은 뒤 수집하고,
`ghcp_ahp_output_collection.py`의 `collect_and_seal` → `after_termination` 순서로
진행한다. 별도 디렉터리에 마스킹된 snapshot과 원본 파일 SHA256/목록을 저장하고,
fsync·재독해를 마친 뒤에만 정상 정리를 허용한다. 봉인은 프로필·디렉터리 식별자와
새 nonce에 결합되어 다른 작업의 봉인 재사용을 거부한다. 독립 목록과 수집 결과를 대조하고
바이트 해시도 다시 읽어, 같은 크기의 덮어쓰기가 시각 비교를 통과하지 못하게 한다.
봉인 파일·lifecycle receipt 누락/변조는 삭제 후에도 재검사한다.

두 5과제 fixture 경로는 반드시 이 수집기를 바인딩한다. bound client는 기존
`capture(workspace=...)`로의 우회를 거부하며, gate validator도 봉인/receipt가
없는 capture를 거부한다. 일반 진단용 legacy capture는 유료 실행 경로가 아니다.
`hold_outputs`는 writer와 cleanup을 함께 보류한다는 transport 계약이며,
현재 테스트의 응답은 `synthetic=true`다. 실제 프로세스 정지 방법·중단 지연까지
검증된 것으로 쓰지 않는다. 기존 `execution_allowed=false`는 그대로다.

핀 소스 위치는 VS Code commit `2c33b50b16c472efe58357d1d2a8a5414bc23fbf`의
`src/vs/platform/agentHost/node/codex/codexAgent.ts`다. 위 Python/CJS 위치는
조사 HEAD의 `batch-runner/` 기준이다. `thread/start`와 `turn/start`를 구분하는
공식 문서는 프로토콜 참고이며, 최신 예제나 카탈로그로 핀의 적용값을 대체하지 않는다.

## 2. 두 선택지의 기존 관측 — 유료 실행 증거 아님

각 행은 GitHub Actions `ubuntu-24.04`에서 수행한 **인증 zero-turn 1회**다.
네이티브 `thread/start` 응답과 같은 프로세스의 적재 측정이 출처이며,
벤치마크 과제·모델 턴·품질·요금 측정은 포함하지 않는다. 서로 다른 제품/정책
구성이므로 단일 변수의 인과 비교나 성능 우열로 읽지 않는다.

| 항목 | 선택지 1: 패치된 GHCP | 선택지 3: 미패치 기본 정책 |
| --- | --- | --- |
| zero-turn / 그 실행의 커밋 | `42964958467` / `e0d80a089630` | `42988846330` / `4735721587dc` |
| admission 범위 | `authenticated_zero_turn_only` | `default_policy_unpatched_zero_turn_only` |
| sandbox 원보고 | `workspaceWrite` | `workspaceWrite` |
| writableRoots | 측정된 잡 전용 TMPDIR 1개 | `[]`; `excludeTmpdirEnvVar=false`, `excludeSlashTmp=true` |
| approval / permission profile | `untrusted` / `vscode-workspace-read-only` | `on-request` / `vscode-workspace` (`extends=vscode-runtime`) |
| network | `false` | `false` |
| 판정 | `read_only_except_job_tmpdir` | `default_workspace_policy_observed` — read-only 아님 |
| native 초기 model / effort | `gpt-5.6-sol` / `max` | `gpt-5.6-sol` / `max` |
| served model / context / web | `not_reported`; `deferred_to_first_turn` | `not_reported`; `deferred_to_first_turn` |
| admission / 거부 사유 | `true` / `[]` | `true` / `[]` |
| 세션 / native thread / 턴 / CAPI 추론 | `1 / 1 / 0 / 0` | `1 / 1 / 0 / 0` |
| patched_ghcp / execution_allowed | `true` / `false` | `false` / `false` |

선택지 3의 `writableRoots=[]`는 추가 명시 root가 없다는 응답이지 read-only가
아니다. 기본 workspace/TMPDIR 쓰기 의미가 남는다. 선택지 1의 별도 빈-root
판정을 이 프로필에 적용하지 않는다. 초기 model/effort는 served model/effort의
증명이 아니며, deferred 항목은 통과 수에 넣지 않는다.

이 표는 [오프라인 리허설 문서](ghcp-fixed-five-offline-rehearsal.md)의
당시 준비 상태(선택지 3 증거 없음)를 갱신한다. 그 과거 문서와 receipt는 변경하지 않는다.
선택지 3의 별도 정책 계약은 [해당 문서](ghcp-ahp-default-policy-unpatched.md)에 있다.

## 3. 선택지 1 실행 계획 — 패치 제품임을 명시

소유자가 패치 제품과 정책을 선택하고 첫 턴 비용·실행 범위를 별도로 승인한 뒤에만
다음 준비를 진행한다. 선택 자체가 잠금을 해제하거나 dispatch를 승인하지는 않는다.

1. VS Code 1.144.0/Chat 0.72.0/Codex SDK 0.163.0/Copilot CLI 1.0.103을 유지한다.
   원 패치와 후속 패치 묶음 SHA256은
   `6d869d65ec18a5aba93528f27e1277ac37b48a7da439065911e11e6c71f33856`,
   빌드·적재 SHA256은
   `5006baa5e4e032cf28f47de802b386ebed6b2c3616943943b3cfa06fce4a7c43`다.
   receipt·JSON/Markdown 요약에 `patched_ghcp=true`와 같은 프로세스의 적재 증거를 유지한다.
2. 정책 게시 후 prewarm, native 초기 Sol/Max, approval `untrusted`, permission
   `vscode-workspace-read-only`, network `false`, 잡 TMPDIR 이외 쓰기 불가를 재검사한다.
   예전 run의 TMPDIR 경로나 PID를 새 세션에 재사용하지 않는다.
3. 현재 zero-turn 전용 패치 staging/관리 IPC 연결을 **별도 검토된 live connection/task
   경로**에 연결해야 한다. 현재 `ahp-connection`은 일반 `prepare`를 부를 뿐
   선택지 1 패치 staging을 수행하지 않는다(`agentic-v2-ghcp-sol-gate.yml:539-545`).
   `patched_runtime_activation_pending_owner`는 그대로 잠겨 있다
   (`ghcp_ahp_patched_runtime.py:51-53`).
4. 입력은 원본·읽기 전용으로 분리한다. 원문 문제·reference·developer instructions는
   바꾸지 않는다. 원문 deliverable 요구와 잡 TMPDIR 안의 출력 위치를 연결하고,
   §1의 수집·봉인 코드는 fixture에서 검증됐으며, 실제 port의 writer/cleanup hold와
   native observer의 root 바인딩 연결은 남아 있다. workspace/HOME/공용 `/tmp`를
   writable root에 더하거나 심볼릭 링크로 우회하지 않는다.
5. 아래 연결 확인을 통과한 뒤에도 자동으로 5문제를 열지 않는다. 동작 중인
   live task controller, 도구/시간 상한과 비용 중단 장치를 검토하고 같은 run의
   연결 증거를 검사하는 잠금을 정식 구현으로 해결해야 한다.

### 선택지 1의 dispatch 입력 명세 — 현재는 실행 금지

Workflow는 `agentic-v2-ghcp-sol-gate.yml`, ref는 위 브랜치의 **별도 승인된 새 SHA**다.
아래는 기존 입력 이름/값의 명세이며, 지금 HEAD로 보내면 패치된 과제 경로가
되는 것이 아니다. `connection_served_attestation_unavailable`와
`ahp_paid_contract_unverified`는 그대로 남아 있다.

| 기존 입력 | 독립된 1턴 연결 확인 | 후속 고정 5문제 |
| --- | --- | --- |
| `dry_run` | `false` | `false` |
| `execute_paid` | `true` | `true` |
| `execution_adapter` | `ahp-draft` | `ahp-draft` |
| `connection_only` | `true` | `false` |
| `capability_only` | `false` | `false` |
| `authenticated_zero_turn` | `false` | `false` |
| `default_policy_unpatched` | `false` | `false` |

연결 프롬프트는 기존 값 그대로
`Reply with exactly CONNECTED. Do not use any tools.`다.
상한은 클라이언트 **1턴 / 0도구 / 120초**, 완료 응답은 정확히 `CONNECTED`여야 한다
(`ghcp_ahp_connection.py:24-25,136-160`). 첫 턴 메타데이터 가드도 모두 통과해야 한다.
이 연결 확인은 그 자체가 유료일 수 있다. 무도구 연결 성공은 출력 파일 경로를 증명하지 않는다.
현재 고정 5문제 dispatch도 같은 run에서 연결 잡을 다시 요구하므로, 이전 run의
연결 receipt를 재사용하거나 그 추가 연결 턴의 비용을 빼고 계산하면 안 된다.

## 4. 선택지 3 실행 계획 — 미패치 기본 정책을 별도 조건으로 유지

소유자는 `on-request`/`vscode-workspace`와 기본 workspace 쓰기를 수용하는지
명시해야 한다. 선택지 1의 read-only 판정을 지우거나 기본값을 untrusted로 표기하지 않는다.

1. 원본 agent host SHA256
   `bf1c335134a145a8c2af6e00975c3320ef1ad21f542f6c07fdf1361e3cf94780`을 사용한다.
   `patched_ghcp=false`, 별도 비교 행/출력 디렉터리/receipt 체인을 유지한다.
   두 패치와 선택지 1 경로는 그대로 둔다.
2. 기본 정책은 `{}`에서 읽고 raw sandbox·approval·network·permission·roots를 기록한다.
   기본값 수용은 권한 축에 한정한다. 현재와 같이 model=Sol·effort=max·context=1M
   요청은 명시적으로 유지하며, 요청값은 첫 턴 보고값의 대체물이 아니다.
   network는 계속 `false`, Codex sandbox/netns도 그대로다. 새 세션마다 실제 보고값을
   비교한다. 무인 `on-request` 승인이 발생하면 자동 승인·`never` 변경 없이 중단한다.
3. 쓰기 범위가 다르므로 새 ubuntu-24.04 잡/작업 디렉터리, 읽기 전용 원본 입력,
   writable 작업 사본·출력의 잡 내 한정, 호스트 제어 파일/자격증명 분리를 구현·검토한다.
   기본 정책 자체가 VM 전체 격리를 증명하는 것은 아니다. agent 도구가 secret이나
   runner 제어 파일에 접근할 수 없다는 검증 없이는 유료 실행을 열지 않는다.
4. 수집·봉인·삭제는 같은 컨트롤러에서 별도 프로필로 fixture 검증됐다. live task
   transport/hold·관측 root 연결·첫 턴 가드·상한·비용 준비는 선택지 1과 같이 남아 있다.
   데이터·문제 순서·채점 계약은 같게 두되 정책 차이는 계속 별도 조건으로 기록한다.

### 선택지 3의 dispatch 입력 명세 — 현재 유료 selector 없음

현재 `default_policy_unpatched=true`가 유효한 조합은 다음 **zero-turn 전용**이다.
이번에는 이 조합도 dispatch하지 않는다.

| 입력 | 현재 유효한 선택지 3 zero-turn 값 |
| --- | --- |
| `dry_run` / `execute_paid` | `true` / `false` |
| `execution_adapter` | `ahp-draft` |
| `connection_only` / `capability_only` | `false` / `false` |
| `authenticated_zero_turn` / `default_policy_unpatched` | `true` / `true` |

1턴/5문제의 공통 모드 값은 §3 표와 같아야 하지만, **선택지 3을 지정할 유료
프로필 입력은 현재 없음(`not available`)**이다. 새 이름을 있는 것처럼 쓰지 않는다.
별도 승인된 명시적 유료 selector와 기본정책 전용 live admission/receipt 경로를 먼저
추가하고, 그 이름·값을 이 문서에 확정한 뒤에만 실행 가능한 dispatch 명세가 된다.
`default_policy_unpatched=true`와 `execute_paid=true`를 섞으면 기존 guard가 거부한다
(`agentic-v2-ghcp-sol-gate.yml:76-94`). 반대로 이를 `false`로 바꾸는 것만으로
선택지 3 유료 실행이 되는 것도 아니다. CLI fallback으로 대체하지 않는다.

## 5. 두 계획에 공통인 중단·수집 계약

실행 위치는 GitHub Actions `ubuntu-24.04`, environment는 `ghcp-sol-gate`,
permissions는 `contents: read`다. `COPILOT_GITHUB_TOKEN`은 소유자가 유효성을
책임지고 필요한 인증/실행 단계의 env에만 노출한다. argv·파일·artifact에 저장하지
않고, 기존 redaction과 독립 유출 검사를 유지한다. 만료 예상은
**2026-11-11 16:50Z(11-12 01:50 KST)**이며 실제 만료값을 읽어 확인한 것은 아니다.
401/403이면 즉시 중단하고 재시도하지 않는다. 토큰 갱신은 소유자 작업이다.

### 과제와 상한

고정 과제 ID/순서는 `ghcp_sol_actions_gate.py:27-33`의 5개를 그대로 사용한다.
입력은 원본 catalog SHA256
`5f1eca853979b2b4efe6c6ba656545c3a416da920e3faf067d52f5d8ac4ae0eb`와
dataset revision `11e7900cdcac61bc4daf59e65feb238acda98fbf`에 결합한다.
과제마다 새 workspace·세션/thread를 쓰며 대화·캐시·이전 출력을 재사용하지 않는다.

과제별 상한은 **64턴 / 32도구 호출 / 1,200초**, 재시도 0회다
(`ghcp_ahp_client.py:46-57`). 상한 도달 시 새 작업을 받지 않고 해당 과제를
취소/종료한다. 실제 paid matrix는 `max-parallel: 1`, `fail-fast: true`로 대기 과제를
중단한다(`agentic-v2-ghcp-sol-gate.yml:598-603`). 리허설에서 나머지 4과제를 계속
돌린 것과 구분한다. 잡의 25분/외부 1,230초 timeout은 과제 1,200초 예산을 늘리지 않는다.

이는 클라이언트 수락/관측 상한이다. 이미 수락된 1턴과 서버 내부 모델/도구 실행,
종료 지연에는 유한 상한이 아직 증명되지 않았다(`ghcp_ahp_client.py:37-44`).
따라서 64턴을 64번의 provider/premium request나 확정 비용 상한으로 환산하지 않는다.
네이티브 실행 전 제어와 이미 시작된 작업의 중단 검증은 유료 경로를 열기 전 필수다.

### 첫 턴 가드

연결 잡과 **각 과제 자신의 첫 턴**에 다음 보고값을 요구한다.
앞선 연결/zero-turn receipt나 카탈로그·요청값으로 빠진 값을 채우지 않는다.

| 항목 | 요구값 | 읽는 응답 필드 |
| --- | --- | --- |
| served model | `gpt-5.6-sol` | 완료 CAPI 응답 `response.model` |
| effort | `max` | 완료 CAPI 응답 `response.reasoning.effort` |
| context | 정수 `1000000` | 같은 thread/turn의 `thread/tokenUsage/updated.tokenUsage.modelContextWindow` |
| web 사용 | `false` | 완료 응답의 명시적 `response.output[*].type`에 `web_search_call` 없음 |

`ghcp_ahp_first_turn.py:56-130`은 정확히 1개의 native `turn/start`, 같은
프로세스/stream/id의 성공 응답, 1개의 provider 요청과 완료 응답, 오류 없는 capture를
요구한다. 필드 누락·불일치·모순·알 수 없는 output kind·stream 잘림·기한 초과면
그 과제를 중단한다. 빈/없는 값을 기본값으로 바꾸지 않는다. 실제 가드는
`ghcp_ahp_client.py:448-452`에서 첫 `chat/turnComplete` 때 검사하고, 다음
`send_turn`도 검증 전에는 거부한다(`:269-270`).

현재 가드가 첫 턴 **내부에서 이미 실행된 도구를 사전에 막았다는 뜻은 아니다**.
유료 구현에서는 증거 확인 전 도구 실행/승인과 다음 턴을 보류할 수 있는지 별도
확인해야 한다. 도구 진행 없이는 필수 필드를 못 얻거나 사전 차단을 보장하지 못하면
그대로 중단하며 가드를 늦추지 않는다. 서버가 이 필드를 모두 줄지는 미검증이다.
값이 와도 runtime response/SDK 보고이지 모델 내부의 독립 attestation은 아니다.

### 수집과 채점 인계

문제별 transcript, 도구 호출/명령 이벤트, 실제 입력·출력 bytes/hash,
첫 턴 증거, 종료 코드·cleanup을 빠짐없이 남긴다. 도구 입력 문자열은 실행 증거로
표기하지 않는다. 심볼릭 링크·특수 파일·범위 밖 경로·capture 누락·해시 불일치·
유출 검사 실패는 fail-closed다. §1의 수집·봉인·삭제 순서는 구현·fixture 검증됐고,
실제 호스트 hold/관측 root 연결과 native 실측은 남았다. 출력 보존 실패를 빈
deliverable 성공으로 처리하지 않는다. fixture의 `workspace/`는 삭제된 원본이 아니라
봉인에서 재구성한 export mirror이며, 원본 runtime 경로와 구분해 검증한다.

실패 과제는 `status=error`와 진단을 남기고 성공 deliverable로 발행하지 않는다.
검사된 결과만 기존 `workspace/step2_inference_results.json` 및
`workspace/upload/deliverable_files/<task-id>/...` 형식으로 정리한다.
채점 입력 계약 통과와 모델 채점은 별개다. 채점 실행에는 별도 승인·비용 예산과
5과제용 inference/grading identity가 필요하며 full-220 identity를 재사용하지 않는다.

## 6. GHCP usage 기준 비용 상한과 실행 전 결정

2026-11-11 조사 결론: **Sol 요율은 확인했지만, 이 Codex AHP 경로의 과제당 하드
사용량 상한은 확인하지 못했다.** CLI의 `--max-ai-credits`는 진행 중 응답을
끝낸 뒤 멈추는 soft limit이며, 별도 네이티브 Codex 세션에 전달되는 계약도 없다.
21:5x 조사 당시에는 코드 변경이 없었다. 23:2x 지시로 아래 별도 soft guard를
구현했으며 핀·봉인·기존 거부 조건·실행 잠금은 유지한다. 출처와 필드별 구분은
[과금·사용량 조사](ghcp-fixed-five-usage-budget.md)에 정리했다.

| 단위/항목 | 두 선택지의 현재 값 | 해석 |
| --- | --- | --- |
| 입력·출력·reasoning·cache 토큰 | 첫 턴 미실행, `not available` | 수신한 GHCP/SDK usage 필드만 출처와 함께 보존; 미보고는 0이 아님 |
| Sol 공개 요율: 입력 / cache read / cache write / 출력 | 기본 `400 / 40 / 500 / 2000`, long-context `800 / 80 / 1000 / 3000` AI credits / 1M tokens | GitHub 요율과 두 기존 zero-turn 카탈로그가 일치; 사용량·청구액 실측 아님. `1 AI credit = $0.01` |
| premium request 수·Sol 배수 | 실제 값·숫자 상한 모두 `not available` | 배수 과금은 일부 기존 연간 플랜의 legacy 방식. 공개 legacy 표에 Sol 배수 없음; 계정 플랜은 조회하지 않음 |
| 선택지 1: 연결 1회·과제당·고정 5문제·채점 비용 상한 | 모두 `not available` | 패치된 GHCP의 카탈로그 가격 확인은 예산 차단 증거가 아님 |
| 선택지 3: 연결 1회·과제당·고정 5문제·채점 비용 상한 | 모두 `not available` | 기본 정책 수용도 동일한 사용량·진행 중 요청의 상한 문제를 해결하지 않음 |

GitHub의 [현재 과금 문서](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing)는
토큰별 AI credit 과금을 설명한다. Sol 기본/long-context 경계는 입력 `272K` tokens다.
Max는 더 많은 reasoning 토큰을 쓸 수 있지만 고정 premium 배수는 공개되지 않았다.
1M 설정 자체를 매 요청의 입력 1M tokens나 long-context 청구 실적으로 바꾸지 않는다.

5과제에 대해 계산 가능한 것은 클라이언트 허용량 `5 × 64 = 320`턴이다.
`5 × 32 = 160`도구와 `5 × 1,200 = 6,000`초도 클라이언트 기준 합계이며,
서버 내부 작업·취소 지연·청구량의 최악 상한이 아니다.
[legacy의 사용자 프롬프트당 1건 규칙](https://docs.github.com/en/copilot/reference/copilot-billing/request-based-billing-legacy/copilot-requests)이
해당 계정/경로에 적용되고, 모든 과금 프롬프트가 이 admission을 거치며,
Sol 배수 `M`이 확인된다는 조건에서만 과제당 `64M`, 5과제 `320M` premium requests가 된다.
그 규칙에서는 자율 도구 호출에 `160M`을 더하지 않는다. 여기서는 Sol의 `M`과
legacy 적용 조건이 확인되지 않아 **5과제 최악 premium request 수는 `not available`**이다.
연결 확인 1턴과 별도 grader는 이 320턴에 포함하지 않는다.

현재 토큰 과금에서는 한 클라이언트 턴에 여러 모델 요청·compaction이 들어갈 수 있고,
최대 provider 요청 수·누적 과금 토큰·취소 후 초과분의 유한 상한이 증명되지 않았다
(`ghcp_ahp_client.py:6-10,37-44,594-595`). 따라서 공개 요율을 알아도
5과제 AI credits/USD 최악 상한은 `not available`이다. 이는 무한 과금이라는 관측이
아니라, 주어진 64턴·32도구·1,200초만으로 유한 청구 상한을 도출할 수 없다는 판단이다.

`gpt56_sol_ghcp_codex_vm_gate.yaml:119-133`은 GHCP native usage만 쓰고,
미보고/미가격 항목을 null과 사유로 남기며 OpenAI/Foundry 요율 대입을 금지한다.
토큰 usage·native context·provider 호출 수·premium request·청구액은 서로 대체하지 않는다.
1M은 context 요구값이지 출력 토큰 또는 지출 상한이 아니다.

### 토큰 장부 soft guard — 코드·fixture 확인, 유료 미실행

`ghcp_ahp_token_ledger.py`와 `ghcp_ahp_client.py`의 `BudgetedSessionClient`를
고정 5과제 컨트롤러에 연결했다. 선택지 1·3 모두 같은 계산·중단 코드를 쓴다.
범용 `SessionClient`는 프로토콜 테스트용 primitive이며, 과제 경로는 장부가 없는
그 capture를 받지 않는다. live 과제 port 연결이나 연결 확인 1턴의 별도 예산 배선은
아직 실행 승인/구현을 대신하지 않는다. 유료 workflow의 기존 잠금을 풀지 않았다.

- 외부 JSON 입력 `task_credits`, `five_task_credits`, `usage_timeout_seconds`가 모두
  있어야 한다. 금액은 양의 정수 또는 소수점 6자리 이하 문자열이다. 기본값·환경변수
  fallback·0 대입은 없으며 빠지면 첫 과제 턴 전에 거부한다.
- 각 `chat/usage`의 input/output/cacheRead 토큰과 `turnTokenTotals`를 대조한다.
  누계가 같은 재전송은 재차 차감하지 않고, 누계가 증가한 동일 크기 요청은 다시 센다.
  tier는 **이번 모델 요청의 입력**이 `272000` 이하인지 초과인지로 정한다.
  과제 누계가 272K를 넘었다고 앞선 요청을 long-context로 다시 계산하지 않는다.
- cache-write 수가 없는 핀 AHP 응답은 `null`을 남긴다. 0으로 치지 않고 전체 입력에
  가능한 cache-write 요율을 **추가 예비분**으로 잡는다. 따라서 장부는 청구서의 정확한
  재현이 아니라 보수적 예상이며, cache-write 요율이 입력 요율을 대체하는 경우에는
  의도적으로 과대 추정한다. reasoning 토큰은 출력에 포함된 것으로 다루며 이중 합산하지 않는다.
- 예상액이 과제 또는 공유 5과제 상한 **이상**이면 admission을 닫고 진행 중인 턴을
  interrupt한 뒤 writer/cleanup hold → 수집 → 봉인 → dispose/종료/삭제를 따른다.
  상한을 넘겼다는 이유로 수집을 건너뛰지 않는다. 실제 native interrupt/hold는 미실측이다.
- usage 누락·잘못된 형식·누계 감소/중간 누락·미가격 모델·장부 쓰기 실패/변조는 거부한다.
  비용이 불명확하면 알려진 부분만 보존하고 뒤 과제도 시작하지 않는다. 끝날 때까지 한 건도
  usage가 없거나 명시한 usage 무응답 시간이 지나도 진행 보고가 없으면 중단한다.
- `token-ledger.json`은 작업 파일과 분리해 각 상태 변경마다 원자적으로 저장·fsync한다.
  과제별 snapshot도 capture에 해시 결합하고 사용량 원문에서 다시 계산해 검증한다.
  프로필 혼합·동시 과제·장부 재개/초기화는 거부한다. 독립된 5개 잡의 각자 장부로
  합계 상한을 대신할 수 없으며, 현재 구현은 **단일 컨트롤러의 직렬 5과제** 계약이다.

### 계산 가정, 제안값, 진행 중 초과분

다음은 **실측이 아닌 조건부 산술**이다. public GHCP 요율과 기존 카탈로그의 출력
상한 `128000`을 쓴다(선택지 1 `probe.json`의 Sol `maxOutputTokens`). 요청한 1M을
입력 상한으로 가정하고 캐시 읽기 할인은 쓰지 않는다. 실제 카탈로그의 prompt 상한은
`922000`, context는 `1050000`이므로 `1M + 128K`는 독립 상한을 더한 보수적 계산이며
그 조합을 동시에 보낼 수 있다는 주장이 아니다. 출력 상한은 reasoning을 포함한다.

| 조건부 계산 | credits | USD | 전제 |
| --- | ---: | ---: | --- |
| 모델 응답 1개, cache-write 제외 | `800 + 0.128 × 3000 = 1184` | `$11.84` | 입력 1M, 출력 128K, long tier |
| 장부의 응답 1개 보수 계산 | `1184 + 1000 = 2184` | `$21.84` | cache-write 수 미보고, 입력 전체에 추가 예비분 |
| 64응답/과제, cache-write 제외 | `64 × 1184 = 75776` | `$757.76` | **턴마다 모델 응답이 딱 1개**라고 가정 |
| 5과제, 위 64응답 가정 | `5 × 75776 = 378880` | `$3788.80` | 연결 확인·grader·숨은 작업 제외 |
| 64응답/과제, 보수 장부 기준 | `64 × 2184 = 139776` | `$1397.76` | 위 가정 + cache-write 예비분 |
| 5과제, 보수 장부 기준 | `5 × 139776 = 698880` | `$6988.80` | 같은 조건부 가정 |

**소유자 확정 전 제안:** 과제당 **2200 credits($22)**, 5과제 합계 **11000
credits($110)**, usage 무응답 시간 **120초**. 한 응답의 보수 계산 2184를 올림해
과제 예산으로 제안한 것이며, 64턴을 모두 실행할 예산이나 기본값이 아니다. 테스트의
작은 합성 예산 `10/50`도 운영 기본값이나 소유자 제안값으로 가져오지 않는다.

진행 중 작업이 **모델 응답 딱 1개**, usage가 빠짐없이 즉시 도착하고 추가 호출이
시작되지 않는다는 조건에서만 추가 초과분을 **최대 2184 credits($21.84)**로 계산한다
(cache-write 제외 계산은 1184). 이 조건하에서 제안 임계값 + 응답 1개는 과제
`4384 credits($43.84)`, 직렬 공유 합계 `13184 credits($131.84)`다.
**실제 AHP 1턴은 여러 모델 요청·compaction을 포함할 수 있으므로 그 1턴 전체의
최대 초과분은 여전히 `not available`이다.** 최종 usage 누락을 후속 누계나 timeout으로
발견할 수 없는 경우도 있으며, 이 가드는 완전한 청구 관측·서버 취소 시한을 증명하지 않는다.
위 숫자를 실제 과제/5문제의 보장된 최대 지출로 인용하지 않는다.

소유자가 선택지, 첫 턴/5문제 각각의 승인 범위, 유효한 token, 실제 GHCP 계정의
과금 조건과 수치 예산을 정해야 한다. GitHub 계정/조직의 budget + stop-usage 설정은
소유자가 검토할 별도 통제이며 과제별 예산 예약·차감 계약으로 간주하지 않는다.
이번에는 계정/예산을 조회하거나 변경하지 않았다. 엔지니어는 예산을 실행 전에 강제할 경로와
중단 시 초과 위험을 검증해야 한다. **비용 상한 미확정은 실행 전 막힘**으로 남긴다.
soft guard의 제안값과 위 초과 위험을 소유자가 확정하기 전에는 유료 dispatch하지 않는다.

실행 전 완료 순서: 소유자 선택·예산 → 별도 검토된 프로필별 live 경로 → 출력 수명/
격리/상한·누출 음성 테스트 → 정확한 SHA의 model-free CI 녹색 → 별도 승인된 1턴
연결 → 결과 검토와 5과제 실행 승인. 어떤 단계도 자동 승인·자동 재dispatch하지 않는다.
계획서와 후속 오프라인 구현은 유료 단계의 실행이나 기존 잠금의 해제를 수행하지 않는다.
