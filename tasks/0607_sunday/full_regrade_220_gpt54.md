# FULL REGRADE 220 — judge=gpt-5.4 (final baseline) [검증 완료]

> **상태: 220 재채점 relay 완료 + 검증 6항목 채움(read-only 분석, 미커밋).** judge=gpt-5.4, `default_v2.yaml`, OIDC 순차 relay 8 run(~24.8h 순수 compute, 달력상 ~37h; chunk2 1회 인프라 취소→다음날 재개). 산출: `data/grades/exp003_..._judge_gpt-5_4__rubric_v2_tools.json` (220 tasks). 검증은 **기존 grade JSON + gold + mini 재사용**(재채점 재실행/신규 Azure run 없음).
> **git 수동 조작 없음**(read-only, 미커밋).

## 한 줄 결론

220 5.4 **완전성 OK**(220/220, 중복·graded_at누락·empty verdict 0, item 수 mini와 task별 완전 동일, chunk2 취소 경계 깨끗=76+144). **selection 분포 mini와 정확 동일**(ok194/wrong_format20/selection_error5/no_generated1 → selector 모델 무관 확정). avg **53.3%**, critical_pass **0.501**. gold "Overall style" **MAE 1.261**(2-arm 검증 0.852 대비 악화 — **단 mini도 full pipeline 1.212라 악화는 파이프라인 효과**; 5.4의 특이점은 **체계적 under-score** bias −0.64, pdf/xlsx에서 `fail→0` 5건). 5.4 과보수는 item-level로는 약함(+2pp 엄격), holistic Overall-style pdf/xlsx에서 강함. 실측 비용 **$123.37 cached / $158.07 raw (mini의 약 4.2배)** — 추정 5.0×보다 낮음(reasoning 토큰 영향 작음). audit 필드 **0 누락**. → **5.4 최종 baseline 확정**(데이터 무결). 잔여 이슈: pdf/xlsx Overall-style 과보수 = 프롬프트 튜닝 여지.

---

## PART 0 — 완전성 검증 (최우선; chunk2 취소 때문)

| 점검 | 결과 |
|---|---|
| task 수 | **220** ✅ (summary total=220, graded 215, error 5) |
| 중복 task_id | **0** ✅ (unique 220 / rows 220) |
| graded_at 누락 | **0** ✅ |
| zero-item task | **0** ✅ |
| empty verdict | **0** ✅ (10,453 items 전부 verdict 보유) |
| item 수 mini 대비 | **0 mismatch** ✅ (220 task 전부 동일 item 수 → 누락/드롭 없음, 동일 rubric/selector) |

**chunk2 취소 경계 점검(graded_at, UTC):** 06-09 05:13 → 06-10 18:17 연속.
- 06-09분 = **76 task**(= chunk0+1 커밋분, doc의 누적 76과 일치).
- 06-10분 = **144 task**(resume chunk2재개2~최종).
- 76 + 144 = 220. 취소된 **chunk2-1차 partial(77~97)은 미커밋·폐기되어 06-10에 재채점**됨 → 중복/유실 없이 경계 깨끗. ✅

**judge_error 분포:** 275 items = **243**(selection_error 5개 task 내부, 정상) + **32**(215 graded task에 산발, 전체 item의 0.3%). 채점 완전성에 영향 없음.

> **결론: 누락/중복 0 → PART 1~6 진행 가능(보고 필요 없음).**

## PART 1 — 전체 요약

- graded **215** / error **5**. error 5 = selection_error 5: `1aecc095`, `cecac8f9`, `c9bf9801`, `94925f49`, `7151c60a`.
- **selection_status 분포:** `ok 194 / wrong_format_primary 20 / no_generated_candidate 1 / selection_error 5`.
  - **clean mini 220과 분포 완전 동일**(+ 0601 220 기준치와도 일치) → **selector는 judge 모델과 무관**(설계대로) 확정. 차이 0 = 버그 신호 없음. ✅
- **avg_score_pct: 53.3** · **critical_item_pass_rate: 0.501** (judge_pass 0.415, precheck_pass 0.583, judge_error_rate 2.76%).

## PART 2 — 5.4 vs mini 전체 비교

> **⚠️ 전제 정정:** 이전 문서는 "mini clean 112/220"이라 했으나, 현 main의 `..._judge_gpt-5_4-mini__rubric_v2_tools_mini.json`은 **220/220(graded 215)로 완료됨**. → **112 제한 해소, full 220 교집합 비교 가능.**

- 교집합 **220**, item 수 task별 **5.4 = mini (0 mismatch)** → 동일 파이프라인/selector 확인.
- 점수(같은 task, judge만 차이): **5.4 mean pct 54.54 vs mini 55.36 → −0.82pp**(median Δ=0.00). summary avg(53.3 vs 54.1, −0.8pp)와 일치.
- 분포(215 graded pair): 5.4가 mini보다 **>1pt 낮음 78 / ±1pt 동등 69 / >1pt 높음 68**. → 5.4가 약하게 더 보수적이나 대칭에 가까움.
- text 분석에서 본 **5.4 과보수**가 전체 평균을 mini보다 소폭 낮춤(−0.8pp). 큰 격차는 아님(holistic Overall-style에 집중 → PART 3/4).

## PART 3 — gold 20 재비교 (핵심)

- **gold 20 전량 포함** 확인: 5.4 20/20, mini 20/20 (모두 present, no-item 0). (PART 0 완전성과 연계 OK.)
- 산식: |awarded − owner|, criterion="Overall formatting and style of the deliverable", max 5, owner gold = `docs/human-in-the-loop/overall-style-gold.json`.

| 구분 | overall MAE | bias |
|---|---|---|
| gold-20 **2-arm 검증**(0607, meta-only 5.4) | **0.852** | — |
| **5.4 220 full pipeline** | **1.261** ⬆ | **−0.639** |
| (참고) mini 220 full pipeline | 1.212 | −0.163 |

**modality별 (5.4 220 full pipeline) vs 2-arm 기준치:**

| kind | 5.4 MAE | 5.4 bias | 2-arm 기준 |
|---|---|---|---|
| pdf | **1.729** | **−1.354** | 0.74 |
| xlsx | **1.720** | −0.880 | 1.25 |
| docx | 0.700 | +0.500 | 0.85 |
| pptx | 0.688 | −0.688 | 0.53 |

- **2-arm 0.852 → full pipeline 1.261 악화 재현 확인.** 그러나 **mini도 full pipeline에서 1.212** → **MAE 악화의 주원인은 5.4가 아니라 파이프라인**(2-arm은 read_content 60K 윈도, full pipeline은 tool-loop·8 call cap·컨텍스트 차이).
- **5.4의 특이점 = 체계적 under-score**(bias −0.64 vs mini −0.16). pdf(−1.35)·xlsx(−0.88)에서 강함. 주도 사례 5건(5.4 `fail→0`, owner는 mid): `7bbfcfe9`(xlsx 4→0), `7d7fc9a7`(pdf 3→0), `f9a1c16c`(pdf 3→0), `bbe0a93b`(pdf 3→0), `83d10b06`(xlsx 2.5→0).
- docx/pptx는 기준치에 근접(docx는 오히려 +bias=관대).

## PART 4 — 5.4 과보수 경향

- **item-level**(judge 결정 공통 9598 item): 정확 일치 **87.7%**, **5.4 stricter 684(7.1%) vs looser 492(5.1%)** → 순 **+2pp 엄격**(약함). 주 transition: partial→pass 395, fail→pass 135, fail→partial 154(5.4가 더 낮게).
- **인용 사례(0609 가설 검증):**
  - `bbe0a93b`(pdf): "blank cells in Yes/No columns" 등 **3 item에서 5.4=fail(0) vs mini=pass(1.0)**. 5.4 evidence는 표 헤더만 인용 — **긍정 증거 미확인 시 fail**.
  - `ee09d943`(xlsx): "no external links to other workbooks" **5.4=fail(0) vs mini=pass(2.0)** — 파일명 참조를 외부링크로 해석. **모호 증거를 부정 판정.**
- **결론:** 과보수는 (a) item-level 전반에선 약함(+2pp), (b) holistic "Overall style"(특히 pdf/xlsx)에서 강함(PART 3 음수 bias). → **프롬프트 튜닝 포인트:** "전체 스캔 못 했어도 **관찰된 범위로 판단**, 긍정 증거 부재만으로 fail 금지(렌더/컨텍스트 제한 시 partial 고려)".

## PART 5 — 비용 실측

| | judge calls | in tok | out tok | cached(hit) | raw | cached-eff |
|---|---|---|---|---|---|---|
| **5.4** | 8,904 | 107.84M | 4.65M | 55.5M (51.5%) | **$158.07** | **$123.37** |
| mini | 8,904 | 130.09M | 5.52M | 70.5M (54.2%) | $38.05 | $29.24 |

- **실제 배수: raw 4.15× / cached 4.22×** (mini $29 대비). **추정 5.0×($146)보다 낮음.**
- reasoning 토큰 영향 작음: 5.4 out 4.65M(< mini 5.52M), in 107.8M(< mini 130M) — 5.4가 토큰은 오히려 적게 씀. 비용 배수는 **per-token 단가 차이**(gpt-5.4 ≈ 4.2× mini)에서 옴.

## PART 6 — audit 필드

- **10,453 items 전부 `target_scope`·`selected_paths` 보유 → 누락 0** ✅ (`aggregation_rule`/`child_grades` 키도 전 item 존재).
- `target_scope` 분포: file_target 7224 / selection_error 1207 / primary_bundle 1082 / manifest 918 / split_children 22.
- split_children **22개 전부** `child_grades` + `aggregation_rule=blocking_min_else_mean` 보유(나머지 item은 aggregation_rule=None=정상, 비분할이므로).

## 다음

- **pptx 선별 렌더를 5.4 baseline 위에:** 0607 결론(렌더는 pptx에만 효과 −0.062) → "5.4 vs 5.4+렌더" 비교 → 블로그.
- (선택) pdf/xlsx Overall-style 과보수 프롬프트 가드 1줄 추가 후 gold-20 재측정(MAE↓ 기대). owner 판단.
- (선택) mini도 비교 대칭 위해 이미 220 완료됨 — 추가 비용 불필요.

---

## 부록 A — relay 이력 (provenance)

| chunk | run | 결과 |
|---|---|---|
| 0 | 27184813817 | ✅ |
| 1 | 27195838754 | ✅ (76 누적) |
| 2 (1차) | 27208794164 | ⚠️ runner shutdown(인프라 취소, partial 미커밋) |
| 2 (재개1) | 27247455907 | ⚠️ HF 429(익명 다운로드) |
| 2 (재개2) | 27247675556 | ✅ |
| 3 | 27256287905 | ✅ |
| 4 | 27268390020 | ✅ |
| 최종 | 27282749617 | ✅ 220/220 + auto-analysis |

- **chunk2 취소 = GitHub hosted runner 인프라 종료**(self-cancel 아님). rc≠7이라 partial-commit/auto-retrigger 스킵 → 수동 resume 필요. 77~97 진행분 미커밋·재채점(PART 0에서 무결 확인).
- **HF 429 근본 수정 = PR #55**(`download_inference_from_hf.py`에 `token=` 전달) merge(`242beb4`) 후 재발 없음.
- 견고성 메모(owner 판단): runner cancel 시 `if: cancelled()` 가드로 partial 커밋·재트리거 보강 고려.

## 부록 B — 제약 준수

read-only git(커밋/푸시/머지/리셋 없음), 본 문서 미커밋. 재채점 **재실행 없음**(기존 grade JSON 분석만), 신규 대규모 Azure run 없음. mini baseline 파일 보존(별도 파일). gold/mini 재사용. secret 미조작. 누락/중복 0이라 추가 재채점 불요.
