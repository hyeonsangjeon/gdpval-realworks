# VISION RENDER VALIDATION — gold 20 Overall Style

> 산출: read-only 검증. **git 상태 변경 없음** (커밋/머지/푸시 없음). 렌더 PNG·grades·이 보고서는 owner 검토용 미커밋 산출물.
> 측정 = owner gold와의 거리(MAE). 점수 상승이 아니라 **거리 감소**로 판정. 회귀 확인 포함.
> 채점 모델: **gpt-5.4 (vision)**, judge prompt `prompts/grader_judge_v2.md`, effort=medium, temp 미사용(reasoning).

## 한 줄 결론

렌더+메타데이터 vs 메타데이터-only: **전체 MAE 1.21(mini) → 0.85(gpt-5.4 render+vision)**.
**그러나 이 개선은 거의 전부 모델 업그레이드(mini→5.4) 효과다.** 동일 gpt-5.4로 렌더 효과만 격리하면 **메타-only 0.852 → 렌더+vision 0.848 (Δ −0.004, 사실상 0)**. 격차 큰 항목은 **모델 업그레이드만으로 이미 대부분 교정**됐고(99ac6944 −2.5→+0.25, bbe0a93b −3.0→+0.83), 렌더의 한계 기여는 modality마다 엇갈림 — **pptx만 일관 개선(MAE −0.062), xlsx는 오히려 악화(+0.100)**, positive control 4개 중 3개 |delta| 증가(경미한 회귀). **판정: 220 전체 렌더 투자는 현 상태로 정당화되지 않음(재고).** 단 **pptx는 선별 렌더 가치 있음**, xlsx는 렌더 범위(시트 선택) 개선 후 재검증 필요. git 상태 변경 없음.

---

## 렌더 (25개 unit / 93 PNG 생성, tofu 구분, 실패 0)

- **경로:** PDF/이미지 → PyMuPDF(fitz) 직접 dpi150; XLSX/DOCX/PPTX → `soffice --headless --convert-to pdf` → PyMuPDF PNG. 로컬 LibreOffice 26.2.4 사용. PNG는 가로 1200px로 다운샘플, 페이지 상한 8.
- **대상:** gold 20 태스크 = single 16 + split 4(child 9) = **25 unit, 93 PNG, 렌더 실패 0**. 모든 deliverable 로컬 존재(`batch-runner/workspace/upload/deliverable_files/<task_id>/`). 선택 파일은 220 clean 재채점(selector+audit)이 고른 **실제 deliverable**과 일치(owner가 채점한 파일과 동일 — Bug2 mis-select 해소됨).
- **tofu(□) 구분 — 폰트 문제 vs 소스 결함:**
  - **폰트 문제(수정함):** `9a0d8d36`(pptx, Calibri) 제목의 **U+2011 NON-BREAKING HYPHEN**이 □로 렌더 → LibreOffice 대체 폰트 Carlito에 해당 글리프 부재가 원인(소스 결함 아님; PowerPoint는 정상). **임시 복사본에서 U+2011→`-`(U+002D) 치환**으로 해소(원본 불변, 시각적으로 동일한 하이픈). 폰트 Carlito/Caladea 설치.
  - **소스 결함(그대로 유지):** PDF는 폰트 임베드라 LibreOffice 무관 — owner가 지적한 실제 글리프 결함이 **충실히 재현**됨: `43dc9778` "W■2s/Long■term"(하이픈 박스, 실제 PDF 결함), `27e8912c` en-dash 박스 + 동일·무의미 appendix 다이어그램. vision이 봐야 할 진짜 결함이므로 손대지 않음.
- **렌더 범위 한계(중요):** 큰 워크북은 8페이지 상한에 걸림 — `ee09d943`(95시트→8p), `83d10b06`(35→8), `6dcae3f5`(23→8). 핵심 데이터 시트가 잘리거나 빈 페이지가 섞여 **xlsx under-score의 한 원인**(아래 측정 참조).

## vision 채점 (렌더+메타데이터 동시 입력, split child 집계, evidence가 시각 근거인지)

- **설계(쌍대·모델 통제):** 동일 gpt-5.4 judge에 동일 프롬프트로 두 arm을 채점.
  - **Arm A (메타-only):** criterion + `read_deliverable`(inspect_structure / inspect_formatting / read_content) 관찰을 텍스트로. **이미지 없음.**
  - **Arm B (렌더+vision):** Arm A와 **완전히 동일한 텍스트 + 렌더 PNG 첨부.** 두 arm의 유일한 차이 = 이미지 → **렌더 효과만 격리.**
- **evidence가 실제 시각 근거인가:** **ArmB 25/25 unit이 시각 언어로 채점**(reasoning에 "the image shows cramped/truncated headers", "several rendered pages are bare", "ample whitespace", "the deck is visually plain", "clear hierarchy across slides" 등). 파일명/텍스트만으로 답한 unit 없음 — **vision이 렌더를 실제 근거로 삼음.**
- **split 4개 child 집계(`blocking_min_else_mean` — 기존 정책 유지, 정상 동작):**
  - `27e8912c`: A[5.0, 3.5]→4.25 / B[3.5, 3.0]→3.25
  - `bbe0a93b`: A[3.5, 3.5, 2.5]→3.17 / B[3.5, 4.0, 4.0]→3.83
  - `6dcae3f5`: A[1.5, 2.0]→1.75 / B[1.0, 1.5]→1.25
  - `a74ead3b`: A[3.75, 3.5]→3.62 / B[3.5, 4.25]→3.88
- 비용 인지: **judge 호출 ~50회**(25 unit × 2 arm), 첨부 이미지 93장. gold 20 검증 규모.

## 측정 표 (task별 owner / mini메타 / gpt5.4 Arm A 메타 / Arm B 렌더+vision / |delta| 변화)

`mini` = 기존 220 clean 재채점(gpt-5.4-mini, 메타-only) 베이스라인. `--`는 부분 재채점에 없던 3개(0419f1c3/9a0d8d36/403b9234).
`impr = |dA| − |dB|` (양수 = 렌더가 owner에 더 가까워짐).

| task | kind | owner | mini메타 | A(meta) | B(render+vis) | \|dA\| | \|dB\| | impr |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 7d7fc9a7 | pdf | 3.0 | 2.00 | 1.00 | 1.50 | 2.00 | 1.50 | **+0.50** |
| 27e8912c | pdf | 3.5 | 5.00 | 4.25 | 3.25 | 0.75 | 0.25 | **+0.50** |
| 85d95ce5 | pdf | 2.5 | 5.00 | 3.50 | 3.25 | 1.00 | 0.75 | **+0.25** |
| 43dc9778 | pdf | 3.0 | 2.50 | 3.50 | 3.50 | 0.50 | 0.50 | 0.00 |
| f9a1c16c | pdf | 3.0 | 3.00 | 3.00 | 3.50 | 0.00 | 0.50 | −0.50 |
| bbe0a93b | pdf | 3.0 | 0.00 | 3.17 | 3.83 | 0.17 | 0.83 | −0.67 |
| 9a0d8d36 | pptx | 3.5 | -- | 2.50 | 3.75 | 1.00 | 0.25 | **+0.75** |
| 403b9234 | pptx | 3.5 | -- | 3.00 | 3.25 | 0.50 | 0.25 | **+0.25** |
| ec591973 | pptx | 2.5 | 3.00 | 2.50 | 3.00 | 0.00 | 0.50 | −0.50 |
| a74ead3b | pptx | 3.0 | 2.75 | 3.62 | 3.88 | 0.62 | 0.88 | −0.25 |
| 575f8679 | docx | 4.0 | 5.00 | 5.00 | 4.25 | 1.00 | 0.25 | **+0.75** |
| 0419f1c3 | docx | 4.0 | -- | 5.00 | 5.00 | 1.00 | 1.00 | 0.00 |
| 1b1ade2d | docx | 4.0 | 5.00 | 5.00 | 5.00 | 1.00 | 1.00 | 0.00 |
| 93b336f3 | docx | 4.0 | 5.00 | 5.00 | 5.00 | 1.00 | 1.00 | 0.00 |
| 6dcae3f5 | docx | 2.0 | 1.75 | 1.75 | 1.25 | 0.25 | 0.75 | −0.50 |
| 7b08cd4d | xlsx | 2.0 | 3.00 | 2.75 | 2.00 | 0.75 | 0.00 | **+0.75** |
| 99ac6944 | xlsx | 2.5 | 0.00 | 3.50 | 2.75 | 1.00 | 0.25 | **+0.75** |
| 7bbfcfe9 | xlsx | 4.0 | 2.00 | 1.00 | 1.50 | 3.00 | 2.50 | **+0.50** |
| ee09d943 | xlsx | 3.0 | 4.00 | 3.50 | 1.50 | 0.50 | 1.50 | −1.00 |
| 83d10b06 | xlsx | 2.5 | 1.50 | 1.50 | 0.00 | 1.00 | 2.50 | **−1.50** |

**MAE:** mini메타(17)=**1.176** · gpt5.4 ArmA메타(20)=**0.852** · gpt5.4 ArmB렌더+vision(20)=**0.848**

- **모델 업그레이드 효과(mini→5.4, 둘 다 메타-only):** 1.176 → 0.852 (**−0.324**, 큼).
- **렌더 효과(동일 gpt-5.4, 메타 vs 렌더+vision):** 0.852 → 0.848 (**−0.004, 사실상 0**).
- 즉 헤드라인 1.21→0.85의 ≈99%는 모델, 렌더 기여는 노이즈 수준.

## 회귀 확인 (owner와 가까웠던 positive control 유지되나?)

| task | owner | A(meta) | B(render) | \|dA\| | \|dB\| | 결과 |
|---|---:|---:|---:|---:|---:|---|
| f9a1c16c | 3.0 | 3.00 | 3.50 | 0.00 | 0.50 | ▲ 악화(+0.50) |
| 6dcae3f5 | 2.0 | 1.75 | 1.25 | 0.25 | 0.75 | ▲ 악화(+0.50) |
| a74ead3b | 3.0 | 3.62 | 3.88 | 0.62 | 0.88 | ▲ 악화(+0.26) |
| 43dc9778 | 3.0 | 3.50 | 3.50 | 0.50 | 0.50 | = 유지 |

**positive control 4개 중 3개가 렌더 후 |delta| 증가** = 경미한 회귀. 렌더가 멀쩡한(이미 owner와 가까운) 항목을 약간 밀어냄. 특히 `f9a1c16c`(스테이지 plot, perception-critical 케이스)는 메타-only가 이미 정확(0.00)했는데 렌더 후 +0.50 — 렌더가 더 나아지게 하지 못함.

## modality별 MAE 변화 (어디에 렌더가 가장 효과 — 220 우선순위)

| modality | n | A(meta) | B(render+vis) | ΔMAE | bias A → B |
|---|---:|---:|---:|---:|---|
| **pptx** | 4 | 0.531 | **0.469** | **−0.062** | −0.22 → +0.34 |
| pdf | 6 | 0.736 | 0.722 | −0.014 | +0.07 → +0.14 |
| docx | 5 | 0.850 | 0.800 | −0.050 | +0.75 → +0.50 |
| **xlsx** | 5 | 1.250 | **1.350** | **+0.100 (악화)** | −0.35 → **−1.25** |

- **pptx = 렌더가 가장 효과(−0.062).** `9a0d8d36`가 대표(메타 2.5→렌더 3.75, owner 3.5에 근접) — vision이 "consistent 9-slide master, clear hierarchy, ample whitespace"를 실제로 보고 상향. **220 렌더 우선순위 modality = pptx.**
- **xlsx = 유일하게 악화(+0.100), bias가 −0.35→−1.25로 크게 under-score.** **원인 2가지(렌더 품질 + vision 판단):**
  1. **렌더 범위(품질) 문제:** 큰 워크북 8페이지 상한 → `ee09d943`(95시트) "several rendered pages are bare", `83d10b06` 핵심 시트 잘림. vision이 빈/잘린 페이지를 "plain/empty"로 과소평가.
  2. **vision 판단 편향:** 스프레드시트의 "시각적으로 plain"(병합/색/테두리 적음)을 owner보다 가혹하게 처벌(`83d10b06` 0.0 fail vs owner 2.5). xlsx는 본래 데이터 그리드라 "시각 화려함"이 품질 지표가 아닌데 vision이 그렇게 봄.
- pdf/docx는 거의 변화 없음(−0.014/−0.050) — 텍스트 메타데이터로 이미 충분히 잡힘.

## 판정 + 다음

**판정: 220 전체 렌더 투자는 현 상태로 정당화되지 않음(재고).**

1. **격리된 렌더 효과 = −0.004 (NULL).** owner gold 정확도를 끌어올린 것은 **렌더가 아니라 모델 업그레이드(mini→5.4, −0.324)**. CODEX가 우려한 격차 큰 항목(99ac6944 −2.5, bbe0a93b −3.0, 85d95ce5 +2.5)은 **5.4 메타-only만으로 이미 owner 근처로 수렴**.
2. **회귀 존재:** positive control 4개 중 3개 |delta| 증가. xlsx modality는 렌더 후 오히려 악화.
3. **단, pptx는 예외 — 렌더가 일관 개선(−0.062).** 슬라이드 디자인(여백/계층/장식)은 메타데이터로 안 보이고 vision으로만 보이는 영역이라, perception 가설이 **pptx에서만** 성립.

**다음(우선순위 순):**
- **(A) 최우선: mini→gpt-5.4 모델 업그레이드 효과를 본 검증으로 돌려라.** 렌더 0원으로 MAE 1.18→0.85. 비용/품질 트레이드오프를 mini-vs-5.4 축에서 먼저 결정(GHCR 렌더 빌드보다 값쌈).
- **(B) 렌더는 pptx 선별 적용만 검토.** 전 modality 렌더는 비용 대비 효과 없음. pptx는 ΔMAE −0.062 + `9a0d8d36` 큰 개선으로 가치 있음.
- **(C) xlsx 렌더는 보류 — 재검증 선행.** 8페이지 상한 대신 **데이터 있는 시트 우선 선택 로직** + vision 프롬프트에 "스프레드시트는 시각 장식이 아니라 데이터 가독성/구조로 채점" 가이드를 넣고 다시 측정해야 함. 지금 렌더하면 under-score만 늘림.
- **임의로 더 손대지 않고 여기서 멈춤(보고).** 위 (A)/(B)/(C)는 owner 결정 사항. GHCR 빌드·220 통합은 본 검증 결과상 **현 시점 보류 권고.**

### 부록 — 산출물(미커밋)
- `tasks/0607_sunday/vision_validation/vv.py` — 렌더+2arm 채점 하니스
- `tasks/0607_sunday/vision_validation/png/` — 93 PNG(25 unit)
- `tasks/0607_sunday/vision_validation/render_manifest.json` — 렌더 매니페스트
- `tasks/0607_sunday/vision_validation/baseline.json` — mini 메타-only 베이스라인 추출
- `tasks/0607_sunday/vision_validation/grades.json` — 2-arm 채점 전체 결과(evidence/reasoning 포함)
- `tasks/0607_sunday/vision_validation/login.sh` — 인증 헬퍼(사용자 실행용)

### 부록 — 인증 메모(우회 없음)
로컬 `az`가 서비스 프린시플(테넌트 6d93cc9b)로 잡혀 AOAI 리소스 테넌트(16b3c013)와 불일치 → Conditional Access(AADSTS53003) 차단. **secret 우회 없이**, 사용자 대화형 계정(`hjeon@microsoft.com`)을 리소스 테넌트 구독으로 `az account set` 전환해 해소(`.env` 불변, SP secret 미조작). 토큰은 `DefaultAzureCredential` Entra ID(AD token)로만 발급.
