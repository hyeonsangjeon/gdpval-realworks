# GHCP Sol 첫 턴: 과금 단위와 사용량 상한 조사

조사일: 2026-11-11. 저장소 기준 `e9de3a5188a5`; VS Code **1.144.0**
(`2c33b50b16c472efe58357d1d2a8a5414bc23fbf`), Chat **0.72.0**,
Copilot CLI **1.0.103**, Codex SDK **0.163.0**를 고정했다.
대상은 `gpt-5.6-sol` / `max` / 요청 context `1000000`인 두 정책 선택지다.

조사만 수행했다. 공개 문서는 인증 없이 읽었고, 과거 마스킹된 zero-turn 산출물의
카탈로그만 재검토했다. 새 인증·모델 턴·dispatch·비밀값 접근은 없다.
사용량/청구액 실측 표본은 없으며 fixture나 카탈로그 가격을 실측 사용량으로 쓰지 않는다.

## 결론

현재 GitHub 문서의 주 과금 단위는 **토큰 가격을 환산한 AI credits**다.
premium request 배수는 일부 기존 연간 플랜의 legacy 방식이며, 공개 표에
**GPT-5.6 Sol 배수가 없다**. 계정의 적용 플랜·할인·실제 청구 여부는 조회하지 않았다.

Sol의 공개 토큰 요율은 기존 두 zero-turn 카탈로그와 일치한다. 그러나 핀 Codex
AHP가 보내는 usage는 사후 토큰 보고이지 세션별 GHCP 청구 예약/차감 계약이 아니다.
Copilot CLI의 AI credit session limit도 공식적으로 **soft limit**이다.
따라서 과제당 하드 사용량 가드는 구현하지 않았고 코드·가드·잠금은 그대로다.
연결 첫 턴·5과제·grader 각각의 비용 상한은 `not available`로 유지한다.

## 과금 단위와 요율

| 구분 | 공개 문서가 정한 단위 | 이 게이트에서의 해석 |
| --- | --- | --- |
| 현재 토큰 과금 | 입력·출력·cache 토큰의 모델별 가격 → AI credits; `1 AI credit = $0.01 USD` [G1] | 한 사용자 턴에 여러 모델 요청이 있으면 그 토큰들이 사용량을 늘린다 [G3] |
| legacy premium requests | 사용자 프롬프트 1건 × 모델 배수; IDE agent/CLI/Codex preview에 해당 규칙 명시 [G2] | 같은 프롬프트를 처리하는 자율 도구 호출마다 premium 1건을 더하는 규칙은 아님 |
| Max reasoning | 높은 reasoning 설정은 더 많은 토큰·credits를 소비할 수 있음 [G4] | 고정 Max 배수·토큰 수·과제 비용은 제시되지 않음. Copilot **Max 플랜**과 reasoning **max**는 별개 |
| 1M context 요청 | Sol 가격표의 long-context 경계는 입력 `272K` tokens [G1] | context 요청값은 실입력 토큰·매 요청의 가격 tier·출력 상한·누적 비용이 아님 |

[G2]는 2026-06-01 이후 legacy premium request 방식에 남은 기존 연간 Pro/Pro+
가입자에 한정된다. [G5]는 legacy 가입자에게 새 모델/기능이 제공되지 않는다고
명시하며 조사일 표에 Sol을 싣지 않는다. GPT-5.3-Codex의 배수나 OpenAI API/
ChatGPT Codex 가격을 Sol의 GHCP 배수로 대신하지 않는다.

다음은 [G1]의 Sol 요율이다. 단위는 **1M tokens당 AI credits**이며 괄호는
그 문서의 USD 요율이다. 할인·프로모션·포함량을 반영한 계정 청구액이 아니다.

| Sol tier / 입력 기준 | 입력 / cache read | cache write / 출력 |
| --- | --- | --- |
| Default, `≤272K` | `400 / 40` (`$4.00 / $0.40`) | `500 / 2000` (`$5.00 / $20.00`) |
| Long context, `>272K` | `800 / 80` (`$8.00 / $0.80`) | `1000 / 3000` (`$10.00 / $30.00`) |

기존 관측: 선택지 1 run **42964958467**의 `probe.json:1711-1722`와
선택지 3 run **42988846330**의 `probe.json:1700-1711`에는 Sol의
`inputCost/cacheCost/cacheWriteCost/outputCost`와 `longContext*Cost`가 위 값으로 있다.
Sol 레코드에 `multiplierNumeric`은 없다. 이는 **서버 카탈로그가 보고한 가격**이며,
두 run 모두 모델 턴 0이라 소비량/청구액/served model 실측을 제공하지 않는다.

핀 소스의 `codexAgent.ts:2349,2362-2384`는 CAPI 모델의 `billing`을
`normalizeCAPIBilling` → `createPricingMetaFromBilling`으로 모델 `_meta`에 넣는다.
`agentModelPricing.ts:14-35,119-170`은 단위를 credits/1M tokens로 규정하고
배수와 기본/long-context 가격을 구분한다. 가격 필드가 없는 것을 0으로 채우지 않는다.

## 실행 중·종료 후 읽을 수 있는 사용량

아래 소스 경로는 VS Code 핀의 `src/vs/platform/agentHost/` 기준이다.
**Copilot SDK와 OpenAI Codex SDK는 서로 다른 런타임**이다. 공통 메타데이터 타입에
필드가 정의됐다는 이유만으로 Codex가 그 필드를 보고한다고 간주하지 않는다.

| 경로 | 필드와 시점 | 한계 / 소스 |
| --- | --- | --- |
| Codex SDK → AHP, 실제 대상 | `thread/tokenUsage/updated.tokenUsage.{last,total}`: input/output/cached/cache-write/reasoning/total 토큰. AHP `chat/usage`에는 input/output/cacheRead, `_meta.reasoningOutputTokens/modelContextWindow/turnTokenTotals` | SDK 0.163.0 `TokenUsageBreakdown.ts:9`, `ThreadTokenUsage.ts:11`; `codexMapAppServerEvents.ts:514-558`. 이 매핑에는 premium 수·AI credits·청구액이 없음. AHP 매핑은 native `cacheWriteInputTokens`도 그대로 내보내지 않음 |
| Codex 알림 수명 | thread/turn에 대응한 알림을 현재 chat에 전달 | `codexAgent.ts:3899-3934`; 활성 turn이 없으면 반환. 종료 후 전체 청구량 복원이나 모든 서버 내부 작업의 보고를 보장하지 않음 |
| Copilot SDK/provider, 비교용 | live `assistant.usage.cost`, `copilotUsage`; `session.usage.getMetrics.{totalNanoAiu,totalPremiumRequestCost,modelMetrics}` | [G6]. usage 이벤트는 ephemeral이며 resume 때 재생되지 않음. metrics는 누계 조회이며 호출 전 비용 예약이 아님; Codex AHP에는 같은 RPC 계약이 없음 |
| VS Code의 Copilot provider | `copilotUsage.sessionTotalNanoAiu/sessionAiCreditsStatus`, `quotaSnapshots`; chat `_meta['vscode.chatUsage']` | `common/meta/vscode/agentUsageMeta.ts:15-45,110-148`; `node/copilot/copilotAgentSession.ts:3440-3481`이 Copilot SDK metrics를 조회/게시. 상태 `partial/unavailable`이나 누락을 완전한 0으로 읽지 않음 |
| CLI 1.0.103 | `--usage-output-file <file>`: 종료 시 JSON; `--max-ai-credits <credits>`: session limit | 보관된 핀 help `:220-231`. 종료 파일은 실시간 admission이 아니고 강제 종료 시 완전성도 보장되지 않음. CLI 도움말을 새로 실행하지 않음 |
| 계정별 사후 사용량 | billing UI/다운로드 보고서; SDK `account.getQuota`의 premium/account quota | [G6]·[G7]. 세션 단위 누계와 계정/월 단위 잔액은 다름. 이번에는 이 인증 경로를 호출하지 않음 |

[G6]의 `cost`는 premium multiplier로 설명되지만 공통 AHP 메타데이터의 `cost`
주석은 credit cost로 설명된다. 필드 이름만 보고 USD/premium/AI credits를 서로
환산하지 않는다. `totalNanoAiu`도 단위·완전성을 함께 보존하며 예제의 0 대입을
이 게이트의 미보고 값 처리로 가져오지 않는다.
공개 SDK의 모든 필드가 CLI 1.0.103의 JSON에 그대로 나오는지는 실측하지 않았다.

핀 CLI 실행 파일 SHA256은
`f19b3554a6b62605db3a26d5255ebe2a3ee39fcd6a357edb18301ea5037f6f0d`다.
정적 해시만 재확인했다. 기존 help/버전 근거는
`/ai-work/copilot/_tmp/ghcp-sol-cli-contract.9Qj6sx/copilot-pinned-help.txt:220-231`와
`copilot-pinned-version.txt:1`에 있다. package wrapper 버전이나 다른 CLI 버전의
이벤트 스키마로 1.0.103의 종료 파일 스키마를 추정하지 않는다.

## 하드 상한 판단과 5과제 계산

[G8]의 `--max-ai-credits`는 최소 **30 AI credits**의 public-preview **soft limit**다.
진행 중인 응답이 완료된 뒤 멈추므로 설정치를 초과할 수 있다. [G4] 역시 session
limit을 계정/조직의 spending limit 대체물로 보지 않는다.
더구나 이 게이트의 `codexAgent.ts:2638-2700`과 `codexLaunchConfig.ts:162`는
Copilot CLI 프롬프트 루프가 아니라 네이티브 **`codex app-server`**를 띄운다.
진입점 역시 VS Code CLI의 `code agent host`다(`ghcp_ahp_probe.py:686`).
검토한 핀의 Codex session/thread/turn 계약에는 해당 CLI credit limit 전달 경로가 없다.
Codex의 `account/rateLimits/read`도 ChatGPT 계정 상태용이며
GHCP 과제 비용 조회로 대체할 수 없다(`codexAgent.ts:1593-1595,3675-3687`).

사용량 알림을 받은 뒤 취소하는 offline fake는 후속 client 송신 차단을 검사할 수
있지만, 이미 진행 중인 응답의 지출·뒤늦은 usage·compaction을 초과 전에 차단했다는
증거는 만들지 못한다. `codexProxyService.ts:342-364`는 요청을 전달하고 응답을
읽으며, 여기에도 과제별 예산을 원자적으로 예약하는 계약은 없다.
이번 지시의 불가 분기에 따라 **새 usage 가드나 fake 검증 코드는 추가하지 않았다**.

| 계산 범위 | 계산 | 무엇을 상한으로 말할 수 있는가 |
| --- | --- | --- |
| 과제당/5과제 client turn | `64`; `5 × 64 = 320` | 새 client 턴의 admission 상한. 한 턴 안의 provider 호출 수가 아님 |
| 5과제 도구/시간 | `5 × 32 = 160`; `5 × 1200 = 6000`초 | 관측 도구 수/클라이언트 시간 예산 합계. 서버 내부 작업·취소 지연·과금 초과량의 상한이 아님 |
| **조건부** legacy premium | 과제당 `64M`; 5과제 `320M` | legacy 규칙 적용, 모든 과금 프롬프트가 이 admission을 거침, Sol 배수 `M` 확인이 전제. 그때는 자율 도구 160회에 `160M`을 추가하지 않음 |
| 정확한 Sol의 최악 premium 수 | **`not available`** | 공개 legacy 표와 기존 카탈로그에 Sol `M` 없음. 다른 모델 배수를 대입하거나 0으로 쓰지 않음 |
| 현재 AI credits/USD 최악 비용 | **`not available`** | 모든 유료 모델 호출·토큰·취소 초과분의 유한 상한이 증명되지 않음 |

조건부 계산은 **연결 확인 1턴·grader를 제외**한다. 그 둘의 비용도 별도 미확정이다.
현재 토큰 과금에서 정확한 산식은 모든 과제의 과금 모델 호출 `j`에 대해
`총 credits = Σ_j Σ_k (해당 tier의 가격[k] × 과금 토큰[j,k] / 1,000,000)`이다.
`k`는 해당 청구 체계가 보고한 입력·cache-read·cache-write·출력 항목이다.
중복 여부가 불명인 SDK token 필드들을 임의로 더하거나 이중 계산하지 않는다.
이번에 가격은 확인했지만 호출 수와 완전한 과금 토큰 합계의 상한은 확인하지 못했다.

`ghcp_ahp_client.py:6-10,37-44`의 `server_internal_model_requests`와
`server_internal_tool_calls`는 여전히 `no_finite_bound_proven`이다.
`:594-595`의 `model_requests/premium_requests=not_reported`도 그대로다.
이는 무한 사용량을 관측했다는 말이 아니라 현재 증거로 유한 최악값을 보장하지 못한다는
뜻이다. 요청 context `1M`을 `320 × 1M` 누적 토큰 상한으로 쓰지 않는다.

## 실행 전에 필요한 것

두 선택지 모두 소유자가 정책 선택·과금 플랜·승인할 수치 예산을 정해야 한다.
[G9]의 계정/조직 budget 및 stop-usage 설정은 소유자가 검토할 별도 통제다.
추가 사용료의 월/계정 예산을 새 과제별 예약 한도로 바꾸어 부르지 않는다.
이번에는 설정을 조회하거나 변경하지 않았고 hard stop의 실동작도 검증하지 않았다.

엔지니어링 후속 조건은 실제 GHCP 비용 필드의 완전한 수집, 호출 전 상한/예약 또는
명시적으로 승인된 초과 위험, live 과제 port와 기존 첫 턴/수집 가드의 연결이다.
소유자의 정책 선택만으로 이 비용 막힘이 해결되지는 않는다.
`execution_allowed=false` 및 기존 유료 실행 잠금을 유지한다.

## 공개 출처와 재검토 근거

- [G1 — Models and pricing for GitHub Copilot][G1]: Sol 두 tier, cache-write, AI credit 환산.
- [G2 — Requests in GitHub Copilot (legacy)][G2]: 프롬프트/도구/제품별 premium 규칙과 적용 플랜.
- [G3 — Usage-based billing for individuals][G3]: 한 agentic task의 여러 모델 호출, 실제 토큰 기반 사용량.
- [G4 — Optimizing AI usage][G4]: reasoning 설정의 토큰 영향, soft session limits.
- [G5 — Legacy model multipliers][G5]: Sol 미등재, legacy에 새 모델/기능 미제공.
- [G6 — Copilot SDK usage and billing metrics][G6]: 이벤트/누계/가격/계정 조회 계약과 완전성 주의.
- [G7 — Monitoring premium usage (legacy)][G7]: 사후 계정 UI/보고서.
- [G8 — CLI session limit][G8]: 최소 30 AI credits, 진행 응답 완료 뒤 중단하는 soft limit.
- [G9 — GitHub budgets][G9]: 계정/조직/제품/SKU 범위와 stop-usage 설정; 이번에는 미조회·미변경.

핀 원문은 [VS Code `2c33b50b` Agent Host 소스][S1]이며 위 파일:줄은 이 커밋 기준이다.
`node/codex/codexMapAppServerEvents.ts`와 `common/meta/vscode/agentModelPricing.ts`는
공개 raw 파일을 다시 받아 보관 소스와 SHA256 일치를 확인했다.
문서 사본·소스 해시·기존 artifact 해시와 조사 HANDOFF는
`/ai-work/copilot/_tmp/ghcp-premium-cap-20261111.F6SoEZ/`에 보관한다.
이 문서는 GitHub 가격을 사용했으며 OpenAI API/ChatGPT Codex 요율을 혼합하지 않았다.

[G1]: https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing
[G2]: https://docs.github.com/en/copilot/reference/copilot-billing/request-based-billing-legacy/copilot-requests
[G3]: https://docs.github.com/en/copilot/concepts/billing-and-usage/individuals/billing
[G4]: https://docs.github.com/en/copilot/tutorials/optimize-ai-usage
[G5]: https://docs.github.com/en/copilot/reference/copilot-billing/request-based-billing-legacy/model-multipliers-for-annual-plans
[G6]: https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing
[G7]: https://docs.github.com/en/copilot/reference/copilot-billing/request-based-billing-legacy/monitor-premium-requests
[G8]: https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/set-session-limit
[G9]: https://docs.github.com/en/billing/how-tos/set-up-budgets
[S1]: https://github.com/microsoft/vscode/tree/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/src/vs/platform/agentHost
