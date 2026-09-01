# PR3_FULL_GOLD_CORPUS — 정답 185개를 전부 채점하면 얼마가 나오는가

> 명세: [`304-full-gold-corpus.md`](304-full-gold-corpus.md) (SPEC §7-1).
> 1단계 보고서: [`PR3_GOLD_CEILING.md`](PR3_GOLD_CEILING.md) (30개, 82.87%).
> 2단계 보고서: [`PR3_VARIANCE.md`](PR3_VARIANCE.md) (같은 채점 3회, 최대 표준편차 4.02pp).

## 이 문서가 답하는 질문

1단계는 정답 30개를 채점해 **82.87%** 를 냈다. 그 30개는 데이터셋 행 순서 앞에서
잘라낸 것이라 **9개 sector 중 4개, 44개 직업 중 7개**만 덮었다. 그래서 1단계는
질문 하나를 미뤄 두었다: **82.87%는 이 채점기의 천장인가, 아니면 그 30개가
쉬웠던 것인가.**

3단계는 gold 답안이 있는 **185개 전부**를 채점한다. 표본이 아니라 모집단이다.
빠진 35개의 유일한 사유는 데이터셋이 답안 파일을 하나도 싣지 않았다는 것이고,
그 35개를 빼도 sector 9개·직업 44개는 그대로 남는다.

여기 나오는 낮은 점수는 어느 모델이 못했다는 뜻이 아니다. **채점 대상이 벤치마크
스스로 정답이라고 내놓은 결과물**이므로, 낮은 점수는 채점기·입력·도구 중 하나가
새고 있다는 뜻이다.

## 한 줄 결론

정답 185개를 채점했더니 **79.53%** 가 나왔다. 1단계의 82.87%보다 3.34pp 낮다.

| 임계값 | 결과 | 판정 |
|---|---|---|
| 평균 점수 ≥ 90% | **79.53%** | 미달 |
| 필수 항목 통과율 ≥ 0.95 | **0.6394** (227 / 355) | 미달 |
| 채점기 오류율 < 2% | **0.65%** (57 / 8,816) | 통과 |

**3단계도 통과하지 못했다.** 그러나 이 실행이 실제로 확정한 것은 세 임계값의
통과·미달이 아니라 **그 미달이 무엇 때문이 아닌지**다.

- **미리 공개한 다섯 개 한계 탓이 아니다.** 다섯 개를 빼면 79.53% → **80.18%**,
  움직임은 **0.65pp** 뿐이다. 실행 전에 "이 다섯이 천장을 아래로 끌어내린다"고
  적었고, 재 보니 끌어내리는 양이 90%까지 남은 10.47pp의 6%다.
- **채점기 고장 탓도 아니다.** 8,816개 항목 중 오류로 제외된 것이 57개, 판정을
  못 낸 과제가 0개다. 2% 기준을 세 배 이상 여유로 통과한다.
- **1단계 표본이 특별히 쉬웠던 것도 아니다.** 같은 30개를 이번 채점기로 다시 재면
  83.48%다. 30 → 185로 넓히며 잃는 것은 **3.95pp**이고, 그게 넓힘의 대가 전부다.

남는 설명은 하나다. **깎인 점수의 대부분은 도구가 못 읽어서가 아니라, 판정 모델이
읽고 나서 기준을 못 채웠다고 본 것이다.** 만점 미달 2,467개 항목 중 도구 실패
흔적이 evidence에 남은 것은 **79개(3.2%)** 뿐이다.

## 세 숫자를 나란히 놓기

두 실행 사이에 채점기 소스 지문이 바뀌었다. 그래서 82.87%와 79.53%를 직접 빼면
**채점기가 바뀐 몫과 범위가 넓어진 몫이 섞인다.** 1단계의 그 30개가 이번 185개
안에 같은 순서로 들어 있으므로, 둘을 분리할 수 있다.

| | 과제 | 채점기 | 평균 |
|---|---|---|---|
| 1단계 실행 | 30 | `955be41e…` 이전 세대 | 82.87% |
| 이번 실행의 같은 30개 | 30 | `79c2f503…` | **83.48%** |
| 이번 실행 전체 | 185 | `79c2f503…` | **79.53%** |

- **채점기가 바뀐 몫: +0.61pp.** 같은 30개 과제가 새 채점기에서 조금 더 받는다.
  1단계 이후 들어간 읽기·경로 수정들이 정답을 조금 더 읽어낸다는 뜻이고, 어느
  쪽으로도 크게 벌어지지 않았다는 것이 확인 사항이다.
- **범위가 넓어진 몫: −3.95pp.** 이게 3단계에 돈을 쓴 이유에 대한 답이다.
  1단계 표본은 **약간 쉬웠다** — 그러나 82.87%를 설명해 낼 만큼은 아니다.
  직업 7개에서 44개로 넓히면 천장은 4점 가까이 내려가고, 거기서 멈춘다.

즉 **82.87%는 좁은 표본의 우연이 아니라 이 채점기의 실제 천장이었다.** 1단계
보고서가 그 숫자를 근거로 세운 항목별 진단은 3단계에서도 유효하다.

## 미리 공개한 다섯 개 한계 — 그리고 여섯 번째

명세는 유료 실행 **전에** 다섯 과제를 지목하고 "이 다섯은 천장을 아래로
끌어내린다"고 적었다. 실행 후에 이유를 만들어내는 것과 값이 다르기 때문이다.
재 본 결과다.

| 과제 | 이번 점수 | 미리 적은 한계 | 실제로 무슨 일이 일어났나 |
|---|---|---|---|
| `38889c3b` | 73.39% | 듣기 기준 10개 vs `AUDIO_CALL_CAP = 3` | **한계가 풀렸다.** 듣기 호출 6회가 실제로 나갔고 듣기 항목 10개 중 5개를 통과했다(18점 중 9.0점). 압축 파일 안 오디오 배정(#65)과 캡 상향(#86)이 값을 했다 |
| `a73fbc98` | 76.74% | 렌더 대상 102개 vs cap 72 | **한계가 그대로다.** 시각 인식 호출이 **0회**, 시각 항목 34개가 **44점 만점에 0.0점**. 그런데도 과제 총점은 76.74% — 나머지 항목이 받쳐 준다 |
| `e222075d` | 21.67% | `required_visual_render_target_unavailable` | 그대로. 185개 중 세 번째로 낮다 |
| `75401f7c` | 45.18% | 같음 | 그대로 |
| `7de33b48` | 63.94% | 같음 | 그대로 |
| **다섯 개 평균** | **56.18%** | | 필수 항목 5개 중 2개 통과 |

**빼고 다시 계산한 결과** — 명세가 미달 시 하라고 지정한 절차다.

| | 과제 | 평균 | 필수 항목 통과율 |
|---|---|---|---|
| 전체 | 185 | **79.53%** | 0.6394 (227/355) |
| 다섯 개 제외 | 180 | **80.18%** | 0.6429 (225/350) |

**0.65pp.** 이 다섯이 천장을 끌어내리는 것은 사실이지만, 끌어내리는 양이 90%까지의
10.47pp 격차 중 6%에 불과하다. 미리 적어 둔 예측은 방향은 맞았고 크기는 틀렸다.

### 여섯 번째: `0e386e32` — 정답 파일이 zip이 아니다

실행 전 명단에 없던 과제 하나가 **0.00%** 를 받았다. 185개 중 유일한 0점이다.

```
selected_deliverables : PrivateCrypMixV2.zip  (kind: zip, single_primary)
selection_status      : ok
error                 : None
55개 항목 전부 fail, evidence: "BadZipFile: File is not a zip file"
```

채점기는 파일을 고르는 데 성공했고(`selection_status: ok`) 판정도 정상적으로
끝냈다(`error: None`). 열어 보니 zip이 아니었을 뿐이다. **채점기 결함도 도구
결함도 아니고 입력 결함이다** — 데이터셋이 실은 정답 파일이 손상돼 있다.

혼자서 평균을 **0.43pp** 끌어내린다(79.53% → 79.96%). 여섯 개를 전부 빼면
**80.62%** 이고, 90%까지는 여전히 9.4pp가 남는다.

> 이 과제는 여섯 번째 알려진 한계로 명세에 기록해야 한다. 별도 항목으로 남긴다.

## 필수 항목 통과율 0.6394 — 대부분이 기준 하나다

필수 항목(만점의 절대값 ≥ 4)은 355개이고 227개가 통과했다. 1단계의 0.5714보다
올랐지만 0.95에는 한참 못 미친다. **어디서 오는지가 한 줄로 나온다.**

```
35 / 119 통과  ·  "Overall formatting and style of the deliverable"
```

같은 문구의 기준 하나가 **185개 과제 중 119개**에 필수 항목으로 들어 있다. 필수
항목 355개 중 3분의 1이 이 한 문장이고, 그중 **84개가 떨어진다.** 이 기준을 빼고
세면 통과율은 192 / 236 = **0.8136** 으로 올라간다. 여전히 미달이지만, 0.6394와
0.95 사이 격차의 절반 이상이 **개별 과제의 실패가 아니라 코퍼스 전체에 반복되는
기준 하나**라는 뜻이다.

이건 채점기 결함이 아니다. rubric이 그렇게 쓰여 있고, 판정 모델은 정답 문서의
서식·문체가 그 기준을 만족하지 않는다고 본다. 다만 **이 지표를 "필수 항목 통과율"
이라고 부르면서 0.95를 요구하는 것이 타당한지**는 다시 볼 문제다. 한 기준이
분모의 3분의 1을 차지하면, 그 기준 하나의 판정 성향이 지표 전체를 지배한다.

### 판정 셈법에 대한 각주

분석 도구가 같이 내놓는 줄이다.

```
retired 'verdict == pass' spelling would say 187 of 357 (0.5238), differing on 54 item(s)
penalties  54 item(s) with a negative maximum, 7 of them fired
```

지금 규칙과 폐기된 규칙이 54개 항목에서 갈린다. 차이는 전부 **만점이 음수인 감점
항목**이다. 감점 기준에서 `fail`은 "감점 사유가 일어나지 않았다"는 뜻이므로
통과로, `pass`는 "감점 사유가 실제로 있었다"는 뜻이므로 실패로 세는 것이 옳다.
옛 철자는 `verdict == 'pass'`만 봤기 때문에 이 부호를 거꾸로 읽었다. 분모가
357에서 355로 주는 것은 점수에서 제외된 항목 2개 때문이다. 도구가 낸 0.6394는
payload가 자기 안에 기록한 값과 일치한다(`agrees_with_payload: true`).

## 만점 미달 2,467개 항목 — 도구 한계인가 실제 미흡인가

명세가 지정한 분류다. evidence 문자열에서 도구 실패 표지를 찾아 나눴다.

| | 항목 | 비중 | 잃은 점수 | 비중 | 과제 |
|---|---|---|---|---|---|
| 도구 실패 표지 없음 — 판정 모델이 읽고 미흡으로 봄 | 2,388 | 96.8% | 2,584.9 | 95.1% | 183 |
| zip을 열 수 없음 (`BadZipFile`) | 55 | 2.2% | 78.0 | 2.9% | 1 |
| 추출 가능한 텍스트 없음 | 24 | 1.0% | 56.0 | 2.1% | 11 |

**이것이 이 실행의 핵심 소견이다.** 1단계에서는 읽기 도구의 구멍 두 개를 고쳐
78.24% → 82.87%로 올렸다 — 즉 도구가 원인의 큰 몫이었다. 3단계에서 같은 잣대를
185개에 대면 **도구 실패 흔적이 남은 손실은 전체의 4.9%** 다. 그 사이 들어간
읽기 수정들(#61, #63, #64, #66, #67, #78~#81, #83)이 도구 원인을 거의 다 소진했다.

남은 두 갈래를 구분해 둔다.

- **`BadZipFile` 55개**는 도구 한계가 아니라 **입력 파손**이다. 어떤 라이브러리도
  zip이 아닌 파일을 zip으로 열 수 없다.
- **"추출 가능한 텍스트 없음" 24개**는 진짜 회색지대다. #64 이후 채점기는 빈 읽기를
  "내용이 없다"가 아니라 "이 파일에 추출 가능한 텍스트가 없다"로 정확히 보고하고,
  판정 모델은 그 보고를 받고도 항목을 못 채웠다고 본다. 56점, 전체 만점의 0.4%다.

**분류상 라이브러리 한계로 돌릴 수 있는 손실은 최대 56점(0.4%)이다.** 나머지
2,584.9점은 정답 문서가 rubric 기준을 실제로 못 채웠거나, 판정 모델이 못 채웠다고
본 것이다. 이 둘의 구분은 항목 단위 사람 검토 없이는 더 이상 좁힐 수 없고, 그건
이 단계의 범위 밖이다.

### 어떤 경로에서 새는가

| 경로 | 잃은 점수 |
|---|---|
| text | 2,296.2 |
| visual | 238.6 |
| formatting | 146.3 |
| audio | 23.7 |
| mixed | 14.1 |

손실의 **84.5%가 글 읽기 경로**다. 시각·듣기 경로를 아무리 고쳐도 천장은 크게
움직이지 않는다는 뜻이다 — 시각 238.6점을 전부 회수해도 평균은 1.7pp 오른다.

## sector별·직업별 — 어디가 끌어내리는가

| sector | 과제 | 평균 |
|---|---|---|
| Retail Trade | 16 | 85.11% |
| Finance and Insurance | 17 | 84.44% |
| Government | 22 | 82.90% |
| Wholesale Trade | 25 | 82.31% |
| Health Care and Social Assistance | 22 | 79.58% |
| Real Estate and Rental and Leasing | 20 | 78.74% |
| Professional, Scientific, and Technical Services | 24 | 75.90% |
| Manufacturing | 25 | 75.29% |
| Information | 14 | 71.75% |

폭은 13.4pp로, sector 사이 차이가 크지 않다. **끌어내리는 것은 sector가 아니라
직업이다.**

가장 낮은 다섯 직업:

| 직업 | 과제 | 평균 | 필수 항목 |
|---|---|---|---|
| Film and Video Editors | 3 | 50.81% | 3/6 |
| Real Estate Sales Agents | 4 | 63.60% | 2/3 |
| Project Management Specialists | 5 | 64.41% | 0/5 |
| First-Line Supervisors of Production and Operating Workers | 5 | 64.55% | 1/5 |
| Industrial Engineers | 5 | 67.21% | 0/3 |

가장 높은 다섯:

| 직업 | 과제 | 평균 | 필수 항목 |
|---|---|---|---|
| Nurse Practitioners | 3 | 91.90% | 1/2 |
| Pharmacists | 4 | 91.84% | 10/11 |
| Counter and Rental Clerks | 4 | 91.34% | 2/5 |
| Editors | 2 | 90.65% | 11/12 |
| Property, Real Estate, and Community Association Managers | 4 | 89.97% | 3/7 |

**Film and Video Editors 50.81%** 는 설명이 붙는다 — 3개 중 2개(`e222075d`,
`75401f7c`)가 미리 공개한 시각 렌더 한계 과제다. 나머지 낮은 직업들에는 그런
설명이 없다.

44개 직업 중 **90%를 넘는 직업은 4개**뿐이다. 185개 과제 중 90% 이상은 48개,
99% 이상은 3개, 정확히 만점은 **1개**(`854f3814`)다. 0점은 1개, 나머지 181개가
그 사이에 있다.

## 사용량과 청구액

| | 값 |
|---|---|
| 판정 호출 (전체) | **22,528** |
| ├ 본 판정 | 21,833 |
| └ 인식(perception) | 695 — 시각 660 · 듣기 25 · 혼합 10 |
| 렌더 호출 | 670 |
| 본 판정 입력 토큰 | 117,830,948 (그중 캐시 63,501,045) |
| 본 판정 출력 토큰 | 7,563,515 |
| 인식 입력 토큰 | 1,968,673 (그중 캐시 2,712) |
| 인식 출력 토큰 | 315,757 |
| 추론 토큰 (원장 합계) | 6,480,473 |
| 판정 지연 합계 | 154,378초 = 42.9시간 |
| 과제 채점 시간 합계 | 43.8시간 |
| `usage_complete` | **true** |

원장 행 22,528개를 전부 셌고 `record_type`은 전부 `call`, `state`는 전부
`settled`다. 모델은 `gpt-5.6-sol` 22,503건, `gpt-audio-1.5` 25건.

### 실제 청구액

```
estimated_cost_usd : null
pricing_complete   : false
unpriced_models    : ["gpt-5.6-sol", "gpt-audio-1.5"]
```

**22,528개 원장 행 전부**가 `missing_reasons: ["price_missing"]`을 달고 있다.
가격표(`price_table_sha256: f878bb9e…`)에 이 두 모델의 단가가 없기 때문이다.

**그러므로 이 실행의 달러 청구액은 이 저장소에서 계산되지 않는다.** 명세가 지시한
대로 `pricing_complete: false`로 남긴다. **0달러가 아니다** — 22,528번의 유료 호출과
약 1억 2,770만 토큰(입력 1억 1,980만 · 출력 788만)이 실제로 나갔고, 금액만 여기서
확정되지 않는다. 실제 금액은 Azure 구독 청구서에서 읽어야 하며, 이 저장소의 토큰
수가 그 청구서와 대조할 근거다.

## 실행 기록 — 무엇이 돌았고 무엇이 부서졌나

11개 shard를 stride(`tasks[i::11]`)로 나눠 병렬로 돌렸다. head sha `0c522d47`.

| | |
|---|---|
| 발주 | 11개 run, 12:11–12:12 |
| 정상 완료 | 10개, 15:30–17:00Z에 각자 청크 1개로 슬라이스 전부 완료 |
| shard 4 | 청크 0에서 17개 중 6개만 저장하고 시간 초과 (`72a99f1`, `partial chunk 0`) |
| shard 4 재개 | run `33422393221`, 17:57 자동 발주, 18:06:39 게이트 승인, 18:06:44–20:58:52 채점 |
| shard 4 결말 | **exit 128 — 채점을 다 끝내고 저장 직전에 죽었다** |
| shard 4 발표 | artifact에서 꺼내 PR #322로 올림 (`aa6fbcf`). 다시 채점하지 않음 |
| 합치기 | shard 0 재발행 run `33445681382`, 22:20–22:24Z, 새 채점 0건. 워크플로가 스스로 11개를 합쳐 `3230274` 발표 |

### exit 128의 원인

재개 청크는 채점을 전부 마쳤고 로컬 커밋 `d73cb3f`(29,075 삽입 / 56 삭제)까지
만들었다. 그다음 줄에서 죽었다.

```
error: cannot pull with rebase: You have unstaged changes.
error: Please commit or stash them.
```

`core/task_checkpoint.py`의 `discard_checkpoint()`가 느린 과제 `9e39df84`의
체크포인트 파일을 지웠다 — 그 과제를 끝냈으니 지우는 것이 맞다. 그런데 그 파일은
**청크 0이 커밋해 둔 파일**이었고, `grade-run.yml`의 커밋 단계는 `$GRADE_FILE`,
`$COST_LEDGER_FILE`, 그리고 값이 있을 때만 `$GRADE_PROGRESS_FILE` 세 개만
stage한다. 이번 run에서 `GRADE_PROGRESS_FILE`은 비어 있었다. 그래서 삭제가
staged되지 않은 채 남았고, `git pull --rebase`가 거부했다.

**느린 과제 하나를 구하려고 만든 장치가, 바로 그 과제의 결과를 발표하지 못하게
막았다.** (`309-task-internal-checkpoint.md`가 도입한 장치다.)

**돈은 잃지 않았다.** 결과가 artifact `grade-exp_gold_baseline-shard4of11`
(ID `9775455936`, 128,226 바이트)로 올라가 있었고, PR #322가 거기서 꺼내
main에 올렸다(`aa6fbcf`). 다시 채점하지 않았다.

PR #327(`55d0bb3`)이 이 결함을 닫았다. 커밋 단계가 **이 채점의 `_progress/`
디렉터리 안에서, 이 채점의 stem으로 시작하는 추적된 삭제만** 골라 stage한다.
`git add -A`가 아니다 — 11개 shard가 그 디렉터리를 공유하므로 범위를 넓히면 어떤
shard가 자기가 쓴 적도 없는 파일 상태를 근거로 형제의 삭제를 커밋할 수 있다.

`9e39df84`는 이번에 **82.30%** 로 채점을 마쳤다. `304-B-partial-blocked.md`가
"네 번 시도했고 네 번 다 같은 자리에서 멈췄다. 다섯 번째는 하지 않는다"고 접은
과제다. 다시 시도한 것이 아니라 **과제 내부 체크포인트(#309)가 들어간 뒤 처음으로
청크를 건너 완주했다** — 청크 0에서 시작해 청크 1에서 끝났다. 그 설계가 실제
유료 실행에서 작동한다는 것이 여기서 처음 확인됐다(`309`가 "여기까지는 전부 가짜
응답 위에서의 증명"이라고 남겨 둔 항목이다).

### 합치기 — 못 하던 일을, 고친 뒤 워크플로가 스스로 했다

합치기 단계는 죽은 job 안에 있으므로 돌지 않았다. 그런데 **돌았어도 실패했을
것이다.**

```
$ python batch-runner/step9_merge_shards.py <11개 shard> --output <...>
ERROR: shard merge failed: canonical corpus order cannot be reconstructed:
725760 candidate stride layouts exceeds the 200000 cap.
Pass --expected-task-ids with the canonical ordered task id list.
```

shard 파일은 정본 순서를 담지 않고 **그 순서의 해시만** 담는다. 그래서 step9는
어느 입력이 어느 stride 오프셋인지 순열로 뒤져서 맞춘다. 185개를 11개로 나누면
9개 shard가 17개씩, 2개가 16개씩 갖고, 경우의 수는 9! × 2! = **725,760** 으로
도구 상한 200,000을 넘는다. 이 상한은 9분할(4! × 5! = 2,880)을 기준으로 정해졌고
11분할로 옮길 때 다시 계산되지 않았다. **여태 드러나지 않은 이유는 불완전 union
가드가 늘 먼저 걸렸기 때문이다** — 완성된 corpus를 순서 복원까지 들고 간 실행이
이번이 처음이었다.

PR #324(`11edf25`)가 고쳤다. 상한을 올리는 방식이 아니다 — 12분할이면 12! = 4억
7,900만이라 같은 자리로 돌아온다. 대신 **정답을 먼저 넣어 본다.** 호출자는 shard를
파일명 순서(`shard-000`, `shard-001`, …)로 넘기고 그게 곧 stride 순서이므로, 항등
배치가 사실상 항상 답이고 해시 대조 한 번이면 끝난다. 상한은 이제 예외 경로만
지킨다. 추측이 틀리면 여전히 `expected_ordered_task_ids_sha256` 대조에서 걸러지므로
검사가 약해지지는 않는다.

그 고침 위에서 shard 0을 청크 1로 다시 띄웠다(run `33445681382`, head sha
`11edf256`, 22:20:40–22:24:00Z). **새로 채점한 것은 없다.** 청크 0이 17개를 이미
끝내 두었으므로 재발행만 했고, 커밋 `f191555`가 바꾼 것은 파일 한 줄이다.

```
-  "graded_at": "2026-08-31T15:30:07Z",
+  "graded_at": "2026-08-31T22:23:29Z",
```

바뀐 파일도 그 하나뿐이다 — 비용 원장은 손대지 않았다. 그리고 같은 job의 합치기
단계가 이번에는 끝까지 돌았다.

```
[merge] all 11 shard file(s) published; checking whether the corpus is complete
Merged 11 shard(s): tasks=185, avg_pct=79.53
[main 3230274] chore(grades): merge 11 shards for exp_gold_baseline via gold_ceiling_185_v2_sol_max.yaml
 1 file changed, 469752 insertions(+)
   f191555..3230274  main -> main
```

**이 보고서가 읽는 채점 결과는 저 `3230274`가 올린 파일이다.** 손으로 합친 것이
아니다. 결함이 열려 있는 동안 결과를 먼저 읽으려고 손으로 한 번 합쳐 두었지만,
발표된 것은 워크플로 자신의 출력이다. 커밋된 11개 shard로 로컬에서 다시 합치면
그 파일이 바이트 단위로 그대로 재현된다 — 합치기에는 자기 시각이 없다.

합치기 도구는 shard마다 `grader_source_hash`·스키마 버전·부분 상태·경로 정체성·
비용 합계·호출 합계·지연 합계를 대조하고 어긋나면 소리 내어 실패한다. 11개 전부
`config_hash: f9c5f7bab9bd1530`, `grader_source_hash: 79c2f503…`으로 통과했다.

다만 그 발표에는 빠진 것이 하나 있었다. step9는 합친 채점 결과 옆에 **합친 비용
원장**도 쓰고 payload가 그 파일 이름과 sha256을 적어 두는데, 커밋 단계는 채점
결과만 stage했다. 그래서 main에 올라온 첫 185개 완주 결과는 *이 저장소의 어느
복제본에도 없는 파일*을 가리키고 있었다. 아무것도 실패하지 않았고 앞으로도 실패할
일이 없다 — 누군가 비용을 검증하려 들기 전까지는. 이것이 PR #327이 닫은 두 번째
결함이고, 원장 파일도 같은 PR이 함께 올렸다. 새로 만든 것이 아니라 run
`33445681382`의 artifact에서 꺼낸 것이며, 그 사본과 커밋된 11개 shard의 독립
재합침과 payload가 이미 선언한 값이 셋 다 `1b1d2d19…`로 바이트까지 같다.

> 세 결함이 모두 닫혔다. 합치기는 PR #324가, 체크포인트와 원장은 PR #327이 닫았다.
> 셋 다 채점을 다 끝낸 뒤 *발표하는 자리*에서 터졌다는 공통점이 있다 — 채점기가
> 아니라 채점 결과를 남기는 배관이 이번 실행의 약한 고리였다.

### 오래된 형제 디렉터리는 섞이지 않았다

같은 진단 폴더 아래에 폐기된 두 회차가 남아 있다(`src_955be41e…` 22개 파일,
`src_ce7d4978…` 9개 파일). 섞일 수 없다. 출력 디렉터리 이름 자체가 설정 해시와
채점기 소스 해시를 담고, 합치기는 자기 `$SHARD_DIR` 안의 `shard-NNN-of-011.json`만
열거하며, 그래도 섞였다면 `_check_identity_fields`가 거부한다.

## 이전 문서 정정

이 실행이 앞선 문서·항목의 서술 몇 개를 뒤집는다. 여기 모아 둔다.

**1. `43dc9778` 0점은 내가 만든 회귀였고, 이번에 사라졌다.**
폐기된 회차에서 이 과제가 87.36% → 0.00%로 떨어졌다. 원인은 내가 #274에서
`core/grader_routing.py`에 넣은 변경이다. 이번 회차에서 **92.23%** 로 채점됐다.

**2. 그 0점이 "평균을 끌어내렸다"는 항목 #84의 전제는 틀렸다.**
시각 예산을 넘긴 과제는 0점으로 평균에 들어가는 것이 아니라 **집계에서 사라졌다**
(185 → 184). 그래서 평균이 낮아 보이는 것이 아니라 분모가 줄어 있었다.

**3. 발표된 `grader_source_hash`가 실제 값과 달랐다.**
명세와 PR #263이 `c3d1c821…`을 적었으나, 그 회차가 실제로 기록한 값은
`955be41e…`였다. 이번 회차의 값은 `79c2f5035c4aa826355134dd87cdb8fbc320e5a1cc5fde0d8ecf91957f4eabc6`
이고, 파일 이름·payload·shard 11개 전부에서 같은 값이다.

**4. 첫 아홉 개 payload는 중간에 병합된 PR들 때문에 버려졌다.**
#266–#272가 shard가 도는 중에 main에 들어가면서 채점기 소스 지문이 바뀌었고,
이미 채점된 아홉 개가 새 회차와 합쳐질 수 없게 됐다. 명세가 *"shard가 도는 동안
`core/`·`schemas/`·`prompts/`·`grading_configs/`·`grade-run.yml`을 병합하지 말 것"*
이라고 적어 둔 바로 그 사고다. 이번 회차는 그 규칙을 지켜 완주했다.

**5. `38889c3b`의 듣기 한계는 실행 전 예측보다 나아졌다.**
"듣기 기준 10개 vs `AUDIO_CALL_CAP = 3`"으로 적었으나, 실제로는 듣기 호출 6회가
나가 10개 중 5개를 통과했다. 압축 파일 안 오디오 배정과 캡 상향이 사이에 들어갔다.

**6. 이번 실행의 재채점 대상은 옛 174개와 정체성 두 필드가 다르다.**
`config_hash`(`f9c5f7bab9bd1530`)와 `grader_source_hash`(`79c2f503…`) 둘 다
바뀌었다. 그래서 옛 회차의 과제별 점수와 이번 점수를 항목 단위로 빼는 것은
의미가 없고, 이 문서는 그렇게 하지 않았다.

## 판정

| 임계값 | 결과 | 판정 |
|---|---|---|
| 평균 점수 ≥ 90% | 79.53% | **미달** |
| 필수 항목 통과율 ≥ 0.95 | 0.6394 | **미달** |
| 채점기 오류율 < 2% | 0.65% | **통과** |

**3단계는 통과하지 못했다.** 1단계와 같은 자로 쟀고, 같은 두 항목에서 미달이다.

미달의 성격을 명세가 요구한 세 갈래로 분류하면:

- **채점기 결함** — 아니다. 오류율 0.65%, 판정 실패 과제 0개, 3회 반복 실행의 최대
  표준편차 4.02pp(2단계). 채점기는 안정적으로 돌았다.
- **도구 결함** — 최대 56점(전체 만점의 0.4%). 1단계에서 큰 몫이었던 원인이
  그 사이의 읽기 수정들로 거의 소진됐다.
- **입력 결함** — `0e386e32`의 파손된 zip(78점) 하나가 명확하다. 미리 공개한
  다섯 개 한계는 합쳐서 0.65pp.

**그래서 남는 결론은 이렇다.** 정답 문서를 이 rubric으로 채점하면 79.53%가 나오고,
그중 도구·입력·채점기로 설명되는 몫은 1~2pp다. 나머지 8~9pp는 **정답 문서가
rubric 기준을 실제로 못 채우거나, 판정 모델이 못 채웠다고 보는 것**이다. 필수 항목
쪽은 절반 이상이 `"Overall formatting and style of the deliverable"` 기준 하나에서
나온다.

**이 값이 발표되는 모델 점수를 읽는 기준선이다.** 이 코퍼스에서 어떤 모델이 79.53%
근처를 받았다면, 그건 "정답만큼 잘했다"는 뜻이다.

## 도구가 낸 숫자 그대로

위의 모든 숫자는 여기서 나왔다. 손으로 옮겨 적으면 원본과 조용히 어긋날 수
있으므로, 분석 도구의 출력을 그대로 싣고 그 명령을 함께 적는다.
`test_full_gold_corpus_report_quotes_its_run.py`가 채점 결과 파일에 대해 이
명령을 다시 돌려 아래 블록과 글자 단위로 같은지 확인한다. 숫자 하나를 손으로
고치면 그 검사가 깨진다.

185개 과제 전부의 점수가 「Per task」에 있다. 만점 미달 항목은 2,467개라
위에서 12개만 보이고, 전부 보려면 같은 명령에 `--json`을 붙인다.

<!-- generated: python batch-runner/scripts/analyze_gold_ceiling.py data/grades/_diagnostic/cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_185_v2_sol_max__cfg_f9c5f7bab9bd1530__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_79c2f5035c4aa826__v2.2.json --shortfall-limit 12 -->
```text
Gold ceiling — stage 3 -- the whole 185-task gold population
============================================================
  experiment      exp_gold_baseline
  graded at       2026-08-31T22:23:29Z
  run status      final
  grader source   79c2f5035c4aa826355134dd87cdb8fbc320e5a1cc5fde0d8ecf91957f4eabc6
  renderer        LibreOffice 24.2.7.2 420(Build:2), pymupdf 1.28.2
  provenance      gold-corpus

Thresholds
------------------------------------------------------------
  mean score              79.53%   (needs >= 90.0%)   MISS
  required-item pass      0.6394   (needs >= 0.95)    MISS
  grader error rate       0.0065   (needs < 0.02)     PASS

Required items (|max score| >= 4)
------------------------------------------------------------
  227 of 355 passed  (0.6394)
  not scored              2 item(s) the grader excluded, kept out of the denominator
  penalties               54 item(s) with a negative maximum, 7 of them fired
  retired 'verdict == pass' spelling would say 187 of 357 (0.5238), differing on 54 item(s)
  verdicts                187 pass, 105 partial, 63 fail
   35/119 passed  ·  Overall formatting and style of the deliverable

Scores
------------------------------------------------------------
  graded 185 task(s), 0 in error; 3 perfect, 181 partial, 1 zero
  rubric item coverage    0.7123
  judge pass rate         0.7077
    Finance and Insurance                                84.44%  n=17
    Government                                           82.9%  n=22
    Health Care and Social Assistance                    79.58%  n=22
    Information                                          71.75%  n=14
    Manufacturing                                        75.29%  n=25
    Professional, Scientific, and Technical Services     75.9%  n=24
    Real Estate and Rental and Leasing                   78.74%  n=20
    Retail Trade                                         85.11%  n=16
    Wholesale Trade                                      82.31%  n=25

By occupation (44)
------------------------------------------------------------
   50.81%  n=3    required 3/6  ·  Film and Video Editors
   63.60%  n=4    required 2/3  ·  Real Estate Sales Agents
   64.41%  n=5    required 0/5  ·  Project Management Specialists
   64.55%  n=5    required 1/5  ·  First-Line Supervisors of Production and Operating Workers
   67.21%  n=5    required 0/3  ·  Industrial Engineers
   69.11%  n=4    required 44/51  ·  Real Estate Brokers
   69.29%  n=5    required 20/22  ·  Software Developers
   70.44%  n=5    required 2/5  ·  Mechanical Engineers
   70.45%  n=3    required 0/0  ·  News Analysts, Reporters, and Journalists
   71.42%  n=3    required 25/34  ·  Producers and Directors
   72.60%  n=3    required 0/2  ·  Financial and Investment Analysts
   75.66%  n=5    required 0/5  ·  First-Line Supervisors of Non-Retail Sales Workers
   75.78%  n=4    required 1/4  ·  Medical Secretaries and Administrative Assistants
   77.44%  n=5    required 3/14  ·  Medical and Health Services Managers
   78.00%  n=5    required 0/3  ·  Computer and Information Systems Managers
   78.18%  n=5    required 2/8  ·  First-Line Supervisors of Office and Administrative Support Workers
   78.77%  n=5    required 4/5  ·  Registered Nurses
   79.37%  n=5    required 13/16  ·  Administrative Services Managers
   79.45%  n=5    required 7/10  ·  Recreation Workers
   79.49%  n=5    required 3/5  ·  Sales Managers
   79.67%  n=4    required 2/3  ·  Concierges
   80.67%  n=5    required 0/4  ·  Order Clerks
   81.47%  n=3    required 0/2  ·  Financial Managers
   81.72%  n=3    required 1/2  ·  Audio and Video Technicians
   81.85%  n=5    required 0/4  ·  General and Operations Managers
   82.10%  n=5    required 3/5  ·  Accountants and Auditors
   82.15%  n=5    required 2/3  ·  Private Detectives and Investigators
   83.09%  n=4    required 3/4  ·  First-Line Supervisors of Police and Detectives
   85.61%  n=5    required 1/2  ·  Compliance Officers
   86.22%  n=5    required 0/4  ·  Buyers and Purchasing Agents
   86.84%  n=5    required 1/4  ·  Sales Representatives, Wholesale and Manufacturing, Technical and Scientific Products
   87.20%  n=2    required 1/2  ·  First-Line Supervisors of Retail Sales Workers
   87.49%  n=4    required 2/5  ·  Customer Service Representatives
   88.05%  n=5    required 30/34  ·  Shipping, Receiving, and Inventory Clerks
   88.14%  n=4    required 10/14  ·  Lawyers
   88.87%  n=5    required 11/16  ·  Sales Representatives, Wholesale and Manufacturing, Except Technical and Scientific Products
   89.05%  n=4    required 0/1  ·  Personal Financial Advisors
   89.06%  n=3    required 0/0  ·  Securities, Commodities, and Financial Services Sales Agents
   89.78%  n=3    required 3/3  ·  Child, Family, and School Social Workers
   89.97%  n=4    required 3/7  ·  Property, Real Estate, and Community Association Managers
   90.65%  n=2    required 11/12  ·  Editors
   91.34%  n=4    required 2/5  ·  Counter and Rental Clerks
   91.84%  n=4    required 10/11  ·  Pharmacists
   91.90%  n=3    required 1/2  ·  Nurse Practitioners

Subsets
------------------------------------------------------------
  83.48%   n=30   required 21/34  ·  the same thirty stage 1 graded
  56.18%   n=5    required 2/5  ·  the five declared input limits
  80.18%   n=180  required 225/350  ·  everything but those five

Usage
------------------------------------------------------------
  judge calls             22528 (21833 main, 695 perception)
    audio                25
    mixed                10
    visual               660
  main tokens             in 117830948, out 7563515, cached 63501045
  perception tokens       in 1968673, out 315757
  judge latency (total)   154378.13s
  usage complete          True

Bill
------------------------------------------------------------
  estimated cost          UNKNOWN — nothing in this run could be priced
  unpriced because        price_missing

Per task (worst first)
------------------------------------------------------------
  0e386e32-df20-4d1f-b536-7159bc409ad5    0.00%  0.00/78  ·  Software Developers
      55/55 item(s) below max, -78.0 point(s)
  6074bba3-7e3a-4b1c-b8c6-a15bb6695c3b    9.00%  4.50/50  ·  Real Estate Brokers
      2/48 item(s) below max, -45.5 point(s), required item failed
  e222075d-5d62-4757-ae3c-e34b0846583b   21.67%  13.00/60  ·  Film and Video Editors
      23/33 item(s) below max, -47.0 point(s), required item failed
  94925f49-36bc-42da-b45b-61078d329300   28.72%  23.55/82  ·  Real Estate Sales Agents
      48/56 item(s) below max, -58.45 point(s), required item failed
  5e2b6aab-f9fb-4dd6-a1a5-874ef1743909   36.24%  24.64/68  ·  Mechanical Engineers
      27/38 item(s) below max, -43.36 point(s)
  5d0feb24-e8b6-4ace-b64f-d5cd1a8b563d   44.69%  28.60/64  ·  News Analysts, Reporters, and Journalists
      27/46 item(s) below max, -35.4 point(s)
  75401f7c-396d-406d-b08e-938874ad1045   45.18%  25.30/56  ·  Film and Video Editors
      25/40 item(s) below max, -30.7 point(s), required item failed
  c6269101-fdc8-4602-b345-eac7597c0c81   46.37%  28.75/62  ·  Industrial Engineers
      22/31 item(s) below max, -33.25 point(s)
  c357f0e2-963d-4eb7-a6fa-3078fe55b3ba   49.97%  50.47/101  ·  Computer and Information Systems Managers
      42/70 item(s) below max, -50.5333 point(s), required item failed
  1752cb53-5983-46b6-92ee-58ac85a11283   50.62%  35.94/71  ·  First-Line Supervisors of Production and Operating Workers
      29/46 item(s) below max, -35.057 point(s), required item failed
  bf68f2ad-eac5-490a-adec-d847eb45bd6f   51.88%  29.05/56  ·  First-Line Supervisors of Production and Operating Workers
      25/40 item(s) below max, -26.95 point(s), required item failed
  e21cd746-404d-4602-b9d2-01d2812c5b87   52.31%  20.40/39  ·  Financial and Investment Analysts
      18/28 item(s) below max, -18.6 point(s), required item failed
  a079d38f-c529-436a-beca-3e291f9e62a3   53.69%  28.99/54  ·  Producers and Directors
      12/34 item(s) below max, -25.01 point(s), required item failed
  a69be28f-9a84-47c9-992e-b90446cdca9d   54.36%  54.90/101  ·  Sales Managers
      31/54 item(s) below max, -46.1 point(s)
  ce864f41-8584-49ba-b24f-9c9104b47bf0   54.40%  31.55/58  ·  Project Management Specialists
      28/39 item(s) below max, -26.45 point(s), required item failed
  46fc494e-a24f-45ce-b099-851d5c181fd4   54.87%  63.65/116  ·  Mechanical Engineers
      35/81 item(s) below max, -52.35 point(s), required item failed
  61e7b9c6-0051-429f-a341-fda9b6578a84   57.14%  36.00/63  ·  Medical and Health Services Managers
      15/19 item(s) below max, -27.0 point(s), required item failed
  40a99a31-42d6-4f23-b3ec-8f591afe25b6   57.74%  56.01/97  ·  Industrial Engineers
      29/64 item(s) below max, -40.99 point(s), required item failed
  efca245f-c24f-4f75-a9d5-59201330ab7a   58.45%  59.62/102  ·  First-Line Supervisors of Production and Operating Workers
      33/59 item(s) below max, -42.38 point(s), required item failed
  1aecc095-4d76-4b89-b752-1a0f870502cd   58.96%  53.06/90  ·  First-Line Supervisors of Office and Administrative Support Workers
      23/52 item(s) below max, -36.94 point(s), required item failed
  58ac1cc5-5754-4580-8c9c-8c67e1a9d619   60.18%  45.74/76  ·  Project Management Specialists
      22/41 item(s) below max, -30.26 point(s), required item failed
  b5d2e6f1-62a2-433a-bcdd-95b260cdd860   61.06%  39.69/65  ·  Order Clerks
      20/32 item(s) below max, -25.3082 point(s), required item failed
  27e8912c-8bd5-44ba-ad87-64066ea05264   61.32%  32.50/53  ·  Administrative Services Managers
      14/37 item(s) below max, -20.5 point(s), required item failed
  fd6129bd-f095-429b-873c-dcc3137be2c3   61.63%  53.00/86  ·  Project Management Specialists
      35/64 item(s) below max, -33.0 point(s), required item failed
  be830ca0-b352-4658-a5bd-57139d6780ba   63.22%  48.68/77  ·  Industrial Engineers
      29/55 item(s) below max, -28.32 point(s), required item failed
  7de33b48-5163-4f50-b5f3-8deea8185e57   63.94%  33.25/52  ·  Software Developers
      14/39 item(s) below max, -18.75 point(s), required item failed
  83d10b06-26d1-4636-a32c-23f92c57f30b   64.84%  40.85/63  ·  Accountants and Auditors
      15/38 item(s) below max, -22.15 point(s), required item failed
  90edba97-74f0-425a-8ff6-8b93182eb7cb   65.12%  87.26/134  ·  Registered Nurses
      33/71 item(s) below max, -46.74 point(s), required item failed
  e996036e-8287-4e7f-8d0a-90a57cb53c45   65.52%  50.45/77  ·  First-Line Supervisors of Non-Retail Sales Workers
      18/50 item(s) below max, -26.55 point(s), required item failed
  1bff4551-1d54-4e37-b2e0-d5c3f2ea4a45   65.70%  28.25/43  ·  Recreation Workers
      12/29 item(s) below max, -14.75 point(s), required item failed
  2fa8e956-7b35-4c13-95dc-027f02be318b   66.18%  21.84/33  ·  Concierges
      12/28 item(s) below max, -11.16 point(s)
  a45bc83b-22f9-4def-8d89-9c5661b2b86f   66.59%  57.93/87  ·  Computer and Information Systems Managers
      35/72 item(s) below max, -29.07 point(s), required item failed
  6a900a40-8d2b-4064-a5b1-13a60bc173d8   67.65%  34.50/51  ·  Sales Representatives, Wholesale and Manufacturing, Technical and Scientific Products
      13/32 item(s) below max, -16.5 point(s), required item failed
  f1be6436-ffff-4fee-9e66-d550291a1735   67.70%  50.10/74  ·  Medical Secretaries and Administrative Assistants
      22/47 item(s) below max, -23.9 point(s)
  b39a5aa7-cd1b-47ad-b249-90afd22f8f21   68.31%  42.35/62  ·  Financial Managers
      13/32 item(s) below max, -19.65 point(s)
  4b98ccce-9e42-44e9-9115-6fc3e79de288   68.72%  35.73/52  ·  Medical Secretaries and Administrative Assistants
      15/31 item(s) below max, -16.2667 point(s), required item failed
  3f821c2d-ab97-46ec-a0fb-b8f73c2682bc   69.69%  56.45/81  ·  First-Line Supervisors of Non-Retail Sales Workers
      25/46 item(s) below max, -24.55 point(s), required item failed
  76418a2c-a3c0-4894-b89d-2493369135d9   70.21%  50.55/72  ·  Shipping, Receiving, and Inventory Clerks
      14/56 item(s) below max, -21.45 point(s), required item failed
  0fad6023-767b-42c1-a1b3-027cd4f583cb   70.94%  46.82/66  ·  General and Operations Managers
      19/44 item(s) below max, -19.18 point(s), required item failed
  02aa1805-c658-4069-8a6a-02dec146063a   71.10%  61.15/86  ·  Project Management Specialists
      25/71 item(s) below max, -24.85 point(s), required item failed
  6436ff9e-c5f2-47ba-9aaa-49d89b0594ab   71.67%  45.15/63  ·  General and Operations Managers
      19/51 item(s) below max, -17.85 point(s), required item failed
  f9f82549-fdde-4462-aff8-e70fba5b8c66   71.67%  23.65/33  ·  Private Detectives and Investigators
      7/26 item(s) below max, -9.35 point(s)
  ec591973-04d5-48c0-981c-1ab2fcec2dc1   72.01%  55.45/77  ·  First-Line Supervisors of Non-Retail Sales Workers
      24/68 item(s) below max, -21.55 point(s), required item failed
  e4f664ea-0e5c-4e4e-a0d3-a87a33da947a   72.13%  123.33/171  ·  Producers and Directors
      12/50 item(s) below max, -47.665 point(s), required item failed
  38889c3b-e3d4-49c8-816a-3cc8e5313aba   73.39%  45.50/62  ·  Audio and Video Technicians
      10/35 item(s) below max, -16.5 point(s)
  dfb4e0cd-a0b7-454e-b943-0dd586c2764c   73.68%  28.00/38  ·  Compliance Officers
      8/26 item(s) below max, -10.0 point(s)
  90f37ff3-e4ed-4a0b-94bb-bed0f7def1ef   74.24%  43.80/59  ·  Real Estate Sales Agents
      11/30 item(s) below max, -15.2 point(s)
  17111c03-aac7-45c2-857d-c06d8223d6ad   74.42%  44.65/60  ·  Administrative Services Managers
      17/44 item(s) below max, -15.35 point(s)
  5ad0c554-a7a2-48cd-b41a-ebc1bff4a9de   74.44%  46.90/63  ·  Real Estate Sales Agents
      21/60 item(s) below max, -16.1 point(s)
  a10ec48c-168e-476c-8fe3-23b2a5f616ac   74.54%  26.09/35  ·  Concierges
      10/22 item(s) below max, -8.91 point(s), required item failed
  3c19c6d1-672c-467a-8437-6fe21afb8eae   74.75%  59.05/79  ·  Project Management Specialists
      16/41 item(s) below max, -19.95 point(s), required item failed
  3baa0009-5a60-4ae8-ae99-4955cb328ff3   75.27%  42.15/56  ·  News Analysts, Reporters, and Journalists
      15/49 item(s) below max, -13.85 point(s)
  dd724c67-8118-4b99-ab50-4761af705c3b   75.62%  41.59/55  ·  Registered Nurses
      14/31 item(s) below max, -13.41 point(s)
  0353ee0c-18b5-4ad3-88e8-e001d223e1d7   75.91%  81.22/107  ·  First-Line Supervisors of Office and Administrative Support Workers
      36/69 item(s) below max, -25.78 point(s)
  a73fbc98-90d4-4134-a54f-2b1d0c838791   76.74%  33.00/43  ·  Recreation Workers
      6/63 item(s) below max, -10.0 point(s)
  11593a50-734d-4449-b5b4-f8986a133fd8   77.02%  40.82/53  ·  Real Estate Sales Agents
      16/29 item(s) below max, -12.18 point(s)
  74d6e8b0-f334-4e7e-af55-c095d5d4d1a6   77.30%  53.34/69  ·  Medical and Health Services Managers
      20/54 item(s) below max, -15.66 point(s)
  81db15ff-ceea-4f63-a1cd-06dc88114709   77.39%  53.40/69  ·  Medical and Health Services Managers
      11/58 item(s) below max, -15.6 point(s)
  4c18ebae-dfaa-4b76-b10c-61fcdf26734c   77.68%  53.60/69  ·  Compliance Officers
      19/50 item(s) below max, -15.4 point(s)
  d025a41c-c439-4ee1-bc79-dd5c94b27a2d   78.15%  55.49/71  ·  Customer Service Representatives
      17/60 item(s) below max, -15.5125 point(s), required item failed
  46bc7238-3501-4839-b989-e2bd47853676   78.28%  52.45/67  ·  Real Estate Brokers
      14/46 item(s) below max, -14.55 point(s)
  7d7fc9a7-21a7-4b83-906f-416dea5ad04f   78.63%  74.70/95  ·  Accountants and Auditors
      16/56 item(s) below max, -20.3 point(s), required item failed
  a74ead3b-f67d-4b1c-9116-f6bb81b29d4f   78.71%  66.90/85  ·  Child, Family, and School Social Workers
      18/57 item(s) below max, -18.1 point(s)
  8a7b6fca-60cc-4ae3-b649-971753cbf8b9   78.72%  30.70/39  ·  Industrial Engineers
      9/31 item(s) below max, -8.3 point(s)
  11e1b169-5fb6-4d79-8a83-82ddf4987a85   78.93%  59.20/75  ·  First-Line Supervisors of Police and Detectives
      18/60 item(s) below max, -15.8 point(s)
  3600de06-3f71-4e48-9480-e4828c579924   78.96%  41.85/53  ·  Personal Financial Advisors
      19/42 item(s) below max, -11.15 point(s)
  ab81b076-e5d8-473a-9bdb-7ea7c38f6ebc   79.04%  41.10/52  ·  Sales Representatives, Wholesale and Manufacturing, Except Technical and Scientific Products
      10/39 item(s) below max, -10.9 point(s)
  68d8d901-dd0b-4a7e-bf9a-1074fddf1a96   79.48%  68.35/86  ·  First-Line Supervisors of Production and Operating Workers
      16/61 item(s) below max, -17.65 point(s), required item failed
  74ed1dc7-1468-48a8-9071-58775c0d667a   79.59%  39.00/49  ·  Sales Managers
      11/35 item(s) below max, -10.0 point(s), required item failed
  a46d5cd2-55fe-48fa-a4c6-6aaf6b9991b5   79.66%  58.15/73  ·  Private Detectives and Investigators
      15/56 item(s) below max, -14.85 point(s), required item failed
  a95a5829-34bb-40f3-993b-558aed6dcdef   79.67%  35.85/45  ·  First-Line Supervisors of Police and Detectives
      13/29 item(s) below max, -9.15 point(s)
  650adcb1-ed19-4f88-8117-77640f7b94b6   79.76%  98.11/123  ·  Recreation Workers
      15/48 item(s) below max, -24.89 point(s), required item failed
  f841ddcf-2a28-4f6d-bac3-61b607219d3e   79.94%  70.35/88  ·  Order Clerks
      16/59 item(s) below max, -17.65 point(s), required item failed
  69a8ef86-4e69-4fe2-9168-080f1e978e67   80.23%  51.35/64  ·  Sales Managers
      15/47 item(s) below max, -12.65 point(s), required item failed
  1137e2bb-bdf9-4876-b572-f29b7de5e595   80.62%  64.50/80  ·  Order Clerks
      18/62 item(s) below max, -15.5 point(s)
  8314d1b1-5b0f-42a4-b5d5-91c0867b0913   80.85%  94.60/117  ·  Lawyers
      15/43 item(s) below max, -22.4 point(s), required item failed
  105f8ad0-8dd2-422f-9e88-2be5fbd2b215   81.19%  78.75/97  ·  Sales Representatives, Wholesale and Manufacturing, Except Technical and Scientific Products
      13/46 item(s) below max, -18.25 point(s), required item failed
  cecac8f9-8203-4ebd-ad49-54436a8c4171   81.27%  60.95/75  ·  First-Line Supervisors of Retail Sales Workers
      13/55 item(s) below max, -14.05 point(s)
  41f6ef59-88c9-4b2c-bcc7-9ceb88422f48   81.62%  53.87/66  ·  Medical Secretaries and Administrative Assistants
      14/39 item(s) below max, -12.13 point(s), required item failed
  99ac6944-4ec6-4848-959c-a460ac705c6f   81.76%  67.04/82  ·  Audio and Video Technicians
      20/52 item(s) below max, -14.96 point(s)
  24d1e93f-9018-45d4-b522-ad89dfd78079   81.83%  67.10/82  ·  Buyers and Purchasing Agents
      21/52 item(s) below max, -14.9 point(s), required item failed
  116e791e-890c-42b1-ba90-1db02e8bfd45   81.95%  52.45/64  ·  Registered Nurses
      14/46 item(s) below max, -11.55 point(s)
  ee09d943-5a11-430a-b7a2-971b4e9b01b5   81.98%  48.37/59  ·  Accountants and Auditors
      11/44 item(s) below max, -10.632 point(s)
  327fbc21-7d26-4964-bf7c-f4f41e55c54d   82.21%  103.58/126  ·  First-Line Supervisors of Non-Retail Sales Workers
      21/66 item(s) below max, -22.418 point(s), required item failed
  9e39df84-ac57-4c9b-a2e3-12b8abf2c797   82.30%  79.01/96  ·  First-Line Supervisors of Production and Operating Workers
      18/57 item(s) below max, -16.99 point(s)
  6dcae3f5-bf1c-48e0-8b4b-23e6486a934c   82.46%  53.60/65  ·  First-Line Supervisors of Office and Administrative Support Workers
      11/43 item(s) below max, -11.4 point(s), required item failed
  c7d83f01-2874-4876-b7fd-52582ec99e1a   82.55%  43.75/53  ·  Financial and Investment Analysts
      12/43 item(s) below max, -9.25 point(s)
  46b34f78-6c06-4416-87e2-77b6d8b20ce9   82.95%  71.34/86  ·  Financial and Investment Analysts
      15/53 item(s) below max, -14.66 point(s), required item failed
  57b2cdf2-ad62-4591-aa91-aad489740320   83.39%  49.20/59  ·  Private Detectives and Investigators
      11/45 item(s) below max, -9.8 point(s)
  7151c60a-d4cb-4fc4-8169-3d4cb446e6b9   83.81%  35.20/42  ·  Registered Nurses
      8/33 item(s) below max, -6.8 point(s)
  f5d428fd-b38e-41f0-8783-35423dab80f6   83.94%  44.49/53  ·  Concierges
      13/39 item(s) below max, -8.51 point(s)
  1d4672c8-b0a7-488f-905f-9ab4e25a19f7   84.07%  49.60/59  ·  Securities, Commodities, and Financial Services Sales Agents
      8/43 item(s) below max, -9.4 point(s)
  01d7e53e-0513-4109-a242-8ccaf442cd21   84.23%  70.75/84  ·  Recreation Workers
      16/65 item(s) below max, -13.25 point(s)
  bb863dd9-31c2-4f64-911a-ce11f457143b   84.43%  81.90/97  ·  Sales Representatives, Wholesale and Manufacturing, Technical and Scientific Products
      9/53 item(s) below max, -15.1 point(s), required item failed
  7bbfcfe9-132d-4194-82bb-d6f29d001b01   84.53%  44.80/53  ·  Compliance Officers
      11/40 item(s) below max, -8.2 point(s), required item failed
  4520f882-715a-482d-8e87-1cb3cbdfe975   84.73%  148.27/175  ·  Financial Managers
      17/88 item(s) below max, -26.73 point(s), required item failed
  1b1ade2d-f9f6-4a04-baa5-aa15012b53be   84.84%  58.54/69  ·  Buyers and Purchasing Agents
      17/51 item(s) below max, -10.46 point(s), required item failed
  cebf301e-5ea7-41ae-b117-ad8f43e7ac22   84.84%  52.60/62  ·  Computer and Information Systems Managers
      8/35 item(s) below max, -9.4 point(s)
  ffed32d8-d192-4e3f-8cd4-eda5a730aec3   85.00%  64.60/76  ·  Pharmacists
      10/46 item(s) below max, -11.4 point(s)
  a0552909-bc66-4a3a-8970-ee0d17b49718   85.10%  81.69/96  ·  Medical Secretaries and Administrative Assistants
      7/50 item(s) below max, -14.3083 point(s), required item failed
  a99d85fc-eff8-48d2-a7d4-42a75d62f18d   85.10%  65.53/77  ·  Property, Real Estate, and Community Association Managers
      12/52 item(s) below max, -11.47 point(s), required item failed
  61b0946a-5c1c-4bf6-8607-84d7c7e0dfe0   85.37%  69.15/81  ·  Medical and Health Services Managers
      16/50 item(s) below max, -11.85 point(s), required item failed
  a0ef404e-82a6-4507-bff1-633d7c8e0004   85.52%  49.60/58  ·  Counter and Rental Clerks
      10/41 item(s) below max, -8.4 point(s), required item failed
  87da214f-fd92-4c58-9854-f4d0d10adce0   85.57%  63.32/74  ·  Customer Service Representatives
      15/59 item(s) below max, -10.68 point(s), required item failed
  8c8fc328-69fc-4559-a13f-82087baef0a1   85.59%  43.65/51  ·  Film and Video Editors
      8/30 item(s) below max, -7.35 point(s), required item failed
  a328feea-47db-4856-b4be-2bdc63dd88fb   85.83%  20.60/24  ·  Administrative Services Managers
      4/16 item(s) below max, -3.4 point(s)
  84322284-5c2c-4873-b507-b147449d209d   86.03%  62.80/73  ·  Private Detectives and Investigators
      13/51 item(s) below max, -10.2 point(s)
  22c0809b-f8db-489e-93b3-b4da225e3e0e   86.12%  88.70/103  ·  First-Line Supervisors of Police and Detectives
      9/58 item(s) below max, -14.3 point(s), required item failed
  40a8c4b1-b169-4f92-a38b-7f79685037ec   86.20%  96.54/112  ·  First-Line Supervisors of Office and Administrative Support Workers
      22/72 item(s) below max, -15.46 point(s), required item failed
  a97369c7-e5cf-40ca-99e8-d06f81c57d53   86.23%  108.65/126  ·  Lawyers
      12/44 item(s) below max, -17.35 point(s)
  0419f1c3-d669-45d0-81cd-f4d5923b06a5   86.24%  73.30/85  ·  Property, Real Estate, and Community Association Managers
      15/52 item(s) below max, -11.7 point(s), required item failed
  552b7dd0-96f4-437c-a749-0691e0e4b381   86.27%  69.88/81  ·  Shipping, Receiving, and Inventory Clerks
      12/63 item(s) below max, -11.12 point(s)
  3940b7e7-ec4f-4cea-8097-3ab4cfdcaaa6   86.30%  75.08/87  ·  Mechanical Engineers
      13/55 item(s) below max, -11.92 point(s), required item failed
  5a2d70da-0a42-4a6b-a3ca-763e03f070a5   86.56%  77.90/90  ·  Mechanical Engineers
      11/64 item(s) below max, -12.1 point(s)
  93b336f3-61f3-4287-86d2-87445e1e0f90   86.64%  65.85/76  ·  Buyers and Purchasing Agents
      11/53 item(s) below max, -10.15 point(s), required item failed
  aa071045-bcb0-4164-bb85-97245d56287e   86.92%  74.75/86  ·  Counter and Rental Clerks
      12/63 item(s) below max, -11.25 point(s)
  4d61a19a-8438-4d4c-9fc2-cf167e36dcd6   86.96%  60.00/69  ·  General and Operations Managers
      4/43 item(s) below max, -9.0 point(s), required item failed
  c44e9b62-7cd8-4f72-8ad9-f8fbddb94083   87.02%  101.81/117  ·  Administrative Services Managers
      14/44 item(s) below max, -15.19 point(s), required item failed
  3f625cb2-f40e-4ead-8a97-6924356d5989   87.17%  66.25/76  ·  Lawyers
      16/64 item(s) below max, -9.75 point(s)
  0ec25916-1b5c-4bfe-93d3-4e103d860f3a   87.37%  58.54/67  ·  Registered Nurses
      14/42 item(s) below max, -8.46 point(s)
  4d1a8410-e9c5-4be5-ab43-cc55563c594c   87.38%  158.16/181  ·  First-Line Supervisors of Office and Administrative Support Workers
      14/64 item(s) below max, -22.8367 point(s), required item failed
  1a78e076-445e-4c5d-b8ce-387d2fe5e715   87.41%  74.30/85  ·  Nurse Practitioners
      11/63 item(s) below max, -10.7 point(s), required item failed
  15ddd28d-8445-4baa-ac7f-f41372e1344e   87.54%  49.90/57  ·  Buyers and Purchasing Agents
      10/46 item(s) below max, -7.1 point(s)
  eb54f575-93f9-408b-b9e0-f1208a0b6759   87.62%  55.20/63  ·  First-Line Supervisors of Police and Detectives
      10/53 item(s) below max, -7.8 point(s)
  9a0d8d36-6233-4c76-9107-0d1f783c7340   87.88%  45.70/52  ·  Personal Financial Advisors
      12/40 item(s) below max, -6.3 point(s), required item failed
  8077e700-2b31-402d-bd09-df4d33c39653   88.21%  59.10/67  ·  Mechanical Engineers
      14/44 item(s) below max, -7.9 point(s)
  f84ea6ac-8f9f-428c-b96c-d0884e30f7c7   88.28%  51.20/58  ·  Administrative Services Managers
      5/30 item(s) below max, -6.8 point(s), required item failed
  6241e678-4ba3-4831-b3c7-78412697febc   88.43%  144.14/163  ·  Producers and Directors
      12/60 item(s) below max, -18.86 point(s), required item failed
  788d2bc6-82df-4dc7-8467-a0f31405dc14   88.69%  74.50/84  ·  Sales Managers
      8/48 item(s) below max, -9.5 point(s)
  3a4c347c-4aec-43c7-9a54-eb1f816ab1f9   88.72%  65.65/74  ·  Editors
      8/54 item(s) below max, -8.35 point(s), required item failed
  62f04c2f-e0f7-4710-876c-54ee9c2e8256   88.87%  80.87/91  ·  First-Line Supervisors of Non-Retail Sales Workers
      12/53 item(s) below max, -10.13 point(s), required item failed
  045aba2e-4093-42aa-ab7f-159cc538278c   89.73%  65.50/73  ·  Pharmacists
      7/34 item(s) below max, -7.5 point(s)
  c2e8f271-7858-412f-b460-472463ad81d9   89.78%  72.72/81  ·  Computer and Information Systems Managers
      12/67 item(s) below max, -8.28 point(s), required item failed
  8f9e8bcd-6102-40da-ab76-23f51d8b21fa   89.80%  44.00/49  ·  General and Operations Managers
      4/33 item(s) below max, -5.0 point(s), required item failed
  bb499d9c-0263-4684-9238-75e8e86077b1   89.83%  79.95/89  ·  Securities, Commodities, and Financial Services Sales Agents
      9/61 item(s) below max, -9.05 point(s)
  02314fc6-a24e-42f4-a8cd-362cae0f0ec1   89.86%  31.45/35  ·  General and Operations Managers
      5/28 item(s) below max, -3.55 point(s)
  b9665ca1-4da4-4ff9-86f2-40b9a8683048   89.99%  71.99/80  ·  Industrial Engineers
      11/59 item(s) below max, -8.01 point(s)
  ae0c1093-5ea8-4b84-a81e-53ebf7a4321d   90.00%  19.80/22  ·  Private Detectives and Investigators
      3/14 item(s) below max, -2.2 point(s)
  c9bf9801-9640-45fa-8166-1ab01f2d98e4   90.00%  55.80/62  ·  Medical and Health Services Managers
      7/47 item(s) below max, -6.2 point(s)
  f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb   90.00%  71.10/79  ·  Audio and Video Technicians
      8/51 item(s) below max, -7.9 point(s), required item failed
  47ef842d-8eac-4b90-bda8-dd934c228c96   90.10%  89.20/99  ·  Order Clerks
      8/58 item(s) below max, -9.8 point(s), required item failed
  05389f78-589a-473c-a4ae-67c61050bfca   90.23%  79.40/88  ·  Buyers and Purchasing Agents
      12/66 item(s) below max, -8.6 point(s), required item failed
  a4a9195c-5ebe-4b8d-a0c2-4a6b7a49da8b   90.32%  56.00/62  ·  Shipping, Receiving, and Inventory Clerks
      11/55 item(s) below max, -6.0 point(s)
  fe0d3941-e32c-4bf1-a643-b566d2b4cb3c   90.62%  43.50/48  ·  Sales Representatives, Wholesale and Manufacturing, Technical and Scientific Products
      3/27 item(s) below max, -4.5 point(s)
  4122f866-01fa-400b-904d-fa171cdab7c7   90.74%  212.34/234  ·  Software Developers
      15/65 item(s) below max, -21.66 point(s), required item failed
  403b9234-6299-4b5f-a106-70c1bc11ec4c   90.83%  49.05/54  ·  Recreation Workers
      3/17 item(s) below max, -4.95 point(s), required item failed
  d7cfae6f-4a82-4289-955e-c799dfe1e0f4   91.01%  114.67/126  ·  Sales Representatives, Wholesale and Manufacturing, Except Technical and Scientific Products
      9/63 item(s) below max, -11.33 point(s), required item failed
  61717508-4df7-41be-bf97-318dfb2475c0   91.25%  58.40/64  ·  Customer Service Representatives
      7/42 item(s) below max, -5.6 point(s), required item failed
  b78fd844-db76-448e-a783-5e9877cb74c2   91.36%  69.43/76  ·  Financial Managers
      11/51 item(s) below max, -6.57 point(s), required item failed
  60221cd0-686e-4a08-985e-d9bb2fa18501   91.38%  26.50/29  ·  News Analysts, Reporters, and Journalists
      3/20 item(s) below max, -2.5 point(s)
  ed2bc14c-99ac-4a2a-8467-482a1a5d67f3   91.57%  49.45/54  ·  Property, Real Estate, and Community Association Managers
      8/36 item(s) below max, -4.55 point(s), required item failed
  c3525d4d-2012-45df-853e-2d2a0e902991   91.63%  78.80/86  ·  Order Clerks
      9/52 item(s) below max, -7.2 point(s), required item failed
  2c249e0f-4a8c-4f8e-b4f4-6508ba29b34f   91.76%  67.90/74  ·  Software Developers
      7/50 item(s) below max, -6.1 point(s)
  43dc9778-450b-4b46-b77e-b6d82b202035   92.23%  111.60/121  ·  Accountants and Auditors
      7/67 item(s) below max, -9.4 point(s)
  9a8c8e28-ce76-408b-83c3-488422892e58   92.58%  139.80/151  ·  Editors
      7/67 item(s) below max, -11.2 point(s)
  bbe0a93b-ebf0-40b0-98dc-8d9243099034   92.80%  75.17/81  ·  Child, Family, and School Social Workers
      7/61 item(s) below max, -5.83 point(s)
  7b08cd4d-df60-41ae-9102-8aaa49306ba2   92.81%  82.60/89  ·  Accountants and Auditors
      5/59 item(s) below max, -6.4 point(s)
  15d37511-75c5-4c7f-81f1-16e00c0d95f3   92.84%  101.20/109  ·  Sales Representatives, Wholesale and Manufacturing, Technical and Scientific Products
      9/56 item(s) below max, -7.8 point(s), required item failed
  0112fc9b-c3b2-4084-8993-5a4abb1f54f1   93.11%  61.45/66  ·  Nurse Practitioners
      8/55 item(s) below max, -4.55 point(s)
  211d0093-2c64-4bd0-828c-0201f18924e7   93.14%  47.50/51  ·  First-Line Supervisors of Retail Sales Workers
      6/40 item(s) below max, -3.5 point(s), required item failed
  4c4dc603-c21c-4284-8fb1-1b827c1fddf4   93.27%  48.50/52  ·  Securities, Commodities, and Financial Services Sales Agents
      4/37 item(s) below max, -3.5 point(s)
  fd3ad420-6f7d-43b1-a990-c0c5c047d071   93.55%  29.00/31  ·  Real Estate Brokers
      1/21 item(s) below max, -2.0 point(s)
  b7a5912e-0e63-41f5-8c22-9cdb8f46ab01   93.77%  106.90/114  ·  Counter and Rental Clerks
      3/59 item(s) below max, -7.1 point(s), required item failed
  fccaa4a1-1c39-49ac-b701-55361a19966b   94.02%  50.77/54  ·  Concierges
      6/40 item(s) below max, -3.23 point(s)
  8384083a-c31b-4194-80ba-4d335a444918   94.07%  59.27/63  ·  Pharmacists
      5/47 item(s) below max, -3.7334 point(s)
  11dcc268-cb07-4d3a-a184-c6d7a19349bc   94.19%  121.50/129  ·  Shipping, Receiving, and Inventory Clerks
      2/27 item(s) below max, -7.5 point(s), required item failed
  b3573f20-5d3e-4954-948f-9461fda693d2   94.59%  35.00/37  ·  Sales Managers
      1/17 item(s) below max, -2.0 point(s)
  664a42e5-3240-413a-9a57-ea93c6303269   94.60%  47.30/50  ·  Personal Financial Advisors
      6/42 item(s) below max, -2.7 point(s)
  c657103b-b348-4496-a848-b2b7165d28b2   94.74%  54.95/58  ·  Personal Financial Advisors
      6/36 item(s) below max, -3.05 point(s)
  7ed932dd-244f-4d61-bf02-1bc3bab1af14   94.94%  80.70/85  ·  Sales Representatives, Wholesale and Manufacturing, Except Technical and Scientific Products
      4/55 item(s) below max, -4.3 point(s), required item failed
  0ed38524-a4ad-405f-9dee-7b2252659aad   95.00%  49.40/52  ·  Customer Service Representatives
      2/28 item(s) below max, -2.6 point(s)
  1b9ec237-bf9c-41f9-8fa9-0e685fcd93c6   95.17%  56.15/59  ·  Nurse Practitioners
      4/47 item(s) below max, -2.85 point(s)
  2d06bc0a-89c6-4e89-9417-5ffe725c1bc6   95.61%  63.10/66  ·  Real Estate Brokers
      2/34 item(s) below max, -2.9 point(s), required item failed
  2696757c-1f8a-4959-8f0d-f5597b9e70fc   95.85%  39.30/41  ·  Compliance Officers
      2/25 item(s) below max, -1.7 point(s)
  36d567ba-e205-4313-9756-931c6e4691fe   96.30%  52.00/54  ·  Compliance Officers
      1/27 item(s) below max, -2.0 point(s)
  1e5a1d7f-12c1-48c6-afd9-82257b3f2409   96.97%  32.00/33  ·  Property, Real Estate, and Community Association Managers
      1/18 item(s) below max, -1.0 point(s), required item failed
  76d10872-9ffa-4ede-83ee-e0f1ec5e2b8d   97.84%  144.80/148  ·  Child, Family, and School Social Workers
      5/74 item(s) below max, -3.2 point(s)
  19403010-3e5c-494e-a6d3-13594e99f6af   98.19%  121.75/124  ·  Sales Representatives, Wholesale and Manufacturing, Except Technical and Scientific Products
      2/63 item(s) below max, -2.25 point(s), required item failed
  aad21e4c-1d43-45fc-899a-97754a1b1b63   98.31%  124.85/127  ·  Lawyers
      5/84 item(s) below max, -2.15 point(s)
  f2986c1f-2bbf-4b83-bc93-624a9d617f45   98.57%  154.75/157  ·  Pharmacists
      1/77 item(s) below max, -2.25 point(s), required item failed
  b57efde3-26d6-4742-bbff-2b63c43b4baa   98.67%  74.00/75  ·  Sales Representatives, Wholesale and Manufacturing, Technical and Scientific Products
      2/62 item(s) below max, -1.0 point(s)
  2ea2e5b5-257f-42e6-a7dc-93763f28b19d   98.82%  84.00/85  ·  Computer and Information Systems Managers
      1/60 item(s) below max, -1.0 point(s)
  476db143-163a-4537-9e21-fe46adad703b   99.14%  63.45/64  ·  Counter and Rental Clerks
      1/28 item(s) below max, -0.55 point(s), required item failed
  5349dd7b-bf0a-4544-9a17-75b7013767e6   99.26%  147.90/149  ·  Shipping, Receiving, and Inventory Clerks
      1/94 item(s) below max, -1.1 point(s), required item failed
  854f3814-681c-4950-91ac-55b0db0e3781  100.00%  33.00/33  ·  Software Developers
      0/23 item(s) below max, -0.0 point(s)

Shortfalls
------------------------------------------------------------
  2467 of 8816 rubric item(s) scored below their maximum, losing 2718.9011 point(s)
  required item failed in 99 task(s):
      83d10b06-26d1-4636-a32c-23f92c57f30b, 7d7fc9a7-21a7-4b83-906f-416dea5ad04f, f84ea6ac-8f9f-428c-b96c-d0884e30f7c7
      27e8912c-8bd5-44ba-ad87-64066ea05264, c44e9b62-7cd8-4f72-8ad9-f8fbddb94083, f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb
      1b1ade2d-f9f6-4a04-baa5-aa15012b53be, 93b336f3-61f3-4287-86d2-87445e1e0f90, 24d1e93f-9018-45d4-b522-ad89dfd78079
      05389f78-589a-473c-a4ae-67c61050bfca, 7bbfcfe9-132d-4194-82bb-d6f29d001b01, c2e8f271-7858-412f-b460-472463ad81d9
      c357f0e2-963d-4eb7-a6fa-3078fe55b3ba, a45bc83b-22f9-4def-8d89-9c5661b2b86f, a10ec48c-168e-476c-8fe3-23b2a5f616ac
      a0ef404e-82a6-4507-bff1-633d7c8e0004, b7a5912e-0e63-41f5-8c22-9cdb8f46ab01, 476db143-163a-4537-9e21-fe46adad703b
      61717508-4df7-41be-bf97-318dfb2475c0, 87da214f-fd92-4c58-9854-f4d0d10adce0, d025a41c-c439-4ee1-bc79-dd5c94b27a2d
      3a4c347c-4aec-43c7-9a54-eb1f816ab1f9, 8c8fc328-69fc-4559-a13f-82087baef0a1, e222075d-5d62-4757-ae3c-e34b0846583b
      75401f7c-396d-406d-b08e-938874ad1045, e21cd746-404d-4602-b9d2-01d2812c5b87, 46b34f78-6c06-4416-87e2-77b6d8b20ce9
      b78fd844-db76-448e-a783-5e9877cb74c2, 4520f882-715a-482d-8e87-1cb3cbdfe975, ec591973-04d5-48c0-981c-1ab2fcec2dc1
      62f04c2f-e0f7-4710-876c-54ee9c2e8256, 3f821c2d-ab97-46ec-a0fb-b8f73c2682bc, e996036e-8287-4e7f-8d0a-90a57cb53c45
      327fbc21-7d26-4964-bf7c-f4f41e55c54d, 6dcae3f5-bf1c-48e0-8b4b-23e6486a934c, 1aecc095-4d76-4b89-b752-1a0f870502cd
      40a8c4b1-b169-4f92-a38b-7f79685037ec, 4d1a8410-e9c5-4be5-ab43-cc55563c594c, 22c0809b-f8db-489e-93b3-b4da225e3e0e
      bf68f2ad-eac5-490a-adec-d847eb45bd6f, efca245f-c24f-4f75-a9d5-59201330ab7a, 68d8d901-dd0b-4a7e-bf9a-1074fddf1a96
      1752cb53-5983-46b6-92ee-58ac85a11283, 211d0093-2c64-4bd0-828c-0201f18924e7, 8f9e8bcd-6102-40da-ab76-23f51d8b21fa
      0fad6023-767b-42c1-a1b3-027cd4f583cb, 4d61a19a-8438-4d4c-9fc2-cf167e36dcd6, 6436ff9e-c5f2-47ba-9aaa-49d89b0594ab
      40a99a31-42d6-4f23-b3ec-8f591afe25b6, be830ca0-b352-4658-a5bd-57139d6780ba, 8314d1b1-5b0f-42a4-b5d5-91c0867b0913
      46fc494e-a24f-45ce-b099-851d5c181fd4, 3940b7e7-ec4f-4cea-8097-3ab4cfdcaaa6, 61b0946a-5c1c-4bf6-8607-84d7c7e0dfe0
      61e7b9c6-0051-429f-a341-fda9b6578a84, 41f6ef59-88c9-4b2c-bcc7-9ceb88422f48, a0552909-bc66-4a3a-8970-ee0d17b49718
      4b98ccce-9e42-44e9-9115-6fc3e79de288, 1a78e076-445e-4c5d-b8ce-387d2fe5e715, b5d2e6f1-62a2-433a-bcdd-95b260cdd860
      f841ddcf-2a28-4f6d-bac3-61b607219d3e, 47ef842d-8eac-4b90-bda8-dd934c228c96, c3525d4d-2012-45df-853e-2d2a0e902991
      9a0d8d36-6233-4c76-9107-0d1f783c7340, a46d5cd2-55fe-48fa-a4c6-6aaf6b9991b5, 6241e678-4ba3-4831-b3c7-78412697febc
      e4f664ea-0e5c-4e4e-a0d3-a87a33da947a, a079d38f-c529-436a-beca-3e291f9e62a3, 02aa1805-c658-4069-8a6a-02dec146063a
      fd6129bd-f095-429b-873c-dcc3137be2c3, ce864f41-8584-49ba-b24f-9c9104b47bf0, 58ac1cc5-5754-4580-8c9c-8c67e1a9d619
      3c19c6d1-672c-467a-8437-6fe21afb8eae, a99d85fc-eff8-48d2-a7d4-42a75d62f18d, 1e5a1d7f-12c1-48c6-afd9-82257b3f2409
      0419f1c3-d669-45d0-81cd-f4d5923b06a5, ed2bc14c-99ac-4a2a-8467-482a1a5d67f3, 2d06bc0a-89c6-4e89-9417-5ffe725c1bc6
      6074bba3-7e3a-4b1c-b8c6-a15bb6695c3b, 94925f49-36bc-42da-b45b-61078d329300, 403b9234-6299-4b5f-a106-70c1bc11ec4c
      1bff4551-1d54-4e37-b2e0-d5c3f2ea4a45, 650adcb1-ed19-4f88-8117-77640f7b94b6, 90edba97-74f0-425a-8ff6-8b93182eb7cb
      f2986c1f-2bbf-4b83-bc93-624a9d617f45, 74ed1dc7-1468-48a8-9071-58775c0d667a, 69a8ef86-4e69-4fe2-9168-080f1e978e67
      d7cfae6f-4a82-4289-955e-c799dfe1e0f4, 19403010-3e5c-494e-a6d3-13594e99f6af, 7ed932dd-244f-4d61-bf02-1bc3bab1af14
      105f8ad0-8dd2-422f-9e88-2be5fbd2b215, 15d37511-75c5-4c7f-81f1-16e00c0d95f3, bb863dd9-31c2-4f64-911a-ce11f457143b
      6a900a40-8d2b-4064-a5b1-13a60bc173d8, 5349dd7b-bf0a-4544-9a17-75b7013767e6, 11dcc268-cb07-4d3a-a184-c6d7a19349bc
      76418a2c-a3c0-4894-b89d-2493369135d9, 7de33b48-5163-4f50-b5f3-8deea8185e57, 4122f866-01fa-400b-904d-fa171cdab7c7

  -20.0 of 20  [fail, formatting, decided by judge]  e4f664ea-0e5c-4e4e-a0d3-a87a33da947a
      criterion  The screenplay’s plot does follows the "Narrative-style Treatment:" found in
                 SAINTLINESS_StoryBreakdownCharacterDescriptions.pdf (e.g., stated character names,
                 relationships, or key beats)
      evidence   Andy looks through the hole, he sees Janie laying on the bed with the man moving back and
                 forth on top of her.
  -16.0 of 16  [fail, text, decided by judge]  e4f664ea-0e5c-4e4e-a0d3-a87a33da947a
      criterion  The screenplay’s characters do not contradict explicit facts in
                 SAINTLINESS_StoryBreakdownCharacterDescriptions.pdf (e.g., stated character names,
                 relationships, or key beats)
      evidence   He brings his eye to the peep hole on the door, John and Jane waiting to enter room #9 right
                 next to him. Janie struggles with the lock
  -15.0 of 15  [fail, text, decided by judge]  e222075d-5d62-4757-ae3c-e34b0846583b
      criterion  All footage is from royalty-free platforms such as but not limited to Pexels, Pixabay,
                 Unsplash, etc.
      evidence   “this file carries no extractable text, NOT that the content is absent”
  -8.0 of 8  [fail, text, decided by judge]  4122f866-01fa-400b-904d-fa171cdab7c7
      criterion  Terraform creates a Route 53 verification TXT record at _amazonses.<domain> using the
                 aws_ses_domain_identity verification token
      evidence   name = aws_ses_domain_mail_from.ses_domain_mail_from.mail_from_domain type = "TXT" ttl =
                 "600" records = [ "v=spf1 include:amazonses.com ~all"]
  -5.0 of 5  [fail, text, decided by judge]  11dcc268-cb07-4d3a-a184-c6d7a19349bc
      criterion  For item P07-P98K45-20, includes 500 in the Qty Moved column
      evidence   P07-P98K45-20,Interior Rail, Left side,500,Dock C,#N/A,250,250
  -5.0 of 5  [fail, visual, decided by judge]  4d61a19a-8438-4d4c-9fc2-cf167e36dcd6
      criterion  Overall formatting and style of the deliverable
      evidence   split_children: see child_grades for 2 per-target evidence entries
  -5.0 of 5  [fail, text, decided by judge]  6074bba3-7e3a-4b1c-b8c6-a15bb6695c3b
      criterion  Includes 3 to 5 active or pending listings in the “3. Active & Pending Listings” section.
      evidence   Total # of Listings | 10
  -5.0 of 5  [fail, text, decided by judge]  6241e678-4ba3-4831-b3c7-78412697febc
      criterion  The calendar contains only the project tasks listed in the prompt and no unrelated events.
      evidence   Internal Creative Workshop Internal creative review Client Pitch Meeting Client Pitch Review
  -5.0 of 5  [fail, visual, decided by judge]  be830ca0-b352-4658-a5bd-57139d6780ba
      criterion  Overall formatting and style of the deliverable
      evidence   Red section headings overlap body text and divider lines; the bottom-left paragraph is
                 clipped by the dark footer, with uneven spacing throughout.
  -5.0 of 5  [fail, text, decided by judge]  efca245f-c24f-4f75-a9d5-59201330ab7a
      criterion  In Scenario 1, grill guard production meets the requirement of at least 100 units per week on
                 a consistent cadence (e.g., in weekly buckets defined in the worksheet)
      evidence   ,2018-02-01 00:00:00,120,855,960,0,555,1410,,120,Grill Guard Production moved to another
                 production cell
  -5.0 of 5  [fail, text, decided by judge]  f84ea6ac-8f9f-428c-b96c-d0884e30f7c7
      criterion  Structures the final Scan of Research so that it fits within one page.
      evidence   "converted_page_count": 2
  -4.2 of 6  [partial, text, decided by judge]  e4f664ea-0e5c-4e4e-a0d3-a87a33da947a
      criterion  Writes Andy as being an unreliable witness.
      evidence   “But the scream quickly turns to a playful giggle.”
  ... and 2455 more (use --json for all of them)
```

## 재현

```
grade file    data/grades/_diagnostic/cef3a5b9…/exp_gold_baseline__judge_gpt-5_6-sol__
              gold_ceiling_185_v2_sol_max__cfg_f9c5f7bab9bd1530__rubric_11e7900c…__
              inference_11e7900c…__src_79c2f503…__v2.2.json
sha256        381c38089b45a33e20c3af636c289599078707d14a4069cf4031111ef8f055a0
cost ledger   같은 이름 + .cost_ledger.jsonl   (22,528행)
sha256        1b1d2d198ad034ddad703e27b7905176306be18b08ccb76f04e509d20a45192c
```

| 지문 | 값 |
|---|---|
| `expected_ordered_task_ids_sha256` | `cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18` |
| `gold_file_set_sha256` | `50b5e30b6a77bbaccb58a5e7c534a49258b048ba4aada79d7d9be744ab7e6983` |
| `grader_source_hash` | `79c2f5035c4aa826355134dd87cdb8fbc320e5a1cc5fde0d8ecf91957f4eabc6` |
| grading config | `gold_ceiling_185_v2_sol_max.yaml` (`f9c5f7bab9bd1530`) |
| rubric / inference 커밋 | `11e7900cdcac61bc4daf59e65feb238acda98fbf` |
| 판정 모델 | `gpt-5.6-sol`, responses API `2025-04-01-preview`, effort `max`, temp 0, seed 42 |
| 인식 모델 | 시각 `gpt-5.6-sol` (cap 72/과제, 파일 10개), 듣기 `gpt-audio-1.5` (cap 32, 30초) |
| 렌더러 | `LibreOffice 24.2.7.2 420(Build:2)`, pymupdf 1.28.2 |
| 컨테이너 | `ghcr.io/hyeonsangjeon/gdpval-grading@sha256:0f6782c056e31e1ea1d693fc2f8f873da160b232926fa1b6cde75c24e5344a04` |
| 출처 | `gold-corpus` — 진단 경로에만 저장, 대시보드에 실리지 않음 |
| `run_status` | `final`, shard 11개, 185개 전부 `selection_status: ok` |
| rubric 규모 | 항목 8,816개 — 명세가 실행 전 적어 둔 8,816과 일치 |

위 두 지문은 성격이 다르다. `expected_ordered_task_ids_sha256`은 **채점기가 직접
쓰는 값**이라 grade 파일 안에 그대로 들어 있고 출력 디렉터리 이름도 이것이다 —
다음 실행이 같은 185개를 같은 순서로 잡았는지 필드 대 필드로 비교된다.
`gold_file_set_sha256`은 파이프라인에 대응 필드가 없고 명세가 정의한 값이다
(파일마다 `graded_path\tsha256\tsize`를 과제 순서로 개행 연결한 문자열의 SHA-256).
채점한 **답안 바이트**가 같은지를 재는 유일한 수단이므로, 자기 자신끼리만 비교된다.
둘 다 커밋된 매니페스트와 grading config만으로 다시 계산되며, 623MB짜리 원본
파일은 필요 없다.

컨테이너와 렌더러 판은 「같은 조건에서 다시 돌렸다」가 말이 되게 하는 나머지 절반이다.
이미지 digest가 다르면 LibreOffice도 pymupdf도 같다는 보장이 없고, 그러면 시각
항목의 점수 차이가 채점기 탓인지 렌더러 탓인지 가릴 수 없다.

숫자를 다시 내려면:

```bash
python batch-runner/scripts/analyze_gold_ceiling.py <grade file>
```
