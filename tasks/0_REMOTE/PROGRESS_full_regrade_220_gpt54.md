# 0_REMOTE — 진행 핸드오프 (모바일에서 이어가기)

> 작성 2026-06-11. 이 파일은 진행 상황 인수인계용. GitHub 모바일/웹에서 이어서 작업하기 위한 현재 상태 + 다음 할 일 정리.
> 관련 본문서: [tasks/0607_sunday/full_regrade_220_gpt54.md](../0607_sunday/full_regrade_220_gpt54.md)

---

## ✅ 지금까지 완료 (5.4 220 재채점 = 최종 baseline)

**220 전체 gpt-5.4 재채점이 완료됐습니다.** (judge=gpt-5.4, `default_v2.yaml`, OIDC 순차 relay)

- 최종 산출: `data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json` (**220 tasks**, graded 215, error 5)
- 최종 commit `9d9fd79` (grade) + `7b90547` (auto-analysis), origin/main 반영됨.
- mini baseline은 별도 파일로 **보존**(`...judge_gpt-5_4-mini__rubric_v2_tools_mini.json`, 112 tasks).

### relay 체인 (참고)
| chunk | run | 결과 |
|---|---|---|
| 0 | 27184813817 | ✅ |
| 1 | 27195838754 | ✅ (76 누적) |
| 2 (1차) | 27208794164 | ⚠️ runner shutdown(인프라 취소) |
| 2 (재개1) | 27247455907 | ⚠️ HF 429 |
| 2 (재개2) | 27247675556 | ✅ |
| 3 | 27256287905 | ✅ |
| 4 | 27268390020 | ✅ |
| 최종 | 27282749617 | ✅ 220/220 + auto-analysis |

### HF 429 근본 수정 — merge 완료 (PR #55)
- chunk 2가 HF Hub `429`로 끊긴 원인 = download 스크립트가 **익명 요청**(HF_TOKEN 미전달).
- **`batch-runner/scripts/download_inference_from_hf.py`에 `_hf_token()` 추가 + `hf_hub_download`×2/`snapshot_download`에 `token=` 전달** → PR [#55](https://github.com/hyeonsangjeon/gdpval-realworks/pull/55) squash-merge (`242beb4`).
- 이후 chunk 2재개2/3/4가 인증 요청으로 **429 없이 완주**.

---

## 📊 검증 결과 (핵심 수치 — 이미 확보)

### 전체 요약 (5.4 220)
| 지표 | 5.4 (220) | mini (참고) |
|---|---|---|
| graded / error | 215 / 5 | — |
| avg_score_pct | **53.3** | mini 0601 54.1 |
| critical_item_pass_rate | **0.501** | mini 0601 0.528 |
| judge_error_rate | 2.76% | — |
| judge calls | 8,904 | 8,904 |
| tokens in/out | 107.8M / 4.65M | 130M / 5.5M |

- **selection_status 분포 = mini 0601과 정확히 동일**: ok 194 / wrong_format_primary 20 / no_generated_candidate 1 / selection_error 5 → **selector는 모델 무관** 확인 ✅
- **audit 필드 0 누락** (10,453 items 전부 target_scope/selected_paths 보유) ✅
- 5.4 error 5 tasks: `1aecc095`, `cecac8f9`, `c9bf9801`, `94925f49`, `7151c60a`

### 비용 실측 (5.4 220)
- **raw $158.07** (in $134.81 + out $23.26)
- **cached-effective $123.37** (cache_hit 51.5%, cached 55.5M tok)
- 추정($146 cached / $190 raw)과 근사 — reasoning 토큰 영향은 예상보다 작았음(out 4.65M). **mini $29의 약 4.3×(cached) / 4.2×(raw).**

### ⚠️ gold 20 "Overall style" MAE — 예상과 다름 (조사 필요)
| 구분 | MAE |
|---|---|
| gold-20 2arm 검증(0607, 메타-only 5.4) | **0.852** |
| **5.4 220 전체 파이프라인** | **1.261** ⬆ 악화 |

modality별 (5.4 220):
| kind | MAE | bias |
|---|---|---|
| pdf | 1.729 | **−1.35** (과보수/under) |
| xlsx | 1.720 | −0.88 |
| docx | 0.700 | +0.50 |
| pptx | 0.688 | −0.69 |

- **전체 파이프라인 MAE(1.26)가 2arm 검증(0.85)보다 나쁨.** pdf/xlsx에서 5.4가 **체계적 under-score(bias 음수)** — 0609 text 분석에서 예측한 "증거 안 보이면 fail/partial 과보수" 경향이 전체에서 실제로 나타남.
- **가설(미확정):** 2arm 검증은 read_content 윈도를 60K로 크게 줬는데, 전체 파이프라인은 tool-loop이 능동 탐색하더라도 cap(8 calls/item)·컨텍스트가 달라 5.4가 "못 본" 항목을 과보수했을 수 있음. → **다음 조사 포인트.**

---

## 📋 다음 할 일 (모바일/웹에서 이어가기)

### 1. (선택) 5.4 과보수 원인 조사 — gold MAE 0.85 vs 1.26 격차
- gold 20개에서 5.4 220의 "Overall style" evidence/reasoning을 열어, under-score가 **렌더/컨텍스트 부족**인지 **5.4 판단**인지 구분.
- 특히 pdf/xlsx의 음수 bias 항목(99ac6944, 7d7fc9a7, bbe0a93b 등) 점검.
- → 프롬프트 튜닝 포인트("관찰된 범위로 판단, 전체 스캔 못 했어도 과보수 말 것") 도출.

### 2. 대시보드 반영 확인
- 5.4 grade JSON이 대시보드 aggregate에 잡히는지(`npm run aggregate` → `public/generated/`).
- 최종 공식 baseline이 5.4이므로 대시보드가 5.4를 가리키는지 확인.

### 3. (이후) pptx 선별 렌더를 5.4 baseline 위에
- 0607 결론: 렌더는 pptx에만 효과(−0.062). 5.4 220 위에 pptx 렌더 얹어 "5.4 vs 5.4+렌더" 비교 → 블로그.

### 4. (선택) relay 견고성 보강 — owner 판단
- runner 인프라 cancel 시 rc=7 경로를 못 타 수동 resume 필요했음(chunk2 1차). `if: cancelled()` 가드로 마지막 partial 커밋+재트리거 보강 고려. (HF 429는 PR #55로 이미 해결.)

---

## 🔧 유용한 명령 (모바일에선 Actions 탭 / 웹 터미널)

```bash
# 5.4 grade 상태
python3 -c "import json;d=json.load(open('data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json'));print('tasks',len(d['tasks']),d['summary']['graded_tasks'],'graded')"

# auto-analysis 보기 (cost/summary)
cat data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.analysis.md

# relay run 이력
gh run list --workflow=grade-run.yml --limit 8
```

## ⛔ 제약 (이어서 작업 시 유지)
- 5.4 재채점은 **이미 완료** — 재실행 불필요(비용). 같은 걸 또 dispatch하지 말 것.
- mini baseline 파일 보존(별도 파일). selector/점수 로직 불변.
- git 변경은 워크플로 정상 산출(grade chunk commit) + 명시 승인된 PR(예: #55)만. 임의 force-push/reset 금지.
- pptx 렌더는 별도 트랙.
