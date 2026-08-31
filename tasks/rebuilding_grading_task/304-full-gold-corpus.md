# 304 — Full Gold Corpus Ceiling

> PR3 / 3 of 4. SPEC §7-1. Stage 1 = `300-gold-ceiling.md`, Stage 2 = `303-variance-and-error.md`.

## 목적

1단계는 30개 과제에서 천장을 쟀고 **82.87%** 가 나왔다. 3단계는 1단계가 미룬 질문 하나에 답한다: **그 숫자가 나머지 전부에서도 유지되는가.**

1단계 표본은 데이터셋 행 순서 앞에서부터 잘랐다. 재현하기 쉬운 대신 좁다 — 연속된 행이 직업을 공유하기 때문이다. 저장소가 이 성질을 이미 알고 있다. `step8_grade._shard_slice`가 shard를 연속 구간이 아니라 stride로 자르는 이유를 이렇게 적어 두었다: *"the corpus carries whatever ordering bias the source dataset had (sector runs, difficulty drift)".* 같은 편향이 1단계 표본을 **9개 sector 중 4개, 44개 직업 중 7개**로 눌렀다.

그러니 82.87%는 직업의 6분의 1에서 잰 천장이다. 3단계는 44개 직업 전부에서 다시 잰다.

## Acceptance

1단계와 **같은 세 임계값**을 쓴다. 새로 정하지 않는다 — 같은 자로 재야 두 숫자를 나란히 놓을 수 있기 때문이다.

- gold 평균 pct **≥ 90%**
- 필수 항목 통과율 **≥ 0.95**
- grader 오류율 **< 2%**

1단계 실적은 82.87% / 0.5714 / 0.14% 로 셋 중 하나만 통과했다. 3단계의 판정은 통과·미달만이 아니다. **범위를 넓혔을 때 숫자가 어느 쪽으로 움직이는가**가 실제로 알고 싶은 것이다.

- 비슷하게 유지되면 → 82.87%는 grader의 실제 천장이고, 1단계의 좁은 표본이 원인이 아니었다.
- 크게 떨어지면 → 1단계 표본이 쉬운 쪽이었다는 뜻이고, 이미 발표된 모델 점수는 더 낮은 천장 기준으로 다시 읽어야 한다.
- 크게 오르면 → 1단계 표본에 특이하게 어려운 과제가 몰려 있었다는 뜻이다. 어느 과제인지 지목할 수 있어야 한다.

미달 시 grader 결함인지, 입력 결함인지, 도구 결함인지 분류해 보고한다.

---

## 고정 계약 (Stage 3, 185-task)

1단계와 같은 규칙이다. 움직일 수 있는 것은 전부 커밋된 파일에서 다시 계산되며, `batch-runner/tests/test_full_gold_corpus_contract.py`가 어긋나면 실패한다.

### 무엇을 채점하는가

| 항목 | 고정값 | 어디에 박혀 있나 |
|---|---|---|
| 데이터셋 | `openai/gdpval` | `experiments/exp_gold_baseline.yaml` |
| 데이터셋 커밋 | `11e7900cdcac61bc4daf59e65feb238acda98fbf` | grading config `rerun_identity` |
| rubric 커밋 | 같은 커밋 (`main` 아님) | grading config `rubric.revision` |
| parquet 파일 지문 | `f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202` | `experiments/gold_corpus/gold_deliverable_manifest.json` |
| 채점 대상 | **185 task** | grading config `rerun_identity.task_ids` |
| 채점 설정 | `grading_configs/gold_ceiling_185_v2_sol_max.yaml` | — |
| grader 소스 지문 | 실행 시 계산되어 파일명과 grade JSON에 기록 | `compute_grader_source_hash` |
| 컨테이너 이미지 | `ghcr.io/hyeonsangjeon/gdpval-grading@sha256:0f6782c0…` (digest 고정) | `.github/workflows/grade-run.yml` |
| LibreOffice | `LibreOffice 24.2.7.2 420(Build:2)` | `scripts/preflight_grading_renderer.py`, 이미지 빌드 시 검증 |

1단계·2단계와 **데이터셋 커밋이 같다.** 다른 커밋이면 같은 corpus를 잰 것이 아니므로 82.87%와 비교할 수 없다.

### 어떤 185개인가 — 표본이 아니라 전수

데이터셋 자기 행 순서대로 걸어가며 **실제로 gold 답안이 있는 과제를 전부** 담는다. 220개 중 185개가 그렇다.

빠진 35개의 유일한 사유는 **채점할 것이 없다**는 것이다. 데이터셋이 답안 파일을 하나도 싣지 않은 과제는 그 답안을 기준으로 채점할 수 없다. 다른 사유는 없고, 있다면 그건 선택이므로 변호가 필요하다. `test_the_thirty_five_left_out_are_exactly_the_ones_with_no_expert_answer`가 양방향으로 검사한다 — 답안 있는데 빠진 과제도, 답안 없는데 들어온 과제도 없어야 한다.

**그래서 185는 표본이 아니라 모집단이다.** 1단계는 앞에서 잘랐으니 잘라낸 이유를 변호해야 했다. 3단계는 남는 것이 없으므로 변호할 자름이 없다.

### 35개를 빼도 범위가 줄지 않는다

이것이 220개를 묻는 질문에 185개로 답해도 되는 근거다.

| | 과제 | sector | 직업 |
|---|---|---|---|
| 전체 | 220 | 9 | 44 |
| **gold 보유 (3단계)** | **185** | **9** | **44** |
| 1단계 표본 | 30 | 4 | 7 |

**개수가 같은 게 아니라 집합이 같다.** `test_dropping_the_thirty_five_costs_no_sector_and_no_occupation`이 (sector, 직업) 쌍 집합의 동등성으로 검사한다. 빠진 35개가 어떤 sector나 직업을 데리고 나갔다면 3단계는 남은 것에 대해서만 말할 수 있고, 숫자를 인용할 때마다 그 구멍을 같이 말해야 했을 것이다. 그렇지 않다.

1단계 대비 격차 — sector 4→9, 직업 7→44 — 가 3단계에 돈을 쓰는 이유 전부다. 그래서 산문이 아니라 `test_stage_ones_sample_reached_far_less_than_this`로 박아 두었다. 나중에 표본이 넓어지면 이 테스트가 빨개지고, 이 문서의 논거는 조용히 거짓이 되는 대신 다시 써야 한다.

### 1단계의 30개는 이 185개의 앞 30개

두 숫자가 비교 가능하려면 두 실행이 **포개져** 있어야 한다. 82.87%는 30개에서 나왔고, 3단계가 그 측정의 확장이려면 그 30개가 같은 순서로 안에 들어 있어야 한다. `test_stage_one_graded_the_first_thirty_of_exactly_these_tasks`가 검사한다.

순서도 계약의 일부다. `step8_grade.py`는 (a) 원본 순서를 따르지 않는 목록을 거부하고, (b) 고정 목록과 선택된 목록을 순서까지 포함해 동등 비교한다. 재정렬은 조용히 다른 실행이 되는 대신 거부된다.

### 입력 지문

| 지문 | 값 |
|---|---|
| `ordered_task_ids_sha256` | `cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18` |
| `gold_file_set_sha256` | `50b5e30b6a77bbaccb58a5e7c534a49258b048ba4aada79d7d9be744ab7e6983` |

정의는 1단계와 같다.

- `ordered_task_ids_sha256` = 185개 task id를 순서대로 담은 compact JSON 배열
  (`json.dumps(ids, ensure_ascii=False, separators=(",", ":"))`)의 SHA-256.
  **채점기가 직접 쓰는 값**이다 — `step8_grade._ordered_task_ids_sha256`가 계산해
  모든 grade JSON의 `expected_ordered_task_ids_sha256`에 넣고, 출력 디렉터리
  이름도 이 값이 된다.
- `gold_file_set_sha256` = 각 파일의 `graded_path\tsha256\tsize`를 task 순서대로
  개행으로 이어 붙인 문자열의 SHA-256. **이 문서가 정의한 값**이고, 파이프라인에
  대응 필드가 없어 자기 자신끼리만 비교한다.

두 값 모두 매니페스트와 grading config만으로 다시 계산된다 — 623MB짜리 원본 파일 없이도 검증 가능하다. 같은 정의를 1단계 30개에 적용하면 `82d14ac9…` / `cd4448b4…`가 그대로 재현되므로, 계산 방식이 바뀐 것이 아니라 대상이 넓어진 것임을 확인할 수 있다.

### 전수 구성

**파일 248개 / 623,241,071 바이트.** 1단계 표본은 40개 / 184,099,078 바이트였다.

확장자: pdf 85, xlsx 65, docx 64, pptx 17, zip 5, png 3, mp4 2, ipynb 1, py 1, jpg 1, overpassql 1, md 1, txt 1, yaml 1.

sector: Manufacturing 25, Wholesale Trade 25, Professional·Scientific·Technical Services 24, Government 22, Health Care and Social Assistance 22, Real Estate and Rental and Leasing 20, Finance and Insurance 17, Retail Trade 16, Information 14.

rubric 규모: **항목 8,816개 / 만점 14,198점.** 1단계는 1,433개 / 2,243점이었다.

### 알려진 입력 한계 (실행 전 공개)

1단계의 규칙을 따른다 — **실행 후에 이유를 만들어내는 것과 미리 예측해두는 것은 증거로서 값이 다르다.** 아래는 유료 실행 전에 무료 planner(`plan_task_runtime`)를 185개 전부에 돌려 measured한 것이고, 어느 것도 이번에 빼지 않는다.

planner 오류는 **5개 과제에 12건** 남아 있다. 전부 이번 단계 범위 밖의 기존 한계다.

| 과제 | 무엇이 | 왜 남는가 |
|---|---|---|
| `38889c3b` | 듣기 기준 10개 vs `AUDIO_CALL_CAP = 3` | 179.7MB `.zip` 한 개가 답안. 압축 파일 **안**은 읽힌다(1단계에서 고침, WAV stem 5개 48kHz/24bit 확인). 그러나 `grader_routing`·`deliverable_selector`에게는 여전히 확장자 `.zip` 파일 하나라 듣기 모델이 배정되지 않는다. 1단계에서 62점 만점에 2.00점이었고, 남은 28점은 실제로 들어야 답할 수 있다. |
| `a73fbc98` | 렌더 대상 102개 vs cap 72 | 과제 하나가 캡보다 큰 시각 자료를 요구한다. |
| `e222075d`, `75401f7c`, `7de33b48` | `required_visual_render_target_unavailable` | 필수 시각 항목의 렌더 대상이 없다. |

이 다섯은 3단계 천장을 **아래로** 끌어내린다. 1단계 표본에는 `38889c3b` 하나만 들어 있었으므로, 넓히면서 네 개가 새로 들어온다. 평균이 82.87%보다 낮게 나오면 **먼저 이 네 개를 빼고 다시 계산해** 얼마가 이들 탓인지 분리해 보고한다.

#### 실행 후 추가 — 여섯 번째 한계 `0e386e32` (예측하지 못했다)

위 표는 유료 실행 **전에** 적은 것이고 그대로 둔다. 이 항목만 실행 뒤에 붙이며, 예측된 다섯 개와 섞지 않는다.

| 과제 | 무엇이 | 왜 planner가 못 봤나 |
|---|---|---|
| `0e386e32-df20-4d1f-b536-7159bc409ad5` | 정답 파일 `PrivateCrypMixV2.zip`이 **zip이 아니다** | planner는 배정(어느 모델이 무엇을 보는가)을 재고, 파일을 열어 보지는 않는다. 이 파일은 이름·확장자·선택 단계까지 전부 정상으로 보이고, 열 때 비로소 `BadZipFile`이 난다. |

결과: 185개 중 **유일한 0점**. 항목 55개가 전부 같은 이유로 떨어지고 78.0점을 잃는다. `selection_status: ok`, 과제 `error: None` — 어디에도 경보가 뜨지 않는다. 채점기가 아니라 **입력이 부서진** 경우다.

뺄셈은 두 번 한다. 예측한 다섯만 빼면 79.53% → **80.18%**(n=180)이고, 예측 못 한 여섯 번째까지 빼면 **80.62%**(n=179)다. 미리 알던 다섯이 0.65%p, 실행하고서야 안 하나가 0.44%p — 합쳐도 1.1%p다. 3단계가 90%에 못 미친 이유는 알려진 한계가 아니라는 근거가 된다.

### 결과가 발표되지 않는 이유

`step8_grade.py`는 `gold-corpus` 출처의 모든 실행을 진단 경로(`data/grades/_diagnostic/…`)로 보낸다. 대시보드에는 "이건 천장이지 경쟁자가 아니다"라고 말할 방법이 없다.

여기에 두 번째 근거가 겹친다. **185는 gold 모집단 전부이면서 동시에 채점 payload의 부분집합이다.** 모순처럼 보이지만 아니다. `gold_rows_from_parquet`은 220행을 전부 남기고 답안 없는 35행에 `no_gold_deliverable`을 달아 두는데, 그 이유를 자기 docstring에 적어 두었다: *"Dropping them would make a pinned 30-task selection read as the whole corpus downstream, and a subset that calls itself complete is published as a final grade instead of a diagnostic one."*

그래서 scope는 30개일 때와 똑같이 `subset`이고, 출처와 범위 **두 가지** 이유로 진단 경로에 떨어진다. `test_pinning_every_gold_task_is_still_a_subset_of_the_graded_payload`가 이걸 박아 둔다 — 나중에 누가 빈 행을 "정리"하면 이 실행이 조용히 발표 가능한 성적으로 승격되기 때문이다.

### 실행 계획

커밋된 220-task Sol Max 실행 기준으로 task당 평균 19.44분이다. **185개면 약 60시간 직렬.**

**11 shard**로 나눈다. `grade-run.yml`이 허용하는 최대값이고, 워크플로 자신이 그 이유를 적어 두었다: *"shard_count is capped at 11 against a ~71.6h serial projection, so no sharding choice makes a 220-task run fit in one chunk."*

| | 값 |
|---|---|
| shard당 과제 | 16–17개 (stride `tasks[i::11]`) |
| 가장 큰 shard | 17개 ≈ **5.5시간** |
| 청크 예산 | `GRADER_TIME_BUDGET_SEC=20280` = **5시간 38분** |
| job 제한시간 | `timeout-minutes: 359` = **5.98시간** |
| 자동 재개 상한 | 청크 **10개** |

> 이 두 숫자는 처음에 18000/350이었고 #279에서 한 번, #280에서 또 한 번, 그리고 여기서 세 번째로 올라갔다. 세 번 다 같은 이유다 — shard 4의 과제 `9e39df84` 하나가 청크 안에 들어가지 않았다. **올릴 수 있는 한계는 여기까지다.** 아래 뺄셈이 360에서 남는 것을 전부 쓴다. 이 값으로 4차를 돌린 결과는 아래 「`9e39df84` — 네 번 시도하고 접는다」에 있다.

진짜로 지켜야 하는 부등식은 shard 크기가 아니다. 시간 예산은 **채점 단위 사이에서만** 검사되므로, 청크는 예산을 넘긴 뒤 최대 한 단위만큼 더 돈다. 그러므로 **예산 + 그 한 단위 + 저장 시간이 제한시간 안에 들어와야 한다.** 넘치면 shard는 채점 도중 살해당하고, **아무것도 저장하지 못한 채 이미 쓴 돈은 전부 날아간다.**

```
360    플랫폼 강제 종료 (연장 불가)
 -1    우리 timeout이 먼저 걸리도록 남기는 몫
       (우리가 멈추면 always() 업로드가 돌고, 플랫폼이 죽이면 안 돈다)
───
359    timeout-minutes
 -6.3  setup — checkout·pip·HF 다운로드. 측정된 grade job 10건 중 최악값
       (2.85~6.27분). #280은 여기에 단일 표본 4.2를 썼고, 그래서 최악의
       경우가 356.3분으로 355분 제한을 넘고 있었다 — 느린 setup을 만나면
       저장 도중에 죽는 상태였다.
 -12   한 rubric 항목. 측정 최장값(run 33286656393, 과제 9e39df84의
       36→37번 항목, 04:24:48Z→04:36:48Z)
 -2    partial 저장·커밋·자동 재트리거
───
338    GRADER_TIME_BUDGET_SEC = 20280
```

**여유가 아니라 나머지다.** 그래서 20700(345분)은 쓸 수 없다 — 가드가 `9e39df84`를 *끝낸 뒤*가 아니라 *도중에* 걸리는 경로에서 6.3+345+12+2 = **365분**이 되어 플랫폼 강제 종료를 넘고, 그 경우 비용 원장 업로드까지 같이 날아간다. 338은 성공 경로와 실패 경로 **양쪽 모두** 제한시간 안에 들어오는 마지막 값이다(최악 358.3분).

`test_a_chunk_can_always_save_before_the_runner_kills_it`이 이 부등식을, `test_the_budget_is_the_largest_value_that_still_leaves_room_to_save`가 "더 올릴 수 없다"와 "덜 쓰지도 않았다"를 양방향으로, `test_the_widest_shard_finishes_inside_the_auto_resume_cap`이 청크 개수를 검사한다. 전부 `grade-run.yml`에서 숫자를 직접 읽으므로, 워크플로에서 하나만 바꾸면 여기가 빨개진다.

### `9e39df84` — 네 번 시도하고 접는다

예산을 세 번 올린 이유가 전부 이 과제 하나다. 결과를 먼저 적는다.

| 시도 | run | 예산 | 실제 채점 시간 | 끝낸 항목 | 멈춘 자리 | rc |
|---|---|---|---|---|---|---|
| 1 | 33273207562 | 240분 | 261.3분 | 45 / 57 | 46번째 | 5 |
| 2 | 33286656393 | 300분 | 310.4분 | 54 / 57 | 55번째 `feb54fa4` | 5 |
| 3 | 33301041542 | 336분 | 348.0분 | 54 / 57 | 55번째 `feb54fa4` | 5 |
| 4 | 33316285562 | 338분 | 346.0분 | 55 / 57 | 56번째 `b0e21451` | 5 |

세 번 올려서 9개 항목을 샀고, **3차는 한 개도 못 샀다.** 2차와 3차는 같은 54개를 끝내고 같은 항목에서 멈췄는데 걸린 시간만 37.6분 차이가 났다. 즉 움직이는 것은 일의 양이 아니라 **속도**다 — 항목당 5.75 / 5.81 / 6.29 / 6.44분.

그래서 의미 있는 수치는 "이 과제가 몇 분 걸리는가"가 아니라 **"관측된 각 속도로 57개를 다 돌면 몇 분인가"**다.

| 시도 | 항목당 | 57개 환산 | 들어가는가 |
|---|---|---|---|
| 1 | 5.81분 | 331분 | ✅ |
| 2 | 5.75분 | 328분 | ✅ |
| 3 | 6.44분 | **367분** | ❌ |
| 4 | 6.29분 | **359분** | ❌ |

기준선은 예산이 아니라 **플랫폼이 채점에 내줄 수 있는 최대 시간**이다.

```
360    플랫폼 강제 종료
 -6.3  setup (채점 시작 전)
 -2    partial 저장 (채점 끝난 뒤)
───
351.7  채점에 쓸 수 있는 전부
```

최근 두 번의 속도는 각각 7분·15분 **초과**한다. 예산을 어떤 값으로 올려도 메울 수 없다 — 351.7분이 예산의 상한이지 예산이 351.7분의 상한이 아니기 때문이다. 예산을 더 올리면 돈을 잃는 **위치**만 과제 안쪽으로 옮겨간다.

다만 과제 자체가 원래 너무 큰 것은 아니다. 초반 두 번의 속도라면 328~331분으로 여유 있게 들어간다. **관측 4회 중 2회는 되는 도박**이고, 한 판에 약 6시간의 유료 채점이 든다. 이 양면을 `test_the_platform_cannot_give_this_task_the_time_its_recent_pace_needs`와 `test_the_two_earliest_paces_would_have_fitted_so_this_is_a_lottery`가 각각 못 박는다.

**손해는 1개가 아니라 11개다.** `9e39df84`는 shard 4의 17개 중 7번째라서, 재개할 때마다 얘부터 잡고 청크를 다 쓴다. 앞의 6개는 저장돼 있고 **뒤의 10개는 한 번도 시작조차 못 했다.** `test_losing_this_task_strands_the_ten_behind_it`이 이 숫자를 고정된 목록에서 다시 계산한다.

우회로는 전부 막혀 있고, 막혀 있는 것이 옳다.

| 우회로 | 왜 안 되나 |
|---|---|
| 이 과제만 빼고 채점 | 목록이 짧아져 `pinned rerun identity mismatch for task_count` |
| 이 과제를 맨 뒤로 | 개수는 같고 순서가 달라져 `mismatch for task_ids` |
| `per_item_max_output_tokens` 인상 | grading config가 지문 안 — 이미 값 치른 10개 shard가 무효 |
| 다른 환경변수 | 채점 코드가 읽는 `GRADER_*`는 `GRADER_TIME_BUDGET_SEC` 하나뿐 |

앞의 두 개는 `test_the_pinned_list_refuses_both_ways_round_the_stalled_task`가 실제로 예외를 받아 확인한다. 이 고정이 느슨해지면 shard가 조용히 17개 중 15개만 채점하고도 완료라고 말하게 된다.

남는 구조적 해법은 하나뿐이다 — **360분 강제 종료가 없는 러너.** self-hosted 러너에는 이 상한이 없다. 범위 밖이고 과금 주체가 달라지므로 여기서 결정하지 않고 기록만 한다.

p90(32.7분) 기준으로 17개 shard는 여전히 **청크 2개**, 총 22개 job이다. 재개는 사람이 누르지 않는다 — 워크플로가 rc=7을 보고 `resume_chunk+1`로 자기를 다시 띄운다.

shard는 병렬로 돈다. concurrency 키가 `shard_index`를 담고 `shard_count`는 담지 않아서 11개가 서로 다른 그룹이 된다. 합치기는 `step9_merge_shards.py`가 한다.

유료 실행 전에 `dry_run: true`로 전 경로를 무료로 통과시킨다 — 설정 검증, 고정 목록 대조, 컨테이너·렌더러 확인까지 모델 호출 없이 끝나는 구간이 거기까지다.

**shard가 도는 동안 `core/`·`schemas/`·`prompts/`·`grading_configs/`·`grade-run.yml`을 병합하지 말 것.** grader 소스 지문이 바뀌면 합치기가 실패하는데, 그 실패는 이미 돈을 다 쓴 뒤에야 드러난다.

### 기록할 것

실행 후 `tasks/rebuilding_grading_task/PR3_FULL_GOLD_CORPUS.md`에:

- 평균 점수, 필수 항목 통과율, grader 오류율 — 임계값(90% / 0.95 / 2%) 대비
- **1단계 30개와의 대조**: 같은 30개가 3단계 실행 안에서 몇 점을 받았는지. grader 소스 지문이 그 사이 바뀌었으므로 항목 단위로 같은 값이 나올 이유는 없지만, 크게 벌어지면 그 자체가 발견이다
- sector별·직업별 평균 — 어디가 천장을 끌어내리는지
- 위 다섯 개 알려진 한계를 뺀 평균, 뺀 전후를 같이
  - *(실행 후 추가)* 예측하지 못한 여섯 번째 `0e386e32`도 같은 방식으로 한 번 더. 다섯 개만 뺀 값과 여섯 개를 뺀 값을 둘 다 적어, 미리 알던 몫과 실행하고서야 안 몫을 구분할 수 있게 한다
- 만점 미달 항목마다 라이브러리 한계인지 진짜 미흡인지 분류
- 모델별 사용량, 이미지·오디오 채점 호출 수
- 실제 청구액. 가격 미확정 모델(`gpt-5.6-sol`, `gpt-audio-1.5`)이 있으면 `pricing_complete: false`로 남기고 `$0`이라고 쓰지 말 것

---

## 문서 정정

1단계 문서(`300-gold-ceiling.md`)는 *"전수 220개는 Stage 3에서 한다"*라고 적었고, `gold_ceiling_30_v2_sol_max.yaml`의 주석도 *"stage 3 grades all 220"*이라고 적혀 있다. **둘 다 사실이 아니다.** 채점 가능한 전수는 185개다. 220개를 고정하면 답안 없는 35개가 전부 0점으로 들어와 천장이 실제보다 낮게 나오고, 그건 grader 결함처럼 읽힌다.

이 문서의 모든 수치는 커밋된 매니페스트에서 다시 계산한 값이고, 저장소가 공개하는 수치와 일치한다 — `README.md`는 *"220 tasks across 9 industry sectors and 44 occupations"*, `README_KR.md`는 *"9개 산업, 44개 직종, 220개 태스크"*로 이미 같은 값을 적고 있다(`tasks/TASK_DOCS_CLEANUP.md`와 `TASK_DOCS_CLEANUP_KR_EXP.md`가 그 정정을 남긴 기록이다).

로컬 `CLAUDE.md`만 *"11 sectors, 55 occupations"*를 유지하고 있으나, 그 파일은 `.gitignore`의 `CL*` 규칙에 걸려 **어떤 브랜치에도 추적된 적이 없다.** 저장소를 읽는 사람이 볼 수 없는 파일이므로 여기서 정정할 대상이 아니다.
