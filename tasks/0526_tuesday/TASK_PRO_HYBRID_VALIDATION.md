# TASK_PRO_HYBRID_VALIDATION — Pro 단독 vs Hybrid 풀런 측정 (exp003 220 tasks)

> 작성: 2026-05-26 (Tuesday)
> 선행 완료: step8 task #50 silent fail fix (commit `486e4a4`)
> 의사결정 게이트: OpenAI GDPVal "official" 채점은 pairwise human ranking이고
> public automated grader는 `GPT-5-high` 기반. 우리 rubric-based pipeline에서
> 어느 구성이 spec에 더 가까운지 + 진짜 비용은 얼마인지 풀런 1회로 측정.

## TL;DR

이전 작업 (`TASK_TIERED_VALIDATION.md`)은 partial 40-task에서 끝나 비용 추정에 큰 불확실성. step8 fix 후 220-task 완주 가능. 두 config로 head-to-head:

- **Run X**: `validation_pro_only.yaml` — gpt-5.4-pro high 단독 (GPT-5-high spec proxy)
- **Run Y**: `validation_hybrid.yaml` — pro(critical weight≥4) + gpt-5.4(standard, 대부분) + gpt-5.4-mini(fuzzy precheck 옵션)

→ 결과로 답할 질문:
1. **진짜 pro single 풀런 비용**은? (외삽 $494 vs 실측)
2. **하이브리드 풀런 비용**은? (추정 $170~200 vs 실측)
3. **critical_pass / avg_score 차이**: 어느 쪽이 더 보수적/엄격한지 220 tasks 기준
4. **본인 운영 환경에서 wall-clock**: GH Actions 480분 timeout 안에 둘 다 완주 가능한가?
5. **현재 mini default (`data/grades/exp003 없음, 풀런 미실측`) 대비**: 점수 차이가 얼마나 의미 있는지

## 선행 조건 — 모두 충족됨

- ✅ step8_grade.py pct clamp + traceback fix (commit `486e4a4` on main)
- ✅ tiered routing 코드 (Track 1, PR #53)
- ✅ exp003 HF dataset에 deliverables 629개 검증됨
- ✅ Azure SP credentials (internal tenant) OIDC 동작 검증됨
- ✅ 51 grader + 5 schema tests pass

## Config 사양

### `validation_pro_only.yaml` (Run X)

기존 default_gpt5pro.yaml의 **gpt-5.4-pro 버전** 복원. 의도: sweep에서 외삽한 $494 / 142min 추정이 220-task 실제와 얼마나 일치하는지 측정.

핵심 필드:
- judge.model = "gpt-5.4-pro", deployment = "gpt-5.4-pro"
- judge.reasoning.effort = "high"
- grader.deliverable_extract_max_chars = 4000 (원본 pro default 값 그대로)
- judge_routing 없음 (단일 모델)
- batch_size = 1
- filename_template: `{exp_id}__{judge_slug}-prosolo__{rubric_short_sha}__{prompt_v}.json` (current default와 collision 방지)

### `validation_hybrid.yaml` (Run Y)

사용자 제안 구성: pro for critical, gpt-5.4 standard for rest, mini for fuzzy precheck (선택).

핵심 필드:
- 최상위 judge.model = "gpt-5.4" standard (cache key용 기본값)
- judge.reasoning.effort = "medium" (standard tier 기본)
- judge_routing:
  - tier_pro: gpt-5.4-pro, effort="high", route_when.weight_gte=4
  - tier_standard: gpt-5.4, effort="medium"
  - tier_mini: gpt-5.4-mini, effort="minimal", criterion_pattern_match=["executive summary","section titled","contains a header"]
- grader.deliverable_extract_max_chars = 1500
- batch_size = 1
- filename_template: `{exp_id}__{judge_slug}-hybrid__{rubric_short_sha}__{prompt_v}.json`

## 실행 절차 (자율 dispatch)

```
Step 1: 두 config 작성 + validate_grading_config 통과 + commit
Step 2: 두 GH Actions runs 병렬 trigger
        gh workflow run grade-run.yml --ref main \
          -f experiment_yaml=exp003_GPT52Chat_baseline_runner_exec \
          -f grading_config=validation_pro_only.yaml \
          -f force=true -f tasks_limit=0
        (and similar for validation_hybrid.yaml)
Step 3: 두 run 모니터링 (예상 4~6h)
Step 4: 완료 후 grade JSON 회수 + 다음 차원으로 분석
        a. 풀런 비용 (estimated + 추후 실청구 비교)
        b. wall-clock
        c. critical_item_pass_rate, avg_score_pct
        d. 현재 default(mini)의 exp998 smoke 결과와의 일관성
        e. 두 config의 task-level disagreement (어디서 의견 갈리나)
Step 5: COMPARISON_PRO_HYBRID.md 작성 (결과 + 권고)
Step 6: 결정 분기:
        a. 하이브리드가 pro 대비 80% 비용으로 critical_pass 0.95 이상 보존 → 하이브리드를 default 후보로
        b. pro single이 critical_pass에서 유의미하게 우월 ($300+ 정당화) → pro single 후보
        c. 둘 다 mini default 대비 의미 있는 우월 없음 → mini default 유지 + 둘은 named alternative
Step 7: 결정에 따라 default 교체 PR (또는 유지 보고)
Step 8: CHANGELOG에 기록
```

## Acceptance criteria

| 결과 | 결정 |
|---|---|
| 하이브리드 완주 ✓ + critical_pass(hybrid) ≥ critical_pass(pro) − 0.05 + cost ≤ 50% pro | hybrid가 default 후보 |
| 하이브리드 critical_pass(hybrid) > critical_pass(mini default) + 0.1 + cost ≤ $200 | hybrid 채택 강력 권장 |
| pro 풀런 cost > $400 | pro single은 default 후보 제외 (월예산 부담) |
| 어느 한 쪽이 timeout으로 실패 | 그 config는 timeout 대응 (chunk 분할) 추가 작업 필요 |

## 예상 비용

| Run | 추정 비용 | 추정 wall-clock |
|---|---|---|
| X (pro single) | ~$494 (sweep 외삽) | ~5~9h |
| Y (hybrid) | ~$170~220 | ~4~6h |
| 합계 | ~$660~715 | (병렬 실행) |

월예산 $2,500 내 합리적 (~28%). 절반 사용해도 검증 1회 가치.

## Stop conditions

- step8가 또 silent fail → fix 검증 자체 실패, 별도 디버그 task
- GH Actions timeout (480분) 도달 → partial 결과로 분석
- 누적 비용 (X+Y) > $900 → 후속 run abort
- critical_pass < 0.30 → inference quality 문제, 다른 experiment 후보 (exp013 등) 재고

## Files

- `batch-runner/grading_configs/validation_pro_only.yaml` (신규)
- `batch-runner/grading_configs/validation_hybrid.yaml` (신규)
- `data/grades/exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-pro-prosolo__11e7900__v1.json` (Run X 산출물)
- `data/grades/exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-hybrid__11e7900__v1.json` (Run Y 산출물; judge_slug=gpt-5_4)
- `tasks/0526_tuesday/COMPARISON_PRO_HYBRID.md` (분석 보고서)

## Out of scope

- External tenant swap 구현 (별도 `tasks/external_tenant_add/TASK_TENANT_SWAP.md`)
- Pairwise human ranking 구현 (OpenAI official spec; 별도 future task)
- step8 추가 robustness (현재 fix로 task #50 류는 해결됨)
- Cost reduction beyond hybrid (예: pro effort=medium 같은 micro-tuning) — 이번 결과 보고 결정
