# OPUS (Copilot remote) — 대시보드 2차 정리: exp003 옛 카드 숨김 + OFFICIAL 배지

> **기록용 작업 명세** (owner 지시 원문). 작성 2026-06-11. 진행/결과는 `tasks/0607_sunday/dashboard_cleanup_phase2.md`에 별도 기록.

- **Repo:** `gdpval-realworks`, main (phase 1 커밋 `bd82a77` push 완료 — `officialFilter.ts` + `?debug=1` 토글 + KPI official 필터가 이미 라이브).
- **근거:** phase 1 매핑 보고(`tasks/0607_sunday/dashboard_cleanup_phase1.md` PART 4)에서 exp003 7개 카드의 정체가 확정됨. 이제 그 매핑대로 2차를 실행한다.
- **이번 작업:** exp003 중 **옛/부분 카드 5개를 `?debug=1` 뒤로** 보내고, **official 2개에 OFFICIAL 배지**를 단다. phase 1의 필터 구조(`officialFilter.ts`, 단일 지점 필터)를 *확장*하는 작은 작업 — 새 구조 만들지 마라.

## 대상 (phase 1 매핑 기준 — 그대로 사용)

**숨김 5개 (기본 화면에서 제외, `?debug=1`로 복원):**
| id 접미 | 이유 |
|---|---|
| `__gpt-5_4-hybrid__11e7900__v1` | 옛 naming, clean으로 대체 |
| `__gpt-5_4-hybrid__11e7900__v1__v2sm` | 위의 backfill |
| `__gpt-5_4-mini__11e7900__v1` | 옛 naming, clean으로 대체 |
| `__gpt-5_4-mini__11e7900__v1__v2sm` | backfill |
| `__judge_gpt-5_4__rubric_v2_tools_tight` | 10-task 부분 채점 |

**OFFICIAL 배지 2개 (계속 표시 + 배지):**
| id 접미 | 의미 |
|---|---|
| `__judge_gpt-5_4__rubric_v2_tools` | clean 5.4 220 = 최종 baseline |
| `__judge_gpt-5_4-mini__rubric_v2_tools_mini` | clean mini 220 = 비교 기준 |

## 구현 지침

1. **식별 규칙 — `officialFilter.ts` 확장:**
   - 레거시 숨김: 패턴 기반 권장 — id에 `__11e7900__` 포함(옛 naming 관례) 또는 `_tight` 접미. 단 **이 패턴이 official 2개를 절대 잡지 않는지 검증 필수**(예: `_tight`가 `rubric_v2_tools` 접두와 겹치는 점 주의 — endsWith로 정확히).
   - OFFICIAL 배지: 패턴 추론 말고 **명시적 지정**(id 2개 allowlist 또는 동등한 explicit 플래그). "official"은 큐레이션된 지위이지 패턴이 아님 — 미래에 새 official이 생기면 owner가 추가하는 구조.
   - 숨김 규칙은 phase 1의 `isHiddenGrade`에 합류시켜 **단일 지점 필터 유지**(GradingAnalysisView의 하위 렌더·분포 차트·error가 자동 일관).
2. **배지 UI:** 카드에 작은 "OFFICIAL" 태그. 기존 UI 관례(Tailwind/컴포넌트 스타일) 따르고 과하게 디자인하지 마라. `?debug=1`에서도 배지는 유지(전부 보이되 official이 구분되게).
3. **phase 1 동작 불변:** 데모/스모크 숨김, KPI official 필터, 토글 — 그대로. 2차는 *추가*만.
4. **데이터 불변:** 표시 필터/배지만. grade JSON·aggregate 스크립트 건드리지 마라.

## ⛔ GIT
- 커밋/push/머지 금지 — 코드 변경은 로컬 작업트리만. **owner가 검토 후 커밋 지시**(phase 1과 동일 절차: 지시 받으면 기능 코드만 surgical 커밋, push는 별도 지시).
- read-only git 외 상태 변경 금지. 보고서는 파일로 쓰되 커밋 금지.

## 검증
- 기본 화면: exp003 카드 **2개만**(official 5.4 + mini, 둘 다 배지) — 옛 5개 안 보임. 데모/스모크도 여전히 숨김(phase 1 불변).
- `?debug=1`: grades 13개 전부 복원(옛 5개 포함), official 배지는 그 안에서도 표시.
- **역방향 보호:** official 2개가 *어떤 경우에도 숨겨지지 않는지*(패턴 오포착 0) 실데이터로 확인.
- `tsc --noEmit` + `npm run build` + preview에서 양쪽 URL 200.

## 출력 — `tasks/0607_sunday/dashboard_cleanup_phase2.md` (커밋 금지)
```
# DASHBOARD CLEANUP PHASE 2 — exp003 정리 + OFFICIAL 배지
## 한 줄 결론
## 식별 규칙 (패턴 + official allowlist, 오포착 검증)
## 배지 UI (어디에 어떻게, 기존 관례)
## 검증 (기본/debug 양쪽 실측, 역방향 보호, 빌드)
## 변경 파일 (미커밋 — owner 커밋 대기)
```

## 제약 재확인
- phase 1 구조 확장만(새 구조 금지), 단일 지점 필터 유지.
- official 2개는 명시 지정 + 어떤 패턴에도 숨겨지지 않음을 검증.
- 데이터/aggregate 불변, 표시만. 커밋/push 금지(owner 지시 대기).
- 막히면 방향 틀지 말고 보고.
