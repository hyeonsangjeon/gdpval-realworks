# CODEX — 작업 순서 안내 (3개 task 파일 오케스트레이션)

3개의 task 파일을 받았다. 아래 **순서와 게이트**대로 진행해라. 한 번에 다 하지 말고, 각 단계의 산출이 나온 뒤 다음으로 간다. 모든 새 산출물·중간 점검 파일은 `tasks/0601_monday/`에 둔다(폴더 없으면 생성).

## 전체 맥락 (왜 이 순서인가)
원래 질문은 "채점 LLM을 경량(mini) vs 중량(gpt-5.4) 중 뭘로 갈까"였으나, 분석 결과 진짜 병목은 *모델*이 아니라 **채점기가 받는 evidence가 빈약하다**는 것(특히 formatting: critical의 32.5%인데 현재 default는 실제 형식 속성을 0/157 인용). 그래서 방향은 "채점기에게 모든 시각·청각·형식 정보를 추출해 주는 환경 + rubric 판정 절차를 skill로" 가는 것이고, 모델 경량/중량 결정은 그 *뒤*에 measure한다. 이 3파일은 그 방향의 첫 단계들이다.

## 순서

### STEP 0 — `CODEX_close_flip.md` (먼저, 공짜, 독립)
- v2-mini flip 폐기 기록(FINAL_RECOMMENDATION.md에 SUPERSEDED 배너).
- 다른 단계와 의존성 없음. 가장 먼저 끝내라.
- **이미 적용돼 있으면**(FINAL 맨 위에 SUPERSEDED 배너 존재) skip하고 그렇게 보고.
- 끝나면 STEP 1로.

### STEP 1 — `CODEX_1_rubric_criterion_profile.md` (핵심 선행)
- 220 rubric criterion을 modality × (self-contained vs reference-requiring)로 분류.
- 산출: `tasks/0601_monday/rubric_criterion_profile.md`.
- **이게 STEP 2의 입력이다.** self-contained 비율과 "눈·귀 명세"가 안 나오면 STEP 2를 시작하지 마라.
- **GATE — STEP 1 끝나면 멈추고 결과를 보고해라(아래 "보고 형식"). owner 확인 전엔 STEP 2 자동 진행 금지.** 이유: STEP 1 결과(self-contained가 다수냐 reference가 많냐)가 STEP 2 설계의 형태와 *할 가치*를 바꾼다. reference-requiring이 의외로 많으면 접근 자체를 재검토해야 할 수도 있다.

### STEP 2 — `CODEX_2_eyes_ears_design.md` (STEP 1 통과 + owner-go 후에만)
- 추출 환경(A) + skill·동적 rubric 로더(B) 설계.
- 산출: `tasks/0601_monday/grading_eyes_ears_design.md`.
- STEP 1의 `rubric_criterion_profile.md`를 입력으로 읽어라.
- 이건 **설계까지**다 — 무거운 구현(컨테이너 빌드, LibreOffice 파이프라인)·full run·머지는 이 단계에서 하지 말고, 설계 문서의 "구현 무게" 판정으로 owner가 다음을 정한다.

## 단계 간 공통 규칙
- **각 STEP 끝에 멈추고 보고**한 뒤 다음으로. 특히 STEP 1→2 사이는 hard gate(owner 확인 필요).
- 한 STEP이 막히거나 결과가 예상과 다르면, *다음 STEP으로 넘어가지 말고* 무엇이 막혔는지 보고해라(방향을 임의로 틀지 말 것).
- read-only가 기본. Azure run·full-220 run·main push/머지 금지(각 파일의 제약 따름).
- 결론 예단 금지 — 특히 STEP 1에서 "reference-requiring이 많다"가 나와도 정직하게 적어라(접근에 불리해도).

## 보고 형식 (각 STEP 끝)
```
STEP [N] 완료.
산출: tasks/0601_monday/[파일명]
핵심 결과: [3~5줄 — STEP1이면 self-contained/reference 비율 + 눈·귀 명세 요약]
다음 STEP 진행 가능 여부: [예 / owner 확인 필요 / 막힘(이유)]
```

## 시작
STEP 0부터. close_flip이 이미 적용돼 있으면 그렇게 알리고 STEP 1로 진행, STEP 1 끝나면 **GATE에서 멈춰라.**
