# PR3_GOLD_CEILING — 정답을 채점하면 만점 근처가 나오는가

> 명세: [`300-gold-ceiling.md`](300-gold-ceiling.md). 다음 단계인
> [`303-variance-and-error.md`](303-variance-and-error.md)는 이 실행을 1회차로
> 재사용하므로, 아래 "얼어붙인 계약"의 여섯 지문이 그 재사용의 근거다.

## 이 문서가 답하는 질문

채점기가 믿을 만한지 확인하는 가장 값싼 방법은, 벤치마크가 스스로 정답이라고
내놓은 결과물을 채점기에 넣어보는 것이다. 정답이 만점 근처를 못 받으면 잘못은
정답이 아니라 채점기 쪽에 있다. 그러면 지금까지 발표한 모든 모델 점수도 함께
의심해야 한다.

그래서 이 실행은 모델의 실력을 재지 않는다. **채점기 자체를 잰다.** 여기서
나온 낮은 점수는 누구의 모델이 못했다는 뜻이 아니라, 채점기·입력·도구 셋 중
하나가 고장 났다는 뜻이다.

같은 이유로 이 결과는 대시보드에 실리지 않는다. `step8_grade.py`가
`gold-corpus` 출처의 실행을 전부 `data/grades/_diagnostic/` 아래로 보내기
때문에, 정답의 점수가 경쟁 모델 점수 옆에 나란히 서는 일은 구조적으로 생기지
않는다.

## 한 줄 결론

정답을 채점기에 넣었더니 **82.87%**가 나왔다. 90% 이상을 기대했으니 미달이다.
그런데 깎인 점수의 큰 몫은 정답이 부실해서가 아니라 **채점기가 정답을 끝까지
읽지 못해서** 생긴다. 읽기 도구의 구멍 두 개를 고쳐 78.24% → 82.87%로 올렸고,
남은 미달분은 어디서 왜 새는지 항목 단위로 특정했다.

| 임계값 | 결과 | 판정 |
|---|---|---|
| 평균 점수 ≥ 90% | 82.87% | 미달 |
| 필수 항목 통과율 ≥ 0.95 | 0.5714 | 미달 |
| 채점기 오류율 < 2% | 0.14% | 통과 |

**1단계는 통과하지 못했다.** 다만 두 미달의 성격이 전혀 다르다. 평균 점수 쪽은
고칠 수 있는 결함이 실제로 점수를 깎고 있고, 필수 항목 통과율 쪽은 **지표 자체가
이 임계값에 닿을 수 없게 정의돼 있다.** 아래에서 각각 증거와 함께 다룬다.

## 얼어붙인 계약

명세가 얼리라고 지정한 여섯 가지다. 여섯 모두 아래에 지문으로 적어두는데,
다음 단계가 "똑같이 3회 돌렸다"를 주장하려면 무엇과 똑같은지가 파일에 적혀
있어야 하기 때문이다. 적혀 있지 않은 것과의 동일성은 증명할 수 없다.

| 무엇 | 지문 | 어디서 읽었나 |
|---|---|---|
| 과제 30개 목록 | `82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b` | `grading_configs/gold_ceiling_30_v2_sol_max.yaml`의 `rerun_identity.task_ids`에 `step8_grade._ordered_task_ids_sha256`를 적용한 값 (compact JSON 배열의 SHA-256) |
| 정답 파일 40개 | `cd4448b4a25b12aa3ae95616a60fdccc47707298d86a9aa2f7cd2ace9c15a7c8` | `experiments/gold_corpus/gold_deliverable_manifest.json`의 `graded_path\tsha256\tsize`를 과제 순서대로 개행 연결한 SHA-256 |
| 채점 구성 | `gold_ceiling_30_v2_sol_max` | 파일 내용이 아래 채점기 소스 지문에 포함됨 |
| 채점기 소스 | `c33d9d55703fbf5de5f988d427e34efd44d7a73306412caac88a753bad16ff4e` | 실행이 스스로 기록한 `grader_source_hash` |
| 컨테이너 이미지 | `ghcr.io/hyeonsangjeon/gdpval-grading@sha256:0f6782c056e31e1ea1d693fc2f8f873da160b232926fa1b6cde75c24e5344a04` | [`grade-run.yml:413`](../../.github/workflows/grade-run.yml) |
| LibreOffice 판 | `LibreOffice 24.2.7.2 420(Build:2)` | 실행이 스스로 기록한 `renderer_fingerprint.libreoffice_version` |

앞 두 지문은 명세에 적힌 값을 그대로 옮긴 게 아니라 저장소의 설정 파일과
목록 파일에서 다시 계산해 대조했다.
`test_gold_ceiling_report_quotes_its_run.py`가 같은 계산을 다시 하므로, 이 표의
숫자가 코퍼스와 어긋나면 시험이 깨진다.

첫 번째 지문은 한 번 틀렸었다. 예전 판은 같은 30개 id를 **개행으로** 이어 붙인
`09ce9245…`를 적어 두었는데, 채점기가 쓰는 건 **compact JSON 배열**이다. 목록도
순서도 옳았고 구분자만 달랐다. 그 값이 분석 도구로 옮겨 적히면서, 도구가 자기
실행의 결과물을 "고정된 목록이 아니다"라며 거부했다. 그래서 지금은 문서도 도구도
문자열을 베끼지 않고 `step8_grade`의 함수를 불러 다시 계산한다 — 계약을 적는
곳과 계약을 집행하는 곳이 같은 코드를 쓰게 만든 것이다.

정답 40개는 전부 184,099,078 바이트, 확장자별로 `.docx` 13, `.pdf` 12,
`.xlsx` 11, `.pptx` 3, `.zip` 1이다.

## 실행 전에 적어둔 예측

결과를 보고 나서 이유를 만들어내는 것과, 결과를 보기 전에 예측을 적어두는 것은
증거로서 값이 다르다. 그래서 채점이 도는 동안, 결과가 아직 없는 상태에서 두
가지를 미리 계산해 두었다.

### 예측 1 — 형식 때문에 0점이 되는 과제는 없다

`core/deliverable_selector.py`에는 "과제 지문이 요구한 형식의 파일이 결과물에
하나도 없으면 `wrong_format_primary`로 잘라낸다"는 방어 장치가 있다. 여기에
걸리면 내용이 아무리 훌륭해도 0점이다. 정답이 그렇게 잘려나간다면 그건
채점기의 잘못이 아니라 입력 쪽 사정이므로, 미리 구분해 둘 가치가 있다.

30개 과제 각각에 대해, 실행이 쓰는 것과 똑같은 텍스트(과제 지문 + 채점 항목
전문)로 그 함수를 돌렸다. 채점 항목은 30개 과제 모두 불러와졌고, 그중
**23개 과제에서 형식 요구가 실제로 감지**됐다 — 즉 방어 장치가 잠들어 있어서
통과한 게 아니다.

**결과: 30개 중 0개가 `wrong_format_primary`로 예측된다.** 정답은 모두 자기
과제가 요구한 형식을 갖추고 있다. 따라서 이번 실행에서 0점이 나온다면, 그건
"올바른 형식의 정답을 선택기가 걷어찼다"로는 설명되지 않는다.

**맞았다.** 30개 전부 `selection_status: ok`로 채점됐고, 형식 때문에 잘려나간
과제는 하나도 없다.

### 예측 2 — 정답에 없는 형식을 요구하는 과제가 5개 있다

방어 장치는 "요구 형식 중 **하나도** 못 맞출 때"만 작동한다. 그래서 과제가
엑셀과 PDF를 함께 요구하고 정답에 엑셀만 있으면, 선택은 통과하지만 PDF에 관한
채점 항목은 채점할 대상이 없다. 이건 채점기 결함이 아니라 **정답 자체의 미비**로
분류해야 한다.

| 과제 | 정답이 가진 형식 | 지문이 추가로 요구하는 형식 |
|---|---|---|
| `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` | `.xlsx` | pdf |
| `38889c3b-e3d4-49c8-816a-3cc8e5313aba` | `.zip` | audio |
| `15ddd28d-8445-4baa-ac7f-f41372e1344e` | `.docx` | pdf |
| `24d1e93f-9018-45d4-b522-ad89dfd78079` | `.xlsx` | word |
| `4c18ebae-dfaa-4b76-b10c-61fcdf26734c` | `.docx`, `.xlsx` | pdf |

이 5개에서 만점이 안 나오는 것은 예상된 결과지, 발견이 아니다.

### 미리 공개된 읽기 불가 파일

명세가 실행 전에 이미 밝혀둔 사항이다. `38889c3b-e3d4-49c8-816a-3cc8e5313aba`의
정답은 179.7 MB짜리 `DEJA VU  STEMS .zip` 하나뿐인데, 당시
`core/tools/read_deliverable.py`의 확장자 표에는 `.zip`이 없었다. 코드를 직접
확인한 결과 명세의 설명이 정확했다 — `_kind_of`가 `unknown`을 돌려주고, 본문
읽기는 빈 문자열에 "binary or unsupported for text read"를, 서식 검사는
"formatting inspection not supported for this kind"를 돌려주는 상태였다.

예측 2가 같은 과제를 독립적으로 다시 짚어낸다는 점이 눈에 띈다. 이 과제의 지문은
오디오 파일을 요구하는데 정답은 오디오 파일이 아니라 오디오를 담은 압축 파일
하나다.

**여기까지가 실행 전에 적어둔 것이고, 마지막 한 줄이 틀렸다.** 예전 판은 이
과제의 낮은 점수에 이유가 둘이며 "둘 다 채점기 바깥에 있다"고 적었다. 1차 유료
실행은 결과를 정확히 맞혔지만 — 62점 만점에 2.00점, 통과한 항목은 "최상위 zip
압축 파일 정확히 한 개를 제출한다" 하나뿐 — 그 이유 하나는 채점기 바깥이 아니라
**채점기가 쥔 도구 안**에 있었다. 압축 파일 안의 형식은 전부 읽을 수 있는
것들이다. 5개 WAV stem이고 `probe_audio`는 PR2부터 WAV를 읽는다. 지원되지 않은
건 형식이 아니라 컨테이너였고, 그건 우리가 고칠 수 있는 것이었다. 고쳤다 —
자세한 내용과 남은 사각지대는 [명세의 해당 절](300-gold-ceiling.md)에 있다.

예측을 미리 적어두는 값어치가 여기에 있다. 결과만 맞히고 이유를 틀린 것이
기록으로 남았기 때문에, "예상대로였다"로 덮고 지나가는 대신 실제 원인을 찾아
고치게 됐다.

### 예측 3 — 압축 파일 수정이 효과를 내려면 채점기가 먼저 그 방법을 알아내야 한다

이 예측도 채점이 도는 중에, 결과를 보기 전에 적는다.

압축 파일을 열 수 있게 고쳤다는 건 **도구에 기능이 생겼다**는 뜻이지, 채점기가
그 기능을 쓴다는 뜻이 아니다. 채점기는 도구를 자기가 판단해서 호출하는 모델이고,
쓸 수 있는 인자는 도구 설명서에서 배운다. 그래서 설명서를 확인했다.

채점기에게 건네지는 도구 명세의 `scope` 항목 설명은 한 줄이다 —
"Optional op-specific content/formatting scope." 압축 파일 안의 개별 파일을
`scope={"member": "이름"}`으로 열 수 있다는 말은 **거기에 없다**. 그 말이 나오는
곳은 딱 하나, `inspect_formatting`을 압축 파일에 걸었을 때 돌아오는 응답 안의
`note` 필드다.

그래서 이 과제에서 점수가 회복되는 경로는 하나뿐이다.

1. 채점기가 `.zip`에 `inspect_formatting`을 건다
2. 응답의 `note`를 읽고 `scope={"member": ...}`를 배운다
3. 각 stem에 `probe_audio`를 건다

`read_content`만 부르면 파일 목록(이름·종류·크기)까지는 보이지만 그 방법은
끝내 배우지 못한다. 목록만으로도 "WAV 5개가 들어 있는가"는 답할 수 있지만,
표본율·비트 심도·길이는 실제로 열어봐야 한다.

**예측: 32점어치 항목이 전부 회복되지는 않을 것이다.** 회복 폭은 채점기가
`inspect_formatting`을 먼저 불렀는지에 달려 있고, 그건 도구가 보장하는 게 아니라
모델이 그때그때 정하는 일이다.

이게 맞다면 원인은 **능력이 아니라 발견 가능성**이고, 고칠 곳은 두 군데다 —
도구 명세의 `scope` 설명, 그리고 `read_content`가 압축 파일에 돌려주는 목록.
둘 다 한 줄짜리 수정이다. 지금 고치지 않는 이유는 하나다. 채점기 소스 지문이
바뀌면 지금 도는 3개 shard가 합쳐지지 않고, 그 실패는 돈을 다 쓴 뒤에 드러난다.

### 예측 3의 결과 — 틀렸다

예측은 "32점어치가 전부 회복되지는 않을 것"이었다. 실제로는 **39.8점이
회복됐다** — 예측한 32점 전부에 7.8점이 더 붙었다. 이 과제는 2.00/62(3.23%)에서
41.80/62(67.42%)로 올랐다.

틀린 건 결론만이 아니라 그 앞의 걱정이다. 예측은 회복 경로를 3단계로 봤고 그
가운데 단계가 보장되지 않는다는 점을 문제 삼았다. 채점기는 그 3단계를 그대로
밟았다. 도구 설명서에 없는 인자를, 응답 안의 한 줄에서 찾아내 5개 stem 전부에
걸었다. 회복된 항목 23개가 그 증거다 — WAV 형식 5개(10점), 표본율 5개(10점),
비트 심도 5개(10점), 마스터 길이(2점), "샘플을 썼다면"으로 시작하는 선택 항목
4개(4점), 그리고 보컬 1.5점·브리지 1.3점·템포 1.0점의 부분 점수.

**그래서 후속 수정의 성격이 바뀐다.** 도구 설명서에 `scope={"member": ...}`를
적어 넣는 일은 "못 하던 걸 하게 만드는 수정"이 아니라 "매번 되게 만드는
수정"이다. 이번엔 됐지만 그건 모델이 그때 그렇게 정한 것이고, 2단계가 재려는 게
정확히 "그때그때 정하는 일이 얼마나 흔들리는가"다.

남은 20.2점은 발견 가능성 문제가 아니다. 조성 3개 항목, 드럼 기준 트랙과의
동기·드리프트·일치, 시간계 이펙트, 베이스 신스 계열 — 전부 실제로 들어야 답할 수
있다. 이 과제의 **듣기 호출은 두 실행 모두 0회**다. `grader_routing.py`와
`deliverable_selector.py`에게 이 답안은 여전히 확장자가 `.zip`인 파일 한 개라서
듣기 모델이 배정되지 않는다. 명세가 미리 적어둔 사각지대가 그대로 확인됐다.

## 결과

아래 두 블록은 손으로 옮겨 적은 게 아니라 분석 도구를 그대로 돌린 출력이다.
`test_gold_ceiling_report_quotes_its_run.py`가 같은 명령을 다시 실행해 한 글자라도
다르면 실패시킨다. 나중에 숫자를 손보면 문서가 아니라 시험이 깨진다.

### 이번 실행 — 1단계의 답

<!-- generated: python batch-runner/scripts/analyze_gold_ceiling.py data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_c33d9d55703fbf5d__v2.2.json --shortfall-limit 12 -->
```text
Gold ceiling — stage 1 -- the 30-task sample
============================================================
  experiment      exp_gold_baseline
  graded at       2026-08-28T18:41:32Z
  run status      final
  grader source   c33d9d55703fbf5de5f988d427e34efd44d7a73306412caac88a753bad16ff4e
  renderer        LibreOffice 24.2.7.2 420(Build:2), pymupdf 1.28.2
  provenance      gold-corpus

Thresholds
------------------------------------------------------------
  mean score              82.87%   (needs >= 90.0%)   MISS
  required-item pass      0.5714   (needs >= 0.95)    MISS
  grader error rate       0.0014   (needs < 0.02)     PASS

Required items (|max score| >= 4)
------------------------------------------------------------
  20 of 35 passed  (0.5714)
  verdicts                20 pass, 14 partial, 1 fail
    8/19  passed  ·  Overall formatting and style of the deliverable

Scores
------------------------------------------------------------
  graded 30 task(s), 0 in error; 0 near-perfect (>=99%), 30 partial, 0 near-zero (<=1%)
  rubric item coverage    0.74
  judge pass rate         0.739
    Government                                           85.16%  n=13
    Information                                          77.87%  n=3
    Manufacturing                                        84.27%  n=5
    Professional, Scientific, and Technical Services     80.46%  n=9

By occupation (7)
------------------------------------------------------------
   77.87%  n=3    required 1/2  ·  Audio and Video Technicians
   79.34%  n=4    required 0/2  ·  Computer and Information Systems Managers
   81.36%  n=5    required 3/5  ·  Accountants and Auditors
   83.98%  n=5    required 1/2  ·  Compliance Officers
   84.27%  n=5    required 0/4  ·  Buyers and Purchasing Agents
   84.64%  n=5    required 12/17  ·  Administrative Services Managers
   87.99%  n=3    required 3/3  ·  Child, Family, and School Social Workers

Subsets
------------------------------------------------------------
  82.87%   n=30   required 20/35  ·  the same thirty stage 1 graded
  67.42%   n=1    required 0/0  ·  the five declared input limits
      named but not in this payload:
      a73fbc98, e222075d, 75401f7c
      7de33b48
  83.41%   n=29   required 20/35  ·  everything but those five
      named but not in this payload:
      a73fbc98, e222075d, 75401f7c
      7de33b48

Usage
------------------------------------------------------------
  judge calls             3735 (3631 main, 104 perception)
    mixed                1
    visual               103
  main tokens             in 27299254, out 1392576, cached 13103993
  perception tokens       in 266033, out 37479
  judge latency (total)   26264.17s
  usage complete          True

Bill
------------------------------------------------------------
  estimated cost          UNKNOWN — this grade predates the cost receipt
  judge models declared   ['gpt-5.6-sol', 'gpt-audio-1.5']

Per task (worst first)
------------------------------------------------------------
  c357f0e2-963d-4eb7-a6fa-3078fe55b3ba   49.29%  49.79/101  ·  Computer and Information Systems Managers
      42/70 item(s) below max, -51.2133 point(s), required item failed
  83d10b06-26d1-4636-a32c-23f92c57f30b   66.90%  42.15/63  ·  Accountants and Auditors
      15/38 item(s) below max, -20.85 point(s), required item failed
  38889c3b-e3d4-49c8-816a-3cc8e5313aba   67.42%  41.80/62  ·  Audio and Video Technicians
      14/35 item(s) below max, -20.2 point(s)
  dfb4e0cd-a0b7-454e-b943-0dd586c2764c   72.09%  31.00/43  ·  Compliance Officers
      10/26 item(s) below max, -12.0 point(s)
  17111c03-aac7-45c2-857d-c06d8223d6ad   72.75%  43.65/60  ·  Administrative Services Managers
      15/44 item(s) below max, -16.35 point(s)
  a74ead3b-f67d-4b1c-9116-f6bb81b29d4f   74.71%  63.50/85  ·  Child, Family, and School Social Workers
      19/57 item(s) below max, -21.5 point(s)
  4c18ebae-dfaa-4b76-b10c-61fcdf26734c   76.81%  53.00/69  ·  Compliance Officers
      21/50 item(s) below max, -16.0 point(s)
  24d1e93f-9018-45d4-b522-ad89dfd78079   78.11%  64.05/82  ·  Buyers and Purchasing Agents
      24/52 item(s) below max, -17.95 point(s), required item failed
  7d7fc9a7-21a7-4b83-906f-416dea5ad04f   79.68%  75.70/95  ·  Accountants and Auditors
      15/56 item(s) below max, -19.3 point(s), required item failed
  99ac6944-4ec6-4848-959c-a460ac705c6f   81.51%  66.84/82  ·  Audio and Video Technicians
      21/52 item(s) below max, -15.16 point(s)
  ee09d943-5a11-430a-b7a2-971b4e9b01b5   82.15%  48.47/59  ·  Accountants and Auditors
      11/44 item(s) below max, -10.53 point(s)
  7bbfcfe9-132d-4194-82bb-d6f29d001b01   82.36%  43.65/53  ·  Compliance Officers
      12/40 item(s) below max, -9.35 point(s), required item failed
  15ddd28d-8445-4baa-ac7f-f41372e1344e   82.54%  47.05/57  ·  Buyers and Purchasing Agents
      12/46 item(s) below max, -9.95 point(s)
  cebf301e-5ea7-41ae-b117-ad8f43e7ac22   84.52%  52.40/62  ·  Computer and Information Systems Managers
      8/35 item(s) below max, -9.6 point(s)
  a328feea-47db-4856-b4be-2bdc63dd88fb   84.55%  18.60/22  ·  Administrative Services Managers
      4/16 item(s) below max, -3.4 point(s)
  f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb   84.68%  66.90/79  ·  Audio and Video Technicians
      9/51 item(s) below max, -12.1 point(s), required item failed
  1b1ade2d-f9f6-4a04-baa5-aa15012b53be   84.88%  58.57/69  ·  Buyers and Purchasing Agents
      17/51 item(s) below max, -10.43 point(s), required item failed
  c44e9b62-7cd8-4f72-8ad9-f8fbddb94083   85.00%  103.70/122  ·  Administrative Services Managers
      16/44 item(s) below max, -18.3 point(s), required item failed
  93b336f3-61f3-4287-86d2-87445e1e0f90   85.53%  65.00/76  ·  Buyers and Purchasing Agents
      11/53 item(s) below max, -11.0 point(s), required item failed
  c2e8f271-7858-412f-b460-472463ad81d9   85.89%  69.57/81  ·  Computer and Information Systems Managers
      14/67 item(s) below max, -11.43 point(s), required item failed
  43dc9778-450b-4b46-b77e-b6d82b202035   86.40%  104.55/121  ·  Accountants and Auditors
      18/67 item(s) below max, -16.45 point(s)
  f84ea6ac-8f9f-428c-b96c-d0884e30f7c7   86.57%  50.21/58  ·  Administrative Services Managers
      6/30 item(s) below max, -7.79 point(s), required item failed
  05389f78-589a-473c-a4ae-67c61050bfca   90.28%  79.44/88  ·  Buyers and Purchasing Agents
      11/66 item(s) below max, -8.555 point(s), required item failed
  7b08cd4d-df60-41ae-9102-8aaa49306ba2   91.69%  81.60/89  ·  Accountants and Auditors
      5/59 item(s) below max, -7.4 point(s)
  bbe0a93b-ebf0-40b0-98dc-8d9243099034   92.30%  74.76/81  ·  Child, Family, and School Social Workers
      7/61 item(s) below max, -6.24 point(s)
  2696757c-1f8a-4959-8f0d-f5597b9e70fc   92.68%  38.00/41  ·  Compliance Officers
      2/25 item(s) below max, -3.0 point(s)
  27e8912c-8bd5-44ba-ad87-64066ea05264   94.34%  50.00/53  ·  Administrative Services Managers
      2/37 item(s) below max, -3.0 point(s), required item failed
  36d567ba-e205-4313-9756-931c6e4691fe   95.96%  51.82/54  ·  Compliance Officers
      2/27 item(s) below max, -2.18 point(s)
  76d10872-9ffa-4ede-83ee-e0f1ec5e2b8d   96.96%  143.50/148  ·  Child, Family, and School Social Workers
      4/74 item(s) below max, -4.5 point(s)
  2ea2e5b5-257f-42e6-a7dc-93763f28b19d   97.65%  83.00/85  ·  Computer and Information Systems Managers
      3/60 item(s) below max, -2.0 point(s)

Shortfalls
------------------------------------------------------------
  370 of 1433 rubric item(s) scored below their maximum, losing 377.7283 point(s)
  required item failed in 13 task(s):
      83d10b06-26d1-4636-a32c-23f92c57f30b, 7d7fc9a7-21a7-4b83-906f-416dea5ad04f, f84ea6ac-8f9f-428c-b96c-d0884e30f7c7
      27e8912c-8bd5-44ba-ad87-64066ea05264, c44e9b62-7cd8-4f72-8ad9-f8fbddb94083, f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb
      1b1ade2d-f9f6-4a04-baa5-aa15012b53be, 93b336f3-61f3-4287-86d2-87445e1e0f90, 24d1e93f-9018-45d4-b522-ad89dfd78079
      05389f78-589a-473c-a4ae-67c61050bfca, 7bbfcfe9-132d-4194-82bb-d6f29d001b01, c2e8f271-7858-412f-b460-472463ad81d9
      c357f0e2-963d-4eb7-a6fa-3078fe55b3ba

  -5.0 of 5  [fail, text, decided by judge]  f84ea6ac-8f9f-428c-b96c-d0884e30f7c7
      criterion  Structures the final Scan of Research so that it fits within one page.
      evidence   "char_count": 6532, "truncated": false
  -3.25 of 5  [partial, visual, decided by judge]  83d10b06-26d1-4636-a32c-23f92c57f30b
      criterion  Overall formatting and style of the deliverable
      evidence   Bold headers and consistent font are visible, but entries run together across columns (e.g.,
                 “Corporate BanCorporate Loans” and “Cayman IslanWillett Bank Cayman”).
  -2.75 of 5  [partial, visual, decided by judge]  c44e9b62-7cd8-4f72-8ad9-f8fbddb94083
      criterion  Highlights reductions consistently on the org chart with a legend or notation.
      evidence   Several role boxes use blue outlines, but no visible legend or text explains that these
                 outlines denote reductions.
  -2.25 of 5  [partial, visual, decided by judge]  7bbfcfe9-132d-4194-82bb-d6f29d001b01
      criterion  Overall formatting and style of the deliverable
      evidence   Bold headers and clear gridlines provide basic readability, but the excessive blank area,
                 awkward scale, and uneven row spacing make the sheet look unfinished and poorly balanced.
  -2.1 of 5  [partial, visual, decided by judge]  24d1e93f-9018-45d4-b522-ad89dfd78079
      criterion  Overall formatting and style of the deliverable
      evidence   Clear blue title and a bordered 3-column table, but long assumption lines end abruptly at the
                 right, all body text is italic, and most of the page is unused white space.
  -2.0 of 2  [fail, text, decided by judge]  15ddd28d-8445-4baa-ac7f-f41372e1344e
      criterion  The document length is between 2 and 3 pages (inclusive).
      evidence   "kind": "docx", "paragraph_count": 63, "table_count": 1, "section_count": 1
  -2.0 of 2  [fail, text, decided by judge]  17111c03-aac7-45c2-857d-c06d8223d6ad
      criterion  The memo identifies the sender’s role as Administrative Services Manager (wording can vary
                 but must clearly convey this role).
      evidence   From: Your Name
  -2.0 of 2  [fail, text, decided by judge]  17111c03-aac7-45c2-857d-c06d8223d6ad
      criterion  No section/area appears in the Excel schedule that is not Section 1, 2, 3, or 4 (no extras).
      evidence   SECTION 3,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,, ,SECTION ,
  -2.0 of 2  [fail, text, decided by judge]  17111c03-aac7-45c2-857d-c06d8223d6ad
      criterion  All dates or week ranges from 'TENTATIVE CLEANUP SCHEDULE.pdf' are represented in the Excel
                 schedule (no omissions).
      evidence   2025-04-01 00:00:00
  -2.0 of 2  [fail, formatting, decided by judge]  2696757c-1f8a-4959-8f0d-f5597b9e70fc
      criterion  Immediately after the 9.08(c)(3) test question, a regulatory citation appears identifying VA
                 Servicer Handbook M26-4, Chapter 9, paragraph 9.08(c)(3), and the Chapter 9 publication date
                 (August 12, 2024) (punctuation/formatting may vary).
      evidence   Regulatory Cita.on: VA Servicer Handbook M26-4, Chapter 9: VA Purchase, 9.08(c)(3), August
                 12, 2024 When the borrower has discharged
  -2.0 of 2  [fail, text, decided by judge]  27e8912c-8bd5-44ba-ad87-64066ea05264
      criterion  The checklist explicitly cites a foundation checklist from a credible source by naming the
                 organization and the document title (accept phrasing like 'Based on' or 'Adapted from';
                 including a source link is acceptable but not required).
      evidence   ~End of Assessment~ Workstation Ergonomics Checklist 5
  -2.0 of 2  [fail, text, decided by judge]  36d567ba-e205-4313-9756-931c6e4691fe
      criterion  The document visibly includes the exact title text: "Federal Applicant - Risk Assessment
                 Tool"
      evidence   Federal Applicant – Risk Assessment Tool
  ... and 358 more (use --json for all of them)
```

### 고치기 전 실행 — 비교 대상

읽기 도구를 고치기 전에 같은 30개·같은 설정·같은 컨테이너·같은 LibreOffice로 돈
실행이다. 다른 것은 채점기 소스 지문 하나뿐이다(`8513975c…`). 이번 수정이 무엇을
회복했는지는 이 실행과 견줘야만 말할 수 있어서, 지우지 않고 `_superseded/` 아래에
남겨 두었다. 1단계의 답은 아니고 결함의 증거다.

<!-- generated: python batch-runner/scripts/analyze_gold_ceiling.py data/grades/_diagnostic/82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b/_superseded/exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_30_v2_sol_max__cfg_d1bfc8217c9981d2__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf__src_8513975c188f31a6__v2.2.json --shortfall-limit 0 -->
```text
Gold ceiling — stage 1 -- the 30-task sample
============================================================
  experiment      exp_gold_baseline
  graded at       2026-08-28T14:11:53Z
  run status      final
  grader source   8513975c188f31a616ae1e5e0fdc64aff40dc3bbf07375dae41e6cb78dd370f7
  renderer        LibreOffice 24.2.7.2 420(Build:2), pymupdf 1.28.2
  provenance      gold-corpus

Thresholds
------------------------------------------------------------
  mean score              78.24%   (needs >= 90.0%)   MISS
  required-item pass      0.5429   (needs >= 0.95)    MISS
  grader error rate          0.0   (needs < 0.02)     PASS

Required items (|max score| >= 4)
------------------------------------------------------------
  19 of 35 passed  (0.5429)
  verdicts                19 pass, 16 partial
    7/19  passed  ·  Overall formatting and style of the deliverable

Scores
------------------------------------------------------------
  graded 30 task(s), 0 in error; 0 near-perfect (>=99%), 30 partial, 0 near-zero (<=1%)
  rubric item coverage    0.695
  judge pass rate         0.695
    Government                                           85.87%  n=13
    Information                                          56.21%  n=3
    Manufacturing                                        83.94%  n=5
    Professional, Scientific, and Technical Services     71.39%  n=9

By occupation (7)
------------------------------------------------------------
   56.21%  n=3    required 1/2  ·  Audio and Video Technicians
   59.53%  n=4    required 0/2  ·  Computer and Information Systems Managers
   80.87%  n=5    required 3/5  ·  Accountants and Auditors
   83.94%  n=5    required 0/4  ·  Buyers and Purchasing Agents
   84.43%  n=5    required 1/2  ·  Compliance Officers
   86.14%  n=5    required 12/17  ·  Administrative Services Managers
   87.82%  n=3    required 2/3  ·  Child, Family, and School Social Workers

Subsets
------------------------------------------------------------
  78.24%   n=30   required 19/35  ·  the same thirty stage 1 graded
  3.23%    n=1    required 0/0  ·  the five declared input limits
      named but not in this payload:
      a73fbc98, e222075d, 75401f7c
      7de33b48
  80.82%   n=29   required 19/35  ·  everything but those five
      named but not in this payload:
      a73fbc98, e222075d, 75401f7c
      7de33b48

Usage
------------------------------------------------------------
  judge calls             3823 (3719 main, 104 perception)
    mixed                1
    visual               103
  main tokens             in 26251937, out 1332558, cached 12798579
  perception tokens       in 266033, out 34702
  judge latency (total)   24732.19s
  usage complete          True

Bill
------------------------------------------------------------
  estimated cost          UNKNOWN — this grade predates the cost receipt
  judge models declared   ['gpt-5.6-sol', 'gpt-audio-1.5']

Per task (worst first)
------------------------------------------------------------
  38889c3b-e3d4-49c8-816a-3cc8e5313aba    3.23%  2.00/62  ·  Audio and Video Technicians
      34/35 item(s) below max, -60.0 point(s)
  2ea2e5b5-257f-42e6-a7dc-93763f28b19d   19.53%  16.60/85  ·  Computer and Information Systems Managers
      53/60 item(s) below max, -68.4 point(s)
  c357f0e2-963d-4eb7-a6fa-3078fe55b3ba   47.10%  47.57/101  ·  Computer and Information Systems Managers
      42/70 item(s) below max, -53.4333 point(s), required item failed
  83d10b06-26d1-4636-a32c-23f92c57f30b   66.27%  41.75/63  ·  Accountants and Auditors
      15/38 item(s) below max, -21.25 point(s), required item failed
  17111c03-aac7-45c2-857d-c06d8223d6ad   72.21%  44.05/61  ·  Administrative Services Managers
      17/44 item(s) below max, -16.95 point(s)
  4c18ebae-dfaa-4b76-b10c-61fcdf26734c   73.12%  50.45/69  ·  Compliance Officers
      21/50 item(s) below max, -18.55 point(s)
  a74ead3b-f67d-4b1c-9116-f6bb81b29d4f   74.85%  63.62/85  ·  Child, Family, and School Social Workers
      21/57 item(s) below max, -21.375 point(s), required item failed
  dfb4e0cd-a0b7-454e-b943-0dd586c2764c   77.58%  33.36/43  ·  Compliance Officers
      9/26 item(s) below max, -9.64 point(s)
  24d1e93f-9018-45d4-b522-ad89dfd78079   77.68%  63.70/82  ·  Buyers and Purchasing Agents
      20/52 item(s) below max, -18.3 point(s), required item failed
  7d7fc9a7-21a7-4b83-906f-416dea5ad04f   78.53%  74.60/95  ·  Accountants and Auditors
      15/56 item(s) below max, -20.4 point(s), required item failed
  99ac6944-4ec6-4848-959c-a460ac705c6f   80.59%  66.08/82  ·  Audio and Video Technicians
      20/52 item(s) below max, -15.92 point(s)
  ee09d943-5a11-430a-b7a2-971b4e9b01b5   82.03%  48.40/59  ·  Accountants and Auditors
      11/44 item(s) below max, -10.6 point(s)
  7bbfcfe9-132d-4194-82bb-d6f29d001b01   82.83%  43.90/53  ·  Compliance Officers
      11/40 item(s) below max, -9.1 point(s), required item failed
  15ddd28d-8445-4baa-ac7f-f41372e1344e   82.98%  47.30/57  ·  Buyers and Purchasing Agents
      12/46 item(s) below max, -9.7 point(s)
  1b1ade2d-f9f6-4a04-baa5-aa15012b53be   83.58%  57.67/69  ·  Buyers and Purchasing Agents
      17/51 item(s) below max, -11.33 point(s), required item failed
  93b336f3-61f3-4287-86d2-87445e1e0f90   84.47%  64.20/76  ·  Buyers and Purchasing Agents
      11/53 item(s) below max, -11.8 point(s), required item failed
  f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb   84.81%  67.00/79  ·  Audio and Video Technicians
      10/51 item(s) below max, -12.0 point(s), required item failed
  c2e8f271-7858-412f-b460-472463ad81d9   84.90%  68.77/81  ·  Computer and Information Systems Managers
      14/67 item(s) below max, -12.23 point(s), required item failed
  43dc9778-450b-4b46-b77e-b6d82b202035   85.82%  103.84/121  ·  Accountants and Auditors
      17/67 item(s) below max, -17.16 point(s)
  a328feea-47db-4856-b4be-2bdc63dd88fb   86.04%  20.65/24  ·  Administrative Services Managers
      4/16 item(s) below max, -3.35 point(s)
  c44e9b62-7cd8-4f72-8ad9-f8fbddb94083   86.19%  105.15/122  ·  Administrative Services Managers
      14/44 item(s) below max, -16.85 point(s), required item failed
  cebf301e-5ea7-41ae-b117-ad8f43e7ac22   86.61%  53.70/62  ·  Computer and Information Systems Managers
      6/35 item(s) below max, -8.3 point(s)
  05389f78-589a-473c-a4ae-67c61050bfca   90.99%  80.07/88  ·  Buyers and Purchasing Agents
      11/66 item(s) below max, -7.93 point(s), required item failed
  bbe0a93b-ebf0-40b0-98dc-8d9243099034   91.53%  74.14/81  ·  Child, Family, and School Social Workers
      8/61 item(s) below max, -6.86 point(s)
  7b08cd4d-df60-41ae-9102-8aaa49306ba2   91.69%  81.60/89  ·  Accountants and Auditors
      5/59 item(s) below max, -7.4 point(s)
  f84ea6ac-8f9f-428c-b96c-d0884e30f7c7   91.81%  53.25/58  ·  Administrative Services Managers
      5/30 item(s) below max, -4.75 point(s), required item failed
  2696757c-1f8a-4959-8f0d-f5597b9e70fc   92.68%  38.00/41  ·  Compliance Officers
      2/25 item(s) below max, -3.0 point(s)
  27e8912c-8bd5-44ba-ad87-64066ea05264   94.43%  50.05/53  ·  Administrative Services Managers
      3/37 item(s) below max, -2.95 point(s), required item failed
  36d567ba-e205-4313-9756-931c6e4691fe   95.96%  51.82/54  ·  Compliance Officers
      2/27 item(s) below max, -2.18 point(s)
  76d10872-9ffa-4ede-83ee-e0f1ec5e2b8d   97.09%  143.70/148  ·  Child, Family, and School Social Workers
      5/74 item(s) below max, -4.3 point(s)

Shortfalls
------------------------------------------------------------
  435 of 1433 rubric item(s) scored below their maximum, losing 486.0083 point(s)
  required item failed in 14 task(s):
      83d10b06-26d1-4636-a32c-23f92c57f30b, 7d7fc9a7-21a7-4b83-906f-416dea5ad04f, f84ea6ac-8f9f-428c-b96c-d0884e30f7c7
      27e8912c-8bd5-44ba-ad87-64066ea05264, c44e9b62-7cd8-4f72-8ad9-f8fbddb94083, f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb
      1b1ade2d-f9f6-4a04-baa5-aa15012b53be, 93b336f3-61f3-4287-86d2-87445e1e0f90, 24d1e93f-9018-45d4-b522-ad89dfd78079
      05389f78-589a-473c-a4ae-67c61050bfca, a74ead3b-f67d-4b1c-9116-f6bb81b29d4f, 7bbfcfe9-132d-4194-82bb-d6f29d001b01
      c2e8f271-7858-412f-b460-472463ad81d9, c357f0e2-963d-4eb7-a6fa-3078fe55b3ba

  ... and 435 more (use --json for all of them)
```

두 실행 사이에서 크게 움직인 과제는 둘뿐이고, 둘 다 이번에 고친 그 자리다.

| 과제 | 고치기 전 | 고친 후 | 차이 | 무엇이 바뀌었나 |
|---|---|---|---|---|
| `2ea2e5b5-257f-42e6-a7dc-93763f28b19d` | 19.53% (16.60/85) | 97.65% (83.00/85) | **+78.12** | 파워포인트의 표·차트·그룹 안 글자를 읽게 됨 |
| `38889c3b-e3d4-49c8-816a-3cc8e5313aba` | 3.23% (2.00/62) | 67.42% (41.80/62) | **+64.19** | 압축 파일 안의 구성원을 열게 됨 |

나머지 28개는 −5.49점에서 +3.69점 사이에서만 움직였다. 이 폭이 무엇인지는 아래
"채점 판단의 흔들림"에서 따로 다룬다.

## 만점 미달 항목 분류

30개 과제, 2,240점 만점 중 **380.73점이 깎였고 372개 항목이 만점 미만**이다.
아래는 그중 원인을 코드나 원본 파일로 직접 확인한 것들이다. 판정문의 설명을
믿고 옮긴 게 아니라, 문제의 파일을 직접 열어보거나 해당 함수를 읽어서 확인했다.

### (가) 도구 결함 — 검사 결과가 질문에 필요한 사실을 담고 있지 않다

가장 크고 가장 고치기 쉬운 부류다. 채점 항목이 "몇 쪽인가"를 묻는데, 채점기가
쓸 수 있는 검사 결과에 쪽 수가 아예 들어 있지 않다.

`core/tools/read_deliverable.py`의 `_inspect_docx`는 문단 수·표 수·구역 수·스타일
목록을 돌려준다. **쪽 수는 없다.** PDF에는 있다 — `_inspect_pdf`가 `page_count`를
돌려준다. 그리고 쪽 수를 셀 방법이 없는 것도 아니다. 같은 파일의 렌더링 경로는
Word 문서를 PDF로 변환하면서 `converted_page_count`를 이미 계산한다. 숫자는
존재하는데 서식 검사가 그걸 보고하지 않을 뿐이다.

결과는 이렇다.

| 과제 | 채점 항목 | 판정 | 점수 | 채점기가 본 증거 |
|---|---|---|---|---|
| `f84ea6ac-8f9f-428c-b96c-d0884e30f7c7` | 한 쪽 안에 들어가는가 | fail | 0 / 5 | `"char_count": 6532` |
| `c44e9b62-7cd8-4f72-8ad9-f8fbddb94083` | 한 쪽 안에 들어가는가 | partial | 3.75 / 5 | `"paragraph_count": 26` |
| `c2e8f271-7858-412f-b460-472463ad81d9` | 6쪽을 넘지 않는가 | fail | 0 / 2 | `"paragraph_count": 144` |
| `15ddd28d-8445-4baa-ac7f-f41372e1344e` | 2~3쪽인가 | fail | 0 / 2 | `"paragraph_count": 63` |
| `1b1ade2d-f9f6-4a04-baa5-aa15012b53be` | 2~3쪽인가 | fail | 0 / 1 | `"paragraph_count": 66` |
| `a328feea-47db-4856-b4be-2bdc63dd88fb` | 한 쪽 이하인가 | judge_error | — / 2 | `empty_final_text` |

**11.25점이 깎였고 2점은 판정 자체가 안 나왔다.** 여섯 항목 전부 렌더링 0회,
시각 채점 0회다 — 아무도 문서를 그려보지 않았으니 셀 방법이 없었다.

`f84ea6ac`의 0/5은 이 실행 전체에서 **필수 항목이 실패한 유일한 사례**다. 그
문서를 직접 열어보면 서식 검사가 왜 도움이 안 되는지 분명하다. 문단 수가 1,
표가 1이다. 문서 전체가 표 하나로 되어 있어서 문단 수는 아무것도 말해주지 않고,
채점기가 쥔 다른 숫자는 글자 수 6,532뿐이다. 글자 수로 쪽 수를 맞히라는 건
채점기에게 불가능한 요구다.

같은 부류가 PDF에도 하나 있다. `f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb`의 채점
항목은 "PDF 쪽 방향이 가로인가"를 묻는데, `_inspect_pdf`가 돌려주는 것은
`page_count`와 메타데이터뿐이고 **쪽 크기는 없다.** 채점기가 본 증거는
`{"kind": "pdf", "page_count": 1}` 하나였고 fail 0/2로 처리했다. 원본
`Touring Band_Stage Plot.pdf`를 직접 열어 확인한 결과 쪽 크기는 **432 × 288**,
너비가 높이보다 크다 — **가로가 맞다.** 정답은 옳았고 채점기는 판단할 재료가
없었다. 2점.

이 부류의 합계는 **13.25점 + 판정 불가 2점**이다.

### (나) 도구 결함 — "못 읽었다"를 "없다"로 바꿔 읽는다

`43dc9778-450b-4b46-b77e-b6d82b202035`의 정답 PDF에는 글자층이 아예 없다. 직접
확인했다 — 서식 검사는 `{"kind": "pdf", "page_count": 2, "fonts": []}`, 본문
읽기는 `char_count: 0`, 두 쪽 모두 추출되는 글자 길이 0, 입력 서식 위젯 0개.
스캔한 이미지다.

이 과제는 렌더링 2회, 시각 채점 2회를 **실제로 썼다.** 그런데도 10개 항목이
`"text": "", "char_count": 0`을 근거로 "그런 내용은 없다"고 판정했다. **13점.**

정답이 이미지인 것 자체는 결함이 아니다. 결함은 **빈 읽기 결과를 부재의 증거로
쓴 것**이다. 아무것도 못 읽은 결과와 읽었는데 없는 결과는 다른 사실인데, 지금
채점기는 둘을 구분하지 않는다.

### (다) 도구 결함 — 압축 파일 안의 소리를 듣지 못한다

`38889c3b-e3d4-49c8-816a-3cc8e5313aba`에 남은 **20.2점.** 이번 수정으로 열어보고
재는 것까지는 되지만, 실제로 듣는 단계는 여전히 배정되지 않는다. 위
"예측 3의 결과"에 자세히 적었다.

### (라) 라이브러리 한계 — 글자 이어붙임이 단어를 망가뜨린다

`2696757c-1f8a-4959-8f0d-f5597b9e70fc`의 채점 항목은 "9.08(c)(3) 문항 바로 뒤에
규정 인용이 나오는가"를 묻고, 채점기가 본 증거는 이렇다.

```
Regulatory Cita.on: VA Servicer Handbook M26-4, Chapter 9: VA Purchase, 9.08(c)(3), August 12, 2024
```

`Citation`이 `Cita.on`으로 추출됐다. 이 PDF는 "ti"를 한 글자로 붙여 그리는 글꼴을
쓰는데, 그 글자에 박힌 유니코드 대응이 잘못돼 있어 마침표로 나온다. 원본에서
이 단어는 딱 두 번 나오고, **두 번 다 채점 항목이 찾는 바로 그 자리다.**
정답에는 인용이 제대로 적혀 있다. 2점.

이건 우리 코드의 결함이 아니라 PDF 글자 추출 라이브러리의 한계다. 다만 결과는
같다 — 옳은 정답이 틀렸다고 판정됐다.

### (마) 입력 결함 — 정답이 자기 채점표를 문자 그대로는 못 지킨다

가장 점수가 낮은 과제가 여기 있고, 이건 채점기 잘못이 아니다.

**`c357f0e2-963d-4eb7-a6fa-3078fe55b3ba` — 49.29%, 101점 만점에 49.79점.**
30개 중 꼴찌다. 판정문을 믿지 않고 정답 파일 `UAT Plan.xlsx`를 직접 열어
확인했다.

- 채점 항목은 "**첫 줄**에 Role, Module, User Action, Test Scenario, Expected
  Result, Actual Result 머리글이 있을 것"을 요구한다. 실제 파일의 첫 줄은
  `UAT Test Plan`이라는 제목이고, 머리글은 **둘째 줄**에 있다. 게다가 그 열
  이름은 `User Action`이 아니라 `Source Event (User Action)`이다.
- 채점 항목은 "시험 사례 수가 **80~100개**"를 요구한다. 직접 세어보니
  **75개**다(시트 전체가 78행). 80에 못 미친다.
- 채점 항목은 "필수 항목을 비운 채 저장을 시도해 검증 오류가 나는 것을 확인하는
  행"처럼 구체적인 음성 시험 항목들을 요구한다. 정답 시트에 그런 행이 없다.

읽기는 완벽했다. 채점기가 인용한 증거는 전부 실제 셀 내용이다. **채점표가 요구한
것을 정답이 갖고 있지 않다.** 이 한 과제가 380.73점 중 51.21점, 전체 미달분의
13%를 차지한다.

**`83d10b06-26d1-4636-a32c-23f92c57f30b` — 66.90%.** 같은 성격이 더 잘게
번진다. 채점표는 "파일 이름이 `Sample`인 엑셀"을 요구하는데 정답은
`Sample v2.xlsx`고, "`Sample Size Calculation`이라는 이름의 시트"를 요구하는데
정답의 시트는 `Sample`과 `Sample Size`다. 이 두 항목이 곧바로 4점을 깎고,
그다음부터 채점표가 계속 "`Sample Size Calculation` 시트에서는…"이라고 부르는
바람에 뒤따르는 항목들도 줄줄이 부분 점수로 내려간다.

**`36d567ba-e205-4313-9756-931c6e4691fe` — 95.96%.** 채점표는 제목 문자열
`Federal Applicant - Risk Assessment Tool`이 그대로 보일 것을 요구한다. 정답은
`Federal Applicant – Risk Assessment Tool`이다. 붙임표(`-`)와 줄표(`–`)가 다르다.
글자 하나 차이로 2점.

예측 2가 미리 짚은 5개 과제(`7d7fc9a7`, `38889c3b`, `15ddd28d`, `24d1e93f`,
`4c18ebae`)도 같은 부류다. 지문이 요구한 형식 중 일부가 정답에 없다.

### (바) 채점 판단의 흔들림

두 실행 사이에 바뀐 것은 읽기 도구뿐이다. 그런데 읽기 도구와 아무 상관 없는
과제도 움직였다.

- `dfb4e0cd-a0b7-454e-b943-0dd586c2764c` **−5.49점.** 엑셀 한 개짜리 과제이고
  시각 채점 호출은 두 실행 모두 0회다. 같은 파일, 같은 증거인데 4개 항목의
  판정이 뒤집혔다 — 3개는 내려가고 1개는 올라갔다.
- `f84ea6ac-8f9f-428c-b96c-d0884e30f7c7` **−5.24점.** 대부분이 위 (가)의 쪽 수
  항목이 partial(2.25점)에서 fail(0점)로 내려간 몫이다. 채점기가 볼 수 없는
  것을 묻는 항목은, 물을 때마다 다르게 답한다.
- `17111c03-aac7-45c2-857d-c06d8223d6ad`은 백분율로는 +0.54점인데 받은 점수는
  44.05에서 43.65로 **내려갔다.** 만점이 61에서 60으로 바뀌었기 때문이다. 같은
  채점표에서 채점 항목의 총합이 실행마다 달라졌다는 뜻이다.

이건 결함이라기보다 **측정의 폭**이고, 2단계가 재려는 것이 정확히 이것이다.
여기 미리 드러난 폭이 이미 2단계의 임계값(표준편차 5점)에 닿아 있다는 점은
기록해 둘 값어치가 있다.

### (사) 채점기가 답을 내지 못한 2건

`scripts/judge_error_breakdown.py`로 분류한 결과, 1,433개 항목 중 2개가
`judge_no_verdict`(빈 응답)이고 하네스 결함 0건, 모델 결함 0건이다. 두 실행을
짝지어 보면 하네스 쪽 0 → 0, 채점 모델 쪽 0 → 2, 모델 쪽 0 → 0이다. 즉 새로 생긴
2건은 전부 채점 모델이 그냥 빈 응답을 준 경우이고, 우리 코드가 만든 게 아니다.

오류율 0.0014는 임계값 **2%** 아래다. 세 임계값 중 유일하게 통과한 항목이다.

### 필수 항목 통과율이 이 임계값에 닿을 수 없는 이유

**0.5714는 실패한 채점이 아니라 잘못 정의된 지표다.**

`core/grader.py`는 만점의 절대값이 4 이상인 항목을 필수 항목으로 본다
(`MAGNITUDE_THRESHOLD = 4`). 30개 과제에서 그런 항목은 **35개**뿐이고, 그중
**19개가 "결과물의 전반적인 서식과 문체"라는 똑같은 주관적 항목**이다. 나머지
16개도 대부분 비슷한 총평 성격이다.

통과로 세어주는 조건은 판정이 정확히 `pass`일 때뿐이다. `partial`은 통과가
아니다. 이번 실행은 20개 통과, 14개 부분 점수, 1개 실패였다. **0.95를 넘으려면
35개 중 34개가 `pass`여야 한다** — 19개의 주관적 서식 총평 중 부분 점수가 하나
이하여야 한다는 뜻이다. 사람이 채점해도 나오기 어려운 값이고, 채점기의 성능
문제가 아니라 산식의 문제다.

고치기 전 실행은 0.5429였다. 읽기 도구를 고쳐 평균 점수가 4.63점 오르는 동안
이 지표는 0.03밖에 움직이지 않았다 — 지표가 채점기의 실제 개선에 거의 반응하지
않는다는 증거다.

`core/grader.py:92`의 주석은 이 경계값을 1단계(과제 300)가 다시 따져보라고
스스로 적어두고 있다. 그래서 여기서 임의로 바꾸지 않고 그대로 보고한다.
필수 항목의 정의를 바꾸는 것은 지금까지 발표된 모든 모델 점수의 이 지표를 함께
바꾸는 일이라, 소유자 판단이 필요한 사안이다.

## 사용량과 청구액

| 항목 | 이번 실행 | 고치기 전 실행 |
|---|---|---|
| 채점 호출 합계 | 3,735 | 3,823 |
| └ 본채점 | 3,631 | 3,719 |
| └ 지각(이미지·소리) | 104 | 104 |
| 렌더링 호출 | 104 | 104 |
| 본채점 입력 토큰 | 27,299,254 | 26,251,937 |
| 본채점 출력 토큰 | 1,392,576 | 1,332,558 |
| 본채점 캐시 토큰 | 13,103,993 | 12,798,579 |
| 지각 입력 토큰 | 266,033 | 266,033 |
| 지각 출력 토큰 | 37,479 | 34,702 |
| 채점 지연 합계 | 26,264.17초 | 24,732.19초 |
| 렌더링 지연 합계 | 83.52초 | 84.08초 |

**이미지·소리 채점 호출 104회의 갈래는 이렇다.**

- `visual` **103회**
- `mixed` **1회**
- 소리만 쓰는 호출: **0회**

30개 과제 중 20개가 지각 호출을 썼고, 10개는 렌더링도 지각도 0회다. 렌더링
호출 수와 지각 호출 수가 104로 정확히 같다 — 그린 만큼만 봤다는 뜻이다.
소리 호출이 0인 것은 위 (다)에서 말한 배정 문제 때문이고, 명세가
`gpt-audio-1.5`를 미가격 모델로 기록해 두었음에도 이번 실행에서 실제로
호출되지는 않았다.

지각 입력 토큰이 두 실행에서 **정확히 같다**(266,033). 같은 104장을 똑같이
그려서 똑같이 보냈다는 뜻이고, 렌더링 경로가 실행 사이에 흔들리지 않았다는
작은 증거다.

**청구액은 모른다. 0으로 적지 않는다.**

실행이 스스로 기록한 값은 이렇다.

```
estimated_cost_usd: null
pricing_complete: false
unpriced_models: ['gpt-5.6-sol', 'gpt-audio-1.5']
```

`gpt-5.6-sol`과 `gpt-audio-1.5`는 공개 단가가 없다. 단가가 없으면 토큰 수를
곱할 상대가 없으므로 금액을 계산할 수 없다. 이 저장소에서 실제 청구액을 조회할
방법도 없다 — 이 작업 환경의 Azure 계정은 실행이 사용한 계정과 다르다.

그래서 `pricing_complete`는 `false`로 남긴다. 모르는 것을 0으로 적으면 그건
빈칸이 아니라 **틀린 기록**이 된다. 토큰 수와 호출 수는 위 표에 전부 남아 있으니,
나중에 단가가 확정되면 그때 곱하면 된다.

## 판정

**1단계는 통과하지 못했다.** 세 임계값 중 하나만 넘었다.

| 임계값 | 결과 | 판정 | 명세가 요구한 분류 |
|---|---|---|---|
| 평균 점수 ≥ **90**% | 82.87% | 미달 (miss) | **도구 결함**이 주 원인, **입력 결함**이 그다음 |
| 필수 항목 통과율 ≥ **0.95** | 0.5714 | 미달 (miss) | 셋 중 어느 것도 아님 — **지표 정의 결함** |
| 채점기 오류율 < **2%** | 0.14% | 통과 | — |

평균 점수 미달을 분해하면 이렇다. 깎인 380.73점 중 원인을 코드나 원본 파일로
직접 확인한 몫은:

| 원인 | 점수 | 성격 |
|---|---|---|
| 압축 파일 안의 소리를 듣지 못함 | 20.2 | 도구 결함 — 고칠 수 있음 |
| 빈 읽기 결과를 부재로 판단 | 13.0 | 도구 결함 — 고칠 수 있음 |
| Word 쪽 수 / PDF 쪽 방향을 검사가 보고하지 않음 | 13.25 (+판정 불가 2) | 도구 결함 — 고칠 수 있음 |
| 글자 이어붙임 추출 오류 | 2.0 | 라이브러리 한계 |
| 정답과 채점표의 문자 그대로의 불일치 | 57.2 이상 | 입력 결함 — 고칠 수 없음 |

**"채점기 결함"으로 분류된 것은 없다.** 채점 논리 자체가 틀린 사례는 확인되지
않았다. 채점기는 받은 재료 안에서 대체로 옳게 판단했고, 문제는 재료가 부족했던
것과 정답 자체가 채점표를 못 맞춘 것이다.

**"저장소 문제면 고치고, 검증하고, 다시 돌린다"에 따라 이미 한 번 돌았다.**
읽기 도구의 구멍 두 개(파워포인트 표·차트·그룹, 압축 파일 컨테이너)를 고치고
다시 채점해 78.24% → 82.87%를 얻었고, 그 두 수정이 정확히 무엇을 회복했는지는
위 비교표에 있다.

**여기서 한 번 더 돌리지 않는다.** 남은 도구 결함 세 가지를 전부 고쳐도 회복
가능한 최대치는 약 46점, 2,240점 대비 약 2.1점이다. 84~85% 근처가 상한이고
90%에는 닿지 않는다. 90%를 막고 있는 나머지는 (마)의 입력 불일치와 (바)의 판단
폭인데, 둘 다 채점기를 고쳐서 넘을 수 있는 벽이 아니다. 확인되지 않은 개선을
기대하며 같은 값의 유료 실행을 반복하는 것은 명세가 요구한 "고치고, 검증하고,
다시 돌린다"가 아니라 그냥 다시 돌리는 것이다.

### 이 실행이 확정한 것

- **정답의 천장은 약 83%다.** 발표된 모든 모델 점수는 100점이 아니라 이 값을
  기준으로 읽어야 한다.
- 그 천장이 낮은 이유의 대부분은 채점기가 정답을 끝까지 읽지 못해서다. 모델
  점수와 정답 점수는 **같은 손실을 함께 겪는다** — 즉 이 낮은 천장은 모델 간
  비교를 무효로 만들지는 않지만, 절대 점수를 만점 대비로 읽는 것은 무효로
  만든다.
- 채점기가 답을 못 내는 비율은 낮다(0.14%). 채점기는 흔들리지만 멈추지는 않는다.
- 필수 항목 통과율은 지금 정의로는 쓸 수 없는 지표다.

### 후속 항목 (별도 PR)

1. **Word 문서의 쪽 수를 서식 검사가 보고하게 한다.** 숫자는 이미 렌더링 경로가
   계산하고 있다. PDF의 쪽 크기도 함께 내보내면 (가) 전체가 닫힌다. — 약 15점
2. **압축 파일 구성원에 듣기 모델이 배정되게 한다**
   (`grader_routing.py`, `deliverable_selector.py`). — 약 20점
3. **빈 읽기 결과를 부재의 증거로 쓰지 못하게 한다.** 글자 수가 0이면 판단을
   그리기·보기 경로로 넘겨야 한다. — 약 13점
4. **도구 설명서에 `scope={"member": ...}`를 적는다.** 이번엔 채점기가 스스로
   찾아냈으므로 결함 수정이 아니라 재현성 개선으로 다룬다.
5. **필수 항목의 정의를 소유자와 함께 다시 정한다.** 코드를 바꾸면 발표된 모든
   점수의 이 지표가 함께 바뀌므로, 여기서 임의로 결정하지 않는다.
