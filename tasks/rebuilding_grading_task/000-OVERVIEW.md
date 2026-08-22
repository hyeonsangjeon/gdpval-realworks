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
| 303 | [variance + bootstrap CI + judge_error rate](./303-variance-and-error.md) | ⏸ 301이 220-task baseline을 냈으므로 spec상 선행 조건은 해소. 아래 R1이 3회 중 1회를 겸하므로 실제 추가 dispatch는 2회 → owner 승인 대기. |

## 다음 순서 (PR3 이후)

PR3의 남은 항목(300 · 302 · 303)은 전부 유료 dispatch나 비용 결정에 걸려 있다.
그래서 순서를 "무료로 먼저 확정할 수 있는 것 → 유료 중 가장 값어치 있는 것"으로
잡는다. 아래 두 건이 그 순서다.

### C1 — grade job을 prebuilt container로 이전 (무료, 선행)

`ghcr.io/hyeonsangjeon/gdpval-sandbox`는 이미 `libreoffice` 메타패키지를 담고
있다 (`batch-runner/sandbox/Dockerfile:39`). grade job은 아직 shard마다 apt로
설치한다.

**이건 더 이상 장애 수정이 아니다.** shard 5개를 죽였던 apt 정지는 `#26`에서
retry·timeout·dpkg lock timeout으로 이미 처리됐다 (`grade-run.yml:637-668`).
지금 남은 이유는 다르고, 중요한 순서대로:

1. **렌더러가 버전 고정이 안 돼 있는데, 렌더러가 점수를 움직인다.** 설치는
   `libreoffice-core` / `-calc` / `-impress` / `-writer`를 버전 없이 요청한다.
   그날 미러가 주는 게 곧 judge가 보는 이미지를 만든다. 301은 v2의 formatting
   판정이 "본 것"에서 나온다는 걸 확인했다 — 즉 렌더러가 고정 안 되면 점수도
   고정이 안 된다. grader source hash가 같아도 한 달 차이 나는 두 run은 엄밀히
   비교 대상이 아니다. **baseline으로 발행할 run을 만들기 *전에* 해야 하는
   이유가 이것이다.**
2. retry는 미러 장애를 복구 가능하게 만들 뿐 없애지 못한다. container는 미러가
   필요 없다.
3. 같은 패키지를 shard 수만큼 반복 설치한다.
4. `#189`의 .docx 렌더링은 Writer 존재에 의존한다. container에서는 빌드 시점의
   사실이고, apt에서는 런타임의 기대다.

### R1 — 220 task 전체 재채점 (유료, owner gate) ⭐

**유료 중 가장 먼저 할 값어치가 있는 한 건.**

발행된 sol-220 run은 judge error **333 / 10,453 items = 3.19%** 로, 모든 후속
카드가 달고 있는 `< 2%` 게이트를 넘겼다. 원인은 코드에서는 이미 고쳐졌고, 아직
어떤 run에도 반영되지 않았다.

| 원인 | items | 처리 |
|---|---:|---|
| 같은 형식 파일이 여러 개일 때 selector가 선택을 포기 | **243** | `#190` |
| `required_visual_render_target_unavailable` 중 .docx | **65** | `#189` |
| 요청 형식(.xlsx/.pdf/.mp4/.docx)을 모델이 하나도 못 냄 | 12 | harness 결함 아님 — 모델 미제출 |
| `empty_final_text` | 4 | 위와 같음 |
| .docx 아닌 render target 부재 | 8 | 미해결 |
| visual file cap 초과 | 1 (+`#190` 이후 1) | 미해결, 소규모 |

333 중 308이 이미 고쳐졌다. 재실행하면 **~26 / 10,453 = 0.25%** 로 떨어진다 —
기준선을 내려서가 아니라 원인을 없애서 통과한다. 남는 26은 대부분 모델이 채점할
것을 실제로 안 낸 경우다.

게이트와 별개로, **모델이 실제로 제출한 결과물에 0점이 매겨진 rubric item 243개**
(과제 5건)가 복구된다. 그 0점은 지금 발행된 숫자 안에 들어 있다.

**왜 5과제 부분 재채점이 아니라 전체 재실행인가.** 5건만 기존 파일에 덧붙이면 한
run 안에 서로 다른 두 채점 파이프라인이 섞인다. "새로운 기준이 기존 실험에 영향을
주면 안 된다"는 규칙이 막으려는 게 정확히 이 경우다. 전체 재실행에는 그 문제가
없다 — 출력 파일명이 grader source hash를 달고 있고 **그 해시는 이미 바뀌었다**:
발행본 `src_1c967673eb8081a6`, 현재 `src_c8144d680d028d88`
(`compute_grader_source_hash`, `step8_grade.py:136` 이 `batch-runner/core/` 의 모든
`.py`를 해싱하므로 `#189`·`#190` 둘 다 포함된다). 새 run은 새 파일로 떨어지고
**아무것도 덮어쓰지 않는다. 따라서 `force`는 반드시 `false`.**

**선행 조건: C1.** 이 run의 formatting 판정은 LibreOffice 렌더에서 나오는데 지금
설치는 버전을 고정하지 않는다.

**푸는 것:** `< 2%` 게이트를 처음으로 정당하게 통과 · 303의 3회 중 1회를 겸함
(303의 추가 비용이 2회로 감소) · 300에 corpus 전체 비교 대상 제공.

dispatch 명령·canary 절차·acceptance는 board 카드
*"Re-grade all 220 tasks on the fixed pipeline (paid — owner gate)"* 에 있다.
**owner 승인 없이는 dispatch하지 않는다.**

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
