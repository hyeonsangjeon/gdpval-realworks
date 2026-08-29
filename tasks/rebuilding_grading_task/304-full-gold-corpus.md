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
| 청크 예산 | `GRADER_TIME_BUDGET_SEC=14400` = **4시간** |
| job 제한시간 | `timeout-minutes: 320` = **5.33시간** |
| 자동 재개 상한 | 청크 **10개** |

가장 큰 shard(5.5시간)가 job 제한시간(5.33시간)보다 길다. **이건 문제가 아니라 설계다** — shard 하나가 job 하나에 들어갈 필요는 없고, 그래서 청크가 있다. 17개짜리 shard는 청크 2개로 끝나고, 상한 10개에 한참 못 미친다.

진짜로 지켜야 하는 부등식은 다른 것이다. 시간 예산은 **과제를 시작하기 전에만** 검사된다(`step8_grade.py`의 time-guard pre-check). 즉 청크가 예산 1초 전에 마지막 과제를 시작하면 그 과제의 전체 소요시간만큼 더 돈다. 그러므로 **예산과 제한시간 사이의 여유가 과제 하나보다 넓어야 한다.**

- 여유 = 320 − 240 = **80분**
- 과제 하나 p90 = **32.7분** → 들어간다

평균이 아니라 p90으로 재는 이유는, job을 죽이는 건 평균짜리 과제가 아니기 때문이다. 여유가 부족하면 shard는 채점 도중에 살해당하고, **아무것도 저장하지 못한 채 이미 쓴 돈은 전부 날아간다.** `test_a_chunk_can_always_save_before_the_runner_kills_it`이 이 부등식을, `test_the_widest_shard_finishes_inside_the_auto_resume_cap`이 청크 개수를 검사한다. 두 테스트 모두 세 숫자를 `grade-run.yml`에서 직접 읽으므로, 워크플로에서 하나를 바꾸면 여기가 빨개진다.

그러므로 shard당 **청크 2개**, 총 22개 job이다. 재개는 사람이 누르지 않는다 — 워크플로가 rc=7을 보고 `resume_chunk+1`로 자기를 다시 띄운다.

shard는 병렬로 돈다. concurrency 키가 `shard_index`를 담고 `shard_count`는 담지 않아서 11개가 서로 다른 그룹이 된다. 합치기는 `step9_merge_shards.py`가 한다.

유료 실행 전에 `dry_run: true`로 전 경로를 무료로 통과시킨다 — 설정 검증, 고정 목록 대조, 컨테이너·렌더러 확인까지 모델 호출 없이 끝나는 구간이 거기까지다.

**shard가 도는 동안 `core/`·`schemas/`·`prompts/`·`grading_configs/`·`grade-run.yml`을 병합하지 말 것.** grader 소스 지문이 바뀌면 합치기가 실패하는데, 그 실패는 이미 돈을 다 쓴 뒤에야 드러난다.

### 기록할 것

실행 후 `tasks/rebuilding_grading_task/PR3_FULL_GOLD_CORPUS.md`에:

- 평균 점수, 필수 항목 통과율, grader 오류율 — 임계값(90% / 0.95 / 2%) 대비
- **1단계 30개와의 대조**: 같은 30개가 3단계 실행 안에서 몇 점을 받았는지. grader 소스 지문이 그 사이 바뀌었으므로 항목 단위로 같은 값이 나올 이유는 없지만, 크게 벌어지면 그 자체가 발견이다
- sector별·직업별 평균 — 어디가 천장을 끌어내리는지
- 위 다섯 개 알려진 한계를 뺀 평균, 뺀 전후를 같이
- 만점 미달 항목마다 라이브러리 한계인지 진짜 미흡인지 분류
- 모델별 사용량, 이미지·오디오 채점 호출 수
- 실제 청구액. 가격 미확정 모델(`gpt-5.6-sol`, `gpt-audio-1.5`)이 있으면 `pricing_complete: false`로 남기고 `$0`이라고 쓰지 말 것

---

## 문서 정정

1단계 문서(`300-gold-ceiling.md`)는 *"전수 220개는 Stage 3에서 한다"*라고 적었고, `gold_ceiling_30_v2_sol_max.yaml`의 주석도 *"stage 3 grades all 220"*이라고 적혀 있다. **둘 다 사실이 아니다.** 채점 가능한 전수는 185개다. 220개를 고정하면 답안 없는 35개가 전부 0점으로 들어와 천장이 실제보다 낮게 나오고, 그건 grader 결함처럼 읽힌다.

같은 종류의 어긋남이 하나 더 있다. `CLAUDE.md`와 `README`가 *"220 tasks across 11 sectors, 55 occupations"*라고 적고 있는데, 고정된 커밋에서 실제로 재면 **9 sector / 44 직업**이다. 이 문서의 모든 수치는 커밋된 매니페스트에서 다시 계산된 값이다.
