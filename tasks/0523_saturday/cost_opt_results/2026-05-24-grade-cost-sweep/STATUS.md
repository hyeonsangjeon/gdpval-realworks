# Sweep Orchestration Status (실시간)

> 이 문서는 사용자가 외출에서 돌아왔을 때 **한눈에 진행 상황을 파악**하기 위한 단일 진입점이다.
> orchestrator가 자동 갱신한다. 가장 아래로 스크롤하면 가장 최신 상태가 보인다.

---

## 빠른 명령

- **현재 진행 중인 sweep run 확인**
  ```bash
  gh run list --workflow=grade-cost-sweep.yml --limit 5
  ```
- **특정 run 로그 보기** (예: 26353454477)
  ```bash
  gh run view 26353454477 --log
  ```
- **현재 작업 브랜치 최근 commit**
  ```bash
  git log --oneline main..feat/grade-cost-sweep
  ```
- **결과 partial check** (sweep 완료 후 commit-back되면)
  ```bash
  cat tasks/0523_saturday/cost_opt_results/2026-05-24-grade-cost-sweep/RESULTS.md
  ```

## Phase 운영 결정 트리

| Phase A 결과 | 다음 액션 |
|---|---|
| 우승자 존재 + critical 1.0 | Phase B 자동 trigger |
| 우승자 없음 (모든 variant fail) | plan 조정 task 작성, 사용자에게 보고 |
| 일부만 성공 | 부분 결과 + 사용자 검토 요청 |
| cost cap 초과 | abort, 비용 분석 보고 |

## 트리거 명령 참고 (다음 phase로 진행 시)

```bash
# Phase B trigger (Phase A 완료 후, resume 모드)
gh workflow run grade-cost-sweep.yml \
  --ref main \
  -f source_ref=feat/grade-cost-sweep \
  -f phases=B \
  -f resume=true \
  -f experiment_yaml=exp998_smoke_baseline_sample \
  -f output_subdir=2026-05-24-grade-cost-sweep \
  -f max_cost_usd=80
```

```bash
# Phase C trigger (top 2 × 3회 stability, A+B 완료 후)
gh workflow run grade-cost-sweep.yml \
  --ref main \
  -f source_ref=feat/grade-cost-sweep \
  -f phases=C \
  -f resume=true \
  -f experiment_yaml=exp998_smoke_baseline_sample \
  -f output_subdir=2026-05-24-grade-cost-sweep \
  -f max_cost_usd=80
```

## 비용/한도

- **Per-phase 누적 cost cap**: $80 (전체)
- **GH Actions timeout**: 350분 (6시간 -10분 안전 마진)
- **OIDC**: main 브랜치만 federated → 모든 sweep workflow는 `--ref main` 으로
- **Source code**: feat/grade-cost-sweep 브랜치에서 checkout

## 알려진 위험

1. **batch-runner/.env가 stale**: 로컬 실행은 영구 불가. GH Actions만 사용.
2. **dispatcher가 progress.json mid-run으로는 commit 안 함**: 완료까지 라이브 모니터링 어려움. step 종료 후 log 확인 가능.
3. **Phase B는 Phase A 우승자 기반 동적 augmentation**: A 결과가 비어있으면 B는 정적 정의만.
4. **gpt-5.5 미승인 상태**: plan에서 제외됨 (gpt-5.4 family + gpt-4o만 사용).

## Phase 진행 기록

> orchestrator가 phase마다 한 줄 추가한다. 가장 위가 가장 최근.

| 시각 (UTC) | 이벤트 | 비고 |
|---|---|---|
| 2026-05-24 11:56 | Phase A run 26353454477 cancelled (350m timeout) — **11/15 partial**, $19.44 spent, all critical_pass=1.0 | partial 결과 commit + resume 트리거 |
| 2026-05-24 05:57 | Phase A run 26353454477 시작 | 첫 trigger 실패 후 source_ref input 추가하여 재시도 |
| 2026-05-24 05:54 | 첫 GH Actions sweep run 26353388215 — OIDC fail (AADSTS700213, 미등록 ref) | 워크플로우 ref 처리 수정 trigger |
| 2026-05-24 04:42 | 로컬 sweep 시도 2회 — 모두 auth 차단 (`PHASE_A_AUTH_BLOCKED.md`) | $0 spent |
| 2026-05-24 04:36 | feat/grade-cost-sweep 브랜치 + Track 1/2/fix commits | 7 commits + workflow |

---

_마지막 갱신: 2026-05-24 06:08 UTC. orchestrator가 phase 결과 들어올 때마다 위 표 갱신._
