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
      "audio_billed_as": "separate | unpriced",
      "audio_input_usd_per_million": "…",
      "audio_output_usd_per_million": "…",
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

### 4.1 소리 토큰 요율 (`audio_billed_as`)

세 필드 모두 **선택**이다. 없으면 그 항목은 `unpriced`, 즉 **소리를 값 매기지
않는다**는 뜻이다. 기존 항목을 한 글자도 고치지 않고도 fail closed가 되도록 기본값을
그렇게 두었다.

| 값 | 뜻 | 요율 필드 |
|----|-----|-----------|
| `separate` | 소리 입력·출력이 글 요율과 **다른 자기 요율**로 청구된다 | 두 개 다 필수 |
| `unpriced` (기본) | 이 항목으로는 소리를 값 매길 수 없다 | 없어야 한다 |

**"소리도 글 요율로 청구된다"는 세 번째 값은 두지 않는다.** 그렇게 고지한 사업자를
찾지 못했다. 값이 없다는 이유로 옆 칸 숫자를 빌려 쓰는 통로가 바로 그 세 번째
값이므로, 만들지 않는 것이 이 표의 안전장치다.

로더가 거절하는 경우:

- `audio_billed_as`가 위 두 값이 아니다 → `ValueError`
- `separate`인데 두 요율 중 하나가 없다 → `ValueError` (없는 필드 이름을 말한다)
- 요율은 있는데 `audio_billed_as`가 `separate`가 아니다 → `ValueError`
  (적용될 일 없는 숫자가 표에 앉아 있으면 다음 사람이 적용된다고 읽는다)

값을 매기지 못하는 모델은 `providers`에 넣지 않고
`models_deliberately_not_priced`에 **사유·조회한 질의·조회 날짜·무엇이 있으면
해결되는가**를 적는다. 빈 항목이나 `0` 요율로 채우지 않는다 (P1, P2).

### 4.2 이번에 고정한 가격표

| 항목 | 값 |
|------|-----|
| 스키마 | `cost-receipt-price-table-v1` (변경 없음) |
| 지문 (파일 전체 바이트 SHA-256) | `a2d60e1c96390313f41b4a249a7dea3606b62522858902f49f152da30941d2d4` |
| 직전 지문 | `fd09d28c7247e9d40f1f9218d01aa961d6545d377cdaccf51d0857ea6e43c741` |
| 검토일 | 2026-09-07 |
| 출처 | 공개 Azure Retail Prices API (비로그인). 질의 원문은 파일 안 `models_deliberately_not_priced` / `azure_published_meters`에 있다 |
| 요율 변경 | **없음.** `providers`의 네 항목은 바이트 단위로 동일하다 |
| 적용 근거 | 새로 더한 것은 §4.1의 소리 필드 정의와 조회 기록뿐이다. 지문이 움직인 이유는 요율이 아니라 문서다 |

**기존에 고정된 영수증을 덮어쓰지 않는다** — 확인한 내용은 다음과 같다.

- 커밋된 원장이 이미 고정한 지문은 **세 종류**다 — `f878bb9e…` 46,031행,
  `d4203181…` 21,517행, `ff85f9f5…` 1,039행, 그리고 아직 정산되지 않아 지문이
  붙지 않은 예약 23행 (합 68,610). **셋 다 직전 파일과도 이미 다르다.** 지문은
  "이 행을 값 매긴 표"의 기록이지 "지금 파일이 이 내용"이라는 주장이 아니다.
- `build_receipt`는 각 행이 스스로 적은 표를 먼저 읽고, 인자로 받은 지문은 행이
  아무 말도 하지 않을 때만 쓴다 (`core/cost_receipts.py`). 그래서 어제 표로 값
  매긴 행을 오늘 표로 연 재개 라운드가 과거 기록을 고쳐 쓰지 않는다.
- 직전 지문 `fd09d28c…`를 고정한 커밋된 산출물은 **하나도 없다.**
- 살아 있는 파일의 해시를 대조해 실패시키는 코드는
  `core/agentic_pricing.load_pinned_model_pricing` 하나뿐인데, 그것은 스키마가
  `agentic-pricing-v1`이고 최상위 키가 `{schema_version, models}`뿐인 **다른**
  파일을 본다. 이 파일은 그 검사에 애초에 통과하지 못하는 모양이므로 그 경로가
  가리키는 파일이 아니다.

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

세 가지를 반드시 지킨다. 셋 다 같은 모양의 문제다 — 사업자가 보고하는 큰 수 안에
작은 수가 **이미 들어 있는데**, 그 작은 수를 밖에서 한 번 더 곱하는 것.

1. **캐시된 입력 토큰**: 사업자가 보고하는 `input_tokens`는 보통 캐시 적중분을
   **포함한** 총량이다. 따라서 과금 대상 입력은
   `input_tokens - cached_input_tokens`이고, 캐시분은 별도 단가로 한 번만 곱한다.
   `cached > input`이면 데이터가 모순이므로 `usage_partial`로 처리한다.
2. **추론 토큰**: `reasoning_billed_as`가 `output`이면 이미 `output_tokens`에
   포함되어 있으므로 **다시 곱하지 않는다**. `separate`일 때만 별도 단가를
   적용한다. `unknown`이면 값을 매기지 않고 `usage_partial`이다.
3. **소리 토큰**: `audio_tokens`도 `input_tokens` / `output_tokens` 안에 들어 있다
   (§5.5의 측정 근거). 항목이 `separate`면 세 몫으로 갈라 각각 한 번씩만 곱한다.

   ```
   글 입력  = input_tokens - cached_input_tokens - audio_input_tokens
   캐시     = cached_input_tokens
   소리 입력 = audio_input_tokens
   글 출력  = output_tokens - audio_output_tokens
   소리 출력 = audio_output_tokens
   ```

   각 항은 음수가 되지 않게 0에서 자른다. `audio > input`(또는 출력 쪽)이면 포함
   관계가 깨진 것이므로 §5.3.1의 모순 규칙을 따른다.

#### 5.3.1 소리가 값을 못 받는 경우

| 상황 | 처리 |
|------|------|
| 소리 토큰이 있는데 항목이 소리를 값 매기지 않는다 | `price_missing`, 금액 없음 |
| 항목은 소리를 값 매기는데 두 소리 수 중 하나가 보고되지 않았다 | `usage_partial` |
| `audio_input > input` 또는 `audio_output > output` | `usage_partial` |
| 소리와 캐시가 같은 호출에 함께 있다 | `usage_partial` (아래) |

마지막 줄이 열려 있는 축이다. 캐시 적중분 안에 소리가 얼마나 들어 있는지 어느
사업자도 고지하지 않는다. 둘 다 0보다 크면 위 뺄셈이 소리를 캐시에서도 빼는지
아닌지 알 수 없으므로, 짐작해서 한쪽으로 정하지 않고 그 호출을 `usage_partial`로
둔다. 고지가 나오면 그때 규칙을 정한다.

**소리 몫만으로 총액을 만들지 않는다.** 저장된 60개 호출에서 소리는 입력의
9.8%(18,924 중 1,848)다. 소리 수만 곱한 값은 총액이 아니라 총액의 일부이며,
`complete`가 될 수 없다.

`missing_reasons`에 새 열거값을 만들지 않았다. §3.4의 8개는 `grade.schema.json`이
닫아 둔 목록이고, 위 상황은 전부 기존 `price_missing`·`usage_partial`로 정확히
읽힌다. 아홉 번째 값을 더하면 이미 게시된 채점 산출물이 스키마 검증에 걸린다.

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

#### 5.4.1 소리 판독 경로는 이미 연결되어 있다

`perception` 줄은 세션 B 소유 파일(`core/perception/audio.py`,
`core/perception/vision.py`)을 가리키지만, **원장에 쓰는 주체는 그 파일이 아니다.**
`core/grader.py`가 계측 래퍼를 씌우고

```python
self._perception_client = cost_recorder.meter(
    client, provider="azure", stage=STAGE_PERCEPTION
)
```

그 래퍼가 호출 전 `reserve`, 응답 후 `extract_usage(response)`로 `settle`한다.
`meter`·`extract_usage`·`CallUsage`·원장 스키마는 전부 세션 A 파일이다. 따라서
소리 토큰이 원장에 남게 하는 데 **B 파일 수정은 필요하지 않았고, 하지 않았다.**
판독기는 자기 클라이언트를 래퍼에 넘길 뿐이고 기록은 래퍼가 한다.

`core/perception/audio.py`가 부르는 `read_reported_usage`는 B가 보고서용으로
따로 굴리는 누계이며 원장에 들어가지 않는다. 그쪽은 지금도 소리 몫을 보지 않지만,
**보지 않아도 원장은 정확하다.** B가 화면·보고서에 소리 몫을 보이고 싶어지면 그때
`ReportedUsage`에 필드를 더하는 것이 A 쪽 계약 변경이며, 그전까지는 없는 층을
미리 만들지 않는다.

이 연결은 짐작이 아니라 검증했다 —
`tests/test_speech_is_not_charged_at_the_price_of_prose.py`의 「the connection」
절이 실제 `meter()` 래퍼로 모의 응답을 통과시켜 원장 행에 소리 몫이 남는 것,
그 행이 글 요율로 값 매겨지지 않는 것, 소리가 없는 호출은 같은 래퍼·같은 표로
여전히 값이 매겨지는 것을 각각 확인한다.

### 5.5 포함 관계는 측정한 것이다

§5.3의 3번은 규약이 아니라 **저장된 자료에서 나온 결과**다. B의 331건 소리 진단이
남긴 60개 호출에는 각 요청이 실은 소리 길이와 프롬프트 길이가 함께 있다.

| 검사 | `input` 그대로 | `input - audio` |
|------|---------------|-----------------|
| 소리 길이와의 상관 | +0.8488 | **+0.0134** |
| 프롬프트 글자수와의 상관 | +0.4589 | **+0.9224** |
| 글자당 토큰 (평균 ± 표준편차) | 0.28787 ± 0.00276 | **0.25976 ± 0.00093** |

소리 토큰을 빼면 입력이 소리 길이와 무관해지고 프롬프트 길이와 거의 일치한다.
남은 것이 글이라는 뜻이다. 소리 토큰 자체는 길이와 +0.9918로 붙어 있고 초당
9.8597개인데, 이는 사전 등록된 10.00/초와 사실상 같다. 60개 전부에서
`audio_tokens == audio_tokens_billed`였다.

합계는 입력 18,924, 그중 소리 1,848, 출력 4,223이다. 즉 **글 입력 17,076, 소리는
입력의 9.8%**다.

빼기가 아니라 더하기였다면(소리가 입력 *바깥*이었다면) 위 두 열은 반대로 움직였을
것이다. 그러지 않았으므로 뺀다.

### 5.6 값을 매기지 않는 이유는 기록으로 남긴다

`azure:gpt-audio-1.5`는 여전히 `providers`에 없다. 2026-08-30에 이어
**2026-09-07에 다시 확인**했고, 공개(비로그인) Azure Retail Prices API에 질의한
내용·결과·행 수를 `models_deliberately_not_priced`에 그대로 적었다. 새 계정도,
새 Azure 권한도 만들지 않았다.

다섯 질의 모두 이 모델의 미터를 내놓지 않았다. `productName eq 'Azure OpenAI GPT5'`
는 8,321행 9페이지 410개 미터를 돌려주는데 그중 소리를 말하는 것은 없다. 8일 전
같은 질의는 7,235행 8페이지였다. **주변 제품이 늘어나는 동안에도 계속 없다는 것은
누락이 아니라 상태다.**

그래서 금액은 계속 `null`이다. 비슷한 이름의 모델 요율을 빌리지 않았고, 직판
가격을 Azure 가격으로 간주하지 않았다. 해결에 필요한 것은 **두 개의 요율**(소리
입력과 소리 출력)이며, 하나로 뭉친 값은 §5.3의 세 몫 계산에 넣을 수 없다.

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

### 7.1 게시되는 `usage`는 네 칸으로 닫혀 있다

`grade.schema.json`의 `costUsage` 정의는 `additionalProperties: false`이고 칸이
정확히 네 개다: `input_tokens`, `cached_input_tokens`, `output_tokens`,
`reasoning_tokens`. 그러므로 **소리 몫은 영수증에 새 칸으로 올라가지 않는다.**
올렸다면 이미 게시된 채점 산출물 전부가 스키마 검증에 걸린다.

소리 몫은 **원장 행**에 산다 — SQLite 열 `audio_input_tokens`,
`audio_output_tokens`와 내보낸 JSONL의 같은 이름 필드. 원장이 감사 기록이고,
영수증은 그 요약이다. 요약이 좁다고 해서 기록이 좁아지는 것은 아니다.

`build_receipt`가 합산하는 칸도 그 네 개뿐이므로, 소리 몫이 총량에 두 번 더해질
자리 자체가 없다.

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
17. 소리 토큰이 있는데 항목이 소리를 값 매기지 않는다 — `price_missing`, 글 요율
    대체 금지
18. 소리 토큰 이중 과금 없음 — 글·캐시·소리 세 몫이 각각 한 번씩
19. 보고된 소리 `0`은 소리가 아니다 — 값이 정상으로 매겨진다
20. 소리와 추론이 같은 호출에 있어도 각각 자기 총량 안에서 한 번씩
21. 소리와 캐시가 겹치면 `usage_partial` — 짐작으로 정하지 않는다
22. 재시도마다 자기 소리 몫을 갖는다 — 마지막 것으로 덮이지 않는다
23. 소리 몫이 내보내기·가져오기(재개·shard 병합)를 건너 살아남는다
24. 게시되는 영수증 `usage`는 여전히 네 칸이다 (§7)

전부 `tests/test_speech_is_not_charged_at_the_price_of_prose.py`에 있으며,
17~24는 단위 규칙과 **실제 계측 래퍼를 통과하는 경로** 양쪽에서 확인한다.

### 8.3 유료 실행 금지

이 명세의 모든 테스트는 **모의 응답**으로 돈다. 실제 사업자 호출, 로그인, 실제
채점·재채점, Smoke/Pilot/Full 실행은 세션 A·B 어느 쪽도 하지 않는다. 통합 담당
세션이 두 PR 병합 후 한 번만 실제 Smoke를 돌린다.

> **2026-09-07 주석 — 위 문단은 더 이상 실행되지 않았다.**
>
> 위 문장은 지우지 않고 그대로 둔다. 실제로 일어난 일과 다르기 때문이다. 두 PR이
> 병합된 뒤 소유자가 세션 A에게 Smoke를 직접 돌리라고 지시했고, A가 2026-09-07에
> 한 번 돌렸다 (§11). 즉 **"A·B 어느 쪽도 하지 않는다"와 "통합 담당 세션이 한
> 번"이라는 두 조항이 이번에 지켜지지 않았다.**
>
> 명세를 조용히 고쳐 이번 실행이 원래 허용된 것처럼 보이게 만들지 않는다. 그렇게
> 하면 이 문서는 무엇이 계획이었고 무엇이 실제였는지 구별할 수 없게 된다. 바뀐
> 것은 규칙이 아니라 실행 주체이고, 바꾼 사람은 소유자다. §10의 6번도 같다.
>
> 지켜진 부분도 정확히 적는다: 횟수는 **한 번**이었고 (유료 실행 1회), 두 PR
> 병합 이후였으며, 모의 테스트는 여전히 전부 모의로 돈다. 어긋난 것은 **누가**
> 돌렸는가 하나뿐이다.


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
6. 통합 담당 세션에서만 실제 Smoke 1회 — **2026-09-07에 세션 A가 대신 수행했다.
   §8.3의 주석과 §11을 보라. 조항은 고치지 않고 어긋난 사실만 적어 둔다.**
7. Smoke가 완전하면 Pilot, 이후 Full

6번은 선택이 아니다. `core/cost_receipts.py`·`core/cost_metering.py`는
`_HASHED_TREES` 아래에 있어 고치면 `grader_source_hash`가 움직인다. 저장소 자체
검사(`scripts/check_grader_hash_freeze.py`)가 "This diff does move the grader
source hash … the next paid run has to be preceded by a fresh smoke at the new
fingerprint"라고 말한다. shard가 도는 중에 병합하면 `step9`가 열한 개 지문
불일치로 거절하는데 **그 거절은 돈이 다 나간 뒤에 온다.** 그래서 병합 전에
진행 중인 유료 채점이 없음을 먼저 확인한다.

---

## 11. 최신 지문에서의 Smoke 증거 (2026-09-07)

§10의 6번이 요구한 "새 지문에서의 Smoke"를 실제로 돌린 기록이다. 왜 필요했는지는
바로 위 문단이 이미 말한다 — #444가 `core/cost_receipts.py`를 고쳤고, 그래서
`grader_source_hash`가 움직였다.

### 11.1 먼저 확인한 것: 재사용할 증거가 있는가

**돌리기 전에 먼저 찾았다.** 소유자 지시의 첫 항목이 "이미 조건을 만족하는 실행이
있으면 다시 부르지 말고 그 증거를 회수해 검증하라"였기 때문이다. 결과는 **없음**
이었고, 근거는 다음과 같다.

| 확인 | 결과 |
|------|------|
| 커밋된 원장이 고정한 grader 지문 18종에 `f4931215…`가 있는가 | 없다 |
| 진행 중·대기 중인 유료 채점이 있는가 | 없다 (최근 100 실행 중 0건 진행) |
| B의 `34117749459`(소리 진단 성공)로 갈음할 수 있는가 | **아니다** |

마지막 줄이 중요하다. 성공한 실행이라는 이유만으로 동등하다고 보지 않고 항목별로
대조했다. **여섯 축이 전부 다르다** — 워크플로가 `audio-accuracy-probe.yml`(채점
파이프라인이 아니다), 진입점이 `measure_audio_grading_accuracy.py`, 커밋이
`1583caf`, 설정이 `gold_audio_repeat_v2_sol_max.yaml`, 지문이 `7506ce50…`(그
설정에 대해서는 최신이지만 **제3의 설정**이다), 그리고 결정적으로 **비용 원장
사이드카도, `cost-receipt-v1` 영수증도, `data/grades` 산출물도 남기지 않는다.**
검증할 영수증 자체가 없으므로 이 계약의 Smoke가 될 수 없다.

### 11.2 실제로 돌린 것

무료 사전 점검 → 유료 1회. 둘 다 저장소가 이미 정의해 둔 경로다.

| | 실행 ID | 결과 |
|---|---|---|
| 무료 사전 점검 (`grade-dry-run`) | `34128957371` | PASS — `tasks=1 items=38 precheck=0 judge=38` |
| 유료 채점 (`grade`) | `34129417431` | 성공 |

- **표본 수는 명세에서 읽었다.** `cost_smoke_exp026c_v2_gpt54.yaml`의
  `expected_task_count: 1`, 과제 `83d10b06-26d1-4636-a32c-23f92c57f30b` 하나.
  5·30·220으로 부풀리지 않았다.
- **커밋 고정**: `89e242d`에서 dispatch. `grade-run.yml`은 두 job 모두
  `actions/checkout`을 `ref: main`으로 하고 유료 job이 HEAD가 `origin/main`을
  추종하는 로컬 `main`인지 검사하므로 **SHA로 pin할 수 없다.** 그래서 main이
  대상 커밋인 동안 dispatch하고 그 시간 동안 main을 얼리는 방식으로 고정했다.
  이것이 이 워크플로에서 가능한 유일한 고정 방법이다.
- **완화한 것 없음**: 환경 허용 목록, 보안 가드, 인증 범위 어느 것도 건드리지
  않았다. `grading` 환경 게이트는 PR #252의 상시 승인 아래 자체 승인했다. 새 모델,
  새 배포, 다른 테넌트, 새 비용 상한 전부 없다.
- **`tasks_limit: 1`이므로 산출물은 `data/grades/_diagnostic/` 아래로 갈라진다.**
  공개 대시보드 경로는 손대지 않았다. `run_status`도 `diagnostic`이다.

### 11.3 검증 결과 — 12개 항목 전부 통과

`scripts/verify_cost_ledger.py`(이번에 새로 쓴 오프라인 검사, 모델 호출·자격증명
없음)로 확인했다.

| 검사 | 확인한 것 |
|------|-----------|
| `sidecar` | 원장 SHA-256 재계산 = `7d3919a2ba0032b5…` 일치 |
| `identity` | run_id 단일, grade의 grader 지문과 일치 |
| `no_double_billing` | `call_id` 112개 전부 유일, 재시도 보존 |
| `all_calls_settled` | 미정산 예약 **0** — 기록되지 않은 지출 없음 |
| `usage_reconciles` | 토큰 합 정수 단위로 정확히 일치 |
| `usage_containment` | #444의 소리 열 present-and-zero |
| `cost_reconciles` | `Decimal` 합 일치, `complete` ⇒ 금액 존재 |
| `components_reconcile` | 7-튜플 분해 합 일치 |
| `price_table` | 요율표 단일 (`a2d60e1c…`) |
| `partial_cause` | 해당 없음 (`complete`) |
| `task_coverage` | 과제별 비용 귀속, 실패 과제 포함 |
| `legacy_counters` | 구형 `summary.cost` 계수 일치 |

`usage_containment`이 말하는 것을 정확히 적어 둔다: 새 원장에 소리 열이 **있고
값이 0**이다. 옛 원장은 아예 그 열이 없다. 즉 이 말뭉치는 **소리 경로를 실행하지
않는다.** 그러므로 이번 Smoke로 소리 계측이 검증되었다고 말할 수 없다.

### 11.4 옛 실행과의 대조 — 덮어쓰지 않았다

옛 파일 3개와 새 파일 3개가 같은 디렉터리에 **함께** 있다. 아무것도 숨기거나
덮어쓰지 않았다.

| | 옛 (2026-09-01) | 새 (2026-09-07) |
|---|---|---|
| grader 지문 | `7ca55f907056df2d` | `f4931215d1ec316b` |
| 설정 해시 | `c4348e8fa153ce8d` | `5b77131b1e1fc221` |
| 영수증 상태 | `complete` | `complete` |
| 금액 | $0.753121 | $0.791724 |
| 호출 | 84 (채점 83 + 판독 1) | 112 (채점 111 + 판독 1) |
| 요율표 | `f878bb9e…` | `a2d60e1c…` |
| 미정산·재시도 | 0 · 0 | 0 · 0 |
| 점수 (`pct`) | 74.41 | 66.41 |
| `judge_error_rate` | 0.0 | 0.0 |

### 11.5 금액이 왜 올랐는가 — 요율이 아니라 사용량이다

요율표 지문이 움직였으므로 **요율이 올라서 비싸진 것인지 먼저 확인했다.** 아니다.

커밋된 표 네 판(`f878bb9e`→`ff85f9f5`→`fd09d28c`→`a2d60e1c`) 전부에서
`providers["azure:gpt-5.4"]`는 **바이트 단위로 동일**하다 — 입력 2.50, 캐시 0.25,
출력 15.00, `reasoning_billed_as: output`. 지문이 움직인 이유는 §4.2가 이미 적은
대로 요율이 아니라 문서다.

그 요율로 두 금액을 다시 계산하면 **둘 다 발표된 값과 소수점까지 정확히** 나온다.

```
옛: (302038-167424)/1e6*2.50 + 167424/1e6*0.25 + 24982/1e6*15.00 = 0.753121  ✓
새: (377142-248576)/1e6*2.50 + 248576/1e6*0.25 + 27211/1e6*15.00 = 0.791724  ✓
```

차액 **+$0.038603**의 출처도 남김없이 갈린다.

| 항목 | 토큰 변화 | 금액 |
|------|-----------|------|
| 캐시 안 된 입력 | −6,048 | −$0.015120 |
| 캐시된 입력 | +81,152 | +$0.020288 |
| 출력 | +2,229 | +$0.033435 |
| **합** | | **+$0.038603** |

즉 **출력 토큰이 차액의 87%**다. 캐시 적중률은 55.4% → 65.9%로 오히려 좋아졌고,
그래서 호출이 28번 늘었는데도 캐시 안 된 입력은 줄었다.

**호출 83 → 111은 정직하게 미정이다.** 확실히 배제된 것만 적는다: 재시도가 아니고
(양쪽 다 `retry_kind: none` 100%), 미정산이 아니고 (양쪽 0), 모델이 바뀐 것도
아니다 (양쪽 `gpt-5.4` 100%). 특히 #367이 재시도를 별도 행으로 분리했으므로 그것이
행 수를 부풀렸을까 의심했으나, **양쪽 원장에 재시도가 한 건도 없어 그 가설은
성립하지 않는다.** 남는 설명은 채점기가 도구 호출 루프라는 것이다 — 항목당 왕복이
고정이 아니고 2.18 → 2.92로 움직였다. 두 실행 사이에 `core/`가 여러 번 바뀌었고
grader 지문도 움직였으므로 **행동 변화 가능성을 배제할 수 없다.** n=1 대 n=1이므로
측정된 효과가 아니라 관찰이다.

한 가지는 명확히 부정한다: `#376`이 `call_cap_per_task`를 72 → 112로 올렸고 새
실행의 총 호출이 우연히 112지만, **그 상한은 시각 판독 호출의 상한이고 두 실행 모두
판독 호출은 정확히 1건이다.** 상한 근처에도 가지 않았다. 두 수가 같은 것은 우연이며
인과가 아니다.

### 11.6 점수가 내려간 것은 파이프라인 실패가 아니다

**파이프라인 검증은 통과(12/12)이고, 점수 이동은 별개의 관찰이다.** 둘을 섞지
않는다.

이 절이 `972f52a`로 처음 커밋됐을 때의 문장은 이랬다:

> 74.41 → 66.41은 38개 항목 중 **2개가 뒤집힌 것**이다 (통과 24 → 22,
> `judge_pass_rate` 0.6316 → 0.5789). `judge_error_rate`는 양쪽 다 0.0 —
> 채점기가 실패한 것이 아니라 판정이 달라진 것이다. 저장소가 자체 측정한 반복
> 편차(판정 4.75%, 점수 10.5%) 안에 있다.

**"2개"와 "반복 편차 안", 두 군데가 틀렸다.** 원문은 위에 그대로 두고 아래에 맞는
값을 적는다. 틀린 방향이 한쪽이라서 — 움직임을 실제보다 작게, 그리고 "이미 아는
잡음"으로 보이게 만든다 — 조용히 고치지 않는다.

`judge_error_rate`는 양쪽 다 0.0이다. **채점기가 실패한 것이 아니라 판정이
달라진 것**이라는 결론은 그대로다. 아래는 그와 별개의 관찰이다.

바뀐 것을 세 가지 기준으로 나눠 적는다. 세 값이 다르고, 어느 하나가 나머지를
대표하지 않는다.

| 기준 | 옛 → 새 | 움직인 항목 |
|---|---|---|
| **점수**가 달라진 항목 | 46.88 → 41.84점 (63점 만점) | **5 / 38** |
| **판정**(`verdict`)이 달라진 항목 | — | **4 / 38** — `pass`→`fail` 2, `partial`→`fail` 2 |
| `judge_pass_rate` | 0.6316 → 0.5789 (통과 24 → 22) | 겉보기 **2** |

**처음에 적은 "2개"는 맨 아랫줄이다.** `judge_pass_rate`는 `pass`만 통과로
세므로 `partial`→`fail`로 내려간 2개를 **아예 못 본다.** 그 지표만 보면 움직임이
절반으로 보인다. 점수를 실제로 끌어내린 것은 5개 항목이고, 그중 하나는 2.0점
만점에서 0점으로 통째로 내려갔다.

**"반복 편차 안"이라는 말도 취소한다.** 근거로 든 4.75%·10.47%는
`315-repeat-variation-prereg.md` §3의 값인데, 같은 문서 line 92가 못 박듯
**"같은 지문 30과제 3회 실행"**에서 잰 값이다. 즉 **코드가 그대로일 때의 잡음**
폭이다. 이번 두 실행은 **지문이 서로 다르다**(`7ca55f90` → `f4931215`).
같은 코드의 재실행 잡음 폭을 코드가 바뀐 두 실행의 차이에 갖다 대는 것은
기준 자체가 틀린 비교다.

굳이 그 폭에 대 보더라도 안에 들어가지 않는다.

| | 이번 실행 | 같은 지문 반복 편차 | |
|---|---|---|---|
| 판정이 달라진 비율 | 4/38 = **10.53%** | 4.75% (95% 구간 3.82~5.74) | 밖 |
| 점수가 달라진 비율 | 5/38 = **13.16%** | 10.47% | 살짝 밖 |
| 과제 점수 차 | **−8.00pp** | 평균 1.0~1.7pp, **최대 7.05pp** | **최대치보다 큼** |

다만 항목이 38개뿐이라 단정하지는 않는다. 저 4.75%가 맞다고 가정해도 38개 중
4개 이상이 뒤집힐 확률은 **0.105**로, 드물다고 할 만큼 작지 않다. 점수 쪽은
0.367로 평범하다. **한 줄로 정리하면: 판정 이동은 잡음으로 설명되지 않는 쪽에
가깝지만 n=38로는 증명되지 않고, −8.00pp라는 과제 점수 차가 저장소가 같은
지문에서 관측한 최대치를 넘었다는 사실만 확실하다.**

이 관찰은 §11.9의 미해결 항목(호출 83 → 111)과 **같은 방향을 가리킨다** — 새
지문의 채점기가 다르게 행동했을 가능성. 어느 쪽도 이번 n=1 대 n=1로는 증명할 수
없으므로 **양쪽 다 미해결로 남긴다.** 확실한 것만 적는다: 재시도 0, 미정산 0,
모델 동일, `judge_error_rate` 0.0.

그리고 이 실행은 `_diagnostic`이므로 **발표된 점수는 하나도 움직이지 않는다.**
기존 185실행·31건 수치는 그대로다.

### 11.7 이번 실행이 깨뜨린 것 셋과 그 수정

이번 Smoke는 테스트 **세 곳**을 붉게 만들었다. 셋 다 원인은 이번 실행 자신이고,
셋 다 **내 작업 트리가 아니라 커밋된 `main`에서 재현된다.** 즉 이 수정 전까지
`main`이 붉었다. (2)는 작업 트리 변경이 하나도 없는 `602cea4` detached
checkout에서 그대로 재현해 확인했다 — 내 편집 탓으로 돌릴 수 없다.

셋 다 성격이 같다. **산출물이 잘못된 게 아니라, 커밋된 산출물의 수를 세는 테스트가
"다시 돌릴 일은 없다"고 가정하고 있었다.** 그런데 이 저장소의 계약은 지문이
움직이면 반드시 다시 돌리라고 요구한다. 계약을 지키는 순간 깨지도록 되어 있었고,
이번에 그 순간이 왔다.

#### (1) 원장 개수가 32에서 멈춰 있었다

`test_the_grading_ledger_no_longer_dies_with_the_runner.py::test_the_recorded_counts_recompute_from_the_ledgers`
가 **실패**했다. 33번째 원장을 게시했는데 `model_price_table.json`의
`models_deliberately_not_priced['azure:gpt-5.6-sol']['measured_from_committed_ledgers']`
가 아직 32라고 적고 있었다. 테스트가 고쳐야 할 값을 직접 말해 주며, **"주변
산문이 여전히 참인지 확인한 뒤에 쓰라"**고 덧붙인다. 그대로 했다.

| 필드 | 이전 | 이후 |
|------|------|------|
| `ledgers` | 32 | **33** |
| `rows` | 68,610 | **68,722** (+112) |
| `distinct_call_ids` | 45,398 | **45,510** (+112) |
| `duplicate_rows` | 23,212 | **그대로** |
| `gpt_5_6_sol_calls` 등 5.6-sol 수치 전부 | | **그대로** |

뒤의 두 줄이 요점이다. 이번 실행은 충돌 식별자를 만들지 않았고 이 항목이 다루는 두
모델(`gpt-5.6-sol`, `gpt-audio-1.5`)을 **한 번도 부르지 않았다.** 그래서
`what_it_bounds`의 "45,177 of 45,203 calls are under 128,000"을 비롯한 산문이
재계산해도 **동일**하다. 옮겨 적은 것이 아니라 다시 계산해서 같았다.

이 수정이 안전한 이유도 저장소 자체 검사로 확인했다 —
`check_grader_hash_freeze.py`가 `PASS: no grader-source file in this diff`.
`experiments/`는 `_HASHED_TREES`에 없으므로 **이 수정은 방금 돌린 Smoke의 지문을
무효화하지 않는다.** 살아 있는 표의 해시를 고정하는 테스트도 없다 (`a2d60e1c…`가
나오는 곳은 발표된 산출물 안뿐이고, 그것은 "이 행을 값 매긴 표"의 기록이지 현재
파일에 대한 주장이 아니다 — §4.2).

#### (2) 두 번째 Smoke가 "정확히 하나" 가정을 깨뜨렸다

`test_both_cost_halves_recompute_from_their_ledgers.py`에서 **오류 4건**이 났다.
실패(assertion)가 아니라 **fixture setup 단계의 오류**라 테스트가 아예 돌지
못했다. 원인은 한 줄이다:

```python
GRADING_GLOB = "data/grades/_diagnostic/*/exp026c_cost_receipt_smoke*__v2.2.json"
matches = sorted(REPO_ROOT.glob(GRADING_GLOB))
assert len(matches) == 1        # ← 이번 실행으로 2가 되었다
```

주석은 이 파일을 "shape로 찾되 고정하지 않는다"고 설명하고 있었다. 그런데
`_diagnostic` fork는 **새 지문의 재실행을 옛것 옆에 나란히 남기도록 설계된
장치다.** 즉 산출물이 잘못된 게 아니라 **테스트의 가정이 계약과 어긋나 있었다.**
계약대로 재실행하는 순간 반드시 깨지게 되어 있었고, 이번에 그 순간이 왔다.

고친 방식은 **지문으로 집어내기**다. 이 파일이 검증하는 숫자($0.753121, 84콜)는
**첫 실행의 것**이므로, 첫 실행을 이름으로 지목하게 했다.

```python
GRADING_SOURCE = "src_7ca55f907056df2d"
```

새 실행을 지우거나 덮어쓰지 않았다. 형제 파일의 존재는 이제 **충돌이 아니라 계약이
작동한 증거**로 읽히며, 그렇게 주석에 적었다.

같은 자리에서 **잠복 결함 하나**도 함께 닫았다. `grading_rows`가 glob을 **다시**
돌려 `matches[0]`을 집으면서, 원장 파일 이름은 `grading_grade`에서 가져오고
있었다. 파일이 하나일 때는 우연히 일치했지만 둘이 되면 **한 실행의 grade와 다른
실행의 경로를 짝지을 수 있는** 구조였다. 경로 fixture 하나를 공유하도록 바꿔 두
번째 glob을 없앴다.

#### (3) 대시보드 분모 인구조사가 27에 고정돼 있었다

`scripts/__tests__/test_a_denominator_thrown_away_is_still_recoverable.py::test_the_committed_backfill_added_denominators_and_nothing_else`
가 **실패**했다 — `27 payloads should carry recovered denominators; 28 do`.

**이건 CI에서만 잡혔다.** 이 저장소의 backend CI는 pytest를 **두 번** 돌린다.

| | 명령 | 위치 |
|---|---|---|
| 1 | `python -m pytest -m "not integration"` | `batch-runner/` |
| 2 | `python -m pytest scripts/__tests__ -m "not integration"` | 저장소 루트 |

나는 (1)만 돌리고 있었다. `batch-runner/`에서 도는 8,478개가 전부 초록이어도
루트의 183개는 손대지 않은 상태였다. **로컬 초록이 CI 초록을 뜻하지 않았다.**
이후로는 둘 다 돌린다.

내용은 단순하다. 이 테스트는 `data/grades` 전체를 훑어 `wow.item_counts`를
지닌 payload 수를 센다. 새 채점 결과가 28번째다. 이동한 값은 정확히 둘이고 원인은
**파일 하나**다.

| | 이전 | 이후 |
|---|---|---|
| `carried` (payload 수) | 27 | **28** |
| `sector_rows` | 86 | **87** |
| `empty_analytics` | 6 | **6 — 그대로** |

세 번째 줄이 확인 포인트다. 새 payload는 자기 `by_sector`를 갖고 있으므로 "비어
있는" 쪽으로 세어지지 않는다. 실제로 옛 실행과 **모양이 같다** — 같은 섹터 1개,
같은 rubric 38항. 그래서 +1, +1, +0이다.

이 테스트의 docstring은 스스로 **"이 델타 하나하나는 이 suite가 이름 댈 수 있는
파일"**이라는 규율을 세워 두고 있다. 그 규율대로, 숫자만 바꾸지 않고 **두 번째
이동이 언제·무엇 때문에·왜 `empty_analytics`는 안 움직이는지**를 docstring에
적었다.



두 산출물의 `cost_ledger.path` **모양이 다르다.**

| 실행 | `cost_ledger.path` |
|---|---|
| `src_7ca55f907056df2d` (옛) | `exp026c_…__v2.2.cost_ledger.jsonl` — **파일 이름만** |
| `src_f4931215d1ec316b` (새) | `data/grades/_diagnostic/…/exp026c_…jsonl` — **저장소 상대 경로** |

이건 이번에 처음 관찰된 채점기 표류이고, 두 가지 실제 결과가 있다.

- `Path.with_name()`은 구분자가 든 문자열을 **거부한다**(`ValueError`). 그러니
  이 테스트를 새 실행 쪽으로 돌렸다면 오류가 형태만 바꿔 남았을 것이다. 첫
  실행에 고정한 것이 이 점에서도 옳았다.
- `verify_cost_ledger.py:151`은 `Path(declared_path).name`으로 **basename만**
  취한다. 그래서 두 모양 모두 통과한다. 이번 산출물이 그 설계가 필요했다는 것을
  실제로 보여 준 첫 사례다.

#### 새 실행에도 검사를 붙였다

첫 실행만 회귀 테스트가 지키고 새 실행은 아무도 재계산하지 않는 상태를 남기지
않기 위해, `test_verify_cost_ledger.py`에
`test_the_rerun_at_the_new_grader_fingerprint_also_reconciles`를 추가했다.
12개 검사 통과 + `grader_source_hash`가 `f4931215…`로 시작 + `settled_rows ==
call_rows == 112`를 요구한다. 마지막 항이 §11.3에서 말한 **"보냈는데 기록 안 된
호출 0건"**을 테스트로 고정한 것이다.


### 11.8 이 증거는 다음 실행에 재사용할 수 있는가

**조건부로 가능하다.**

| 다음 실행이 | 재사용 |
|---|---|
| 같은 지문 `f4931215…` + 같은 설정 `5b77131b…` | **가능.** 다시 살 필요 없다 |
| `core/**` · `prompts/**` · `grading_configs/**` 중 하나라도 바뀜 | **불가.** 지문이 움직이므로 새 Smoke 필요 |
| 소리 경로를 쓰는 채점 | **불가.** 11.3의 이유 — 이 말뭉치는 소리를 부르지 않는다 |
| 다른 모델·다른 배포 | **불가.** 이 증거는 `gpt-5.4` 한 건이다 |

§11.7의 수정은 요율표와 **테스트 파일 세 개**를 건드렸을 뿐이다. `_HASHED_TREES`는
`core/**.py` · `prompts/**` · `grading_configs/**` 셋뿐이고 `experiments/`도
`tests/`도 `scripts/__tests__/`도 거기 없다. 이 PR의 실제 7개 경로 전부를
`check_grader_hash_freeze.py`에 넣어 `PASS: no grader-source file in this diff`
(exit 0)를 받았다. **그러므로 이 수정은 위 재사용 가능성을 깎지 않는다.** 확인
시점에 진행 중인 유료 채점도 0건이라 지문 동결과 충돌할 여지도 없었다.

### 11.9 여전히 열려 있는 것

- `gpt-5.6-sol`과 `gpt-audio-1.5`는 계속 **미등록**이다. 이번에 값을 채우지
  않았고, 같은 공개 API를 다시 조회하지도 않았다 (#444가 2026-09-07에 이미
  다섯 가지로 조회했고 그 기록이 표 안에 있다). 임의 요율로 메우지 않았다.
- 소리 계측은 이 Smoke로 **검증되지 않았다** — 실행되지 않았기 때문이다.
- 호출 수 증가의 원인은 미정이다 (§11.5).
- **판정이 4/38 움직인 원인도 미정이다** (§11.6). 위 항목과 같은 방향을 —
  새 지문의 채점기가 다르게 행동했을 가능성을 — 가리키지만, n=1 대 n=1이라
  둘 중 어느 것도 증명하지 못한다. **두 항목을 서로의 근거로 쓰지 않는다.**
  가르려면 같은 지문에서 반복 실행이 필요하고, 그것은 이번 승인 범위 밖이다.


---

## 12. 게시된 채점 결과를 아무도 검사하지 않던 구멍 (2026-09-07)

§11은 **Smoke가 무엇을 깨뜨렸는지**를 적었다. 이 절은 그것과 다른 질문에
답한다 — **왜 그걸 이틀 뒤 다른 사람의 PR에서야 알게 됐는가.**

### 12.1 실제로 일어난 일 (실행 기록으로 확인)

채점 파이프라인은 결과를 `main`에 **직접 push**한다. 이번 Smoke는 두 번 밀어
넣었다.

| commit | 시각 (UTC) | 내용 |
|---|---|---|
| `94bb8fa` | 2026-09-07 13:59:34 | 채점 결과 JSON + 원장 |
| `602cea4` | 2026-09-07 13:59:37 | 자동 분석 문서 |

두 commit에서 **실행된 workflow는 0건이다.**

```
$ gh run list --commit 94bb8fa9e9bd50be9c5191efd85be2f5594c26b2 → 0
$ gh run list --commit 602cea4f38205fa4f16a2daa34649b3c92e3b115 → 0
```

그래서 실패 5개는 **이틀 뒤 B의 #447**에서, 그것도 B가 건드리지도 않은 파일에서
처음 드러났다. #447의 CI는 자기 브랜치 base(=`main`)를 함께 돌렸을 뿐이다.
B의 진단 작업과는 아무 상관이 없었다.

### 12.2 왜 안 돌았나 — 이건 설정 실수가 아니다

GitHub 공식 문서(*Triggering a workflow* → *Triggering a workflow from a
workflow*)가 명시한다: **workflow가 자기 `GITHUB_TOKEN`으로 만든 push는 새
workflow 실행을 만들지 않는다.** 무한 재귀를 막기 위한 의도된 제약이다.
`grade-run.yml`이 바로 그 기본 토큰으로 push하므로, 게시된 commit은 정의상
아무 검사도 받지 못한다.

즉 "테스트를 켜는 걸 잊었다"가 아니라 **켤 수 있는 자리가 없었다.** 그래서
고침도 "빠뜨린 트리거 추가"가 아니라 **같은 실행 안에서 이어 붙이기**여야 한다.

### 12.3 #448이 고친 것과 남긴 것

#448은 실패 5개를 **손으로** 되돌렸다. 셋 다 같은 모양이었다 — *산출물은
맞는데, 테스트가 "재실행은 없을 것"이라고 가정했다.*

| # | 무엇 | 손으로 한 일 |
|---|---|---|
| 1 | 요율표의 원장 수 | 32 → 33 |
| 2 | 비용 양쪽 대조 테스트 | "결과가 하나뿐"이라는 단정 → 실행 이름(`GRADING_SOURCE`)으로 지목 |
| 3 | 저장소 전수 조사 | 27 → 28 payload, 86 → 87 sector 행 |

**남은 공백은 둘이다.**

- (가) 게시된 그 commit에서 **여전히 아무것도 안 돈다.** #448은 증상을 지웠고
  경로는 그대로다.
- (나) 1번과 3번은 **다음 정상 Smoke에서 또 빨개진다.** 고정된 숫자가 살아
  있는 저장소를 세고 있는 한, 정상적인 새 영수증 하나가 올바른 숫자를 틀리게
  만든다.

### 12.4 고침 (가) — 게시한 그 commit을 그 실행이 검사한다

`grade-run.yml`의 `grade` job이 push할 때마다 `git rev-parse HEAD`를 적어
`published_commits`로 내보내고, **읽기 전용 후속 job** `verify-published`가
그 SHA를 정확히 checkout해서 모델 호출 없는 검사 5종을 돌린다.

| 검사 | 무엇을 본다 |
|---|---|
| `published` | 그 commit들이 정말 `origin/main` 조상인가 |
| `no_deletions` | 결과를 지우거나 덮어쓰지 않았는가 |
| `payload` | 파일이 그 commit에 있고 JSON으로 열리는가 |
| `schema` | 파이프라인이 쓰는 그 검증기로 `grade.schema.json` 통과 |
| `ledger` | `verify_cost_ledger`에 통째로 위임 — 금액이 원장에서 재계산되는가 |
| `aggregation` | 대시보드 집계가 이 트리에서 성공하는가 |

새 secret·PAT·권한 확대는 없다. 오히려 좁혔다 (`permissions: contents: read`).
`pull_request_target`도 쓰지 않는다.

**실제 게시 commit에 대고 돌린 결과** (2026-09-07, 로컬, 모델 호출 0):

```
$ python batch-runner/scripts/verify_published_grades.py \
      --commits 94bb8fa 602cea4 --ref origin/main
[PASS] published    : 2개 commit 모두 origin/main(1e06e452aca9) 조상
[PASS] payload      : 열림, task 1개, run_status='diagnostic'
[PASS] schema       : grade.schema.json 통과 (schema_version 1.4)
[PASS] ledger       : 12/12 대조, 정산된 호출 112건, 영수증 완결
[PASS] aggregation  : 집계 성공
VERDICT: pass   (exit 0)
```

**실행기의 head SHA나 변경 전 base가 아니라, 게시된 그 SHA를 본 결과다.**

### 12.5 고침 (나) — "스냅샷"과 "저장소 검사"를 갈랐다

같은 증상의 두 도구는 **정반대의 규칙**을 따라야 한다.

| | 무엇인가 | 새 영수증이 생기면 |
|---|---|---|
| 요율표의 5.6-sol 측정 | **스냅샷** — 특정 33개 원장을 잰 값 | 아무 일도 없어야 한다 |
| 분모 복구 전수 조사 | **살아 있는 저장소 검사** | 새것도 같은 규칙을 지켜야 한다 |

**스냅샷 쪽.** 33개 원장의 목록과 sha256을
`experiments/execution_envelope/gpt56sol_ledger_corpus.json`에 고정하고,
그 파일의 digest(`8287b6ad…defee8`)를 요율표 안에 적었다. 이제 34번째 영수증은
아무 숫자도 건드리지 않고, 고정된 원장이 **지워지거나 한 줄이라도 고쳐지면**
파일 이름을 대고 실패한다. 목록이 몰래 늘어나는 것도 digest가 막는다.

> 행 수는 원래 "이 파일이 온전한가"를 묻는 대용품이었다. 그런데 행 수는 남이
> 게시해도 움직이고, **줄을 제자리에서 고치면 전혀 움직이지 않는다.**
> digest는 묻고 싶었던 것을 정확히 묻고, 파일 단위로 답한다.

**저장소 검사 쪽.** `28`/`87`/`6`이라는 숫자를 버리고, 그 숫자들이 대신 서
있던 **성질**로 바꿨다.

> 결과에 분모가 복구되어 있다 ⟺ 지금의 요약기가 그 결과의 공개 비율
> (`SCALAR_RATES` 5종)을 그대로 재현한다.

실제 말뭉치 34건에 대해 **위반 0건**이었다 (일치 28 · 불일치 6 — 즉 그 숫자들은
애초에 이 성질에서 나오는 값이었지 독립된 사실이 아니었다). 이제 새 결과가
생기면 개수가 아니라 **같은 규칙**을 요구한다.

### 12.6 순환·중복·실패에 대한 설계

| 상황 | 동작 |
|---|---|
| 검증이 또 채점을 부른다 | **불가능.** 후속 job은 유료 단계를 부르지 않고 push도 못 한다(`contents: read`) |
| 중복 실행 | 같은 실행 안의 후속 job이라 게시 1회당 정확히 1회 |
| 게시할 게 없음 | `published_commits`가 비면 job 자체를 건너뜀 |
| 채점이 중간에 죽음 | `if: always()` — **push 후 죽은 실행이야말로 검사해야 할 대상**이라 `success()`를 쓰지 않았다 |
| JSON 누락·손상 | `payload` 검사가 실패로 잡는다 |
| 같은 실험의 정상적 복수 결과 | 결과는 **덧붙는다**. 지움이 감지되면 `no_deletions` 실패 |
| 원장 추가 | 스냅샷은 그대로, 새 원장은 파싱만 검사 |

**`continue-on-error`는 어디에도 없다.** 검증 실패는 workflow를 빨갛게 만들고,
어느 commit의 어느 검사가 실패했는지 job summary와 90일 보관 artifact에 남는다.
실패해도 게시된 결과를 되돌리거나 지우지 않는다 — 증거는 보존하고 수정은 앞으로
나아간다.

### 12.7 테스트 (모델 호출 0)

| 파일 | 개수 | 무엇을 |
|---|---|---|
| `tests/test_verify_published_grades.py` | 40 | 검증기 전부. 위 표의 모든 상황을 **실제 Smoke 산출물 2건**과 작은 모의 트리로 |
| `tests/test_the_grading_ledger_no_longer_dies_with_the_runner.py` | 17 (기존 12) | 스냅샷 고정 + #448 회귀 |
| `scripts/__tests__/test_a_denominator_thrown_away_is_still_recoverable.py` | 42 (기존 40) | 성질 검사 + 양방향 음성 대조 |

#448 회귀는 **말로 확인하지 않고 돌려서 확인한다.** 고정 2개짜리 모의 말뭉치에
3번째를 게시해 — 결과가 안 움직이고, digest도 안 흔들리고, 새것은 "잉여"로
보고되는지. 반대로 고정된 원장을 지우거나 고치면 반드시 실패하는지.
분모 쪽도 같다 — 새 결과가 판정을 안 움직이는지, 그리고 규칙의 **양쪽 절반이
아직 무는지**.

`GRADING_SOURCE`가 사라지면(누가 "어차피 하나뿐인데" 하고 지우면) 실패하는
검사도 넣었다. 같은 자리에서 같은 방식으로 되돌아가는 걸 막기 위해서다.

같은 모양의 결함을 **하나 더** 찾아 고쳤다: 185-task 금액 상한 테스트가
`assert len(merged) == 1`로 유일성을 단정하고 있었다. #448의 2번과 같은
가정이며, 다음 재채점에서 똑같이 터졌을 것이다.

### 12.8 이번에 사지 않은 것

**새 유료 실행 0건.** 저장된 Smoke 산출물과 임시 모의 fixture로만 검증했다.
채점기 지문 입력(`core/**` · `step8_grade.py` · `schemas/` · requirements 폐포 ·
prompt template)은 **한 파일도 건드리지 않았다** — `git diff origin/main` 결과
0개. `check_grader_hash_freeze.py`에 이 PR의 실제 경로 전부를 넣어
`PASS: no grader-source file in this diff` (exit 0). 확인 시점 진행 중인 유료
채점도 0건이다. 값 없는 모델은 그대로 미등록이며 임의 요율을 넣지 않았다.

### 12.9 남은 한계

- **소급 적용은 안 된다.** `verify-published`는 **다음** 채점 실행부터 돈다.
  `94bb8fa`에 대한 증거는 위 12.4의 **로컬 실행 기록**이지 Actions 실행이 아니다.
  같은 스크립트·같은 검사·같은 commit이지만, 자동으로 남은 것은 아니다.
- **`_diagnostic` 게시의 집계 검사는 비어 있다.** 집계기는 `data/grades/`를
  **평면으로만** 훑어서 `data/grades/_diagnostic/<hash>/…`에 닿지 못한다.
  그래서 이번 검사는 "집계가 이 트리에서 성공한다"까지만 말하고 **그 파일에
  대해서는 아무 말도 하지 않는다.** 보고서에 그렇게 적히도록 문구를 고쳤다
  ("집계되지 않았고, 됐다고 주장하지도 않음"). 정상(비진단) 채점은 평면
  경로에 게시되므로 범위 안에 들어온다.
- **advisory다.** branch protection에 등록되기 전까지는 빨간 검사도 병합을
  막지 못한다. `check_grader_hash_freeze.py`와 같은 한계이고, 같은 이유로
  여기서 더 주장하지 않는다.
- §11.9의 미해결 항목(호출 수 증가 원인, 판정 4/38 이동 원인, 소리 계측
  미검증)은 **그대로 열려 있다.** 이번 작업은 그 원인들을 건드리지 않았다.

### 12.10 이 수정 자체가 같은 실수를 저질렀다 (그리고 그것을 고쳤다)

**있는 그대로 적는다.** PR #451이 `9126ee3`로 병합된 직후, `main`에 이런 실행
기록이 하나 생겼다.

```
workflowName: .github/workflows/grade-run.yml   ← 워크플로 "이름"이 아니라 "경로"
event       : push
conclusion  : failure
jobs        : 0            ← job이 하나도 없다
headSha     : 9126ee3ad941e38254c84d51adab736d931f3f30
```

job이 0개인 실패는 **워크플로 파일 자체를 GitHub이 읽지 못했다**는 뜻이다.
`gh run view`도 그렇게 말한다 — *"This run likely failed because of a workflow
file issue."* 병합 직전 네 개 commit(`5704cf8`·`1e06e45`·`3ede896`·`972f52a`)에는
이 기록이 없으므로, **내 변경으로 새로 생긴 것**이다. 그동안 채점 워크플로는
**실행 자체가 불가능**했다.

**원인은 한 줄이다.**

```yaml
jobs:
  grade:
    env:
      PUBLISHED_COMMITS_FILE: ${{ runner.temp }}/published_commits.txt   # ← 여기
```

GitHub 공식 문서의 컨텍스트 가용성 표에 따르면 `jobs.<id>.env`가 읽을 수 있는
것은 `github`·`needs`·`strategy`·`matrix`·`vars`·`secrets`·`inputs` **일곱
개뿐**이다. `runner`는 없다. runner가 아직 배정되기 전에 평가되는 자리이기
때문이다. 그리고 이 경우 **빈 문자열이 되는 게 아니라 파일 전체가 로드되지
않는다.**

**왜 테스트가 못 잡았나.** 이건 문법상 **완전히 올바른 YAML**이다. 그래서
`yaml.safe_load`는 아무 불평 없이 읽었고, 이 워크플로의 모양을 검사하는 기존
단언 251개도 전부 초록이었다. 파싱으로는 절대 못 잡는 종류다.

**고침.** job의 `env:`에서 빼고, runner를 읽어도 되는 **step**으로 옮겼다.

```yaml
- name: Name the file that records what this run publishes
  run: |
    echo "PUBLISHED_COMMITS_FILE=$RUNNER_TEMP/published_commits.txt" \
      >> "$GITHUB_ENV"
```

`grade` job의 맨 앞쪽(체크아웃보다도 앞)에 **조건 없이** 두었다. 뒤따르는 세
개의 push 기록 step보다 반드시 먼저 돈다.

**한 줄만 고치고 끝내지 않았다.** 같은 *종류*의 편집을 전부 막는 검사를
`tests/test_step8_grade.py`에 넣었다.

| 검사 | 대상 |
|---|---|
| `..._reads_a_context_github_refuses_to_provide_there` | 워크플로 **16개 전부**, job 31개의 job-level `env:`와 `if:` |
| rc7 테스트에 추가한 단언 | 이 이름을 **step이** 정하는가, **쓰기 전에** 정하는가 |

검사가 진짜로 무는지 확인했다. 문제의 줄을 **원래 모습 그대로 되돌려 놓고**
돌렸더니 두 테스트가 실패하며 파일·job·키·컨텍스트를 이름으로 지목했다.

```
grade-run.yml: jobs.grade.env.PUBLISHED_COMMITS_FILE reads `runner`
```

이름 짓는 step을 append보다 **뒤로** 옮겨서도 돌려 봤고, 그것도 실패한다.
확인 후 원상복구했다.

정규식을 짤 때 하마터면 놓칠 뻔한 함정도 하나 적어 둔다. `needs.validate-request
.outputs.…`처럼 job 이름에 하이픈이 있으면, 단순한 패턴은 하이픈에서 토큰이
끊겨 **`request`라는 없는 컨텍스트를 읽었다고 오탐**한다. 실제로 처음 판에서
오탐 4건이 났다. 정상 표현식 두 종류를 테스트에 **정탐으로 못 박아** 두었다.

그리고 `if:`는 `${{ }}` 없이도 쓸 수 있다(`if: inputs.dry_run == true`). 실제로
이 저장소 18개 중 **10개가 괄호 없는 형태**다. 괄호 안만 보는 검사였다면 그
10개를 통째로 놓쳤을 것이다. 두 형태를 모두 본다.

**이 항목을 남기는 이유.** §12 전체가 *"게시된 변경을 아무 검사도 보지 않았다"*는
문제를 닫는 작업인데, 그 수정 자체가 **정확히 같은 방식으로** 실패했다. 검사가
없는 자리에 새 코드를 넣으면 그 코드도 검사받지 못한다. 지우고 조용히 고치는
편이 보기에는 낫겠지만, 그러면 이 문서가 기록하려던 바로 그 실패 사례를 없애는
셈이 된다.
