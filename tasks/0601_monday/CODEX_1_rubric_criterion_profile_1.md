# CODEX — rubric criterion 성격 분석 (read-only, 배치 없음, mobile 가능)

- **Repo:** `gdpval-realworks` (local, `main`)
- **왜 이게 우선:** 채점기에 "눈과 귀"(modality별 추출 + 판정)를 만들어주는 grading skill을 설계하려는데, *무엇을* 만들지는 rubric criterion이 *무엇을 요구하는지*에 달렸다. criterion이 절대 기준("클리핑 없나")이면 추출만으로 채점되고, 상대 기준("원본보다 나은가")이면 reference가 필요하다. deliverable_files는 100점 보장이 아니고 wav 등은 null이라, **reference에 의존하는 criterion이 얼마나 되는지가 이 접근의 성립 여부를 가른다.**
- **목적:** 220 task의 모든 rubric criterion을 (a) modality × (b) self-contained vs reference-requiring로 분류해, grading skill이 만들어야 할 "눈·귀"의 정확한 명세를 도출한다. **결론을 내리는 게 아니라 명세의 입력을 만드는 작업.**

## 성공 기준
- 모든 criterion이 두 축으로 분류돼 집계됨(추정 아님, rubric 텍스트 기반).
- "이 접근이 reference 없이 성립하는가"에 데이터로 답함(self-contained 비율).
- 분류 기준(어떤 문구를 self-contained로, 어떤 걸 reference-requiring으로 봤는지)을 명시 — 재현 가능하게.

## 권한/제약
- **read-only.** 코드·config·grade JSON 수정 금지. Azure run·full-220 run 금지(인증 불필요).
- 숫자는 rubric에서 실제 집계. main push/머지 금지.

## 작업

### 1. rubric 로드 + modality 분류 (modality는 이미 분포 있음 — 재계산해 정합 확인)
- GDPVal 220 task rubric 로드(`rubric_loader.py` / HF 캐시 `openai/gdpval` / 기존 grade JSON 중 쉬운 경로).
- 각 criterion을 `grader_routing.py`의 `classify_criterion`으로 visual/audio/formatting/text 분류. (modality_distribution.md와 숫자 일치하는지 확인 — 안 맞으면 그 사실 기록.)

### 2. self-contained vs reference-requiring 분류 (이게 핵심·신규)
각 criterion 텍스트를 읽고 둘로 분류:
- **self-contained (절대 기준):** deliverable *자체*만 보면 판정 가능. reference/원본 불필요. 예: "오디오에 클리핑이 없다", "B열이 통화 형식이다", "차트가 포함돼 있다", "문서에 섹션 N개가 있다", "표 헤더가 굵다", "특정 항목이 명시돼 있다".
- **reference-requiring (상대/외부 기준):** 판정에 원본·정답·외부 사실과의 비교가 필요. 예: "원본 대비 믹싱이 개선됐다", "입력 데이터를 정확히 반영한다", "사실관계가 맞다(외부 지식 필요)", "요청한 변경이 모두 적용됐다(원본 대비)".
- **모호하면** 제3범주 `ambiguous`로 두고 왜 모호한지 적어라. 무리하게 한쪽으로 밀지 말 것.
- 각 범주의 *판정 근거가 무엇인지*도 메모: self-contained는 "어떤 추출이 있으면 판정되나"(예: ffmpeg 클리핑 검출, openpyxl number_format), reference-requiring은 "무엇과 비교해야 하나".

### 3. 교차 집계
- **modality × {self-contained / reference-requiring / ambiguous}** 교차표(개수 + %).
- **critical item(|max|≥4)에 한정한** 동일 교차표 — 일반과 따로.
- modality별로 self-contained가 다수인가? 특히 audio/visual/formatting에서 — 이게 "추출만으로 그 modality를 채점할 수 있나"를 답함.

### 4. "눈·귀" 명세 도출
- 각 modality의 self-contained criterion을 채점하려면 *어떤 추출 능력*이 필요한지 목록화:
  - audio → 어떤 측정(클리핑/LUFS/길이/포맷/스펙트럼…)이 어떤 criterion을 커버하나. 필요 라이브러리(ffmpeg/soundfile/pedalboard 등).
  - visual → 렌더링 필요한가, 어떤 속성.
  - formatting → 어떤 형식 속성(number format/conditional formatting/alignment/렌더…). (formatting_diagnosis.md의 inspect_formatting 누락 목록과 연결.)
- reference-requiring criterion은 별도 목록 — 이건 추출로 안 되니 "나중에 어떻게 다룰지" 미결 항목으로.

## 출력 — `tasks/0601_monday/rubric_criterion_profile.md` 하나
(폴더 없으면 생성. 이 작업의 모든 산출물·중간 점검 파일은 `tasks/0601_monday/` 아래에 둔다. 기존 컨텍스트 *읽기*는 `tasks/0531_sunday/`·`tasks/rebuilding_grading_task/`·grade JSON에서 — 읽기 경로는 안 바뀜.)
```
# RUBRIC CRITERION PROFILE
## 한 줄 결론
self-contained [X%] / reference-requiring [Y%] / ambiguous [Z%]. 
→ 추출 기반 grading skill로 [대부분 / 상당수 / 일부]의 criterion 채점 가능. reference 문제는 [무시 가능 / 별도 설계 필요].
## 분류 기준 (self-contained vs reference-requiring 판정 룰)
## modality × 성격 교차표 (전체 / critical 한정)
## modality별 self-contained 다수 여부
## "눈·귀" 명세 (modality별 필요 추출 능력 + 라이브러리, criterion 매핑)
## reference-requiring criterion 목록 (미결, 나중 설계)
## ambiguous 목록 (왜 모호한지)
```

## 제약 재확인
- read-only, Azure run 없음, push 없음.
- self-contained/reference 분류 룰을 명시(재현 가능).
- 숫자는 rubric 실제 집계, 추정 금지.
- 결론 예단 금지 — reference-requiring이 의외로 많을 가능성도 정직하게.
