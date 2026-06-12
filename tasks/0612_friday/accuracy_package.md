# ACCURACY PACKAGE — 과보수 튜닝 + pptx 렌더 (+대시보드 안착)

> 작성 2026-06-12. **PART 0만 커밋·push**(owner가 한정 git 권한 부여). **PART 1~3 코드/프롬프트/하니스/본 보고서는 로컬 미커밋**(owner 검토 대기). 명세 원문: `tasks/0_REMOTE/2026-06-12-accuracy_package.md`.

## 한 줄 결론

**PART 0:** origin/main은 `f0c58f3`였고 phase 1(`bd82a77`)+문서(`e2f4c5b`)가 **미push 상태**였음(owner 인식과 불일치). `e2f4c5b`는 정체불명이 아니라 **내가 만든 phase-1 문서 커밋**. phase 2 코드 커밋(`a272a5d`) 후 `f0c58f3..a272a5d` **push 완료**, deploy 성공, **라이브 번들에 allowlist·OFFICIAL·debug 확인**(grades 13). **PART 1:** 과보수(fail→0 5건) = "긍정 증거 부재(파서오류/관찰부족/plain)→fail" — 그러나 **격리 2-arm A/B에서 현행 프롬프트 MAE 0.698(≪ full-pipeline 1.261)**이라 **과보수는 프롬프트가 아니라 tool-loop/관찰수집 아티팩트**. 1b 튜닝은 under-score는 고치나 **과관대로 스윙(bias +0.05→+0.42, MAE 0.698→0.697 = 무개선, worsened 9>improved 7)**. **PART 2:** pptx 렌더 ΔMAE **+0.158**(악화) — 2-arm의 −0.062 **재현 실패**, 렌더가 과관대 유발. **PART 3:** 두 개입 모두 gold-MAE 개선 못 함 → **220 재채점 NO-GO 권고**. 진짜 수정은 **파이프라인(관찰수집/파서오류 처리)** 레벨. git: PART 0만 커밋, 나머지 미커밋.

---

## PART 0 — 대시보드 phase 1+2 origin 안착 (자가 진단·해결) ✅

**진단(`git fetch` 후):**
- origin/main = `f0c58f3` — **phase 1 `bd82a77` 미push**(owner는 push 완료로 인식 → 실제 미반영). 로컬이 origin보다 2 앞섬.
- `e2f4c5b` 정체 = `docs(dashboard): phase 1 cleanup report + remote task spec` — **내가 phase 1 때 만든 문서 커밋**(report + spec record). 미스터리 아님.
- phase 2(officialFilter 확장 + OFFICIAL 배지)는 작업트리에 미커밋 상태로 존재 확인(`OFFICIAL_GRADE_IDS`/`isLegacyExp003`/배지 present).

**조치(허용된 git 범위 내):**
- phase 2 **대시보드 코드 2개만** surgical 커밋 → `a272a5d` (`officialFilter.ts` + `GradingAnalysisView.tsx`). 무관 변경/PART1~3 미혼입.
- `git push origin main` → **`f0c58f3..a272a5d`** (bd82a77 + e2f4c5b + a272a5d 일괄 반영).
- deploy.yml 자동 트리거(run `27363728644`) → **success**.

**라이브 검증(`hyeonsangjeon.github.io/gdpval-realworks`):**
- 페이지 200. 배포 번들 `assets/index-tzkQFZV7.js`(= 내 로컬 phase-2 빌드 해시 동일).
- 번들 내 마커 확인: `judge_gpt-5_4__rubric_v2_tools`(allowlist) ✅, `OFFICIAL`(배지) ✅, `debug`(토글) ✅.
- `generated/grades-index.json` 13개 정상. → 기본 화면 exp003 official 2개+배지, `?debug=1` 13 복원 (필터 로직은 phase1/2에서 실증, 라이브 번들에 반영 확인).

## PART 1 — 5.4 과보수 진단 + 프롬프트 튜닝 (analyzer-first)

### 1a 진단 — fail→0 5건 분류 (5.4 baseline evidence 직접 판독)
| task | kind | owner→aw | 분류 | 근거(evidence) |
|---|---|---|---|---|
| 7bbfcfe9 | xlsx | 4→0 | **파서 예외 아티팩트** | `"font_color": "Values must be of type <class 'str'>"` (openpyxl TypeError가 evidence에 누출 → 스타일 결함으로 오판) |
| 7d7fc9a7 | pdf | 3→0 | **파서 예외 아티팩트** | 동일 TypeError 문자열 |
| f9a1c16c | pdf | 3→0 | **관찰 부족→fail** | `"fonts":["Helvetica",...]`만(시각/레이아웃 미관찰)→partial 대신 fail |
| bbe0a93b | pdf | 3→0 | **관찰 부족→fail(split)** | child 1개 fail(fonts만)→blocking_min으로 전체 0 |
| 83d10b06 | xlsx | 2.5→0 | **plain 과처벌** | `merged_ranges:[], has_charts:false`→0(owner "plain하지만 유효") |

→ 공통축 = **관찰에서 긍정 증거를 못 보면 fail**(0609 bbe0a93b/ee09d943와 동일). **단 1c가 보여주듯 이 fail→0은 격리 프롬프트가 아니라 full-pipeline tool-loop(파서오류·관찰부족)에서 발생.**

### 1b 튜닝 (로컬 미커밋, `batch-runner/prompts/grader_judge_v2.md`)
- **Rule 5 외과적 교체**: "tool이 useful한 것 못 주면 fail" → "**관찰한 범위로 판정; 부재(불완전 관찰/파서오류/plain)는 그 자체로 결함 아님; absent/unrelated 또는 관찰된 명백 결함일 때만 fail**". anti-hallucination·absent→fail 유지. `prompt_version v2.2`. diff 9줄.

### 1c A/B (gold-20, 같은 gpt-5.4, 격리 2-arm meta-only, 50콜) — `ab_grade.py`/`ab_result.json`
| arm | MAE | bias |
|---|---|---|
| **A (현행)** | **0.698** | **+0.048** |
| **B (튜닝)** | **0.697** | **+0.422** |

modality별(A→B MAE / bias): pdf 0.68→0.74 (+0.18→+0.49) · xlsx 1.10→1.13 (**−0.50→+0.33**, 부호 반전) · docx 0.70→0.42 · pptx 0.22→0.44. 회귀: **improved 7 / worsened 9 / unchanged 4**.

**판정:**
1. **격리 세팅 현행 MAE 0.698 ≪ full-pipeline 1.261** → 과보수는 **프롬프트 판정 로직이 아니라 full-pipeline tool-loop**(관찰수집 단계의 파서오류·관찰부족)에서 옴. (격리에선 7bbfcfe9도 A=1.0이지 0이 아님 — fail→0은 파이프라인 아티팩트.)
2. 튜닝은 under-score(xlsx bias −0.50→+0.33, fail케이스 일부 교정)는 줄이나 **과관대로 스윙**(전체 bias +0.05→+0.42, 정확하던 9건 악화). **MAE 순개선 0.** → **1b 광범위 튜닝은 220 적용 부적합**(과보수↔과관대 트레이드만).

## PART 2 — pptx 선별 렌더 (검증된 게인만) — `render_ab.py`/`render_result.json`

- **검증(gold pptx 4, 프롬프트 고정=현행, meta vs meta+render):**
  | arm | MAE | bias |
  |---|---|---|
  | meta | 0.312 | −0.062 |
  | +render | 0.470 | +0.470 |
  - **ΔMAE = +0.158 (악화)** — 2-arm 0607의 −0.062 게인 **재현 실패**. 렌더 PNG가 judge를 **과관대**로(이미지 "괜찮아 보임"→점수↑, ec591973 −0.25→+1.00, a74ead3b +0.50→+0.88).
  - meta-only 자체가 이미 MAE 0.312로 낮음 → pptx는 메타로 충분, 렌더 한계효용 음(−).
- **통합 설계(참고, 권고는 보류):** opt-in YAML 플래그(`render.enabled: pptx`)로만 활성, 기본/기존 baseline 불변. 설치는 워크플로 `apt-get install libreoffice fonts-noto-cjk fonts-liberation`(단순) vs GHCR 프리빌드 이미지(반복 비용↓). **단 게인이 없어 통합 비권장.**

## PART 3 — 통합 검증 + 220 권고 (실행 금지 준수)

- **조합([튜닝+렌더]) 별도 실행 안 함**: 두 구성요소가 각각 무개선/악화(둘 다 과관대)라 조합은 예측상 더 나쁨 — 비용 절약 차원에서 생략(harness는 준비됨, 원하면 1커맨드).
- **권고: 220 재채점 NO-GO** (튜닝·pptx렌더 어느 것도). 근거: gold-MAE 개선 0, 둘 다 과관대 회귀. ~$123+렌더 비용 대비 정확도 이득 음/영.
- **진짜 수정 방향(다음 iteration, 파이프라인 레벨):**
  1. **파서/tool 오류 문자열을 evidence로 쓰지 않게**(예: `inspect_formatting`의 openpyxl TypeError를 결함이 아닌 "관찰 불가"로 처리) — fail→0 2건 직접 해소.
  2. **holistic style에서 fail 허용 전 관찰 충분성 게이트**(메타가 빈약하면 fail 대신 partial, 또는 그때만 렌더 라우팅).
  3. 격리 MAE 0.70이 보여주듯 **판정은 관찰이 좋으면 정확** → 투자는 verdict 가이드가 아니라 **관찰 품질**에.
- **220 GO 시 준비물(owner 승인 시):** opt-in 플래그 config + 출력 파일명 별도(`..._judge_gpt-5_4__rubric_v2_tools_<variant>.json`, 기존 baseline 보존). 단 현 데이터론 GO 비권장.

## 변경 파일

**PART 0 (커밋·push 완료, origin/main=`a272a5d`):**
- `src/lib/officialFilter.ts`, `src/components/dashboard/GradingAnalysisView.tsx` (phase 2; phase 1 `bd82a77`/`e2f4c5b`도 함께 push됨).

**PART 1~3 (로컬 미커밋 — owner 검토):**
- `batch-runner/prompts/grader_judge_v2.md` (1b Rule 5, **적용 비권장** — 채택 안 하면 `git checkout`으로 복원; 본 task는 git 변경 PART0만 허용이라 미복원).
- `tasks/0612_friday/ab_grade.py`, `render_ab.py` (검증 하니스), `ab_result.json`, `render_result.json` (결과), `png/` (렌더 중간물 6MB, 재생성 가능).
- 본 보고서 `tasks/0612_friday/accuracy_package.md`.

> 측정은 전부 **owner gold와의 MAE/bias + 회귀**(점수 상승 아님). N 작음(gold-20/pptx-4) + 격리 2-arm 세팅이라 방향성 결과 — 그러나 **두 개입 모두 적용 근거 없음**은 분명.
