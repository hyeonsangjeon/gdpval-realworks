# [분석] text criterion mini vs 5.4 신뢰도

> **벤치마크 분석** — production 모델 결정용이 아님(production은 전부 5.4로 이미 기움, 예산 여유). mini의 신뢰 불가가 *판단형*(formatting/visual)에 국한인지 *사실 확인형*(text)에서도 그런지의 **경계 지도**를 그린다.
> **git 상태 변경 없음**(read-only, 미커밋). **220 재채점 없음** — 기존 220 mini grade JSON 재사용 + text item 30개만 gpt-5.4 소규모 재채점. 인증: 로컬 `az login`(user, tenant 16b3c013), stale SP env unset(`.env` 불변).

## 한 줄 결론

text item **30개** mini vs 5.4: **verdict 일치율 86.7%(26/30)**, numeric **93%** > existence **80%**, |score diff|(max 대비) 평균 **0.099**(매우 작음). **mini는 text(사실 확인)에서 5.4와 거의 일치 → mini의 신뢰 불가는 *판단형*(formatting/visual)에 국한**되고 사실 확인형에선 쓸 만하다. 불일치 4건은 양방향(2건 mini 맞고 5.4 과보수, 2건 모호 criterion서 5.4 partial이 더 정확)이며 **랜덤 대량 오류가 아님**. 즉 mini 약점의 경계 = **"판단(judgment)"**. (분석 목적 — production은 전부 5.4 유지, 본 결과가 그 결정을 바꾸지 않음.)

---

## 1. text item 표본 (추출 기준 + 목록)

- **모집단:** 220 mini JSON(`data/grades/exp003_...rubric_v2_tools_mini.json`)의 **`routing_modality="text"` + `decided_by="judge"`** item = 4,122개. 그중 deliverable이 로컬에 있는 것 760개(numeric 335 / existence 262 / other 163).
- **추출:** *객관적 유형*(numeric/existence) 위주로 task/modality/verdict 층화, task당 ≤3개로 분산 → **30개**(numeric 15 / existence 15; verdict fail 14 / pass 13 / partial 3; 13개 task; pdf 12·xlsx 11·docx 5·pptx 2).
- 객관 기준: 파일에 정답이 명확히 있는 것 — 예: "Form 8959 line 19 is $5,125"(숫자), "section titled 'Household Composition'"(존재), "1251 April ending balance equals $369,976.70"(값).

| 유형 | 개수 | 예시 criterion |
|---|---:|---|
| numeric(숫자/값) | 15 | "Schedule 3 line 11 is $4,113" / "assembly cost INR 107,900" |
| existence(존재/필드) | 15 | "Outputs list includes a Drums wedge entry" / "first tab is a Table of Contents" |

(전체 30개 표: `tasks/0609_tuesday/_text_sample.json`, 채점 결과 `tasks/0609_tuesday/text_grades.json`.)

## 2. 5.4 재채점 (소규모, 비용)

- 동일 프롬프트(`prompts/grader_judge_v2.md`)·동일 deliverable·**렌더 없음**(text는 렌더 무관)으로 30개를 gpt-5.4 채점. `read_deliverable`(inspect_structure/formatting + read_content) 관찰을 mini와 동일하게 입력.
- **비용: 30 calls ≈ <$0.5**(text는 이미지 없어 토큰 가벼움). 새 대규모 run 없음.
- 공정성: text 정답이 컨텍스트에 들어오도록 read_content 윈도를 충분히(≤60K) 확보 — 양 arm 동일 관찰 블록.
- (구현 노트: 재채점 점수 스케일 버그 — 5.4 awarded가 max 대신 ×5로 기록 — 를 `g54_award_fixed = partial × item_max`로 사후 정정. verdict는 영향 없음.)

## 3. mini vs 5.4 비교

### verdict 일치율 / score diff
| 지표 | 값 |
|---|---|
| **verdict 일치율** | **26/30 = 86.7%** |
| — numeric | 14/15 = **93%** |
| — existence | 12/15 = **80%** |
| **\|score diff\|** (max 대비 fraction) | 평균 **0.099**, 최대 1.00 |
| 불일치 | 4건 |

→ text에서 mini와 5.4는 **대부분 같은 결론**. 점수 차이는 평균 0.1(만점 대비)로 작고, numeric은 93%로 특히 높음.

### 불일치 4건 판별 (파일 내용 직접 확인 — text는 객관)
| # | task | criterion(요약) | mini | 5.4 | **판별** |
|---|---|---|---|---|---|
| 1 | bbe0a93b | 스페인어 표에 교통 관련 질문 | pass ✓ | fail | **mini 맞음.** Espanol.pdf(전체 815자)에 "¿Tiene transporte confiable?" 명확히 존재. 5.4가 영어 가이드를 인용하며 fail — **5.4 판단 오류(과보수)** |
| 2 | ee09d943 | 보이는 수식 오류(#REF! 등) 없음 | pass ✓ | fail | **mini 맞음.** 76K 추출 텍스트에 #REF!/#VALUE! 등 0건. 5.4는 "전 시트 스캔 못 함"으로 fail — **5.4 과보수 오류** |
| 3 | 1b1ade2d | TRAR 버전관리/개정이력 명시 | pass | partial | **5.4가 더 정확.** "TRAR" 문자열 부재(문서는 TRSO), audit trail은 있음 — mini의 pass는 관대, 5.4 partial 합당 |
| 4 | 1b1ade2d | PM이 승인 흐름 상태 모니터 명시 | pass | partial | **모호 criterion.** "dashboards ... real-time visibility to PM"은 있으나 "approval flow" 명시 없음 — 5.4 partial이 문자적으로 더 정확 |

### mini 오차 패턴 — text에서는?
- **랜덤 대량 오류 아님.** 불일치 4/30이고, 양방향: 2건은 mini가 맞고 **5.4가 과보수**, 2건은 모호 criterion에서 5.4 partial이 더 정밀.
- **일관된 축:** **5.4 = 엄격/문자적(증거가 관찰에 안 보이면 fail/partial), mini = 관대(함의로 pass)**. 이건 mini의 *결함*이라기보다 둘의 *엄격도 차이*. 객관적으로 따지면 text에서 **mini도 5.4도 큰 오류는 드물다.**
- formatting(Overall-style)의 mini MAE 1.18 + RANDOM(stdev 1.44)과 **대조적** — text에서는 mini가 안정적.

## 4. 해석 (mini 약점의 경계)

### 경계: 판단형(judgment)에 국한, 사실 확인형(text)은 쓸 만
- **검증된 신호:** text criterion에서 mini는 5.4와 **86.7% 일치**(numeric 93%), 점수 차 평균 0.1. mini의 신뢰 불가는 **formatting/visual 같은 *판단형*에 집중**되고, 숫자/존재/값 같은 *사실 확인형*에서는 5.4와 사실상 동급.
- 이는 0607 결정 보고서의 하이브리드 라우팅(판단 criterion만 5.4, text는 mini) 가설을 **데이터로 뒷받침** — 적어도 *반증하지 않음*.

### text 유형별
- **numeric(93%) > existence(80%).** 숫자/값 일치는 mini가 특히 안정적. 존재("X 섹션이 있나")는 약간 더 갈리는데, 갈림의 원인이 **criterion 모호성**(TRAR/approval-flow처럼 문서가 동의어/함의로 충족)이지 mini의 무작위 오류가 아님.
- 즉 existence의 불일치는 "mini가 못 믿을"이 아니라 "criterion이 해석 여지를 줌 + mini가 관대".

### ⚠️ 한계 (신호일 뿐, 단정 금지)
- **30개 소표본**, **17개 task에 국한**(220 mini JSON의 부분 재채점 범위), 객관적 numeric/existence 유형만. 주관적 text(품질/적절성 서술)는 제외.
- gold/owner 라벨 없이 **mini vs 5.4 상호 비교 + 파일 직접 판별**로 정답을 정함 — owner gold 대비 절대 정확도는 아님.
- 5.4의 과보수(불일치 2건)는 read_content 관찰에 의존하는 **메타-only 채점의 한계**일 수 있음(파이프라인의 능동 tool-loop 5.4는 더 탐색해 다르게 판단 가능). 본 probe는 메타-only 단발 채점.
- **production 결정(전부 5.4)을 바꾸지 않음.** 이건 mini 약점 경계의 *지도*이지 모델 교체 근거가 아님.

### 결론 한 줄
**mini의 "못 믿음"은 판단형(formatting/visual)에 국한**되고, **사실 확인형 text에서는 5.4와 86.7% 일치(numeric 93%)로 쓸 만**하다. 불일치는 양방향·소수이며 5.4의 과보수/criterion 모호성이 주원인 — mini의 무작위 오류가 text로 번지지는 않는다.

---

### 부록 — 산출물(미커밋) / 근거
- 표본: `tasks/0609_tuesday/_text_sample.json` (30개), 후보 풀 `tasks/0609_tuesday/_text_candidates.json` (760개).
- 채점: `tasks/0609_tuesday/text_grades.json` (mini vs 5.4 verdict/score/evidence/reasoning, `g54_award_fixed` 포함).
- 하니스: `tasks/0609_tuesday/text_probe.py` (5.4 text 재채점, 렌더 없음).
- mini 원본: `data/grades/exp003_...rubric_v2_tools_mini.json`.

### 부록 — 제약 준수
git 상태 변경 없음(read-only, 미커밋). 220 재채점 없음(text 30개만, <$0.5). 새 대규모 Azure run 없음. 로컬 az login(user, tenant 16b3c013), stale SP env unset(`.env` 불변), secret 미조작. 소표본 한계 명시, 단정 회피, production(전부 5.4) 불변.
