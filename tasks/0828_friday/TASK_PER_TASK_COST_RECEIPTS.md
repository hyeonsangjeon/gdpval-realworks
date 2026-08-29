# SPEC: Per-Task Cost Receipts — 문제 풀이 비용과 채점 비용의 분리 원장

## 0. 메타

- **Status**: Session A (ledger + instrumentation) in progress
- **Owner**: hyeonsangjeon
- **Repo**: `hyeonsangjeon/gdpval-realworks`
- **Project card**: Project #5 — `문제별 문제 풀이 비용과 채점 비용 기록`
- **계약 버전**: `cost-receipt-v1`
- **통화**: USD (표시 통화는 `currency` 필드가 결정하며 코드에 상수로 박지 않는다)

이 명세는 **모델·제공 서비스에 중립적**이다. 본문에 특정 배포 이름, 특정 사업자
이름, 특정 단가를 적지 않는다. 그런 값은 전부 커밋된 가격표 파일과 실험 설정에만
존재하며, 코드와 이 문서는 그 파일을 읽는 방법만 정의한다.

### 0.1 병렬 소유권

| 세션 | 범위 |
|------|------|
| A | 가격표, `CostReceiptLedger`, 호출 계측, grade schema 1.4, 재개·병합 보존, Python 테스트 |
| B | `self_report.json` 투영, 보고서, HF 게시, 집계 스크립트, React 대시보드, 프런트 테스트 |

세션 A는 React/TypeScript/보고서 화면을 수정하지 않는다. 세션 B는 원장 계산 로직과
grade schema를 수정하지 않는다. 계약 변경이 필요하면 Project 카드에 먼저 기록한다.

---

## 1. 문제 정의

지금 저장소는 비용에 대해 두 가지만 안다.

1. **실행 전 상한** — `core/execution_envelope_cost.py`가 "최악의 경우 얼마까지
   나올 수 있는가"를 계산한다. 예측이 아니라 천장이고, 승인 게이트용이다.
2. **흩어진 사용량** — `step2_run_inference.py`의 `_bounded_agentic_metrics`,
   `core/grader.py`의 `judge_*_tokens` / `perception_*_tokens`,
   `step8_grade.py`의 `summary.cost`가 토큰 수를 모은다. 그러나
   `summary.cost.estimated_cost_usd`는 **항상 `null`**이고
   `pricing_complete`는 **항상 `false`**다. 즉 사용량은 있는데 값이 붙은 적이 없다.

없는 것은 세 가지다.

- **작업 단위 귀속**: 어떤 호출이 어느 task의 어느 단계에 속하는지 남지 않는다.
- **문제 풀이와 채점의 분리**: 두 비용이 서로 다른 파이프라인에서 발생하는데,
  이를 합산 불가능하게 분리해 보관하는 자리가 없다.
- **감사 가능성**: 재시도·재개·폐기된 호출은 집계에서 사라진다. 실제로 돈이 나간
  호출인데 결과물이 교체되면 기록도 함께 사라진다.

## 2. 설계 원칙

### P1. 0달러는 측정 결과일 때만 쓴다

`0`은 "무료였다"는 **주장**이다. 모르는 것은 `null`이고 상태는 `partial`이다.
사용량이 없거나, 가격이 없거나, 호출이 실제로 나갔는지 불분명하면 금액을
`estimated_cost_usd`에 넣지 않는다. 확인된 부분만 `known_cost_usd`에 남긴다.

진짜 `$0`은 하나뿐이다: **모델을 한 번도 부르지 않은 규칙 기반 경로**. 이때만
`complete` + `estimated_cost_usd: 0`이다.

### P2. 가격은 정확히 일치할 때만 적용한다 (fail closed)

`(provider, resolved_model)` 쌍이 가격표에 **정확히** 있어야 값을 매긴다. 비슷한
이름, 접두사 일치, 상위 모델 대체는 전부 금지한다. 없으면 `price_missing` 사유와
함께 `partial`이다. 실행을 다른 모델로 바꾸지 않는다.

### P3. 원장은 추가 전용이다

호출은 지워지지 않는다. 결과물이 교체되어도, 재개로 다시 돌려도, shard가 병합돼도
이전 호출 기록은 남는다. 비용은 "마지막 시도"가 아니라 "실제로 나간 모든 호출"의
합이다.

### P4. 원장에 비밀이 들어가지 않는다

프롬프트 원문, API 키, 응답 전문, 내부 추론(raw chain-of-thought)은 저장하지
않는다. 요청 식별자가 필요하면 SHA-256 해시만 남긴다. 원장은 공개 산출물로
게시될 수 있다는 전제로 작성한다.

### P5. 공유 사용료는 임의 배분하지 않는다

한 작업에 직접 귀속되는 실행 환경 사용료만 그 작업의 영수증에 넣는다. 여러 작업이
공유한 컨테이너·풀 사용료는 나누어 배분하지 않고, 해당 작업 영수증을 `partial`로
유지하며 사유를 남긴다. 근사 배분은 측정이 아니라 창작이다.

---

## 3. 공유 계약 (`cost-receipt-v1`)

세션 B가 소비하는 형태다. 필드 이름과 의미는 고정이다.

### 3.1 상태

| 상태 | 뜻 |
|------|-----|
| `complete` | 모든 구성 호출의 사용량과 가격이 확인됨. `estimated_cost_usd`가 숫자다. |
| `partial` | 일부만 확인됨. `known_cost_usd`만 있고 `estimated_cost_usd`는 `null`이다. |
| `unavailable` | 이 실행에는 원본 사용량 기록 자체가 없다 (예: 계측 이전 실험). |
| `not_run` | 이 단계가 실행되지 않았다 (예: 미채점). 비용이 0인 것이 아니라 사건이 없다. |

`unavailable`과 `not_run`은 둘 다 금액이 없지만 **다른 이야기**다. 전자는 "썼는데
기록이 없다", 후자는 "쓰지 않았다"이다. 화면에서 같게 보이면 안 된다.

### 3.2 영수증 (receipt)

```json
{
  "schema_version": "cost-receipt-v1",
  "status": "complete | partial | unavailable | not_run",
  "currency": "USD",
  "estimated_cost_usd": 0.0421,
  "known_cost_usd": 0.0421,
  "model_cost_usd": 0.0400,
  "runtime_cost_usd": 0.0021,
  "model_calls": 7,
  "usage": {
    "input_tokens": 120340,
    "cached_input_tokens": 41000,
    "output_tokens": 8800,
    "reasoning_tokens": 5200
  },
  "components": [
    {
      "stage": "generation",
      "retry_kind": "none",
      "status": "complete",
      "model_calls": 1,
      "known_cost_usd": 0.0180,
      "usage": { "...": 0 }
    }
  ],
  "price_table_sha256": "…64 hex…",
  "missing_reasons": []
}
```

규칙:

- `estimated_cost_usd`는 `status == "complete"`일 때만 숫자다. 그 외에는 `null`.
- `known_cost_usd`는 상태와 무관하게 **확인된 금액의 합**이다. 총액이 아니다.
- `model_cost_usd + runtime_cost_usd == known_cost_usd`.
- `usage.reasoning_tokens`는 **참고 표시**다. 사업자가 추론 토큰을 출력 토큰에
  포함해 청구하면 `output_tokens`에 이미 들어 있으므로 다시 곱하지 않는다.
  §5.3 참조.
- `missing_reasons`는 §3.4의 열거값만 담는다.

### 3.3 작업·실험 필드

작업(task) 레코드와 실험 요약 모두 같은 두 필드를 가진다.

- `problem_solving_cost` — 전처리 + 생성 + Self-QA + 모든 재시도 + 직접 귀속
  실행 환경 사용료
- `grading_cost` — 주 채점 + 판독(시각·소리) + 채점 재시도 + 직접 귀속 채점 실행
  환경 사용료

두 값은 **절대 합산되지 않는다**. 서로 다른 파이프라인, 서로 다른 승인, 서로 다른
모델이다. 실험 요약의 값은 작업별 값의 합이며, 하나라도 `complete`가 아니면
요약도 `complete`가 아니다.

감사 원장 참조:

```json
"cost_ledger": { "path": "…/cost_ledger.jsonl", "sha256": "…64 hex…" }
```

### 3.4 `missing_reasons` 열거값

| 값 | 언제 |
|----|------|
| `usage_absent` | 응답에 사용량이 없다 |
| `usage_partial` | 사용량 일부 필드가 없다 |
| `price_missing` | `(provider, model)`이 가격표에 없다 |
| `call_reachability_unknown` | 요청이 사업자에 도달했는지 불명 (타임아웃 등) |
| `runtime_cost_unattributable` | 공유 실행 환경이라 작업 귀속 불가 |
| `runtime_cost_unpriced` | 실행 환경 사용료 단가가 없다 |
| `ledger_absent` | 이 실행에 원장이 없다 |
| `stage_unsupported` | 해당 실행 경로에 모델 호출 계측이 없다 |

---

## 4. 가격표

파일: `batch-runner/experiments/execution_envelope/model_price_table.json`

기존 `models` 블록(실행 전 상한 계산용)은 **그대로 둔다**. 영수증용으로 형제 키를
추가한다.

```json
{
  "cost_receipt_schema_version": "cost-receipt-price-table-v1",
  "providers": {
    "<provider>:<resolved_model>": {
      "input_usd_per_million": "…",
      "cached_input_usd_per_million": "…",
      "output_usd_per_million": "…",
      "reasoning_billed_as": "output | separate | unknown",
      "reasoning_usd_per_million": "…",
      "source": "<가격 고지 URL>",
      "last_reviewed": "YYYY-MM-DD",
      "currency": "USD",
      "unit": "per 1,000,000 tokens"
    }
  },
  "runtime": {
    "<runtime_kind>": {
      "usd_per_hour": "…",
      "attribution": "per_task | shared",
      "source": "…", "last_reviewed": "…", "currency": "USD"
    }
  }
}
```

- 키는 `provider:resolved_model`이다. `resolved_model`은 **응답이 실제로 보고한
  모델**이지 요청에 적은 배포 이름이 아니다. 둘이 다르면 응답 값을 쓴다.
- `price_table_sha256`은 **파일 전체 바이트**의 SHA-256이다. 영수증마다 기록해
  나중에 어느 가격표로 계산했는지 재현할 수 있게 한다.
- `attribution: "shared"`인 실행 환경은 작업에 배분하지 않는다 (P5).
- 항목 추가·수정은 `source`와 `last_reviewed` 없이 허용하지 않는다.

## 5. 계측

### 5.1 단계 (`stage`)

| 값 | 대상 |
|----|------|
| `preprocessing` | 입력 파일 전처리 — 소리·영상 분석 등 |
| `generation` | 결과물 생성 본 호출 |
| `self_qa` | 자체 점검과 그로 인한 재생성 |
| `grading` | 주 채점 |
| `perception` | 채점 중 시각·소리 판독 |

`preprocessing`·`generation`·`self_qa`는 `problem_solving_cost`로,
`grading`·`perception`은 `grading_cost`로 흐른다. 이 매핑은 코드에 한 곳에만
존재해야 한다.

### 5.2 재시도 종류 (`retry_kind`)

| 값 | 뜻 |
|----|-----|
| `none` | 첫 시도 |
| `semantic` | 결과 품질 때문에 다시 함 (Self-QA 지적 등) |
| `infrastructure` | 오류·타임아웃·속도 제한 때문에 다시 함 |
| `resume` | 이전 실행이 끊겨 재개하며 다시 함 |
| `internal_recovery` | 실행 경로 내부의 도구 오류 복구 |

전부 실제로 돈이 나간 호출이므로 전부 합산 대상이다. 구분하는 이유는 비용의
출처를 읽을 수 있게 하기 위해서다.

### 5.3 이중 과금 방지

두 가지를 반드시 지킨다.

1. **캐시된 입력 토큰**: 사업자가 보고하는 `input_tokens`는 보통 캐시 적중분을
   **포함한** 총량이다. 따라서 과금 대상 입력은
   `input_tokens - cached_input_tokens`이고, 캐시분은 별도 단가로 한 번만 곱한다.
   `cached > input`이면 데이터가 모순이므로 `usage_partial`로 처리한다.
2. **추론 토큰**: `reasoning_billed_as`가 `output`이면 이미 `output_tokens`에
   포함되어 있으므로 **다시 곱하지 않는다**. `separate`일 때만 별도 단가를
   적용한다. `unknown`이면 값을 매기지 않고 `usage_partial`이다.

### 5.4 연결 지점

| 경로 | 파일 | 단계 |
|------|------|------|
| 서버 별도 Python 프로세스 | `core/subprocess_runner.py` | `generation` |
| Azure Code Interpreter | `core/code_interpreter.py` | `generation` |
| 기존 Sandbox | `core/hardened_sandbox_runner.py` | `generation` |
| Agentic Sandbox | `core/agentic_sandbox_runner.py` | `generation` |
| Self-QA | `core/output_qa.py`, `step2_run_inference.py` | `self_qa` |
| 소리·영상 전처리 | `core/audio_analyzer.py`, `core/video_analyzer.py` | `preprocessing` |
| 주 채점 | `core/tool_calling_judge.py`, `core/grader.py` | `grading` |
| 판독 | `core/perception/vision.py`, `core/perception/audio.py` | `perception` |
| 채점 재시도 | `core/grader.py` | `grading` (`retry_kind` 구분) |

**미지원 경로**: Agentic Sandbox V2와 Native Codex처럼 실제 모델 실행 경로가
없거나 확인되지 않은 곳은 비용을 만들어내지 않는다. `stage_unsupported`를 달고
`partial`, 실행되지 않았으면 `not_run`이다.

## 6. 원장 (`CostReceiptLedger`)

파일: `batch-runner/core/cost_receipts.py`. 저장소는 SQLite.

### 6.1 왜 SQLite인가

동시에 도는 shard 여러 개가 같은 파일에 쓴다. JSONL 추가 쓰기는 프로세스 경계를
넘으면 줄이 섞일 수 있고, 중복 정산을 막을 유일성 제약을 걸 수 없다. SQLite는
둘 다 해결한다. 교환·게시용으로는 JSONL로 내보낸다.

### 6.2 수명주기: 예약 → 정산

```
reserve(call_id, task_id, stage, retry_kind, provider, model, …)
  → 호출 전에 행을 만든다. 상태 reserved.
settle(call_id, usage=…, resolved_model=…)
  → 응답 후 사용량을 채우고 가격을 적용한다. 상태 settled.
abandon(call_id, reason=…)
  → 호출이 나가지 않았음이 확실할 때. 상태 abandoned, 비용 0.
```

예약을 먼저 하는 이유: **호출은 나갔는데 응답을 못 받은 경우**를 잃지 않기 위해서다.
정산되지 않은 예약 행은 사라지지 않고 `call_reachability_unknown`으로 남아 그 작업
영수증을 `partial`로 만든다. 이것이 "API 도달 여부 불명확"의 처리다.

"호출 전 실패"(요청을 만들다 실패)는 `abandon`이며 비용에 영향이 없다.

### 6.3 중복 정산 방지

`call_id`는 기본 키다. 같은 `call_id`를 두 번 정산하면:

- 사용량이 **같으면** 조용히 무시한다 (재시도된 쓰기).
- 사용량이 **다르면** 오류다. 원장 손상 신호이며 조용히 덮어쓰지 않는다.

`call_id`는 호출 지점에서 결정적으로 만든다:
`sha256(run_id | task_id | stage | retry_kind | attempt_index | sequence)`.
프롬프트 내용은 넣지 않는다 (P4).

### 6.4 내보내기·가져오기·검증

- `export_jsonl(path)` — 한 줄에 한 호출, 결정적 키 순서, 정렬된 순서.
- `import_jsonl(path)` — 재개·병합용. 이미 있는 `call_id`는 §6.3 규칙을 따른다.
- `verify(path)` — 내보낸 파일의 SHA-256과 행별 무결성을 확인한다.

### 6.5 재개와 shard 병합

- **재개**: 이전 라운드의 원장을 가져와 이어 쓴다. 이전 라운드의 실패·폐기 호출
  비용은 그대로 남는다. 결과물만 교체되고 비용은 누적된다.
- **shard 병합**: 각 shard가 자기 원장 JSONL을 사이드카로 남긴다. `step9`가
  이를 합집합으로 가져온다. `call_id`가 결정적이므로 중복은 자동으로 한 번만
  집계된다.

## 7. Grade schema 1.4

`batch-runner/schemas/grade.schema.json`에 `1.4`를 추가한다.

- 1.4는 작업별 `grading_cost` 영수증과 요약 `grading_cost`, `cost_ledger` 참조를
  요구한다.
- **1.0~1.3은 계속 읽힌다.** 기존 조건절은 손대지 않고 1.4 전용 조건절을 더한다.
- 기존 `summary.cost` 블록은 유지한다 (사용량 집계). 1.4에서
  `summary.grading_cost`가 값이 붙은 영수증을 담당한다.
- exp003처럼 비용 필드가 없는 기존 결과와 구형 보고서는 계속 열려야 한다.

## 8. 검증

### 8.1 산술

`problem_solving_cost.known_cost_usd` ==
최초 생성 + Self-QA + 의미 재시도 + 실행 오류 재시도 + 재개 + 직접 귀속 실행
사용료의 합. 소수점 오차 없이 `Decimal`로 계산한다.

`grading_cost`는 주 채점 + 판독 + 채점 재시도의 합이며, 두 값이 섞이는 경로가
코드에 존재하지 않아야 한다.

### 8.2 테스트 목록

각각 독립 테스트로 존재한다.

1. 실패한 작업 — 비용은 남고 결과는 실패
2. 응답 사용량 누락 — `usage_absent`, `partial`
3. 미등록 가격 — `price_missing`, `partial`, 대체 금지
4. API 도달 불명확 — 미정산 예약이 `partial`을 만든다
5. 호출 전 실패 — `abandon`, 비용 영향 없음
6. 규칙 기반 무호출 채점 — `complete`, `$0`
7. 미채점 — `not_run`
8. 같은 호출 두 번 정산 — 한 번만 집계
9. 캐시 토큰 이중 과금 없음
10. 추론 토큰 이중 과금 없음
11. 재개 후 이전 비용 보존
12. shard 병합 후 이전 비용 보존
13. 결과물 교체 후 이전 비용 보존
14. 문제 풀이·채점 비용 미혼합
15. exp003 및 구형 보고서 읽기 호환
16. 공유 실행 환경 — 배분 금지, `partial` 유지

### 8.3 유료 실행 금지

이 명세의 모든 테스트는 **모의 응답**으로 돈다. 실제 사업자 호출, 로그인, 실제
채점·재채점, Smoke/Pilot/Full 실행은 세션 A·B 어느 쪽도 하지 않는다. 통합 담당
세션이 두 PR 병합 후 한 번만 실제 Smoke를 돌린다.

## 9. 중단 규칙

다음이 발견되면 유료 실행 전에 멈춘다.

- 원장 손상 (같은 `call_id`에 다른 사용량)
- 중복 정산이 집계에 반영됨
- 문제 풀이 비용과 채점 비용의 혼합
- 원장에 프롬프트 원문·키·응답 전문 저장
- 가격표 정확 일치 실패를 대체로 넘김

## 10. 통합 순서

1. 세션 A PR — 계약·가격표·원장·계측·schema 1.4·테스트
2. 세션 B PR — 투영·보고서·게시·집계·대시보드
3. A 먼저 병합
4. B를 최신 main에 rebase, 전체 CI
5. 모델 없는 end-to-end fixture로 작업별·실험별 합계 검증
6. 통합 담당 세션에서만 실제 Smoke 1회
7. Smoke가 완전하면 Pilot, 이후 Full
