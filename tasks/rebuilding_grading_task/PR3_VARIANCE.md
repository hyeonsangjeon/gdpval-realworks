# PR3_VARIANCE — 같은 채점을 세 번 하면 점수가 얼마나 움직이는가

> PR3 / 4 of 4. 명세: [`303-variance-and-error.md`](./303-variance-and-error.md) (SPEC §7-4, §7-5)
> 1단계 보고서: [`PR3_GOLD_CEILING.md`](./PR3_GOLD_CEILING.md)

## 이 문서가 답하는 질문

1단계는 정답 30개를 채점해서 **82.87%** 라는 숫자를 냈다. 그 숫자를 놓고 무엇이
잘못됐는지 일곱 갈래로 나눴고, 얼마를 잃었는지 항목별로 셌다.

그런데 그 모든 이야기는 **82.87%가 그 채점의 성질이지 그날의 운이 아니라는 것**에
기대고 있다. 같은 입력을 같은 채점기에 다시 넣었을 때 79%나 86%가 나온다면, 1단계
보고서의 "이 항목에서 2.0점을 잃었다"는 문장들은 측정이 아니라 잡음을 읽은 것이다.

이 문서는 그것만 묻는다. **아무것도 바꾸지 않고 세 번 채점하면, 점수는 얼마나
움직이는가.**

명세가 정한 합격선은 셋이다.

| | 기준 | 왜 이 숫자인가 |
|---|---|---|
| 과제별 점수 표준편차 | ≤ **5.0**pp | 한 과제의 점수가 실행마다 이만큼 넘게 흔들리면 그 과제의 채점 결과는 근거로 못 쓴다 |
| judge 오류율 | < **2%** | 도구 호출 경로가 답을 못 내는 비율. 1단계와 같은 기준 |
| 평균의 95% 신뢰구간 폭 | < **10.0**pp | 이 코퍼스로 낸 평균값에 붙는 불확실성의 크기 |

**셋 다 통과했다.** 가장 심하게 움직인 과제의 표준편차 **4.02**pp, judge 오류율
**0.09%**, 신뢰구간 폭 **7.26**pp.

코퍼스 평균은 세 번 모두 83% 근처에 떨어졌다 — **82.87% · 83.07% · 83.25%**,
가장 먼 두 값의 차이가 **0.37**pp다. 그러므로 1단계의 82.87%는 그날의 운이 아니고,
"이 항목에서 2.0점을 잃었다"는 1단계의 문장들은 잡음이 아닌 것을 읽고 있었다.

다만 **평균이 잠잠한 것과 과제 하나하나가 잠잠한 것은 다르다.** 30개 중 4개는
5pp 넘게 벌어진 폭 안에서 움직였고, 그 사실은 평균 어디에도 나타나지 않는다.
아래의 나머지는 대부분 그 차이에 관한 것이다.

## 명세와 달라진 점 — 하나, 그리고 그 이유

명세 1번 항목은 이렇게 적혀 있다.

> exp003 부분집합 (예: 첫 30 task) 3회 채점

**이 문서는 exp003이 아니라 1단계의 정답 30과제를 세 번 채점했다.** 바꾼 이유는
둘이고, 둘 다 명세가 쓰일 때는 없던 사정이다.

첫째, **측정 대상이 달라진다.** 명세가 쓰일 때 1단계는 아직 돌지 않았다. 지금은
돌았고, PR3 전체에서 사람이 인용할 숫자는 exp003의 어떤 값이 아니라 1단계의
82.87%다. 안정성을 재야 할 대상은 실제로 인용되는 그 숫자다. exp003 부분집합의
분산을 재면 "채점기는 대체로 안정적이다"까지는 말할 수 있지만 "82.87%를 믿어도
된다"는 말은 못 한다.

둘째, **유료 실행이 한 번 줄어든다.** 1단계의 채택된 실행이 그대로 1회차가 된다.
같은 30과제, 같은 정답 바이트, 같은 채점 설정, 같은 채점기 소스, 같은 컨테이너다.
새로 발주한 것은 2회차와 3회차뿐이다.

명세의 `judge_error_rate < 2%`, 표준편차, 신뢰구간 기준은 그대로 적용했다.

## 얼어붙인 계약

세 실행이 **같은 실행의 반복**이라는 것이 이 측정의 전제다. 분석 도구는 아래
항목이 하나라도 다르면 숫자를 내지 않고 거부한다 — 다른 것을 재고 있으면서 분산을
보고하느니 아무것도 보고하지 않는 편이 낫기 때문이다.

| 무엇을 | 어디에 적혀 있나 | 세 실행이 공유한 값 |
|---|---|---|
| 채점한 과제 목록 | `expected_ordered_task_ids_sha256` | `82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b` |
| 과제 수 | `expected_task_count` | 30 |
| 채점기 소스 | `grader_source_hash` | `c33d9d55703fbf5de5f988d427e34efd44d7a73306412caac88a753bad16ff4e` |
| 채점 모델과 설정 | `judge` | `gpt-5.6-sol` · reasoning_effort `max` · temperature 0 · seed 42 · 설정 `gold_ceiling_30_v2_sol_max` (`d1bfc8217c9981d2`) |
| 채점 프롬프트 | `prompt` | `prompts/grader_judge.md` v2.2 |
| 채점표 | `rubric` | `openai/gdpval` @ `11e7900cdcac61bc4daf59e65feb238acda98fbf` |
| 문서 변환기 | `renderer_fingerprint` | `LibreOffice 24.2.7.2 420(Build:2)` · PyMuPDF 1.28.2 |
| 정답 파일 판 | `source_inference_revision` | `11e7900cdcac61bc4daf59e65feb238acda98fbf` |
| 정답의 출처 | `source_azure_ai_provenance_status` | `gold-corpus` |
| 결과 파일 형식 | `schema_version` | `1.3` |

여기에 파일에는 적히지 않지만 세 실행이 공유한 것이 하나 더 있다. 채점이 돌아간
**컨테이너**다. `grade-run.yml`은 이미지를 태그가 아니라 다이제스트로 고정한다 —
`ghcr.io/hyeonsangjeon/gdpval-grading@sha256:0f6782c056e31e1ea1d693fc2f8f873da160b232926fa1b6cde75c24e5344a04`.
그래서 위 표의 LibreOffice 판번호는 이 상자 안의 판번호이고, 이 저장소가 놓인
기계와는 무관하다.

표에서 눈여겨볼 것이 하나 있다. **채점 설정은 따로 얼린 항목이 아니라 `judge`
안에 들어 있다.** 설정 파일이 한 글자라도 달라지면 `config_hash`가 달라지고, 그
차이는 `judge` 비교에서 잡힌다. 항목을 하나 더 만들지 않은 이유가 그것이다.

## 얼리지 않은 것 하나 — Azure 경로

`azure_ai_routes`는 **일부러 얼리지 않았다.**

채점은 shard로 나뉘어 여러 Azure 엔드포인트에서 돌고, 병합 단계
(`step9_merge_shards.py:54-67`)는 그 경로 지문을 **합집합으로 모은다**. 주석이
그 이유를 직접 적어 두었다 — 4과제짜리 앵커 실행조차 이미 서로 다른 채점기 지문
두 개를 관측했다. 즉 경로가 하나로 고정되는 실행은 존재하지 않는다.

그래서 경로를 계약에 넣으면 **1단계의 채택된 실행 자신이 거부된다.** 그 실행은
지문 두 개를 달고 있다. 기준을 만들면서 그 기준으로 기준선을 탈락시키는 셈이다.

**보고는 하되 판정에는 쓰지 않는다.** 아래 결과 블록의 `azure route` 줄이 세
실행이 실제로 지나간 경로 전부다.

세 실행이 관측한 경로 지문은 **둘이고, 세 실행 모두 같은 둘이다.**

```
4883551d5001c23b50b24d0f2290fc01a6febacf73374667fce8a0c7111de517
5df8d48b6568d7a6ae41c99f61044cdab00e6cdee4cbc1ac4960efcf3881e5e7
```

즉 이번에는 얼리지 않은 항목이 실제로도 움직이지 않았다. **그렇다고 얼렸어야
했다는 뜻은 아니다.** 이 셋이 같은 둘을 본 것은 세 번 다 shard 3개로 같은 30과제를
같은 방식으로 나눴기 때문이고, 과제 수나 shard 수가 달라지면 조합도 달라진다.
얼렸다면 이번 세 번은 통과했겠지만 그 다음 실행이 아무 결함 없이 걸렸을 것이다.

## 방법

### 왜 가장 심하게 흔들린 과제가 기준을 정하는가

명세의 기준은 "task-level pct 표준편차 ≤ 5pp"다. 30개 과제의 표준편차를 평균
내면 대부분 잠잠한 코퍼스에서 한 과제만 15pp씩 튀어도 평균은 1pp 아래로 나온다.
그 평균은 "채점이 안정적이다"라고 말하지만, 그 한 과제의 점수는 근거로 쓸 수 없다.

그래서 판정은 **가장 심하게 움직인 과제 하나**로 한다. 평균과 중앙값도 같이
적는다 — 그건 코퍼스 전체의 성질을 말해 주지만, 합격 여부를 정하지는 않는다.

표준편차는 표본 형태(ddof=1)로 계산한다. 세 번의 실행은 "가능한 모든 실행" 중
셋을 뽑은 것이지 전부가 아니기 때문이다.

### 신뢰구간을 무엇으로 만들었는가

평균의 95% 신뢰구간은 부트스트랩으로 낸다. 과제를 복원추출로 30개 다시 뽑고, 뽑힌
과제마다 그 과제의 세 점수 중 하나를 복원추출로 고른 뒤, 그 조합의 평균을 기록한다.
이것을 10,000번 반복하고 2.5·97.5 백분위를 취한다.

여기에는 **두 가지 서로 다른 불확실성**이 섞여 있고, 도구는 그 둘을 갈라서도
보고한다.

- **tasks only** — 과제만 다시 뽑는다. "다른 30과제를 골랐다면 평균이 얼마나
  달랐을까"
- **runs only** — 과제는 고정하고 실행만 다시 뽑는다. "같은 30과제를 다시
  채점하면 평균이 얼마나 달랐을까"
- **tasks and runs** — 둘 다. 판정에 쓰는 값

이 구분이 실용적으로 중요한 이유는, 구간이 너무 넓게 나왔을 때 **무엇을 늘려야
하는지가 정반대**이기 때문이다. tasks 쪽이 지배적이면 과제를 늘려야 하고, runs
쪽이 지배적이면 채점을 더 반복해야 한다.

난수 씨앗은 `20260828`으로 고정돼 있다. 이 보고서의 숫자 블록은 테스트가 명령을
다시 돌려 **한 바이트까지 같은지** 대조하기 때문에, 씨앗이 시계에서 오면 그 대조가
불가능해진다.

## 결과

<!-- generated: python batch-runner/scripts/analyze_variance.py data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_c33d9d55703fbf5d__v2.2.json data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/_repeats/run-002/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_c33d9d55703fbf5d__v2.2.json data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/_repeats/run-003/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_c33d9d55703fbf5d__v2.2.json -->
```text
Repeat variance — stage 2
====================================================================
  run 1    data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_c33d9d55703fbf5d__v2.2.json
  run 2    data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/_repeats/run-002/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_c33d9d55703fbf5d__v2.2.json
  run 3    data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/_repeats/run-003/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_c33d9d55703fbf5d__v2.2.json

  task list       82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b
  grader source   c33d9d55703fbf5de5f988d427e34efd44d7a73306412caac88a753bad16ff4e
  judge           gpt-5.6-sol (effort max, temperature 0, seed 42)
  grading config  gold_ceiling_30_v2_sol_max / d1bfc8217c9981d2
  prompt          prompts/grader_judge.md v2.2
  renderer        LibreOffice 24.2.7.2 420(Build:2), pymupdf 1.28.2
  gold revision   11e7900cdcac61bc4daf59e65feb238acda98fbf

Thresholds
--------------------------------------------------------------------
  runs compared           3   (needs >= 3)   PASS
  worst task stdev        4.0221pp   (needs <= 5.0pp)   PASS
  judge error rate        0.0009   (needs < 0.02)   PASS
  95% CI width            7.257pp   (needs < 10.0pp)   PASS

Corpus mean
--------------------------------------------------------------------
  per run                 82.8733%, 83.0727%, 83.2457%
  across runs             83.0639%
  spread / stdev          0.3723pp / 0.1863pp

95% confidence interval on the corpus mean (bootstrap)
--------------------------------------------------------------------
  tasks and runs         [79.19%, 86.447%]   width 7.257pp
  tasks only             [79.1943%, 86.5178%]   width 7.3235pp
  runs only              [82.627%, 83.489%]   width 0.862pp
  10000 resamples, seed 20260828, sampled with replacement

Per-task stability
--------------------------------------------------------------------
  stdev across 30 task(s): worst 4.0221pp, mean 1.1042pp, median 0.6681pp
  scored identically in every run: 1 task(s)
  over the 5.0pp ceiling: none

Least stable tasks
--------------------------------------------------------------------
  stdev  4.0221pp  range   7.05pp  a328feea-47db-4856-b4be-2bdc63dd88fb
      84.55%, 77.50%, 84.38%  ·  Administrative Services Managers
  stdev  3.2843pp  range   5.86pp  f84ea6ac-8f9f-428c-b96c-d0884e30f7c7
      86.57%, 92.07%, 86.21%  ·  Administrative Services Managers
  stdev  3.1755pp  range   6.28pp  dfb4e0cd-a0b7-454e-b943-0dd586c2764c
      72.09%, 69.77%, 76.05%  ·  Compliance Officers
  stdev  3.0672pp  range   5.51pp  ee09d943-5a11-430a-b7a2-971b4e9b01b5
      82.15%, 76.64%, 81.73%  ·  Accountants and Auditors
  stdev  1.6782pp  range   3.17pp  f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb
      84.68%, 87.85%, 87.22%  ·  Audio and Video Technicians
  stdev  1.5363pp  range   3.06pp  38889c3b-e3d4-49c8-816a-3cc8e5313aba
      67.42%, 69.19%, 66.13%  ·  Audio and Video Technicians
  stdev  1.4737pp  range   2.94pp  a74ead3b-f67d-4b1c-9116-f6bb81b29d4f
      74.71%, 76.00%, 77.65%  ·  Child, Family, and School Social Workers
  stdev  1.4087pp  range   2.44pp  2696757c-1f8a-4959-8f0d-f5597b9e70fc
      92.68%, 95.12%, 95.12%  ·  Compliance Officers
  stdev   1.355pp  range   2.62pp  83d10b06-26d1-4636-a32c-23f92c57f30b
      66.90%, 69.52%, 68.81%  ·  Accountants and Auditors
  stdev  1.3437pp  range   2.67pp  c357f0e2-963d-4eb7-a6fa-3078fe55b3ba
      49.29%, 50.36%, 47.69%  ·  Computer and Information Systems Managers
  ... and 20 more (use --json for all of them)

Per-item agreement
--------------------------------------------------------------------
  same verdict in every run     1333/1433   changed 100 (6.98%)
  same awarded score            1236/1433   changed 197 (13.75%)
    decided by judge         1433 item(s), verdict changed 100, score changed 197

  How much of the movement cancels out
    run 1 vs run 2    151 item(s) moved   gross    59.21pt   net   10.32pt   cancelled 82.57%
    run 1 vs run 3    144 item(s) moved   gross   56.735pt   net   6.505pt   cancelled 88.53%
    run 2 vs run 3    152 item(s) moved   gross   68.625pt   net   3.815pt   cancelled 94.44%
  Points are rubric points, not corpus pp — a task's pct normalises by its own maximum.

Items that answered differently
--------------------------------------------------------------------
  range    3.0pt of 5   f84ea6ac-8f9f-428c-b96c-d0884e30f7c7  6d68ba81-478d-43c3-9fb7-e933313c5570
      fail -> partial -> fail   ·   0 -> 3 -> 0
  range    2.0pt of 2   43dc9778-450b-4b46-b77e-b6d82b202035  dd163c57-a9be-44f3-bcb9-9440e059eb71
      pass -> pass -> judge_error   ·   2 -> 2 -> 0
  range    2.0pt of 2   4c18ebae-dfaa-4b76-b10c-61fcdf26734c  b9650eab-cf9d-4a96-8b6f-5c4457312abb
      pass -> pass -> fail   ·   2 -> 2 -> 0
  range    2.0pt of 2   dfb4e0cd-a0b7-454e-b943-0dd586c2764c  d116babd-e404-4f00-9112-5c6d993e7a2b
      partial -> fail -> pass   ·   1 -> 0 -> 2
  range    2.0pt of 2   ee09d943-5a11-430a-b7a2-971b4e9b01b5  2495d241-e93f-498f-914d-12aca102122b
      pass -> fail -> pass   ·   2 -> 0 -> 2
  range    2.0pt of 2   ee09d943-5a11-430a-b7a2-971b4e9b01b5  e14ffdcb-6050-464d-bb1a-844c826f228e
      pass -> fail -> pass   ·   2 -> 0 -> 2
  range    2.0pt of 2   f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb  761c5cc3-09ae-4b0a-953d-123c3ca9ec1b
      fail -> partial -> pass   ·   0 -> 1.5 -> 2
  range    1.7pt of 2   dfb4e0cd-a0b7-454e-b943-0dd586c2764c  07153c11-c95c-4d45-b4b7-b58e831c4e7e
      fail -> partial -> partial   ·   0 -> 1 -> 1.7
  range    1.6pt of 2   a74ead3b-f67d-4b1c-9116-f6bb81b29d4f  2d1c5ac5-163f-4cbc-a3dc-148f316b2ff4
      partial -> pass -> pass   ·   0.4 -> 2 -> 2
  range    1.5pt of 2   38889c3b-e3d4-49c8-816a-3cc8e5313aba  18450dbc-8c9f-41d1-bc5d-0332fd5f2baa
      partial -> partial -> fail   ·   1.5 -> 1.5 -> 0
  ... and 188 more (use --json for all of them)

Judge errors
--------------------------------------------------------------------
  run 1    2/1433 = 0.0014   PASS
  run 2    0/1433 = 0.0   PASS
  run 3    2/1433 = 0.0014   PASS
  pooled   4/4299 = 0.0009

Usage per run
--------------------------------------------------------------------
  run 1  graded at 2026-08-28T18:41:32Z
      judge calls         3735 (3631 main, 104 perception)
        mixed              1
        visual             103
      main tokens         in 27299254, out 1392576, cached 13103993
      perception tokens   in 266033, out 37479
      judge latency       26264.17s, usage complete True
      estimated cost      UNKNOWN — this grade predates the cost receipt
      judge models        ['gpt-5.6-sol', 'gpt-audio-1.5']
      azure route         4883551d5001c23b50b24d0f2290fc01a6febacf73374667fce8a0c7111de517
      azure route         5df8d48b6568d7a6ae41c99f61044cdab00e6cdee4cbc1ac4960efcf3881e5e7
  run 2  graded at 2026-08-28T22:38:04Z
      judge calls         3738 (3634 main, 104 perception)
        mixed              1
        visual             103
      main tokens         in 26689319, out 1393484, cached 12709773
      perception tokens   in 266033, out 42022
      judge latency       24833.42s, usage complete True
      estimated cost      UNKNOWN — this grade predates the cost receipt
      judge models        ['gpt-5.6-sol', 'gpt-audio-1.5']
      azure route         4883551d5001c23b50b24d0f2290fc01a6febacf73374667fce8a0c7111de517
      azure route         5df8d48b6568d7a6ae41c99f61044cdab00e6cdee4cbc1ac4960efcf3881e5e7
  run 3  graded at 2026-08-29T01:22:18Z
      judge calls         3766 (3662 main, 104 perception)
        mixed              1
        visual             103
      main tokens         in 27266562, out 1385129, cached 13001172
      perception tokens   in 266033, out 42267
      judge latency       24433.4s, usage complete True
      estimated cost      UNKNOWN — this grade predates the cost receipt
      judge models        ['gpt-5.6-sol', 'gpt-audio-1.5']
      azure route         4883551d5001c23b50b24d0f2290fc01a6febacf73374667fce8a0c7111de517
      azure route         5df8d48b6568d7a6ae41c99f61044cdab00e6cdee4cbc1ac4960efcf3881e5e7
```

## 읽는 법

블록을 위에서부터 읽으면 되지만, 그 안에서 **무엇이 무엇을 말하는지는 서로
다르다.** 세 합격선이 재는 것이 사실 같지 않기 때문이다.

**`worst task stdev`가 이 문서의 본론이다.** "같은 답안을 다시 채점하면 점수가
움직이는가"에 정면으로 답하는 값은 이것 하나다. 30개 중 가장 심하게 움직인 과제
하나의 표준편차이고, 이 값이 작으면 어느 과제의 점수를 인용해도 된다.

**`judge error rate`는 채점의 안정성이 아니라 도구 경로의 신뢰도를 잰다.** 판정을
내리려다 실패한 비율이다. 점수가 얼마나 흔들리는지와는 다른 질문이고, 1단계와
같은 기준(2%)을 쓰는 이유는 같은 것을 재기 때문이다.

**`95% CI width`는 이름이 말하는 것과 다른 것을 잰다 — 이 점은 짚고 넘어가야
한다.** 신뢰구간 블록의 세 줄을 비교하면 바로 보인다.

- `runs only` — 과제를 고정하고 채점만 다시 뽑은 구간. **반복 채점의 불안정성**
- `tasks only` — 채점을 고정하고 과제만 다시 뽑은 구간. **코퍼스의 다양성**
- `tasks and runs` — 둘을 합친 것. 합격 판정에 쓰는 값

세 줄의 폭을 비교해 보면 `tasks and runs`는 거의 전부 `tasks only`에서 온다.
`runs only` 폭은 그보다 **한 자릿수 작다.** 즉 명세가 "CI 95% 폭 < 10pp"라고
적은 이 기준은 실제로는 **30개 과제의 점수가 서로 얼마나 다른지**를 재고 있고,
같은 채점을 반복했을 때의 흔들림은 그 안에서 반올림 수준으로 묻힌다.

이것은 도구의 결함이 아니라 기준 자체의 성질이다. 정답 30과제의 점수는 60%대부터
99%대까지 퍼져 있고, 그 퍼짐은 채점을 몇 번 반복하든 줄지 않는다. 그래서 이
기준은 **통과하더라도 "반복 채점이 안정적이다"의 근거로는 쓸 수 없다.** 그 근거는
`worst task stdev`와 `runs only` 폭이다. 세 줄을 갈라서 보고하는 이유가 이것이다.

이 사실이 기준을 무르게 만들지는 않는다. 폭이 10pp를 넘었다면 그것도 알아야 할
것이었고 — 다만 그때 늘려야 할 것은 채점 횟수가 아니라 과제 수였을 것이다.


## 사용량과 청구액

세 실행의 호출 수와 토큰은 위 블록의 `Usage per run`에 실행별로 적혀 있다. 여기서는
그 숫자를 다시 옮기지 않고, **왜 청구액 자리가 비어 있는지**만 적는다.

각 실행의 `estimated cost` 줄은 금액 대신 `UNKNOWN — not every model used has a
published price`라고 나온다. 결과 파일의 `pricing_complete`가 `false`이기 때문이고,
그렇게 되는 이유는 이 채점이 쓴 두 모델 — **`gpt-5.6-sol`** 과 **`gpt-audio-1.5`**
— 에 공개 단가가 없어서다. 단가표에 없는 모델의 토큰은 곱할 수가 없다.

**여기서 0을 적지 않는 것이 중요하다.** 값이 비어 있는 이유는 돈이 들지 않아서가
아니라 **얼마인지 이 저장소가 알 수 없어서**다. 0을 적으면 그 두 문장이 같은 것으로
읽히고, 그 뒤에 이 숫자를 합산하는 사람은 실제 지출을 0으로 더하게 된다. 그래서
도구는 금액 자리에 0을 넣지 않고 `UNKNOWN`을 넣으며, 이 보고서의 테스트는 본문에
달러 기호 뒤에 0이 오는 표기가 나타나면 실패한다.

실제 청구액은 Azure 구독 쪽 사용량 기록에서 확인해야 하고, 그것은 이 저장소가
접근하는 범위 밖이다. **대신 곱할 수 있는 재료는 전부 남겨 두었다** — 실행별
호출 수, 입력·출력·캐시 토큰이 모두 위 블록에 있으므로, 단가가 공개되는 시점에
누구든 곱하기만 하면 된다.


## 판정

| 기준 | 결과 | |
|---|---|---|
| 과제별 점수 표준편차 ≤ 5.0pp | **4.0221**pp | 통과 |
| judge 오류율 < 2% | **0.09%** (4 / 4,299) | 통과 |
| 평균의 95% 신뢰구간 폭 < 10.0pp | **7.257**pp | 통과 |

**세 기준 모두 통과했으므로 303은 닫힌다.** 명세가 오류율 초과에 대비해 적어 둔
사다리(`reasoning_effort` medium → high, 그래도 안 되면 도구 호출 cap 조정)는
쓸 일이 없었다. 참고로 쓸 수도 없었다 — 이 채점의 `reasoning_effort`는 이미
`max`이고, 사다리의 첫 칸은 올릴 자리가 없다. 초과했다면 두 번째 칸부터
시작해야 했을 것이다.

### 이 통과가 보증하는 것

**코퍼스 평균은 인용해도 된다.** 세 번의 평균이 82.87 · 83.07 · 83.25%로 폭
0.37pp 안에 들어왔고, 실행만 다시 뽑은 신뢰구간도 0.86pp다. 1단계가 낸
"정답의 천장은 약 83%"는 반복해도 같은 자리에 있다.

세 값이 계속 오른 것은 눈에 띄지만 **추세로 읽을 근거가 없다.** 세 숫자가 우연히
오름차순으로 놓일 확률은 3분의 1이다.

### 이 통과가 보증하지 않는 것 — 기준 자체의 한계

**과제 하나의 점수는 같은 신뢰를 갖지 않는다.** 30개 중 4개가 5pp보다 넓은 폭
안에서 움직였다.

| 과제 | 세 번의 점수 | 폭 | 표준편차 |
|---|---|---|---|
| `a328feea` (행정서비스 관리자) | 84.55 · 77.50 · 84.38 | **7.05**pp | 4.02 |
| `dfb4e0cd` (준법감시 담당자) | 72.09 · 69.77 · 76.05 | **6.28**pp | 3.18 |
| `f84ea6ac` (행정서비스 관리자) | 86.57 · 92.07 · 86.21 | **5.86**pp | 3.28 |
| `ee09d943` (회계사·감사) | 82.15 · 76.64 · 81.73 | **5.51**pp | 3.07 |

넷 다 기준을 통과했다. **그런데 통과한 방식을 봐야 한다.** 값 세 개의 표준편차는
아무리 커도 폭을 √3으로 나눈 값을 넘지 못한다. 즉 **"표준편차 ≤ 5pp"는 3회
반복에서 폭 8.66pp까지를 허용한다.** 같은 답안이 같은 채점기에서 8.66점 움직여도
이 기준은 통과라고 말한다.

이건 도구가 봐준 것이 아니라 명세가 고른 통계량이 그런 성질을 갖는다는 뜻이다.
그래서 위 블록의 `Least stable tasks`는 표준편차와 **폭을 나란히** 적는다. 판정은
명세대로 표준편차로 하되, 읽는 사람이 실제 움직임을 볼 수 있어야 하기 때문이다.

실용적인 결론은 이렇다. **코퍼스 단위 숫자는 ±0.2pp 수준으로 믿어도 되고,
과제 하나의 점수는 ±3pp 정도를 달고 읽어야 한다.** 1단계 보고서가 손실을
항목 유형별 **합계**로 셌기 때문에 그 결론들은 이 구분의 안전한 쪽에 있다.

### 나머지 26개는 매우 안정적이다

위 넷을 빼면 그림이 다르다. 30개의 표준편차는 **중앙값 0.67pp**이고, 한 과제는
세 번 모두 **완전히 같은 점수**를 받았다. 흔들림은 코퍼스 전체에 퍼져 있는 성질이
아니라 소수 과제에 몰려 있다.

### 점수가 안 움직인 것과 판단이 안 움직인 것은 다른 이야기다

여기까지의 모든 숫자는 **점수**를 잰 것이다. 점수는 한 과제의 항목 수십 개를 더한
값이고, 더하기 전에 갈린 판단은 더한 뒤에는 보이지 않는다. 그래서 위 문단의
"안정적이다"는 아직 **"같은 항목이 세 번 다 같은 답을 받았다"**를 뜻하지 않는다.
그 질문은 따로 재야 한다.

항목을 `(과제, 채점 항목)`으로 짝지어 세 실행을 맞대 보면 그림이 뒤집힌다.
채점 항목 1,433개 중

- **판정이 갈린 항목 100개 (6.98%)**
- **받은 점수가 움직인 항목 197개 (13.75%)**
- 항목이 하나라도 움직인 과제 **30개 중 29개**

코퍼스 평균이 폭 0.37pp 안에 들어온 그 데이터에서 나온 숫자다.

#### 왜 이렇게 많이 움직이는데 점수는 가만히 있는가

**서로 상쇄되기 때문이다.** 실행 두 개를 짝지어, 움직인 점수의 **절댓값 합**과
움직임을 **부호대로 더한 합**을 나란히 놓으면 바로 보인다.

| 짝 | 움직인 항목 | 절댓값 합 | 부호 합 | 상쇄된 비율 |
|---|---|---|---|---|
| 1 vs 2 | 151개 | 59.21점 | 10.32점 | **82.57%** |
| 1 vs 3 | 144개 | 56.735점 | 6.505점 | **88.53%** |
| 2 vs 3 | 152개 | 68.625점 | 3.815점 | **94.44%** |

2회차와 3회차 사이에서는 움직인 점수의 **94%가 서로 지워졌다.** 오른 항목과
내린 항목이 거의 같은 양이었다는 뜻이다. 합계만 보면 채점기가 두 번 다 같은
판단을 한 것처럼 보이지만, 실제로는 152개 항목에서 답이 달라졌고 그 차이가
서로를 가린 것이다.

*(여기서 "점"은 채점표의 배점이지 코퍼스 pp가 아니다. 과제마다 만점이 다르므로
과제를 가로지르는 점수 합에는 공통 단위가 없다. 그래서 이 표는 pp로 환산하지
않는다.)*

가장 뚜렷한 예가 `24d1e93f`다. **항목 17개가 움직여 30개 과제 중 가장 많이
흔들렸는데, 점수 표준편차는 0.3803pp로 매우 안정적인 쪽에 있다.** 위 문단이
"안정적"이라고 부른 26개 중 하나이고, 그 26개 가운데 **25개가 움직인 항목을
갖고 있다.**

거꾸로, 세 번 모두 같은 점수를 받은 그 한 과제(`36d567ba`)는 **움직인 항목이
0개인 유일한 과제이기도 하다.** 그 과제의 점수가 가만히 있었던 것은 상쇄 덕이
아니라 정말로 아무 판단도 갈리지 않았기 때문이다. 30개 중 하나뿐이다.

#### 판정을 바꾸지는 않는다

**303의 합격 기준은 명세가 정한 셋이고, 셋 다 통과했다.** 위 숫자는 네 번째
기준이 아니다. 명세에 없는 기준을 사후에 만들어 이미 받아들여진 단계를 다시
떨어뜨리는 것은 이 문서가 할 일이 아니다.

바뀌는 것은 **이 통과를 무엇의 근거로 쓸 수 있는가**다.

- **코퍼스 평균은 그대로 인용해도 된다.** 상쇄가 우연이 아니라 대칭적 churn의
  성질이고, 세 실행이 그것을 실제로 보여 줬다.
- **"채점기가 같은 답안에 같은 판단을 한다"의 근거로는 쓸 수 없다.** 항목 단위로는
  7%가 갈렸다. 개별 항목의 판정을 인용하는 글은 이 숫자를 달고 인용해야 한다.

**갈린 판단은 전부 judge 경로에서 나왔다** — 결정론적 사전검사가 실행마다 다른
답을 낸 경우는 0건이다. 두 경로를 합쳐서 세면 이 사실이 judge의 비율 안에 묻히므로
도구는 경로를 갈라 적는다. 사전검사가 갈리는 것은 비율이 아니라 결함이기 때문이다.

### 1단계가 예고한 것이 그대로 나왔다

넷이 아무 데서나 나온 것이 아니다. 1단계 보고서의 「(바) 채점 판단의 흔들림」은
읽기 도구를 고치기 전후 두 실행을 비교하면서 흔들린 과제 셋을 이름으로 지목했고,
그중 **점수가 가장 크게 움직인 둘**이 `dfb4e0cd`(−5.49점)와 `f84ea6ac`(−5.24점)다.
**둘 다 이번 넷 안에 있다.** 그 절은 이렇게 끝난다.

> 여기 미리 드러난 폭이 이미 2단계의 임계값(표준편차 5점)에 닿아 있다는 점은
> 기록해 둘 값어치가 있다.

**닿았다. 4.02pp로 넘지는 않았다.** 두 실행에서 읽은 예고를 세 실행이 확인한
셈이고, 예고와 확인이 서로 다른 데이터에서 나왔다는 점에서 우연으로 보기 어렵다.

원인은 그러나 하나가 아니고, 갈라 보면 **가장 크게 움직인 하나는 채점이 흔들린
것조차 아니다.**

#### 첫째 — 답할 수 없는 질문 하나가 과제 전체를 흔든다

`a328feea`와 `f84ea6ac`는 둘 다 Word 문서에 **"한 쪽 안에 들어가는가"**를 묻는
항목을 갖고 있다. 1단계가 특정한 바로 그 자리다 — 서식 검사는 Word 문서의 쪽 수를
돌려주지 않고, 채점기는 글자 수로 쪽 수를 맞혀야 한다.

`f84ea6ac`에서는 그 항목(5점)이 `fail` · `partial` · `fail`로 갈렸다. 폭 5.86pp
중 **5.17pp가 이 항목 하나에서 나온다.**

`a328feea`는 더 분명하다. 항목 16개 중 **딱 하나만 움직였고**, 그 하나가 쪽 수
항목이다.

| | 쪽 수 항목의 판정 | 받은 점수 | 만점 | 백분율 |
|---|---|---|---|---|
| 1회차 | `judge_error` | 18.6 | **22** | 84.55% |
| 2회차 | `fail` | 18.6 | **24** | 77.50% |
| 3회차 | `partial` | 20.25 | 24 | 84.38% |

**1·2회차는 받은 점수가 18.6으로 똑같다.** 7.05pp 차이는 전부 **만점이 달라서**
생겼다. 이 보고서의 대표 숫자(표준편차 4.02pp)를 정한 과제가 이것이다.

#### 채점기가 답을 못 내면 그 항목은 만점에서 빠진다

왜 만점이 움직이는가. `core/grader.py:1250-1252`가 만점을 이렇게 센다.

```python
scored_items = [it for it in items if not it.score_excluded]
total_awarded = sum(it.awarded_score for it in scored_items)
total_max = sum(max(0, it.max_score) for it in scored_items)
```

그리고 `judge_error`는 **반드시** `score_excluded`가 된다 (`grader.py:1240-1241`,
스키마도 이를 강제한다 — `grade_payload.py:93`).

**의도는 옳다.** 채점기가 제 잘못으로 답을 못 냈는데 그 벌을 답안이 받으면 안
되므로, 그 항목은 분자에서도 분모에서도 빠진다.

**그런데 부작용이 있다.** 실행마다 실패하는 자리가 다르므로 **실행마다 만점이
달라진다.** 30과제 중 3과제에서 실제로 그렇게 됐고, 만점이 움직인 자리는 판정
실패 4건의 위치와 **정확히 일치한다** — 빠진 점수도 그 항목의 배점과 정확히 같다.
채점 항목 수는 세 번 모두 1,433개로 같았다. 결과적으로 서로 다른 실행의 백분율은
**같은 만점 위에서 잰 값이 아니다.**

여기에 이상한 순서가 따라온다. 위 표에서 **채점기가 실패한 1회차(84.55%)가
"못 했다"고 판정한 2회차(77.50%)보다 높다.** 받은 점수는 같은데도 그렇다. 즉
채점기가 답을 못 내는 쪽이 답안에 더 유리하다.

이것은 1단계가 열어 둔 관찰을 닫는다. 1단계는 `17111c03`에서 "만점이 61에서
60으로 바뀌었다 ... 같은 채점표에서 채점 항목의 총합이 실행마다 달라졌다는
뜻이다"라고 적고 이유를 특정하지 못했다. **이유가 이것이다** — 그 과제는 1·3회차에
1점짜리 항목에서 판정 실패가 났고 2회차에는 나지 않았다. 같은 일이 `43dc9778`에도
3회차에만 일어났다(2점).

[후속 항목](./PR3_REPORT.md#후속-항목)에 등록했다. 고르는 문제이지 버그는
아니다 — 지금 방식은 답안을 보호하고, 대안(실패 항목을 0점으로 세기)은 분모를
고정하는 대신 채점기의 실패를 답안에 떠넘긴다. 다만 **어느 쪽을 고르든, 실행마다
만점이 달라진다는 사실은 백분율을 비교하는 쪽에 알려져 있어야 한다.**

#### 둘째 — 다 보고도 갈리는 판단

`dfb4e0cd`와 `ee09d943`에는 위 설명이 통하지 않는다. 둘 다 만점이 고정돼 있고,
움직인 항목이 쪽 수 같은 "볼 수 없는 것"이 아니다.

`dfb4e0cd`는 1단계가 이미 확인한 대로 엑셀 하나짜리 과제이고 **시각 채점 호출이
0회**다. 세 실행에서 움직인 항목 3개는 전부 표의 값을 확인하는 항목이다 — 예를
들어 "모든 데이터 행에 지출 구분이 들어 있는가"가 `partial` · `fail` · `pass`로
갈렸다. 같은 파일, 같은 증거, 같은 프롬프트다.

`ee09d943`도 같은 성질이다. 2점짜리 항목 둘 — **"4월 시산표의 순이익이
448,342.40인가"** 같은 산술 확인 — 이 `pass` · `fail` · `pass`로 갈렸다. 숫자
하나를 맞춰 보는 항목이고, 답은 실행과 무관하게 정해져 있다.

**여기서 움직이는 것은 채점기의 눈이 아니라 판단 자체이고, 도구를 고쳐도 줄지
않는다.** 이쪽이 반복 채점의 바닥값이다.

#### 그래서 무엇을 하면 무엇이 줄어드는가

넷 중 **둘은 고칠 수 있고 둘은 바닥값이다.** 후속 항목 1번(서식 검사가 Word
문서의 쪽 수를 보고하게 한다)을 적용하면 첫째 부류가 줄고, 그와 함께 이 보고서의
대표 숫자인 4.02pp도 내려갈 가능성이 높다 — 그 숫자를 정한 항목이 정확히 그
쪽 수 항목이기 때문이다. 남는 것이 진짜 바닥값이고, 그때 다시 재면 둘이 갈린다.

### judge 오류는 실행마다 다른 자리에서 난다

오류 수는 2 · 0 · 2건이었다. 세 번 다 같은 자리에서 나지 않았다는 뜻이고,
**판정 실패 자체가 재현되지 않는 사건**이라는 것을 보여 준다. 비율이 0.09%로
기준의 22분의 1이므로 조치 대상은 아니지만, 오류를 "특정 과제의 성질"로 다루면
안 된다는 점은 기록해 둔다.
