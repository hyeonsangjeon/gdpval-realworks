# GHCP 고정 5과제 토큰 장부 재검토

검토 기준은 `87ae8a6232964d3d95dc369763a55acd1b6c6b31`이다. 이번 검증은
핀 소스 정적 조사와 오프라인 fake 런타임에 한정한다. 실제 호스트 실행·인증·모델
응답·청구 자료는 새로 얻지 않았다. `execution_allowed=false`와 기존 핀·봉인을 유지한다.

## 한 AHP 턴의 요청 수

VS Code `1.144.0 / 2c33b50b16c472efe58357d1d2a8a5414bc23fbf`, Chat `0.72.0`,
Codex SDK `0.163.0`을 대상으로 한다. SDK의 공개 태그 `rust-v0.163.0`가 가리키는
커밋은 `83086188ae0614bd882818ff1aa23f3194962012`다. 아래 Rust 파일은 그 커밋만
읽었다. 최신 버전이나 다른 에이전트의 기본값을 가져오지 않았다.

원문 기준 경로: [VS Code Agent Host](https://github.com/microsoft/vscode/tree/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost),
[Codex SDK Rust](https://github.com/openai/codex/tree/83086188ae0614bd882818ff1aa23f3194962012/codex-rs).
VS Code 파일은 이 경로의 `node/` 아래이며 Rust 파일은 `codex-rs/` 아래다.

| 핀 소스 위치 | 확인한 동작 | 수량 상계에 대한 의미 |
| --- | --- | --- |
| VS Code `node/codex/codexLaunchConfig.ts:162`, `codexAgent.ts:6628` | native `codex app-server`를 사용하고 AHP send를 `turn/start`로 전달 | Copilot CLI prompt loop와 별개. AHP 1턴=모델 요청 1회가 아님 |
| SDK `core/src/session/turn.rs:454,569,675,795` | sampling/tool 후속 루프, mid-turn 및 post-turn compaction | 전체 루프를 제한하는 요청 횟수 카운터를 확인하지 못함 |
| SDK `model-provider-info/src/lib.rs:67,68,455,499,506` | request 설정 기본 4, stream 재시도 기본 5, 각각 설정 상한 100 | 한 sampling의 재시도 설정이지 AHP 전체 요청 수가 아님. request 값은 `ApiRetryConfig.max_attempts`로 전달 |
| SDK `core/src/responses_retry.rs:93,141` | 조건부 `UnboundedConnectionRetries` 분기와 일반 재시도 분기 | 해당 feature가 실제 켜졌다고 주장하지 않음. 전체 요청 상계를 만드는 근거로 쓸 수 없음 |
| SDK `core/src/compact.rs:283,288,348` | compaction 자체 요청 루프. context 초과 시 history 항목을 줄이고 retry counter 재설정 | compaction도 요청 수/요율/usage 완전성 계산에 포함해야 함 |

Copilot CLI `1.0.103` 배포 tarball은 npm의 SHA512 integrity와 대조해 정적으로만
풀었다. 실행 파일 SHA256은 기존 근거와 같은
`f19b3554a6b62605db3a26d5255ebe2a3ee39fcd6a357edb18301ea5037f6f0d`다.
설치 wrapper의 package.json은 `1.0.98`이지만 실제 파일은 `1.0.103` 배포 바이트와
일치한다. wrapper 번호로 다른 번들을 조사하지 않았다. 이 실행 파일의 내장 bytecode에서
Codex AHP 전체 요청 수 제한을 추출했다는 주장은 하지 않는다. 실제 Codex 경로를
결정하는 것은 위 Agent Host 소스이며 CLI의 session soft limit을 그 경로에 대입하지 않는다.

**결론:** 64 AHP 턴·32 도구·1,200초는 컨트롤러 제한이다. 내부 CAPI 요청 수의
검증된 최대값은 `not available`이다. 횟수 제한 없이 이어질 수 있는 루프가 있다는
정적 근거를 실제 무한 호출 관측이나 실제 사용량으로 바꾸어 부르지 않는다.

## interrupt부터 네트워크 취소까지

1. VS Code `agentService.ts:12717`은 active turn을 대조한다.
   `agentSideEffects.ts:1911,1932`는 로컬 turn 상태를 끝내고 `agent.chats.abort`를
   비동기로 호출한다. 따라서 AHP cancelled 알림 자체가 native 취소 완료 영수증은 아니다.
2. `codexAgent.ts:6837,6851,6860`은 native turn ID·ready connection이 있을 때만
   `turn/interrupt`를 보낸다. 실패는 `:6865`에서 로그로 남긴다.
   `codexAppServerClient.ts:371`의 이 request에는 응답 deadline이 없다.
3. SDK `app-server/src/request_processors/turn_processor.rs:1629,1655`는
   `Op::Interrupt`를 제출하고 active-turn 요청의 응답을 `TurnAborted`까지 보류한다.
   `core/src/tasks/mod.rs:945,963,971`은 cancellation token을 취소하고 내부 task에
   100ms 정리 기회를 준 뒤 task handle을 abort한다. 이 전후의 queue·lock·cleanup·네트워크
   경로까지 100ms로 제한한다는 코드는 아니다.
4. SDK `core/src/session/turn.rs:2680,2730,2757`은 stream 생성/next를 취소할 수 있다.
   `:2741`의 response drain은 별도 preempt 처리이며, 사용자 cancellation의
   `Err(_) => TurnAborted` 분기와 구분해야 한다.
   `core/src/client_common.rs:134`의 drop이 cancellation token을 취소하고
   `core/src/client.rs:2528,2543`이 상위 stream을 해제한다.
   `codex-api/src/sse/responses.rs:554`는 수신 채널이 닫히면 SSE reader를 종료한다.
5. VS Code `codexProxyService.ts:336,351`은 native HTTP 연결 close에
   `AbortController.abort()`를 연결한다. `copilotApiService.ts:683,697`이 그 signal을
   CAPI fetch로 넘긴다. 응답 전체 수신을 의무적으로 기다리는 설계가 아니다.

이는 취소가 전달될 수 있는 코드 경로의 확인이지 서버 중단 지연 실측이 아니다.
usage는 SDK `core/src/session/turn.rs:3291`에서 pending tools를 정리한 뒤 전달될
수 있고, VS Code `codexAgent.ts:3926`은 active turn 없는 usage를 버린다. 취소 때
최종 청구량이 모두 도착한다고 보장할 수 없다. 실제 native interrupt와 writer/cleanup
hold의 연동, 최종 usage 회수는 live 경로를 열기 전 남은 항목이다.

## 초과분 계산의 경계

GHCP long-context 요율로 입력 1M·출력 128K를 독립 상한으로 가정하면
`800 + 0.128 × 3000 = 1184 credits ($11.84)`다. cache-write 미보고 예비분
`1000`을 더한 장부 추정은 **2184 credits ($21.84)**다. 두 토큰 상한의 동시
실현 가능성을 주장하지 않으며, reasoning은 출력에 포함해 한 번만 센다.

이 숫자는 **모델 응답 딱 1개**, 완전하고 즉각적인 usage, 추가 요청 없음이라는
조건에서만 초과분 계산에 쓸 수 있다. AHP 턴 전체의 실제 최대 초과분은
**credits / USD 모두 `not available`**을 유지한다. 이를 정하려면 모든 도구·재시도·
compaction·병렬 작업을 포함한 요청 수와 동시 수의 강제 상한, 각 요청의 강제 토큰
상한, 최종 usage 완전성 및 서버 취소/과금 종료 계약이 필요하다.

## 고정 HEAD 리뷰와 수정

| 검토 항목 | 기준 HEAD에서 확인한 내용 | 이번 조치 |
| --- | --- | --- |
| 정확히 상한인 경우 | 비교는 `>=`로 정상. 과제 상한은 해당 과제만 닫았음 | 이번 리더 지시의 남은 과제 거부에 맞춰 공유 중단 상태에 영구 기록 |
| 272K 경계 | 이번 요청의 전체 input이 `272000`을 초과할 때만 long tier | 기존 경계 테스트 유지; 전부 cache-read인 입력에서도 경계 확인 추가 |
| cache read/write | 두 값 구분. write 미보고는 null+전 입력 예비분 | 계산 변경 없음. 청구액과 보수 장부를 구분 |
| usage 중복 | 같은 누계·같은 last는 중복 제외, 누계가 증가한 동일 크기 요청은 과금 | 기존 테스트 유지; 동시 동일 sequence 충돌 시 한 번만 계수하고 전체 거부 확인 |
| 과제 합계 경합 | `RLock`과 active-task 슬롯으로 단일 장부에서 직렬 admission | 실제 5개 테스트 스레드의 경쟁에서 1개 입장·4개 거부 확인. 분산 장부 보장은 아님 |
| interrupt/cleanup 실패 | control error 기록만 남겨 합계를 계속 알려진 값으로 취급; 다음 과제 입장 가능 | 실패를 합계 미확정으로 기록, 다음 과제 거부. 정상 완료 후 dispose 실패도 성공 취소 |

실패 주입 4종(interrupt 송신, dispose 송신, terminate false, terminate 예외)을
두 프로필에 적용한 8개 테스트는 수정 전 모두 실패했다. 수정은 cleanup/수집을
생략하지 않는다. known subtotal을 보존하고 unknown remainder를 0으로 치지 않는다.
capture 단계의 기존 `capture_host_not_stopped` 거부도 그대로 유지한다.

## 제안 예산으로 하는 오프라인 리허설

조건: 선택지 1·3 각 5과제, 고정 synthetic 응답·파일, 과제 2200 / 합계 11000
credits / usage timeout 120초를 **명시 입력**. 모델·CAPI·인증·grader 호출 0.
`ghcp_ahp_offline_fixture.budget_scenario`가 입력을 만들며, 실제 장부·첫 턴 가드·
수집/봉인·기존 grader 입력 검증기를 통과한다. 이는 컨트롤러 계약 검사이며 실제
모델 품질·usage 완전성·취소 지연의 시험이 아니다.

| 시나리오 | 독립 기대값 | 순서/남은 과제 확인 |
| --- | --- | --- |
| 정상 | 5개 완료, 0.074 credits | interrupt 없음; 각 출력 수집→봉인→삭제 |
| 과제 초과 | 과제 1=2201, gate 중단 | interrupt→수집→봉인; 2–5 턴 입장 0 |
| 합계 초과 | 앞 4개×2199 + 마지막 2205=11001 | 과제 5 interrupt→수집→봉인, 이후 작업 0 |
| usage 누락 | 120초에서 unknown, 수치 null | 과제 1 출력 보존, 2–5 턴 입장 0 |
| usage 형식 오류 | unknown, 수치 null | 과제 1 출력 보존, 2–5 턴 입장 0 |

합계 사례에는 남은 과제가 없다. 다른 예산(0.0296)의 기존 합계 경계 테스트가
과제 2에서 거부한 뒤 과제 3–5를 막는지 별도로 확인한다. 조건을 섞어 11000
리허설이 그 순서를 관측했다고 쓰지 않는다. 두 프로필×5사례의 회귀 테스트는
`test_leader_proposal_five_task_rehearsals_preserve_stop_collection_and_seal`이다.
회귀 테스트와 별도 보관용 실행 모두 10/10 기대 결과 통과, 실패 0이다. 관련 묶음은
422 통과 /0 실패 /0 건너뜀이며, 이번에 추가한 회귀 사례는 26개다.

원문·해시·실행 결과 보관 위치:
`/ai-work/copilot/_tmp/ghcp-ledger-audit-20261111.SRUOrY/`.
실행 계획과 소유자 미확정 예산은 [첫 턴 계획서](ghcp-fixed-five-first-turn-plans.md)에 있다.
