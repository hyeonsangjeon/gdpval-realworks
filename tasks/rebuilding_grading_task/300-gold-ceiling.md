# 300 — Gold-Ceiling Test

> PR3 / 1 of 4. SPEC §7-1.

## 목적

`openai/gdpval` rubric에 포함된 gold deliverable을 v2 grader로 채점. **gold가 ceiling을 안 찍으면 grader/입력이 여전히 깨진 것** — 가장 중요한 sanity check.

이미 발표된 모든 모델 점수는 이 천장을 기준으로 읽힌다. 그러니 측정 대상이 흔들리면 측정 자체가 무의미하다. 아래 "고정 계약"은 흔들릴 수 있는 것을 전부 못으로 박은 목록이다.

## 작업

1. `data/gdpval-local`의 reference_files / gold_deliverable_files 위치 확인
2. 새 stub experiment yaml `experiments/exp_gold_baseline.yaml` 작성: gold deliverable 자체를 결과물로 등록
3. v2 grader로 220 task 전체 grade (또는 첫 sample 30)
4. 결과 분석:
   - avg_score_pct 평균 (기대 ≥ 90% — gold이라면 거의 만점)
   - critical_item_pass_rate (기대 ≥ 0.95)
   - judge_error_rate (기대 < 2%)
   - 만점 못 받은 항목들의 evidence — 라이브러리 한계 vs 진짜 미흡 판별

## Acceptance

- gold 평균 pct ≥ 90%
- critical_pass ≥ 0.95
- 미달 시 grader/tool 결함 보고 (PR2로 되돌림 또는 hotfix)

### 소유자 결정 — `critical_pass`는 더 이상 합격을 가르지 않는다 (2026-09-03)

위의 `critical_pass ≥ 0.95` 줄은 이 문서가 처음 쓰였을 때의 기대치 그대로 남겨 둔다.
값을 바꾸지도, 지우지도 않는다. 다만 **합격 판정에서는 빠졌다.**

이유는 그 숫자가 이름값을 한 적이 없기 때문이다. GDPVal v2 rubric에는 `required`
필드가 있지만 220개 task · 10,453개 항목 전부에서 `null`이다
(`data/grades/_validation/REQUIRED_ITEM_DEFINITION.md`). 그래서 채점기는 "필수인가"
대신 "배점이 큰가"(`abs(max_score) >= 4`, `core/grader.py:118-138`)를 대신 쓴다.
배점 4점 이상 항목의 통과율은 실제로 측정된 값이고 계속 인쇄할 가치가 있다. 하지만
그것은 *필수* 기준을 얼마나 만족했는지가 아니며, 아무도 검증한 적 없는 대체값 위에서
단계의 합격·불합격을 가를 수는 없다.

- 임계값 `4`는 그대로 둔다. `MAGNITUDE_THRESHOLD`는 grader 소스 지문의 입력이라
  건드리면 이미 발표된 모든 실행을 다시 매겨야 한다. 기존 grade JSON도 고치지 않는다.
- `0.95`는 참고선으로 계속 인쇄된다. 지금 값이 거기서 얼마나 떨어져 있는지는 여전히
  보인다 — 다만 그것으로 합격을 정하지 않을 뿐이다.
- 분모가 0이면 `0%`가 아니라 **"not recorded"** 로 인쇄한다.
  `scripts/analyze_gold_ceiling.py`의 `Diagnostics` 절.

이 변경이 과거 판정을 뒤집지 않는다는 확인: Stage 1(평균 82.87%)과 Stage 3(평균
79.53%)은 **평균 점수에서 이미 미달**이라, 이 게이트를 빼도 두 단계 모두 그대로
불합격이고 종료 코드도 그대로 `1`이다.

---

## 고정 계약 (Stage 1, 30-task)

한 번의 유료 실행이 무엇을 측정한 것인지 나중에도 재현·반박할 수 있도록, 움직일 수 있는 것을 전부 고정한다. 아래 값은 전부 저장소에 커밋된 파일에서 다시 계산되며, `batch-runner/tests/test_gold_ceiling_contract.py`가 어긋나면 실패한다 — 즉 신뢰가 아니라 검사 대상이다.

### 무엇을 채점하는가

| 항목 | 고정값 | 어디에 박혀 있나 |
|---|---|---|
| 데이터셋 | `openai/gdpval` | `experiments/exp_gold_baseline.yaml` |
| 데이터셋 커밋 | `11e7900cdcac61bc4daf59e65feb238acda98fbf` | grading config `rerun_identity` |
| rubric 커밋 | 같은 커밋 (`main` 아님) | grading config `rubric.revision` |
| parquet 파일 지문 | `f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202` | `experiments/gold_corpus/gold_deliverable_manifest.json` |
| 채점 대상 | 30 task | grading config `rerun_identity.task_ids` |
| 채점 설정 | `grading_configs/gold_ceiling_30_v2_sol_max.yaml` | — |
| grader 소스 지문 | 실행 시 계산되어 파일명과 grade JSON에 기록 | `compute_grader_source_hash` |
| 컨테이너 이미지 | `ghcr.io/hyeonsangjeon/gdpval-grading@sha256:0f6782c0…` (digest 고정) | `.github/workflows/grade-run.yml` |
| LibreOffice | `LibreOffice 24.2.7.2 420(Build:2)` | `scripts/preflight_grading_renderer.py`, 이미지 빌드 시 검증 |

컨테이너 digest와 LibreOffice 버전은 실행 시 `renderer_fingerprint`로 grade JSON 안에 다시 기록된다. 즉 사후에 "그때 뭘로 렌더링했나"를 문서가 아니라 결과물에서 확인할 수 있다.

### 어떤 30개인가

데이터셋 자기 행 순서대로 걸어가며 **실제로 gold 답안이 있는** 첫 30개. 220개 중 185개만 gold를 가지므로, 앞쪽 34행 안에서 4개가 답안 없음으로 건너뛰어진다.

앞에서부터 자르는 이유는 재현성이다. seed도 없고 표본 추출 코드도 없으니, 데이터셋만 있으면 누구나 같은 30개를 다시 얻는다. 대신 표본은 좁다 — 연속된 행이 직업을 공유하므로 4개 sector, 7개 직업뿐이다. 이건 대표성 조사가 아니라 grader 온전성 검사다. 전수 220개는 Stage 3에서 한다.

순서도 계약의 일부다. `step8_grade.py`는 (a) 원본 순서를 따르지 않는 목록을 거부하고, (b) 고정 목록과 선택된 목록을 순서까지 포함해 동등 비교한다. 재정렬은 조용히 다른 실행이 되는 대신 거부된다.

### 입력 지문

| 지문 | 값 |
|---|---|
| `ordered_task_ids_sha256` | `82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b` |
| `gold_file_set_sha256` | `cd4448b4a25b12aa3ae95616a60fdccc47707298d86a9aa2f7cd2ace9c15a7c8` |

- `ordered_task_ids_sha256` = 30개 task id를 순서대로 담은 compact JSON 배열
  (`json.dumps(ids, ensure_ascii=False, separators=(",", ":"))`)의 SHA-256.
  이건 **채점기가 직접 쓰는 값**이다. `step8_grade._ordered_task_ids_sha256`가
  계산해서 모든 grade JSON의 `expected_ordered_task_ids_sha256`에 넣고,
  출력 디렉터리 이름도 이 값이 된다. 그래서 2단계 반복 실행은 이 값을
  payload 필드와 그대로 맞대볼 수 있다.
- `gold_file_set_sha256` = 각 파일의 `graded_path\tsha256\tsize`를 task 순서대로
  개행으로 이어 붙인 문자열의 SHA-256. 이건 **이 문서가 정의한 값**이다.
  파이프라인 어디에도 정답 파일 묶음을 지문화하는 코드가 없어서, payload에는
  대응하는 필드가 없다. 자기 자신끼리만 비교한다.

> 같은 30개를 다른 방식으로 인코딩하면 당연히 다른 지문이 나온다. 예전 판의 이
> 표에는 같은 id 목록을 개행으로 이어 붙인 `09ce9245…`가 적혀 있었고, 그 값이
> 분석 도구에 그대로 옮겨져 **1단계 자기 실행을 거부했다**. 목록도 순서도 옳았고
> 구분자만 달랐다. 그래서 지금은 도구가 이 값을 문자열로 베끼지 않고
> `step8_grade`의 함수로 다시 계산해 맞춘다.

두 값 모두 매니페스트와 grading config만으로 다시 계산된다 — 623MB짜리 원본 파일 없이도 검증 가능하다.

**표본 구성**: 파일 40개 / 184,099,078 바이트. 확장자는 docx 13, pdf 12, xlsx 11, pptx 3, zip 1. sector는 Government 13, Professional·Scientific·Technical 9, Manufacturing 5, Information 3. 직업은 Accountants and Auditors 5, Administrative Services Managers 5, Buyers and Purchasing Agents 5, Compliance Officers 5, Computer and Information Systems Managers 4, Audio and Video Technicians 3, Child·Family·School Social Workers 3.

### 알려진 입력 한계 (사전 공개 → 1차 실행이 확인 → 고침)

task `38889c3b-e3d4-49c8-816a-3cc8e5313aba`의 gold 답안은 179.7MB `.zip` 한 개다. 실행 전에 이 표본에서 빼지 않겠다고 적어두었다 — 빼면 천장이 실제보다 좋아 보이기 때문이다. 미리 적어두는 이유는, 실행 후에 이유를 만들어내는 것과 미리 예측해두는 것은 증거로서 값이 다르기 때문이다.

1차 유료 실행이 예측을 그대로 확인했다: **62점 만점에 2.00점**. 통과한 항목은 "최상위 zip 압축 파일 정확히 한 개를 제출한다" 하나뿐이고, 그건 zip이라서 통과한 것이다. 나머지 34개 항목은 전부 "binary or unsupported for text read" 또는 "not an audio file"이라는 증거를 달고 떨어졌다.

**다만 예측의 이유가 틀렸다.** 예전 판은 이걸 "읽기 도구의 형식 미지원"이라고 적었다. 압축 파일 **안**의 형식은 전부 지원된다 — 5개 WAV stem이고, `probe_audio`는 PR2부터 WAV를 읽는다. 지원되지 않은 것은 형식이 아니라 **컨테이너**였다. 아무도 열어보지 않은 파일을 놓고 표본율·비트 심도·길이를 물은 것이다.

그래서 고쳤다. `core/tools/read_deliverable.py`가 이제 압축 파일의 목록을 내용으로 돌려주고, `scope={"member": "<이름>"}`으로 개별 구성원에 아무 op이나 걸 수 있다. 실제 답안에 걸어 확인한 결과: 5개 stem 전부 48,000Hz / `pcm_s24le`(24비트) / 스테레오, MASTER 137.14초(2분 17초). 이걸로 32점어치 항목(WAV 형식 5, 표본율 5, 비트 심도 5, 길이 1)이 증거를 갖게 된다.

**아직 닿지 않는 것**은 남은 28점이다. `grader_routing.py`와 `deliverable_selector.py`에게 이 답안은 여전히 확장자가 `.zip`인 파일 한 개라서, 듣기 모델이 배정되지 않는다. 조성(G장조 → A♭장조 → G장조), 템포 140, 보컬 없음, 브리지 1:22–1:49, 시간계 이펙트, 신스 계열, `DRUM REFERENCE TRACK.wav`와의 동기 — 전부 실제로 들어야 답할 수 있고, 이번 수정 범위 밖이다. 후속 항목으로 분리해 점수 영향까지 적어 둔다.

### 결과가 발표되지 않는 이유

`step8_grade.py`는 `gold-corpus` 출처의 모든 실행을 진단 경로(`data/grades/_diagnostic/…`)로 보낸다. 대시보드에는 "이건 천장이지 경쟁자가 아니다"라고 말할 방법이 없어서, 정규 경로에 놓이면 모델들과 나란히 순위에 오르기 때문이다. 이 규칙은 채점 범위가 얼마나 넓은지와 무관하다 — 전수를 고정해도 여전히 진단이다.

### 실행 계획

커밋된 220-task Sol Max 실행 기준으로 task당 평균 19.44분, 중앙값 19.29분, p90 32.7분이다. 30 task면 약 9.7시간 — 한 청크의 4시간 예산(`GRADER_TIME_BUDGET_SEC=14400`)을 넘는다.

그래서 **3 shard × 10 task**로 나눈다. shard당 약 3.2시간이면 자동 재개(rc=7) 없이 한 청크 안에 끝난다. shard는 병렬로 돌고, `step9_merge_shards.py`가 하나로 합친다.

유료 실행 전에 `dry_run: true`로 전 경로를 무료로 통과시킨다 — 설정 검증, 고정 목록 대조, 컨테이너·렌더러 확인까지 모델 호출 없이 끝나는 구간이 거기까지다.

**shard가 도는 동안 `core/`·`schemas/`·`prompts/`·`grading_configs/`·`grade-run.yml`을 병합하지 말 것.** grader 소스 지문이 바뀌면 합치기가 실패하는데, 그 실패는 이미 돈을 다 쓴 뒤에야 드러난다.

### 기록할 것

실행 후 `tasks/rebuilding_grading_task/PR3_GOLD_CEILING.md`에:

- 평균 점수, 필수 항목 통과율, grader 오류율 — 임계값(90% / 0.95 / 2%) 대비
- task별 증거: 만점 미달 항목마다 라이브러리 한계인지 진짜 미흡인지 분류
- 모델별 사용량, 이미지·오디오 채점 호출 수
- 실제 청구액. 가격 미확정 모델(`gpt-5.6-sol`, `gpt-audio-1.5`)이 있으면 `pricing_complete: false`로 남기고 `$0`이라고 쓰지 말 것

임계값 미달이면 grader 결함인지, 입력 결함인지, 도구 결함인지 분류한다. 저장소 문제면 고치고, 검증하고, 다시 돌린다.

### Stage 2 준비물 (여기서 만들어 둔 것)

`303-variance-and-error.md`는 같은 30개를 **세 번** 채점해야 한다. 그런데 실행을 식별하는 값은 하나도 바꿀 수 없다 — grader 소스, 설정, 대상, 입력이 전부 같아야 분산 측정이 성립한다. 그래서 세 번 모두 같은 출력 경로로 떨어지고, 두 번째는 "이미 있음"으로 거부되며 `--force`는 첫 번째를 지운다.

그래서 `--run-ordinal`을 추가했다. 실행 번호만 출력 디렉터리를 가르고, 식별값은 하나도 건드리지 않는다. shard 갈림길보다 **위**에 두었으므로, 한 청크에 안 들어가는 반복도 여전히 쪼갤 수 있다. 1번은 정규 경로를 그대로 쓴다 — 반복 묶음의 원본은 평범한 실행이고 별도 플래그가 필요 없다.
