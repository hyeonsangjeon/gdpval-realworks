# DASHBOARD CLEANUP PHASE 1 — 데모/스모크 백도어 + exp003 매핑

> 작성 2026-06-11. phase-1 코드는 `feat(dashboard)` 커밋 `bd82a77`로 반영(이 보고서는 별도 `docs` 커밋). push는 owner 검토 후. 명세 원문: `tasks/0_REMOTE/2026-06-11-dashboard_cleanup_phase1.md`.

## 한 줄 결론

데이터 소스 = **빌드타임 aggregate(`data/grades/*.json`, `batch-runner/results/*`) → `public/generated/*.json` → 런타임 fetch** (HuggingFace 아님). 데모(`dummy_gpt5_baseline`) + 스모크(grades `exp998_smoke*` 5개 / report `exp999` 1개)를 기본 화면에서 **숨기고 `?debug=1`로 복원**(표시 필터, 비가역 0). 상단 **Best Success Rate 100%→99.5%**(smoke `exp999` 제외 → official `exp010` 220-task), **Experiments 22→21**. **exp003 7개 카드 전부 유지(1차에서 0개 사라짐).** 매핑: clean 5.4 = `__judge_gpt-5_4__rubric_v2_tools`(220/215, 53.3), clean mini = `__judge_gpt-5_4-mini__rubric_v2_tools_mini`(220/215, 54.1); **owner가 물은 "gpt-5.4-pro 77%"는 exp003가 아니라 exp998 smoke**(3-task). 2차 숨김 후보 5개(제안만). phase-1 코드 커밋 `bd82a77`(push 보류).

> ⚠️ **지표 구분(중요):** 상단 *Best Success Rate*는 inference **Self-QA 완수율**(official 최고 99.5%)이고, exp003의 **~53%는 grade 점수**(Grading 탭, LLM-judge). 둘은 **다른 지표** — 그래서 스모크를 빼도 Success Rate는 ~59%가 아니라 99.5%(exp010, 실제 220-task)로 정상.

---

## PART 0 — 데이터 소스 (코드에서 직접 확인, HF 가정 안 함)

| 화면 영역 | 훅 | 런타임 fetch | 빌드타임 생성 스크립트 | 입력 |
|---|---|---|---|---|
| Grading Analysis 카드 | `useGrades()` (`src/hooks/useGrades.ts:86`) | `${BASE_URL}generated/grades-index.json` | `scripts/aggregate-grades.mjs` | `data/grades/*.json` |
| 상단 KPI / Leaderboard / Trend / Errors | `useReports()` (`src/hooks/useReports.ts`) | `generated/reports-index.json` | `scripts/aggregate-reports.mjs` | `batch-runner/results/*/report/report_data.json` |
| (보조) experiments-index | `useExperiments()` | `generated/experiments-index.json` | `scripts/aggregate-experiments.mjs` | `batch-runner/experiments/*.yaml` |

- **로딩 방식:** 전부 *런타임 fetch* of *빌드타임에 생성된 repo 내 정적 JSON*. **HuggingFace 아님** (grade JSON의 `dataset_url` 필드에 HF 링크가 들어있을 뿐, 카드 리스트 데이터 자체는 repo 내 JSON).
- `public/generated/`는 **gitignore**(빌드 시 재생성). aggregate는 `predev`/`prebuild` npm hook + `deploy.yml`에서 실행.
- **카드 리스트를 만드는 곳:** grade 카드 = `grades-index.json`의 배열을 `GradingAnalysisView`가 `grades.map(...)`. KPI = `reports-index.json`의 `cross_experiment.experiments`를 `Dashboard.tsx`가 집계.

## PART 1–2 — 데모/스모크 식별 규칙 + 토글 구현

**식별 규칙 (패턴/플래그 — `src/lib/officialFilter.ts`, 신규):**
- `isSmokeId(s)` = `/(^|[_-])exp99\d/i` 또는 `/smoke/i` → grades `exp998_smoke_baseline_sample`, report `exp999`(name "Smoke Baseline Run") 모두 포착. **exp003~exp025는 불포착**(검증됨).
- `isDemoGrade(g)` = `g.is_dummy === true || g.grade_status === 'legacy_dummy'` → `dummy_gpt5_baseline`.
- `isHiddenGrade(g)` = demo || smoke(`experiment_id`|`id`). | `isHiddenExperiment(e)` = smoke(`short_id`|`experiment_name`).

**토글 (URL 파라미터, localStorage 미사용):**
- `Dashboard.tsx`: `useSearchParams()` → `debug = searchParams.get('debug') === '1'`. `displayExperiments` useMemo에 `if (!debug) list = list.filter(e => !isHiddenExperiment(e))` 추가(deps에 `debug`). `<GradingAnalysisView debug={debug} />`로 전달.
- `GradingAnalysisView.tsx`: `useGrades()` → `allGrades`, 그 뒤 `grades = debug ? allGrades : allGrades.filter(g => !isHiddenGrade(g))`(useMemo). 하위 모든 렌더(overview 카드/분포 차트/파이/error/quick links)가 `grades` 사용 → **단일 지점 필터**.
- **삭제가 아니라 표시 필터** — `grades-index.json`/`reports-index.json` 불변, 토글로 100% 복원(비가역 위험 0). `?debug=1`은 접근제어 아닌 표시 토글.

**변경 파일(커밋 `bd82a77`):** `src/lib/officialFilter.ts`(신규), `src/pages/Dashboard.tsx`(+debug/필터), `src/components/dashboard/GradingAnalysisView.tsx`(+debug prop/필터).

**실데이터 동작(grades-index/reports-index에 규칙 적용):**
- GRADES: default **7 표시 / 6 숨김**(debug 13). 숨김 = `dummy_gpt5_baseline` + `exp998_smoke*`×5. **exp003 잘못 숨김 0**.
- EXPERIMENTS: default **21 / 1 숨김**(debug 22). 숨김 = `exp999`(3-task, 100%).

## PART 3 — 상단 지표 정상화 (최소 수정)

- 지표 계산 위치: `Dashboard.tsx`의 `bestRate = Math.max(...displayExperiments.map(e=>e.success_rate_pct))`, `bestQA`, `Experiments = displayExperiments.length`, `Tasks Evaluated = displayExperiments[0].total_tasks`. **모두 `displayExperiments` 파생** → 그 배열만 official로 필터하니 KPI가 자동 정상화(추가 수정 1줄 = 필터, 별도 지표 리팩터 없음).
- **Best Success Rate: 100.0%(exp999 smoke) → 99.5%**(exp010, 실제 220-task). `?debug=1`이면 100%.
- **Experiments: 22 → 21**(official). **Tasks Evaluated:** 정렬상 smoke(3-task)가 1위로 끼면 "3"이 뜰 위험이 있었는데 smoke 제외로 220 안정.
- 토글 연동: `debug` deps로 KPI·탭 데이터가 토글 상태에 따라 함께 바뀜.

## PART 4 — exp003 매핑 (조사만, 1차에서 숨기지 않음)

카드 ↔ 파일은 **1:1**(grade `id` = `data/grades/<id>.json` 파일명). 모두 `exp003_GPT52Chat_baseline_runner_exec` 접두.

| id 접미 | judge | tasks | graded | avg% | 분류 |
|---|---|---:|---:|---:|---|
| `__judge_gpt-5_4__rubric_v2_tools` | gpt-5.4 | 220 | 215 | 53.3 | ✅ **clean 5.4 220 OFFICIAL** |
| `__judge_gpt-5_4-mini__rubric_v2_tools_mini` | gpt-5.4-mini | 220 | 215 | 54.1 | ✅ **clean mini OFFICIAL** |
| `__gpt-5_4-hybrid__11e7900__v1` | gpt-5.4 | 220 | 219 | 49.25 | 옛 naming(hybrid) → 2차 후보 |
| `__gpt-5_4-hybrid__11e7900__v1__v2sm` | gpt-5.4 | 220 | 219 | 48.18 | 위 sign-aware backfill → 2차 후보 |
| `__gpt-5_4-mini__11e7900__v1` | gpt-5.4-mini | 220 | 219 | 51.47 | 옛 naming(mini) → 2차 후보 |
| `__gpt-5_4-mini__11e7900__v1__v2sm` | gpt-5.4-mini | 220 | 219 | 50.97 | backfill → 2차 후보 |
| `__judge_gpt-5_4__rubric_v2_tools_tight` | gpt-5.4 | **10** | 10 | 54.77 | tight 10-task 부분 → 2차 후보 |

- **`gpt-5.4-pro` 카드(77%) 정체:** exp003가 **아님**. `exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1`(+`__v2sm`) = **3-task 스모크**(avg 77.83). → 1차 smoke 규칙으로 이미 숨겨짐(owner의 "exp003 pro" 인식은 오인).
- **clean 220 official 식별:** 5.4(`__judge_gpt-5_4__rubric_v2_tools`, 방금 검증한 53.3) + mini(`__judge_gpt-5_4-mini__rubric_v2_tools_mini`, 54.1). 둘 다 새 selector+audit, 215 graded/220.
- **2차 숨김 후보(제안만, 이번엔 실행 안 함):** 옛 `__11e7900__v1` 4개(hybrid×2, mini×2; 219 graded·옛 naming, clean에 의해 대체) + `_tight` 1개(10-task 부분) = **5개**. official 2개에 `OFFICIAL` 배지 권장. **exp003 정리는 owner가 이 매핑 보고 2차에서.**

## 검증

- **빌드:** `tsc --noEmit` exit 0, `npm run build`(tsc && vite) exit 0(vite 2.40s).
- **서빙:** preview(4317)에서 `/`·`/?debug=1`·`/generated/grades-index.json` 모두 **HTTP 200**, JS 번들 정상 참조.
- **토글(실데이터 로직 실측):**
  - `?debug` 없음 → 데모/스모크 카드 안 보임(grades 7), exp003 7개 다 보임, KPI official(Best 99.5% / Exp 21).
  - `?debug=1` → 전부 복원(grades 13, exp 22, Best 100%).
- **exp003 불가침:** 1차에서 exp003 카드 **0개** 사라짐(7/7 유지) ✅.

## 다음 (owner 커밋 후): 2차 정리

- exp003 **official만 남김**: clean 5.4(`__judge_gpt-5_4__rubric_v2_tools`) = 최종 baseline + clean mini(비교용). 옛 `__11e7900__v1`/`__v2sm` 4개 + `_tight` 10-task = 숨김(+`?debug=1` 복원).
- official 2개에 **OFFICIAL 배지** 부여(식별 규칙 확장).

## 부록 — 변경 파일 / git 준수

- **신규:** `src/lib/officialFilter.ts`
- **수정:** `src/pages/Dashboard.tsx`, `src/components/dashboard/GradingAnalysisView.tsx`
- git: phase-1 코드 = `feat(dashboard)` 커밋 `bd82a77`; 이 보고서 + 명세기록 = `docs` 커밋. **push는 owner 검토 후**(아직 origin 미반영). `public/generated/`는 빌드 재생성물(gitignore). 데이터 JSON 불변(표시 필터만).
