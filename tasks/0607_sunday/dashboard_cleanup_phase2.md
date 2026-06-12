# DASHBOARD CLEANUP PHASE 2 — exp003 정리 + OFFICIAL 배지

> 작성 2026-06-11. **코드 변경은 로컬 작업트리만, 미커밋**(owner 검토 후 커밋 지시 — phase 1과 동일 절차). git HEAD 불변(`e2f4c5b`). 명세 원문: `tasks/0_REMOTE/2026-06-11-dashboard_cleanup_phase2.md`. 근거 매핑: phase 1 보고 PART 4.

## 한 줄 결론

exp003 **옛/부분 5개를 `?debug=1` 뒤로** 숨기고(패턴: 옛 4-tuple naming `__<7hex>__v\d` + `_tight` 접미 — **official 오포착 0 실데이터 검증**), **official 2개**(`…__judge_gpt-5_4__rubric_v2_tools` = 5.4 baseline, `…__judge_gpt-5_4-mini__rubric_v2_tools_mini` = mini)는 **명시 allowlist**로 지정 + **OFFICIAL 배지** + **역방향 보호**(어떤 규칙도 official 숨기지 못함). 기본 화면 grade 카드 **2개(둘 다 official·배지)**, `?debug=1` 13개 전부. **phase 1 동작 불변**(데모/스모크 숨김·KPI official 필터·토글; `Dashboard.tsx` 미변경). `tsc` 0 / `build` 0 / preview 200. **git 미커밋**(owner 지시 대기).

---

## 식별 규칙 (officialFilter.ts 확장 — 단일 지점 필터 유지)

phase 1 구조를 *확장*만 함(새 구조 없음). `src/lib/officialFilter.ts`에 추가:

- **`OFFICIAL_GRADE_IDS`** = `Set([clean 5.4 id, clean mini id])` — **명시 allowlist**(패턴 아님). "official"은 큐레이션된 지위 → 새 official 생기면 owner가 이 Set에 추가.
- **`isOfficialGrade(g)`** = `OFFICIAL_GRADE_IDS.has(g.id)`.
- **`isLegacyExp003(g)`** = `/__[0-9a-f]{7}__v\d/i.test(g.id) || g.id.endsWith('_tight')`
  - 앞 패턴 = 옛 4-tuple naming `<exp>__<judge>__<sha7>__v<n>`(`__11e7900__v1`, `__v2sm` backfill 포함) 4개.
  - `_tight` = 10-task 부분 채점 1개.
- **`isHiddenGrade(g)`** (phase 1 함수에 **합류** → 단일 지점):
  ```ts
  if (isOfficialGrade(g)) return false           // ← 역방향 보호
  return isDemoGrade(g) || isSmokeId(g.experiment_id)
      || isSmokeId(g.id) || isLegacyExp003(g)
  ```
  GradingAnalysisView의 카드·분포 차트·error·quick-links가 모두 `isHiddenGrade` 경유라 자동 일관.

**오포착 검증(실데이터, 핵심):** official 2개에 `isHiddenGrade`가 `true`인 경우 **0**.
- `_tight`는 **endsWith**로 정확히 — official `…__rubric_v2_tools`(접두 겹침)는 `_tight`로 안 끝나므로 미포착.
- official id엔 `__<sha7>__v` 패턴 없음(rubric_v2_tools naming).
- 추가로 `isHiddenGrade` 최상단 `isOfficialGrade` 가드가 **이중 안전망**.

## 배지 UI

- 위치: `GradingAnalysisView`의 `GradeOverviewCard` 헤더(제목 옆), 기존 `DEMO`/`WOW` 배지와 **동일 관례**.
- 마크업: `inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-[9px] font-bold uppercase tracking-wider text-emerald-400` + `Award` 아이콘(이미 import됨) + `OFFICIAL`, `title="Curated official baseline run"`.
- `isOfficialGrade(grade)`일 때만 렌더. **`?debug=1`에서도 표시**(배지는 필터와 독립 — 전부 보이되 official 구분).

## 검증

- **실데이터 시뮬(grades-index 13개):**
  - 기본: shown **2**(둘 다 `[OFFICIAL]`) / hidden **11**(demo 1 + smoke 5 + legacy exp003 5).
  - `?debug=1`: 13개 전부.
  - **역방향 보호:** `isOfficialGrade && isHiddenGrade` → **0건**.
  - 숨긴 legacy exp003 5 = `__gpt-5_4-hybrid__11e7900__v1`(+`__v2sm`), `__gpt-5_4-mini__11e7900__v1`(+`__v2sm`), `__judge_gpt-5_4__rubric_v2_tools_tight`.
- **phase 1 불변:** 데모/스모크 여전히 숨김, KPI official 필터·토글 그대로. `Dashboard.tsx` **미변경**(experiments/KPI 영향 0).
- **빌드:** `tsc --noEmit` exit 0, `npm run build` exit 0(vite 1.90s). preview(4318) `/`·`/?debug=1`·`/generated/grades-index.json` 모두 **200**.

## 변경 파일 (미커밋 — owner 커밋 대기)

- **수정:** `src/lib/officialFilter.ts` (+`OFFICIAL_GRADE_IDS`/`isOfficialGrade`/`isLegacyExp003` + `isHiddenGrade`에 legacy 합류 & 역방향 가드).
- **수정:** `src/components/dashboard/GradingAnalysisView.tsx` (+`isOfficialGrade` import, `GradeOverviewCard`에 OFFICIAL 배지).
- **미변경:** `src/pages/Dashboard.tsx`(KPI/experiments는 phase 1 그대로).
- git: **HEAD 불변(`e2f4c5b`), 커밋/푸시 없음.** owner 지시 시 phase 1과 동일하게 기능 코드만 surgical 커밋(문서는 별도/지시 따름).

## 다음 (owner 커밋 후)

- (선택) Leaderboard/Trend에도 OFFICIAL 강조가 필요하면 같은 allowlist 재사용(현재는 Grading 탭 grade 카드에만 배지). owner 판단.
- 새 official run 승격 시 `OFFICIAL_GRADE_IDS`에 id 추가(코드 1줄).
