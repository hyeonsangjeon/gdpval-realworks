# 소리 판독 비용이 `null`인 이유 — 원인 분해와 재현 (2026-09-07)

세션 A. 저장된 자료와 모의 응답만 사용했다. **새 유료 호출 없음.** 새 계정 없음,
새 Azure 권한 없음.

관련 명세: [`TASK_PER_TASK_COST_RECEIPTS.md`](TASK_PER_TASK_COST_RECEIPTS.md)
§4.1–4.2, §5.3, §5.4.1, §5.5–5.6, §7.1

---

## 0. 한 줄로

원인은 하나가 아니라 **셋**이었다. 둘은 이번에 닫혔고, 하나는 우리가 닫을 수 없다.
그래서 금액은 여전히 `null`이지만, **이제는 이유가 달라졌다** — 예전에는 아무도
값을 안 넣어서였고, 지금은 코드가 넣기를 거부해서다.

| # | 원인 | 상태 |
|---|------|------|
| (a) | Azure가 이 모델의 요율을 고지하지 않는다 | **열려 있음 — 우리 밖의 일** |
| (b) | 소리 토큰이 총량 안인지 밖인지 몰랐다 | **닫힘 — 저장 자료로 측정** |
| (c) | 소리 토큰이 기록되지도, 거부되지도 않았다 | **닫힘 — 이번 변경** |

---

## 1. 재현: 지금 커밋된 원장이 실제로 어떤 상태인가

`data/grades/**` 의 커밋된 `*.cost_ledger.jsonl` 32개를 읽었다. 아래 수치는 전부
이 저장소에 커밋된 파일만으로 다시 낸 것이다 (재현 스크립트는 §6 참조).

```
원장 파일                                 32
전체 행                               68,610      settled 68,587 / reserved 23
```

모델별 행 수는 **어느 이름으로 세느냐에 따라 다르다.** 둘 다 적는다.

| 모델 | 요청한 이름으로 | 응답이 보고한 이름으로 |
|------|---------------|---------------------|
| `azure:gpt-5.6-sol` | 68,350 | 68,338 |
| `azure:gpt-audio-1.5` | **176** | **165** |
| `azure:gpt-5.4` | 84 | 84 |
| (이름 없음) | — | 23 |

차이 23행은 **응답을 못 받아 정산되지 않은 예약**이다. 예약 시점에는 요청한 이름만
있고 응답이 보고한 이름이 아직 없다. 가격표는 §4의 규칙대로 **응답이 보고한 이름**으로
찾으므로, 값 매기기에 쓰이는 수는 오른쪽 열이다.

소리 모델 176행만 보면:

```
단계          perception 176 (전부)
상태          settled 165 / reserved 11
사유          price_missing 165 (미정산 11은 사유가 붙기 전)
금액이 붙은 행                             0
소리 몫을 담고 있는 행                      0   ← (c)의 증거
입력 합계 72,634 · 출력 12,038 · 캐시 0 · 추론 0
```

11개 `reserved`는 정산되지 않은 예약이다. 명세 §6.2대로 사라지지 않고 남아
`call_reachability_unknown`으로 그 작업 영수증을 `partial`로 만든다.

**소리 몫을 담은 행은 0개다.** 이 176개는 계측이 소리를 볼 수 있게 되기 전에
쓰였다. 그래서 이 행들의 소리 몫은 원장에서 복원할 수 없다.

### 1.1 앞선 초안의 숫자 여섯 개를 정정한다

이 문서 초안과 PR 본문 초안은 68,616행 / 정산 68,593 / 일치 90 / 지문 네 종류라고
적었고, `azure:gpt-5.4-2026-03-05` 6행을 목록에 넣었다. **커밋된 나무에는 그런 행이
없다.** 초안의 집계가 저장소에 없는 파일까지 훑은 것이다. 위 표는 커밋된 32개
파일만으로 다시 낸 값이며, 누구든 §6의 스크립트로 같은 수를 얻는다.

**결론은 하나도 바뀌지 않는다** — 달라진 행 0개, 뒤집힌 행 0개, 소리 값 못 매김,
지배적 원인은 여전히 `gpt-5.6-sol`이다. 바뀐 것은 자릿수뿐이지만, 재현되지 않는
숫자를 적어 두는 것 자체가 이 문서가 막으려는 일이므로 고쳐 적는다.


## 2. 원인 (a) — 요율이 없다 · 열려 있음

공개(비로그인) Azure Retail Prices API에 다섯 가지로 물었다. 질의 원문과 결과는
`batch-runner/experiments/execution_envelope/model_price_table.json`의
`models_deliberately_not_priced["azure:gpt-audio-1.5"].re_verified`에 그대로 있다.

| 질의 | 결과 |
|------|------|
| `contains(meterName,'audio'/'Audio'/'AUDIO')` | 119개 미터, 8개 제품 — **gpt-audio / audio-1.5 없음** |
| `contains(meterName,'1.5')` | 682행, 37쌍 — 소리 관련 없음 |
| `productName eq 'Azure OpenAI GPT5'` | **8,321행 / 9페이지 / 410개 미터 — 소리 언급 없음** |
| `contains(productName,'Audio')` | 6행, 전부 'Audio Streaming' (다른 서비스) |
| skuName / armSkuName | 109행, 7개 SKU, 전부 gpt4o realtime |

2026-08-30에도 같은 질의를 했고 그때 `Azure OpenAI GPT5`는 7,235행 8페이지였다.
**주변 제품이 8일 만에 1,086행 늘어나는 동안에도 이 모델의 미터는 계속 없다.**
누락이라기보다 상태로 읽는 것이 맞다.

이것은 우리가 코드로 닫을 수 있는 문제가 아니다. 그래서:

- 비슷한 이름의 모델 요율을 빌려오지 않았다.
- 직판 가격을 Azure 가격으로 간주하지 않았다.
- `0`을 넣지 않았다 (원칙 P1 — `0`은 "무료였다"는 주장이다).

**해결에 필요한 것**: 소리 **입력**과 소리 **출력** 두 개의 요율. 하나로 뭉친
값은 §5.3의 세 몫 계산에 넣을 수 없다. 출처는 실제 사업자·응답 모델·지역/배포
요율 조건이 맞는 공식 고지여야 한다.

## 3. 원인 (b) — 포함 관계 · 닫힘

소리 토큰이 `input_tokens` **안**에 있는지 **옆**에 있는지에 따라 계산이 완전히
달라진다. 짐작하지 않고, B의 331건 진단이 남긴 60개 호출로 측정했다.

| 검사 | `input` 그대로 | `input - audio` |
|------|---------------|-----------------|
| 소리 길이와의 상관 | +0.8488 | **+0.0134** |
| 프롬프트 글자수와의 상관 | +0.4589 | **+0.9224** |
| 글자당 토큰 (평균 ± 표준편차) | 0.28787 ± 0.00276 | **0.25976 ± 0.00093** |

소리를 빼면 남은 것이 소리 길이와 **무관해지고** 프롬프트 길이와 거의 **일치**한다.
남은 것이 글이라는 뜻이고, 곧 소리는 안에 있었다는 뜻이다. 밖에 있었다면 두 열은
반대로 움직였을 것이다.

곁가지 확인: 소리 토큰 자체는 길이와 +0.9918, 초당 9.8597개(사전 등록값 10.00과
사실상 같음), 60개 전부에서 `audio_tokens == audio_tokens_billed`.

**규모**: 입력 18,924 중 소리 1,848 — **9.8%**. 소리 수만 곱한 값은 총액이 아니라
총액의 10분의 1이다. 그래서 소리 몫만으로 `complete`를 만들지 않는다.

## 4. 원인 (c) — 기록도 거부도 없었다 · 닫힘

이번 변경 전 상태:

1. `extract_usage`가 응답의 `audio_tokens`를 **읽지 않고 버렸다**. 그래서 176개
   행에 소리 몫이 없다.
2. `CallUsage`·원장 테이블에 담을 칸이 **없었다**.
3. `price_call`은 소리를 **몰랐다**. 그래서 누군가 `azure:gpt-audio-1.5`에 평범한
   글 요율 항목을 하나 추가하는 순간, 입력 전체를 글 요율로 곱하고 영수증을
   `complete`로 뒤집으며 **자신 있게 틀린 숫자**를 냈을 것이다.

3번이 핵심이다. 오늘의 `partial`은 **맞지만 이유가 틀렸다** — 코드가 거부해서가
아니라 아무도 표에 줄을 안 넣어서 맞은 것이었다. 이제는 코드가 거부한다.

닫은 방법 (전부 세션 A 파일):

- `extract_usage` — `prompt_tokens_details` / `input_tokens_details` /
  `completion_tokens_details` / `output_tokens_details`의 `audio_tokens`를 읽는다.
- `CallUsage` — `audio_input_tokens`, `audio_output_tokens` 추가.
- 원장 SQLite — 같은 이름의 열 두 개. 내보내기·가져오기도 함께 다닌다.
- `price_call` — §5.3의 세 몫 계산과 §5.3.1의 거부 규칙.
- 가격표 — `audio_billed_as` 필드와 로더 검증 (§4.1).

**게시되는 영수증은 바뀌지 않았다.** `grade.schema.json`의 `costUsage`는
`additionalProperties: false`에 칸이 네 개다. 소리 몫은 영수증이 아니라 원장에
산다 (§7.1). 새 `missing_reason`도 만들지 않았다 — 그 열거값도 닫혀 있고, 위
상황은 기존 `price_missing`·`usage_partial`로 정확히 읽힌다.

## 5. 연결은 이미 되어 있었다

소리 판독기는 세션 B 소유(`core/perception/audio.py`)라 손댈 수 없다. 그런데
**손댈 필요가 없었다.**

원장에 쓰는 주체는 판독기가 아니라 `core/grader.py`가 씌우는 계측 래퍼다:

```python
self._perception_client = cost_recorder.meter(
    client, provider="azure", stage=STAGE_PERCEPTION
)
```

래퍼가 호출 전 `reserve`, 응답 후 `extract_usage(response)`로 `settle`한다.
`meter`·`extract_usage`·`CallUsage`·원장 스키마는 전부 세션 A 파일이므로, A 쪽만
고쳐도 소리 몫이 원장까지 도달한다.

짐작이 아니라 확인했다 — `tests/test_speech_is_not_charged_at_the_price_of_prose.py`
「the connection」절이 실제 `meter()` 래퍼로 모의 소리 응답을 통과시켜 다음을 본다.

- 원장 행에 `audio_input_tokens: 30`이 남는다
- 그 행이 글 요율로 값 매겨지지 않고 `price_missing` + `partial`이 된다
- 같은 작업의 **문제 풀이** 영수증은 건드려지지 않는다 (두 원장 분리)
- 소리가 없는 호출은 같은 래퍼·같은 표로 **여전히 값이 매겨진다**

`core/perception/audio.py`가 부르는 `read_reported_usage`는 B가 보고서용으로 따로
굴리는 누계이고 원장에 들어가지 않는다. 그쪽은 지금도 소리 몫을 보지 않지만, 보지
않아도 원장은 정확하다. B가 화면에 소리 몫을 보이고 싶어지면 그때
`ReportedUsage`에 칸을 더하는 것이 A 쪽 계약 변경이다. 그전까지 없는 층을 미리
만들지 않는다.

## 6. 재산정: 무엇이 가능하고 무엇이 불가능한가

커밋된 원장의 **정산된 68,587행 전부**를 **오늘 표**로 다시 계산해 저장된 금액과
비교했다.

```
재계산 == 저장값                84      (gpt-5.4 84행 전부)
다름                             0
저장값 있는데 재계산 안 됨        0
저장값 없는데 재계산됨            0
둘 다 없음 (값 매길 수 없음)  68,503
```

84 + 68,503 = 68,587. **한 행도 달라지지 않았다.** 숫자가 있던 행은 그대로고, 없던
행은 그대로 없다. 가격표 지문이 움직인 이유는 요율이 아니라 문서라는 §4.2의 서술이
여기서 확인된다.

값 매길 수 없는 68,503행의 내역:

| 모델 | 행 | 왜 |
|------|-----|-----|
| `azure:gpt-5.6-sol` | 68,338 | 요율 미등록 (표에 사유 기재됨) |
| `azure:gpt-audio-1.5` | 165 | 요율 미등록 — 이 문서의 주제 |

**따로 짚어 둘 것**: 채점 비용이 `null`인 지배적 원인은 소리가 아니라
`gpt-5.6-sol`이다 — 68,338행 대 165행이다. 소리 쪽을 닫아도 채점 총액은 여전히
`null`이며, 그것을 풀려면 별도로 `gpt-5.6-sol` 요율이 필요하다. 그쪽도 임의
숫자를 넣지 않았다.

### 176개 소리 행의 재산정은 불가능하다

두 가지 독립된 이유 때문이며, 둘 중 하나만으로도 불가능하다.

1. **요율이 없다** (원인 a). 곱할 수가 없다.
2. **소리 몫이 그 행에 없다** (원인 c의 과거분). 요율이 생기더라도 세 몫으로
   가를 근거가 그 행 안에 없다.

오늘 측정한 9.8%를 곱해 소급 복원하는 방법은 **쓰지 않는다.** 그것은 이미 돈이 나간
호출에 대해 이 저장소가 지어낸 숫자다. **기록이 없으면 복원하지 않는다.**

앞으로 나가는 호출은 계측이 소리 몫을 남기므로, 요율이 확보되는 시점부터는 요율
하나만 있으면 계산된다. 즉 **원인 (c)를 닫은 효과는 소급이 아니라 향후분에 있다.**

### 어떤 숫자도 "Azure 청구서 실청구액"이 아니다

이 문서에 나오는 모든 금액은 **커밋된 원장 + 커밋된 가격표로 재계산한 값**이다.
실제 청구서를 조회한 적이 없고 (로컬 az 테넌트는 워크플로 테넌트와 다르다),
조회했다고 표시하지도 않는다.

### 재현 방법

위 수치는 전부 이 저장소 안의 것만으로 다시 낼 수 있다. `batch-runner/`에서:

```python
import json
from pathlib import Path
from core.cost_receipts import CallUsage, load_receipt_price_table, price_call

root = Path(".").resolve().parent
table = load_receipt_price_table(
    root / "batch-runner/experiments/execution_envelope/model_price_table.json"
)
for path in sorted(root.glob("data/grades/**/*.cost_ledger.jsonl")):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("state") != "settled":
            continue
        usage = CallUsage(
            input_tokens=row.get("input_tokens"),
            cached_input_tokens=row.get("cached_input_tokens"),
            output_tokens=row.get("output_tokens"),
            reasoning_tokens=row.get("reasoning_tokens"),
            audio_input_tokens=row.get("audio_input_tokens"),
            audio_output_tokens=row.get("audio_output_tokens"),
        )
        again = price_call(
            table.lookup(row.get("provider") or "", row.get("resolved_model") or ""),
            usage,
        ).cost_usd
        # 저장값 row["model_cost_usd"] 와 비교
```

두 가지만 주의한다. `price_call`은 **가격을 먼저, 사용량을 나중에** 받고, 조회
키는 요청한 이름이 아니라 **응답이 보고한 이름**(`resolved_model`)이다. 요청한
이름으로 조회하면 정산되지 않은 23행이 조용히 다른 모델로 세어지고, 그것이 §1.1의
초안 숫자가 어긋난 방향이다.


## 7. 이번에 고정한 것

| 항목 | 값 |
|------|-----|
| 가격표 지문 | `a2d60e1c96390313f41b4a249a7dea3606b62522858902f49f152da30941d2d4` |
| 직전 지문 | `fd09d28c7247e9d40f1f9218d01aa961d6545d377cdaccf51d0857ea6e43c741` |
| 검토일 | 2026-09-07 |
| 요율 변경 | **없음** — `providers` 네 항목 바이트 동일 |

기존에 고정된 영수증은 덮어쓰지 않았다. 근거는 §4.2에 있다 — 요약하면 지문은
"이 행을 값 매긴 표"의 기록이지 "지금 파일이 이 내용"이라는 주장이 아니고,
`build_receipt`가 각 행이 스스로 적은 표를 먼저 읽으며, 직전 지문을 고정한 커밋된
산출물은 하나도 없다.

## 8. 남은 것

| # | 무엇 | 누구 |
|---|------|------|
| 1 | `gpt-audio-1.5` 소리 입력·출력 두 요율의 공식 출처 | 저장소 밖 (Azure 고지 대기) |
| 2 | `gpt-5.6-sol` 요율 — 채점 총액의 지배적 원인 | 저장소 밖 |
| 3 | 소리와 캐시가 겹칠 때의 규칙 — 고지가 없어 `usage_partial`로 열어 둠 (§5.3.1) | 고지 나오면 |
| 4 | 소리 몫을 화면·보고서에 보이려면 `ReportedUsage` 확장 | A(계약) → B(표시), 필요해질 때 |
| 5 | **이 변경은 채점기 원본 지문을 움직인다.** 다음 유료 실행 전에 새 지문으로 smoke를 한 번 돌려야 한다 | 통합 담당 (§8.1) |

1·2번이 해결되기 전까지 금액은 `null`이고 상태는 `partial`이다. 그것이 이 설계가
의도한 동작이다.

### 8.1 채점기 지문이 움직인다

`core/cost_receipts.py`와 `core/cost_metering.py`는 `_HASHED_TREES` 아래에 있어서,
고친 이상 `grader_source_hash`가 바뀐다. 저장소 자체 검사로 확인했다.

```
$ python scripts/check_grader_hash_freeze.py \
    --changed-paths <바뀐 경로 JSON> --runs <진행 중 실행 JSON>
PASS: no paid grade run in flight

This diff does move the grader source hash. That is fine right now, but it
means the next paid run has to be preceded by a fresh smoke at the new
fingerprint.
  - batch-runner/core/cost_metering.py
  - batch-runner/core/cost_receipts.py
```

병합 시점에 진행 중인 유료 채점이 없음을 먼저 확인했다 —
`gh run list --workflow=grade-run.yml`의 최근 100건과 저장소 전체 최근 60건 모두
`completed`이고, 가장 최근 채점은 2026-09-02다. **shard가 도는 중에 병합하면
step9가 열한 개 지문 불일치로 거절하는데, 그 거절은 돈이 다 나간 뒤에 온다.**
그래서 순서가 이것이다: 진행 중 없음 확인 → 병합 → 다음 유료 실행 전 smoke 1회.

### 8.2 이번에 통과시킨 검사

| 검사 | 결과 |
|------|------|
| 이 변경의 새 테스트 (`test_speech_is_not_charged_at_the_price_of_prose.py`) | **41 passed** (1.89초) |
| 전체 백엔드 스위트 (로컬) | **8431 passed, 8 skipped, 45 deselected** (17분 13초, exit 0) |
| 채점기 지문 동결 (`check_grader_hash_freeze.py`) | **PASS** — 진행 중 유료 실행 없음 |
| 실행 환경 사전검사 (`check_execution_envelope_advance_check.py`) | 로컬 exit 1 — **이 변경과 무관** |

두 번째 줄은 오해하기 쉬우니 적어 둔다. 이 상자에는 Azure 환경 변수 다섯 개가
없어서(로컬 az 테넌트가 워크플로 테넌트와 다르다) 스크립트가 `azure_code_interpreter`를
`evidence_insufficient`로 두고 1로 끝난다. **`origin/main`을 그대로 꺼내 같은
스크립트를 돌린 결과가 바이트 단위로 동일했다** — 즉 이 exit 1은 원래 있던
로컬 환경 사정이지 이 변경이 만든 것이 아니다. CI는 그 변수들을 넣어 준다.

파일 무결성 부분은 로컬에서도 통과한다 — 세 실행 자리 전부 "3 of 3 input file(s)
read off this machine, compared in full, and agreed". 사전검사가 이미
`gpt-audio-1.5`에 대해 "no published price was found … it is not zero"라고
경고하고 있는데, 이 문서의 결론과 같은 말이다.

