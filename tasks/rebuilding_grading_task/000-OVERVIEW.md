# 000 — OVERVIEW (Grading Pipeline v2 Rebuild)

> Authoritative SPEC: [`SPEC_GRADING_PIPELINE_V2.md`](./SPEC_GRADING_PIPELINE_V2.md)
> Prior analysis on main: `data/grades/_validation/STRATIFY_v2_*.md`, `SCORE_MATH_AUDIT.md` (commit `a1457a4`)

## 핵심 요약

1. **단일 메인 judge**: production은 `gpt-5.6-sol`
	reasoning_effort=`max`. tier 없음. 최초 PR2 baseline인 `gpt-5.4 medium`은
	`default_v2.yaml` 비교 identity로 보존.
2. **눈/귀 부착**: text 추출 폐기, judge가 `read_deliverable` tool로 파일 직접 조회. production 시각 항목 → `gpt-5.6-sol` reasoning_effort=`max`, 오디오 지각 → `gpt-audio-1.5`.
3. **score-math sign-bug fix**: `verdict='pass'` 부호 시멘틱 정규화, `|max_score|≥4` critical 재정의, `total_max≤0` degenerate 케이스 explicit 처리.
4. **legacy 제거**: `deliverable_extract_max_chars`, tier 분기, `required` OR-가지 잔재 전부.

## PR 분할 (SPEC §6 + 본 작업자 분해)

### PR1 — Score-Math Sign-Bug Fix (선행, 필수)  ✅ **CLOSED** — see [PR1_REPORT.md](./PR1_REPORT.md)

| # | task | 상태 |
|---|---|---|
| 100 | [sign-aware aggregate](./100-sign-aware-aggregate.md) | ✅ `240b860` |
| 101 | [critical redefinition](./101-critical-redefinition.md) | ✅ `ad3b922` |
| 102 | [non-positive total_max handling](./102-handle-nonpositive-total-max.md) | ✅ `b9c46e8` |
| 103 | [backfill existing grades](./103-backfill-existing-grades.md) | ✅ `933c25e` |
| 104 | [regression sweep + report](./104-pr1-regression-sweep.md) | ✅ (this commit) |

**Acceptance**: PR1 끝나면 main 헤드라인 지표(`avg_score_pct`, `critical_item_pass_rate`)가 sign-aware로 신뢰 가능.

### PR2 — Tool-Calling Grader Rebuild (메인, 새 세션 권장)  ✅ **CLOSED** — see [PR2_REPORT.md](./PR2_REPORT.md)

| # | task | 상태 |
|---|---|---|
| 200 | [exp011 env audit](./200-env-audit.md) → [PR2_ENV_AUDIT.md](./PR2_ENV_AUDIT.md) | ✅ (this commit) |
| 201 | [read_deliverable tool 정의/구현](./201-tool-interface.md) | ✅ (this commit) |
| 202 | [judge prompt v2 (tool-aware)](./202-judge-prompt-tool-aware.md) | ✅ (this commit) |
| 203 | [메인 grader rewrite (tool-calling)](./203-grader-main-rewrite.md) | ✅ (this commit) |
| 204 | [modality routing](./204-perception-routing.md) | ✅ (this commit) |
| 205 | [vision perception (gpt-5.4 vision)](./205-vision-judge.md) | ✅ (this commit) |
| 206 | [audio perception (gpt-audio-1.5)](./206-audio-judge.md) | ✅ (this commit) |
| 207 | [legacy removal](./207-legacy-removal.md) | ⚠️ PARTIAL (this commit) — config archive only; code strip deferred |
| 208 | [config schema + validator 업데이트](./208-config-schema-update.md) | ✅ (this commit) |

### PR3 — Validation Gates (새 세션, PR2 후)

| # | task | 상태 |
|---|---|---|
| 300 | [gold-ceiling test](./300-gold-ceiling.md) | ⚠️ PARTIAL — v2 path live-verified on 3-task smoke (run `26677864500`, judge_error 1.19%, evidence tool-grounded). Gold-subset run pending. See [PR3_SMOKE_FINDINGS.md](./PR3_SMOKE_FINDINGS.md). |
| 301 | [exp003 재채점 + formatting 격차 붕괴 + bare-CSV evidence](./301-exp003-revalidation.md) | ✅ DONE — 220 재채점 완료 + 분석 완료. **formatting 격차는 붕괴하지 않고 -25.5pp → -46.0pp로 확대**; v1의 "hybrid over-rejects" 진단이 뒤집힘 (mini가 못 봐서 관대했던 것). bare-CSV 판별은 통과. 보고서는 `tasks/**` privacy 규칙(`5349cbf`) 때문에 [data/grades/_validation/PR3_EXP003_REVALIDATION.md](../../data/grades/_validation/PR3_EXP003_REVALIDATION.md)에 위치. |
| 302 | [cost budget 재추정](./302-cost-budget-recheck.md) | ⚠️ 미해결이지만 **전제가 낡음** — 당시 projection은 N=3 smoke 기준이었고, 그 뒤 220-task 실주행이 이미 끝났다. PR3_SMOKE_FINDINGS.md의 A/B/C는 그 낡은 projection 위에 서 있으므로 그대로 답할 수 없음. 실측 기준으로 다시 세워야 함 (owner gate). |
| 303 | [variance + bootstrap CI + judge_error rate](./303-variance-and-error.md) | ⏸ 301이 220-task baseline을 냈으므로 spec상 선행 조건은 해소. 유료 dispatch 3회 필요 → owner 승인 대기. |

## 자율 판단 결정 기록 (working memo)

이 작업의 owner agent가 SPEC 모호 영역에서 내린 결정. PR3 끝나면 CHANGELOG에 흡수.

| topic | decision | rationale |
|---|---|---|
| back-fill 정책 | (c) v1 보존 + v2 새 파일 명명 | published 데이터 손상 없이 비교 가능 |
| `total_max≤0` remediation | option 1 (positive-only denominator) | single-line change, 시멘틱 명확, option 2/3 후속 확장 여지 |
| critical 임계값 | `\|max_score\| >= 4` 상수 분리, 주석으로 "저자 signal 부재 컨벤션" 명시 | SPEC §4.4 직접 채택 |
| Grading skills 추출 | PR2 종료 후 grading-engineer agent용으로 추출 | 코드 안정화 후 skill 문서화가 자연 |
| tool 구현 방식 | library tool-calling (SPEC §4.2) 채택 | SPEC 명시 + 현 사용자 인프라(Azure Responses API) 부합 |
| prompt version bump | v1 → v2 archive 보존 | tool-aware 전환 명시 |
| PDF→image 백엔드 | `pdf2image+poppler` 대신 `PyMuPDF` (`fitz`) | 이미 requirements에 있고 wheel-only, GHA system 패키지 불필요 (task 200 audit) |
| 오디오/비디오 probe 백엔드 | `ffmpeg-python`/`moviepy` 대신 `PyAV` (`av`) 우선 | wheel이 ffmpeg 동봉, `grade-run.yml`에 `apt-get install ffmpeg` 추가 불필요 (task 200 audit) |
| `soundfile` 명시 의존 | 201에서 `requirements.txt`에 명시 추가 | 현재는 `librosa`/`pedalboard`의 transitive — 명시화로 fragility 제거 (task 200 audit) |
| v1 prompt 조기 교체 여부 | 교체하지 않고 `grader_judge_v2.md` 별도 신규 생성 + `grader_judge_v1_archive.md` 복사 보존. PR2 끝나고 207에서 v1 삽제 | 203 ToolCallingJudge는 legacy Judge와 공존 예정 — 둘 다 프롬프트 파일 필요 |
| perception routing 테스트 위치 | 기존 `test_grader_routing.py`(tier routing)와 분리해 `test_perception_routing.py` 신규 | concern 분리 — 207에서 legacy tier 테스트 삭제해도 modality routing 테스트는 살아남 |
| perception 클래스 의존성 주입 방향 | `client`을 생성자에 inject (클래스 내부 생성 X) | main judge가 Responses API 클라이언트 소유 + 테스트에서 FakeClient 제공 용이 |
| audio deployment 누락 처리 | `judge()` 호출 시점에 endpoint env 체크, 누락이면 `judge_error=endpoint_missing` graceful return | import-time hard fail 피하고 audio 항목에서만 결속 (main judge는 계속 동작) |
| grade-run.yml default config 교체 타이밍 | 2026-07-26 `default_v2_sol_max.yaml`로 전환 완료 | dry-run 기본, 명시적 paid 승인, protected `grading` environment를 함께 적용. 이전 5.4 config는 비교·재현용으로 보존. |
| 207 legacy 주니케이션 범위 | **조건부 PARTIAL**: v1 sweep/tier configs (`validation_*`, `tiered_*`, `_sweep_template`, `recommended_*`) 명시 아카이브 + README + `_archive_v1/README.md`. **하지만** `core/grader.py`의 `_use_batch`/`_tier_judges`/`_summarize_deliverables`/`deliverable_extract_max_chars` 코드 렌더링 변경 없음. `core/grader_batch.py`도 올. | `default_gpt5pro.yaml`은 현재 default가 아니라 historical comparison identity로 보존. legacy 코드 제거는 별도 cleanup PR에서 기존 historical config 재현성과 함께 처리. |

## 작업 흐름 (자동, 사용자 개입 없음)

각 task별:
1. 해당 task md 읽고 변경 범위 확정
2. 코드 변경
3. 영역 테스트 + 회귀
4. 통과 → commit + push
5. task md 상태 ☐ → ✅ 업데이트 (이 OVERVIEW)
6. 다음 task 자동 진행

PR 단위:
1. 마지막 task 완료 시 PR-요약 리포트 1장 (`PR{N}_REPORT.md`)
2. 검증 게이트 자동 실행
3. PASS → 다음 PR (또는 새 세션 핸드오프 메모)

## 비목표 (다시 확인)

- inference / 220 deliverable 재생성 안 함
- pro/hybrid를 default로 채택 안 함
- pairwise-vs-gold(GDPval 표준 win-rate) 모드 구현 안 함 (별도 후속)
- 비디오 *지각* 채점 안 함 (objective probe까지만)
