# PR3_REPEAT_VARIATION — 같은 지문인데 판정이 뒤집힌다, 얼마나

> 사전등록: [`315-repeat-variation-prereg.md`](../../../tasks/rebuilding_grading_task/315-repeat-variation-prereg.md)
> 앞 문서: [`PR3_VARIANCE.md`](../../../tasks/rebuilding_grading_task/PR3_VARIANCE.md)
> 이 분석은 이미 있는 채점 결과 세 벌만 읽는다. **모델 호출 0회, 채점 비용 0원.**

## 한 문장으로

**전체 평균은 다시 채점해도 1pp 안에서 그대로다. 항목 하나하나의 판정은 스무 번에
한 번꼴로 뒤집힌다.** 둘 다 사실이고, 둘은 같은 이야기가 아니다.

## 이 문서가 답하는 질문

발표된 점수 하나에는 서로 다른 두 가지가 섞여 있다.

| | 무엇인가 | 다시 재면 |
|---|---|---|
| **과제 난이도** | 30개 과제로 어떤 것들이 뽑혔는가 | 다른 과제를 뽑으면 달라진다 |
| **채점기 변덕** | 같은 답안을 두 번째 볼 때 채점기가 같은 말을 하는가 | 같은 과제라도 달라진다 |

`PR3_VARIANCE.md`의 관문은 이 둘을 나누지 않았다. 과제를 다시 뽑으면 7.32pp,
실행을 다시 뽑으면 0.86pp가 나오는데, 관문은 어느 쪽도 따로 보고하지 않았다.
사전등록 §2가 적은 대로 **"관문을 통과했다는 사실은 반복 채점이 안정적이라는
증거가 아니다."**

그래서 이 문서는 처음부터 둘째 것만 겨냥한다. 방법은 **짝짓기**다. 같은 과제의
1회차 점수와 2회차 점수를 함께 놓고 빼면, 그 과제가 어려웠는지 쉬웠는지는 뺄셈
안에서 사라지고 **두 채점 사이에 움직인 것만 남는다.**

## 사전등록과 달라진 점 — 하나

사전등록 §14는 이 보고서를 `tasks/rebuilding_grading_task/PR3_REPEAT_VARIATION.md`에
두라고 적었다. **이 문서는 `data/grades/_validation/`에 있다.** `tasks/**`는
`.gitignore`가 닫아 둔 경로이고 그 안의 기존 문서들은 규칙보다 먼저 있었기 때문에
남아 있는 것이지, 새 파일을 그리로 넣으라는 뜻이 아니다. `_validation/`에는 이미
같은 성격의 검증 문서 여섯 개가 있다. 분석 내용은 §14 그대로다.

## 세 실행이 정말 "같은 실행의 반복"인가

이 측정의 전제 전부가 여기에 걸려 있다. 분석 도구는 지문 **16개**를 두 번 확인한다
— 세 실행이 서로 같은가, 그리고 그 값이 사전등록이 적어 둔 값과 같은가. 하나라도
다르면 숫자를 내지 않고 멈춘다. 서로만 같으면 **다른 코퍼스를 세 번 돌린 것도
통과**하기 때문에 둘 다 필요하다.

| 지문 | 값 |
|---|---|
| 과제 목록 해시 | `82d14ac9…e7e8b` (30개) |
| 채점기 소스 해시 | `c33d9d55…6ff4e` |
| 채점 설정 | `gold_ceiling_30_v2_sol_max` / `d1bfc8217c9981d2` |
| 모델·배포 | `gpt-5.6-sol` / `gpt-5.6-sol` |
| API 버전 | `2025-04-01-preview` |
| 추론 강도·온도·씨앗 | `max` · `0` · `42` |
| 판정 프롬프트 | `prompts/grader_judge.md` v2.2 |
| 채점표 리비전 | `11e7900c…98fbf` |
| 렌더러 | LibreOffice 24.2.7.2 420(Build:2), pymupdf 1.28.2 |
| 정답 리비전 | `11e7900c…98fbf` |
| 페이로드 스키마 | `1.3` |

**얼리지 않은 것 하나.** `azure_ai_routes`는 한 실행 안에서도 값이 하나가 아니다
(`step9_merge_shards.py`가 합집합으로 병합하는 이유가 그것이다). 얼리면 1단계가
채택한 실행이 스스로를 거부한다. 그래서 **보고만 하고 관문에는 넣지 않았다.**

**스키마를 오늘 값이 아니라 `1.3`으로 고정한 이유.** `step8_grade.py`는 그 뒤
`1.4`로 옮겨 갔다. 오늘 값에 고정하면 이 세 파일이 스스로를 거부한다.

**같은 파일을 두 번 넣는 사고.** 여기서 가장 위험한 실수다. 모든 차이가 정확히
0으로 나오고, 0은 모든 관문을 여유 있게 통과하며, 보고서는 **아무것도 비교하지
않은 채 "완벽하게 안정적"이라고 발표한다.** 그래서 파일 해시 세 개와 `graded_at`
세 개가 모두 달라야 하고, 겹치면 경고가 아니라 오류다.

## 분모가 움직인다 — 백분율을 그냥 빼면 안 되는 이유

채점 항목 1,433개 중 **3개**가 세 실행 중 어느 하나에서 `judge_error`로 빠졌다.
빠진 항목은 분자에서만 빠지는 게 아니라 **만점(분모)에서도 빠진다.**

가장 또렷한 자리가 과제 `a328feea`다. 같은 18.6점이

- 만점 22점 위에서는 **84.55%**
- 만점 24점 위에서는 **77.50%**

즉 **채점기가 답을 못 낸 실행이 더 높은 점수를 받는다.** 그래서 이 문서는 두 기준을
따로 낸다.

| 기준 | 무엇을 재는가 |
|---|---|
| **공통분모 기준 (주)** | 세 실행 모두에서 점수가 있는 1,430개 항목만으로 다시 계산. 차이가 오직 채점기 때문인 유일한 기준 |
| **발표값 기준 (부)** | 파일에 적힌 `pct` 그대로. 사람들이 실제로 인용하는 숫자 |

만점이 움직인 과제는 `43dc9778`(121/121/119), `a328feea`(22/24/24),
`17111c03`(60/61/60) 셋이다. **분모 이동은 흡수하지 않고 별도 지표로 보고한다.**
조용히 보정하면, 이 문서가 지적하려고 쓰인 잘못을 이 문서가 저지르는 셈이 된다.

## 결과

<!-- generated: python batch-runner/scripts/analyze_repeat_variation.py data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_c33d9d55703fbf5d__v2.2.json data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/_repeats/run-002/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_c33d9d55703fbf5d__v2.2.json data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/_repeats/run-003/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_c33d9d55703fbf5d__v2.2.json -->
```text
repeat variation - the same answers, graded three times
==============================================================

  run-001  2026-08-28T18:41:32Z  final  sha256 ccdc43ec4fdeee31
  run-002  2026-08-28T22:38:04Z  final  sha256 3fdc899df73e0cf0
  run-003  2026-08-29T01:22:18Z  final  sha256 999bec6cc653ae14

  resamples 10000   seed 20260901   unit task   percentile 2.5/97.5

moving denominator (section 5)
  shared items 1433   common denominator 1430   dropped 3
  judge_error 4   score_excluded 4   disagreeing 0
  total_max moved  43dc9778  121 / 121 / 119
  total_max moved  a328feea  22 / 24 / 24
  total_max moved  17111c03  60 / 61 / 60

corpus mean, common denominator (primary)
  run-001  mean 83.1275%  median 84.6145%  stdev 10.5381
  run-002  mean 83.6129%  median 85.2340%  stdev 10.6954
  run-003  mean 83.5383%  median 85.1568%  stdev 10.6619
  spread across runs 0.4854pp

corpus mean, as published (secondary)
  run-001  mean 82.8733%  median 84.6150%  stdev 10.2996
  run-002  mean 83.0727%  median 85.2300%  stdev 10.4591
  run-003  mean 83.2457%  median 84.8850%  stdev 10.3872
  spread across runs 0.3723pp

per-task movement, common denominator (metric 1)
  run-001 vs run-002  signed -0.4854pp  absolute 1.3546pp  max 5.6964pp
            corpus mean shift 95% CI [-1.1597, +0.1859]  half-width 0.6728pp
  run-001 vs run-003  signed -0.4107pp  absolute 1.0476pp  max 3.9535pp
            corpus mean shift 95% CI [-0.8997, +0.0481]  half-width 0.4739pp
  run-002 vs run-003  signed +0.0746pp  absolute 1.2690pp  max 6.2791pp
            corpus mean shift 95% CI [-0.6911, +0.8323]  half-width 0.7617pp
  all pairs  absolute mean 1.2237pp  median 0.7545pp  max 4.1860pp

per-task movement, as published (metric 1, secondary)
  run-001 vs run-002  signed -0.1993pp  absolute 1.6173pp  max 7.0500pp  half-width 0.8407pp
  run-001 vs run-003  signed -0.3723pp  absolute 1.0183pp  max 3.9600pp  half-width 0.4697pp
  run-002 vs run-003  signed -0.1730pp  absolute 1.5003pp  max 6.8800pp  half-width 0.8894pp

result changed on a second grading (metric 5), 4299 item pairs
  verdict       204 pairs  4.7453%  (66 / 65 / 73)
                95% CI [3.8208, 5.7446]  width 1.9238pp
  score outcome 450 pairs  10.4676%  (153 / 144 / 153)
                95% CI [8.2527, 12.7323]  width 4.4796pp
  adjacent moves 175   two-step pass/fail moves 23   same verdict, moved score 246
  transition  fail->judge_error            1
  transition  fail->partial                51
  transition  fail->pass                   10
  transition  judge_error->fail            2
  transition  judge_error->partial         1
  transition  partial->fail                35
  transition  partial->pass                46
  transition  pass->fail                   13
  transition  pass->judge_error            2
  transition  pass->partial                43

why the unit is the task and not the item (section 6)
  task cluster   [3.8208, 5.7446]  width 1.9238pp   OFFICIAL
  naive item     [4.1172, 5.3966]  width 1.2794pp   not used
  the naive interval is 1.5037x narrower than the one this analysis reports
  the naive lower endpoint can only land on multiples of 0.0233pp, and the exact binomial puts the 2.5th percentile between
    176 of 4299 = 4.0940%  P(X <= k) = 0.02241
    177 of 4299 = 4.1172%  P(X <= k) = 0.02672

what was actually observed (metric 3, section 9)
  pass 3175   partial 585   fail 535   judge_error 4
  judge_error rate 0.0930%
  refusal        not in this schema and not observed - absent, not measured
  tool failure   no field exists - not measured. The zero end of the read census was offered as a proxy and is not one: see never_read
  read_deliverable per item  0x 92   1x 2855   2x 516   3x 822   4x 8   5x 2   6x 4
    of the 92 that never called it: 92 rendered it and looked, 0 used some other tool, 0 reached the file no way at all
    and they were routed  visual 92
  routing modality  formatting 207   mixed 3   text 3858   visual 231

cost and latency per run (metric 6)
  run-001  judge calls 3735  in 27565287  out 1430055  cached 13109489
            latency 25545.5s   routes grader/direct-v1
            cost unregistered - gpt-5.6-sol, gpt-audio-1.5 is not in the price table
  run-002  judge calls 3738  in 26955352  out 1435506  cached 12712485
            latency 24092.7s   routes grader/direct-v1
            cost unregistered - gpt-5.6-sol, gpt-audio-1.5 is not in the price table
  run-003  judge calls 3766  in 27532595  out 1427396  cached 13003884
            latency 23733.0s   routes grader/direct-v1
            cost unregistered - gpt-5.6-sol, gpt-audio-1.5 is not in the price table

the target (section 8)
  worst half-width 0.8894pp   target <= 1.0pp   MET
  pair difference stdev worst case 2.1448pp   runs required 3   held 3

VERDICT  MET
```

## 이 숫자들이 무슨 뜻인가

### 1. 평균은 안 움직인다

세 실행의 코퍼스 평균은 **82.87% · 83.07% · 83.25%**, 가장 먼 두 값의 차이가
**0.37pp**다. 다시 채점했을 때 평균이 얼마나 움직이는지에 붙는 95% 구간은 세 짝
모두 **반폭 0.9pp 이하**이고, **여섯 구간이 전부 0을 품는다** — 어느 실행이
일관되게 후하다고 말할 근거가 없다는 뜻이다.

사전등록 §8이 정한 목표는 **반폭 ≤ 1.0pp**였다. 관문은 두 기준 중 **나쁜 쪽**으로
잡았고(공통분모 0.76pp, 발표값 0.89pp), **0.89pp로 통과했다.**

1.0pp라는 목표가 자의적이지 않은 이유: 82.87%에서 90%까지는 **7.13pp**가 남아
있다. 반복 채점의 흔들림이 그 간격의 8분의 1이면, "아직 90%에 못 미친다"는 판단은
반복 채점 때문에 뒤집히지 않는다.

**추가 유료 실행은 필요 없다.** §13의 공식
`R = ceil((1.96·σ_d/(목표·√n))²) + 1` 에 가장 넓은 짝의 σ_d = 2.14pp를 넣으면
필요 실행 수는 **3회**이고, 우리는 3회를 이미 갖고 있다.

### 2. 항목 하나하나는 움직인다

항목 짝 4,299개(1,433개 × 3짝) 중

- **판정이 뒤집힌 것 204개 = 4.75%** (95% 구간 3.82 ~ 5.74%)
- **점수 결과가 달라진 것 450개 = 10.47%** (95% 구간 8.25 ~ 12.73%)

두 숫자를 나눈 이유는 **판정 이름은 그대로인데 점수만 움직인 항목이 246개**이기
때문이다. `partial`이 2.0점에서 1.5점으로 내려가도 이름은 `partial`이다. 판정만
세면 그 246개가 안 보이고, 점수만 세면 사람이 인용하는 문장이 뒤집힌 사실이 안
보인다.

**두 칸을 건너뛴 이동 23건.** `pass`가 `fail`이 되거나 그 반대인 경우다. 나머지
175건은 옆 칸 이동이다.

### 3. 평균이 잠잠한데 항목이 흔들리는 이유

**뒤집힘이 양쪽으로 거의 고르게 나기 때문이다.** 위로 올라간 이동이 107건,
내려간 이동이 91건, 판정 실패가 낀 것이 6건이다. 뒤로 갈수록 아주 조금 후해지는
기울기가 보이지만(82.87 → 83.07 → 83.25), 앞서 본 대로 **그 기울기는 95% 구간
안에서 0과 구별되지 않는다.**

그래서 두 문장은 함께 참이다.

- **"이 코퍼스의 평균은 82.9%다"** — 다시 채점해도 ±0.9pp 안에서 그대로다.
- **"이 항목은 pass였다"** — 스무 번에 한 번은 다시 채점하면 다른 판정이 나온다.

**한 항목의 판정을 근거로 문장을 쓸 때는 두 번째 사실이 적용된다.**

## 왜 항목이 아니라 과제를 다시 뽑는가

1,433개 항목을 독립된 관측 1,433개로 다루면 표본이 커 보이고, 그건 사실이 아니다.
한 과제 안의 항목들은 같은 산출물·같은 파일·같은 채점 맥락을 공유하고, **과제가
움직이면 그 안의 항목들이 함께 움직인다.**

| 재추출 단위 | 판정 뒤집힘 95% 구간 | 폭 |
|---|---|---|
| **과제(공식)** | 3.8208 ~ 5.7446% | **1.9238pp** |
| 항목(쓰지 않음) | 4.1172 ~ 5.3966% | 1.2794pp |

항목 단위로 재면 구간이 **1.50배 좁게** 나온다. 좁은 쪽이 더 정밀한 게 아니라,
없는 정보를 있다고 가정한 결과다. 그래서 공식 구간은 넓은 쪽이다.

### 사전등록의 4.094와 여기의 4.117

사전등록 §6은 항목 구간의 아래끝을 **4.094**로 적었고 여기서 다시 돌리면
**4.117**이 나온다. 구현을 열한 가지로 바꿔 봐도 전부 4.117이었다. **원인은 구현이
아니라 정수다.**

항목 재추출의 통계량은 4,299개 중 몇 개라는 정수를 4,299로 나눈 값이므로
**0.0233pp 간격의 눈금 위에만 떨어진다.** 정확한 이항분포로 계산하면

| 개수 | 비율 | P(X ≤ 개수) |
|---|---|---|
| 176 | 4.0940% | 0.02241 |
| 177 | 4.1172% | 0.02672 |

**참값인 2.5% 백분위는 176과 177 사이에 있다.** 어떤 추출도 그 사이 값을 낼 수
없으므로 두 숫자 모두 같은 양의 정직한 실현값이고, 차이는 **항목 하나**다. 폭
차이는 0.024pp이고 설계 효과 결론(약 1.5배)은 그대로다. 이건 추출 결과가 아니라
산술이므로 도구가 매번 정확히 계산해서 위 표에 찍는다.

## 재지 않은 것

사전등록 §9의 원칙 그대로 — **없는 것은 없다고 적는다.**

| | 관측 |
|---|---|
| 거부(refusal) | **이 스키마에 필드가 없고 관측되지도 않았다.** "거부율 0%"라고 쓰면 잰 것처럼 읽히는데, 잰 적이 없다 |
| 도구 실패 | 전용 필드가 없어 **재지 않았다.** 호출 횟수 분포의 0회 칸을 대용물로 쓰자는 얘기가 있었는데, 대용물이 아니다(바로 아래) |
| 판정 실패 | 4건 / 4,299짝 = 0.093%. `score_excluded`와 **완전히 같은 4건**이다 |
| 음성 | **0개.** 307·310~312에서 관측된 음성 판정 흔들림은 구조적으로 이 구간 안에 들어올 수 없다 |
| 선택 실패 | 4,299/4,299 `ok` |
| 과제 오류 | 세 실행 모두 0 |

`read_deliverable`를 **한 번도 부르지 않고** 판정한 항목이 92개 있다. 도구 실패
후보로 보고 후속으로 넘겼던 건인데, 답이 나왔다. **도구 실패가 아니다.**

92개 전부가 그림으로 가는 항목이고(`routing_modality: visual`), 92개 전부가
그림을 실제로 만들어서 봤다(`perception_called: true`, 쓴 도구는
`harness_render_to_image` + `harness_vision_perception`, 그중 25개는 두 번 이상).
도구를 하나도 못 쓴 항목은 0개고, 판정도 pass 78 · partial 14로 판정 실패가
하나도 없다.

즉 **산출물을 안 연 게 아니라, 글자 대신 그림으로 열었다.** 그림으로 가는 항목은
`read_deliverable`을 부를 일이 애초에 없다. 방향을 뒤집으면 더 분명하다. 그림으로
간 231개 중 92개가 이렇고, 글자로 간 3,858개 중에는 **한 개도** 이렇지 않다.

그래서 도구가 이제 0회 칸을 세 갈래로 쪼개 찍는다 — 그림으로 봤다 / 다른 도구를
썼다 / 파일에 아예 닿지 못했다. 실패 후보는 마지막 하나뿐이고, 이 실행에서는
0이다.

## 비용

세 실행 모두 `estimated_cost_usd`가 비어 있다. `gpt-5.6-sol`과 `gpt-audio-1.5`가
가격표에 없기 때문이다. **금액은 "미등록"으로 적는다.** 값을 못 매긴 실행은 공짜
실행이 아니고, `$0.00`이라고 쓰면 가격표의 구멍이 청구서에 대한 주장으로 바뀐다.

토큰과 시간은 실측이 있다: 판정 호출 3,735 · 3,738 · 3,766회, 입력 약 2,700만
토큰, 출력 약 143만 토큰, 판정 누적 시간 약 6.6 ~ 7.1시간.

## 이 문서를 어떻게 검증하는가

- 위 `결과` 블록은 주석에 적힌 명령을 **그대로 다시 돌려 한 바이트까지 대조**한다
  (`test_repeat_variation_report_quotes_its_run.py`). 난수 씨앗이 `20260901`로
  고정된 이유가 이것이다 — 시계에서 오는 값이면 이 대조가 불가능하다.
- 사전등록 §12의 **돌연변이 여섯 가지**(지문 변조 · 같은 파일 두 번 · 판정값 위조 ·
  재추출 단위 과제→항목 · 씨앗 변경 · 음성 주입)를 각각 심어 놓고 **전부 빨개지는지**
  확인한다.
- **음성 대조**: 같은 파일을 세 번 넣으면 차이가 정확히 0으로 나오고, 그 0이
  발표되기 전에 같은-파일 검사가 먼저 막는다는 것을 확인한다.
- 기존 `analyze_variance.py`는 **한 줄도 고치지 않았다.** 이 도구는 코드를 공유하지
  않는 별도 파일이다 — 저쪽을 고치면 2단계가 발표한 숫자가 움직이기 때문이다.
- 기존 채점 결과 파일은 **읽기만 했다.**
