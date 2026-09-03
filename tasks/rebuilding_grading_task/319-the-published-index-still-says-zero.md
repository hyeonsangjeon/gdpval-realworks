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
