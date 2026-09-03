# 319 · 발행된 인덱스가 아직 `$0`을 싣고 있다

> 발견 경위: [`PR3_COST_BUDGET.md`](./PR3_COST_BUDGET.md) §10.
> **화면에 보이는 결함이 아니다.** 발행물 안에 놓인 함정이다.

---

## 무엇이

`public/generated/grades-index.json`의 **19행 중 16행**이 이 값을 싣고 있다.

```json
"summary_v1": { "cost": { "estimated_cost_usd": 0 } }
```

같은 블록에 토큰은 **실제 값**이 들어 있다. 가장 큰 행은 입력 **130,092,056** ·
출력 **5,523,697** 토큰짜리 mini 실행이고, 그 옆에 `0`이 적혀 있다.
나머지 3행은 `null` 2 · `cost` 블록 없음 1이다.

---

## 왜

`scripts/aggregate-grades.mjs`가 legacy summary를 그대로 펼친다.

```js
summary_v1: {
  ...summary,          // <- 여기서 estimated_cost_usd: 0.0 이 그대로 실린다
  wow,
  ...
  // Only on a run that recorded something. Absent here is what the
  // dashboard reads as "no record" — never as $0.
  ...(costSummary ? { grading_cost: costSummary } : {}),
},
```

**주석이 적은 원칙과 두 줄 위의 코드가 어긋나 있다.** 새 영수증 경로(`grading_cost`)는
"기록이 없으면 아예 안 싣는다"를 지키는데, 그 위의 spread는 옛 payload가 들고 있던
`0.0`을 검사 없이 통과시킨다. 그 `0.0`은 영수증 체계보다 먼저 만들어진 schema 1.0/1.3
채점 파일에서 온 것이고, 당시엔 "가격을 못 매겼다"를 `0`으로 적었다.

---

## 지금 당장 위험하지는 않은 이유

| 확인 | 결과 |
|---|---|
| `src/`에서 `summary_v1.cost`를 읽는 곳 | **없음** |
| 금액을 그리는 함수 `src/lib/cost.ts:478` `summaryTotalCell` | schema 1.4의 `cost_summary`만 먹는다 |
| 인덱스 19행 중 `cost_summary`를 가진 행 | **0개** |

즉 **사용자에게 `$0.00`이 보이는 화면은 지금 없다.** 이 값은 발행된 JSON 안에
가만히 앉아 있다.

그래도 고쳐야 하는 이유는 하나다. 이 저장소의 규칙은
**"기록이 없는 것은 `0`이 아니라 없음"** 이고
(`core/execution_envelope_preflight.py`, `src/lib/cost.ts`의 `≥` 표기,
[`317`](./317-pricing-the-185-task-run.md) §2 전체가 그 규칙 위에 서 있다),
**발행물이 그 규칙을 어기고 있는 상태**다. 나중에 누가 `summary_v1.cost`를 읽는
화면을 하나 붙이면 그날 바로 `$0.00`이 뜬다.

---

## 고치는 방향

1. `aggregate-grades.mjs`에서 legacy `cost.estimated_cost_usd`를 **그대로 싣지 않는다.**
   `0`은 "미기록"으로 정규화(`null`)하거나, 필드를 아예 떨어뜨린다.
2. `null`과 `0`을 구분하지 못하는 경로가 또 있는지 aggregate 쪽 전수 확인.
3. 회귀 검사: 발행된 인덱스 어느 행에도 `estimated_cost_usd: 0`이 없어야 한다.
   변이 검사로 정규화를 되돌리면 죽는지 확인.

**주의 — 어느 것이 "진짜 0"인가.** 실제로 한 푼도 안 쓴 실행(모델 호출 0회)은
`0`이 정직한 값이다. 위 16행은 전부 토큰이 0이 아니므로 그 경우가 아니지만,
정규화 규칙은 "토큰이 있는데 금액이 0" 만 잡아야 한다. 무조건 `null`로 밀면
반대쪽 거짓말이 된다.

---

## 같은 종류의 결함이 바로 한 단계 아래에서 이미 고쳐졌다

`#403`(`80aa34c`)이 **같은 파일에서** 이걸 고쳤다 — 과제에 점수가 없을 때
`t.pct`를 `0`으로 읽던 자리다.

```js
- const pct = typeof t.pct === 'number' ? t.pct : 0;
+ if (!Number.isFinite(t.pct)) { return { num_grades: 0, scores: [], avg_score: null, ... }; }
+ const pct = t.pct;
```

커밋 메시지가 원칙을 그대로 적고 있다 — **"점수가 없는 행은 0점을 받은 행이
아니다."** 위의 `estimated_cost_usd: 0`은 **같은 문장의 금액 판**이고,
같은 함수 안에서 **아직 안 고쳐진 쪽**이다. 즉 이 항목은 새 주장이 아니라
이미 저장소가 받아들인 원칙의 남은 적용 지점이다.

---

## 왜 302 PR에서 안 고쳤나

- 화면에 보이는 결함이 아니라 급하지 않다.
- 고칠 자리가 `scripts/aggregate-grades.mjs`와 그 검사들이라 **302의 범위
  (backend 측정 + 문서)와 겹치지 않는다.**
- 프런트엔드 생성기 쪽은 지금 다른 작업이 물려 있어 한 PR에 섞으면 검토가 흐려진다.

---

## 고쳤다

`scripts/aggregate-grades.mjs`의 그 spread를 `projectLegacySummary(summary)`로
바꿨다. 데이터는 한 글자도 건드리지 않았다 — `data/grades/`의 payload 16개는
지금도 `0.0`을 그대로 들고 있다. 달라진 것은 **생성기가 그 값을 다시 발행하느냐**다.

### 규칙을 어디서 가져왔나

새 규칙을 만들지 않았다. `core/cost_receipts.py` 맨 위에 이미 적혀 있는 문장을
그대로 옮겼다 — *"usage 블록이 없다는 것은 공짜였다는 뜻이 아니라, 아무도 얼마인지
말할 수 없다는 뜻이다. 진짜 `$0`은 공급자에 한 번도 닿지 않은 경로뿐이다."*
영수증 경로는 `scripts/cost-receipt.mjs`의 `measuredAmount`가 이미 이 문장을
지키고 있었고, 이 spread가 payload의 `0`이 그 검사를 우회할 수 있던 **마지막
자리**였다.

### 위 "주의"를 그대로 구현했다

무조건 `null`로 밀지 않는다. **블록 자신에게** 물어본다 — 이 실행은 누군가에게
닿은 기록을 남겼는가? `total_judge_calls` · `total_input_tokens` ·
`total_output_tokens` 셋이 그 기록이고, **셋이 모두 있고 모두 `0`일 때만** `0`이
살아남는다.

한 걸음 더 닫았다. **없는 카운터는 `0`인 카운터가 아니다.** 카운터가 아예 없는
블록은 "공짜로 돌았다"처럼 보이면서 그것을 가장 증명하지 못하는 모양이므로,
정규화하는 쪽으로 fail closed 한다. 금액에 적용한 논리를 면제 근거 자체에 한 번 더
적용한 것이다.

### `null`이지 삭제가 아니다

이 저장소는 이미 그 함정에 한 번 빠졌다. `undefined !== null`이 참이라
`!== null`로 막아 둔 화면이 `undefined.toFixed`에 닿아 실험 페이지를 통째로
내린다(`scripts/cost-receipt.mjs:711-716`). 지금 쓰는 writer도 값을 못 매긴 실행에
`null`을 적으므로(`core/cost_projection.py:810`), 두 시대가 "없음"을 같은 말로
적게 된다.

### 같은 spread의 두 번째 구멍

`...summary`는 payload의 **run 단위** `summary.grading_cost`도 함께 실어 나른다.
아래 줄이 그것을 덮어쓰는 것은 `costSummary`가 있을 때뿐이고,
`summarizeCostReceipts`는 영수증을 든 과제가 하나도 없으면 `null`을 돌려준다 —
즉 **payload의 총액을 검증 없이 발행할 수 있는 경로**가 남아 있었다. 지금 발행되는
19개는 전부 schema 1.0/1.1/1.3이라 실제로 새는 파일은 없지만, 같은 문장의 나머지
반쪽이고 이 파일의 절 머리글이 *"run summary는 여기서 행에서 유도한다, payload에서
베끼지 않는다"* 라고 이미 금지하고 있다. 그래서 함께 막았다.

### 잰 것

| | |
|---|---|
| `grades-index.json` 필드 차이 | **16개, 전부 `estimated_cost_usd: 0 → null`** |
| 나머지 생성 파일 7개 | `_generated` 타임스탬프 1개씩 |
| 전체 차이 | **23개. 그 밖에 움직인 값 0** |
| 고친 뒤 분포 | `null` 18 · 블록 없음 1 · **숫자 금액 0행** |
| cost 블록의 비금액 필드(토큰·호출·지연) | **0개 이동** |
| 키 순서 | 보존 |
| 디스크의 payload | **16개 그대로 `0.0`** |
| 새 테스트 | **14개** (`scripts/__tests__/a-zero-beside-real-tokens-is-not-a-price.test.mjs`) |
| 심은 결함 | **12개 중 12개 검출**, 빠져나간 것 0 |
| scripts 전체 | 401 → **415개 통과** |
| 모델 호출 | **0회 · $0** |

전수 확인(위 2번)도 했다. `scripts/*.mjs`에서 summary·cost를 펼치는 자리는 네
곳이고 셋은 이미 영수증 경로다. `data/grades/**`의 모든 키를 깊이 무관하게 세어
`projectCostSummary`/`projectCostReceipt`를 거치지 않는 금액 키가
`.summary.cost.estimated_cost_usd` 하나뿐임을 확인했다.
`reports-index.json`의 금액 3개는 전부 `status: complete`이고
`known_cost_usd`와 일치한다 — 그 경로는 깨끗하다.
