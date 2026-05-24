# TASK_GRADE_COST_SWEEP — Autonomous cost optimization sweep (Global Standard + prompt batching)

> **선행 task**: [TASK_GRADE_COST_OPTIMIZATION.md](./TASK_GRADE_COST_OPTIMIZATION.md) — 본 task는 그 계획의 **Phase 0 측정 + Phase 1~3 검증**을 자율 실행 형태로 구현한 것.
>
> **목표**: 사람이 개입하지 않고, 다중 grading config 변종을 자동 디스패치하여 정확도 제약 안에서 **풀런 비용 Pareto-frontier 우승자**를 도출하고, 결과를 `RESULTS.md`로 자동 생성한다.

---

## TL;DR

- **입력**: `tasks/0523_saturday/grading_cost_sweep_plan.yaml` (테스트 매트릭스, 본 task에 명세 포함)
- **실행기**: `scripts/grading_cost_sweep.py` (신규)
- **타깃 데이터**: `exp998_smoke_baseline_sample` 3 tasks / 94 rubric items (고정 벤치마크)
- **사용 모델**: Global Standard 배포만 사용 (Azure Batch API SKU 도입 X). 본인 endpoint의 가용 모델 7종 중 judge 후보:
  - `gpt-5.4-pro` (100 kTPM) — pro tier
  - `gpt-5.4-pro-2` (60 kTPM) — pro 보조 (parallel sharding 용)
  - `gpt-5.4` (150 kTPM) — standard tier
  - `gpt-5.4-mini` (150 kTPM) — extended precheck 후보
  - `gpt-5.4-nano` (250 kTPM) — 초경량 mini 후보
  - `gpt-4o` (100 kTPM) — diversity validator (sanity only)
  - **제외**: `gpt-5.2-chat` (inference 모델, Judge≠Inference 규칙 위반)
- **출력**:
  - `tasks/0523_saturday/cost_opt_results/<ts>/RESULTS.md` (사람용)
  - `tasks/0523_saturday/cost_opt_results/<ts>/summary.json` (기계용)
  - `tasks/0523_saturday/cost_opt_results/<ts>/winner_config.yaml` (drop-in `default_*.yaml` 후보)
  - `tasks/0523_saturday/cost_opt_results/<ts>/runs/<config_name>/grade.json` (개별 grade 결과)

---

## Hard Constraints (절대 위반 금지)

본 task는 grading-engineer mode hard rule을 그대로 상속한다:

1. **Evidence mandatory**: 모든 judge verdict에 evidence ≤ 200 chars. 누락 시 verdict=fail.
2. **Precheck before judge**: PRECHECK_PATTERNS 매칭 항목은 LLM에 가지 않는다.
3. **Reproducibility**: `temperature=0`, `seed=42`, 4-tuple cache key `(exp_id, judge_model, rubric_sha, prompt_v)`. 모든 변종이 이를 준수.
4. **Schema frozen**: `data/grades/*.json`은 `schemas/grade.schema.json` v1.0 그대로. sweep 결과는 별도 sandbox 디렉토리 사용.
5. **judge_error ≠ fail**: 분리 카운트.
6. **TPM guard**: 변종 config의 `tpm_guard.max_concurrent`는 해당 모델의 TPM의 70% 이하로 산출되도록 강제. quota 침해 시 sweep abort.
7. **No cross-pipeline coupling**: step1~step7 건드리지 않음.
8. **OIDC only**: `AZURE_OPENAI_API_KEY` env 의존 추가 금지.
9. **Cost cap**: 전체 sweep 누적 예상 비용이 **$80** 초과 시 abort (실측값으로 매 변종 종료마다 누계 갱신).
10. **CHANGELOG**: sweep 완료 후 `[Unreleased]`에 결과 요약 한 줄 자동 추가.

---

## Architecture: Autonomous Dispatcher

### 흐름

```
┌────────────────────────────────────────────────────────────────────┐
│ scripts/grading_cost_sweep.py                                       │
│                                                                     │
│ 1. Load sweep plan (YAML)                                           │
│ 2. Validate: model availability, TPM cap, schema, deps              │
│ 3. For each variant in plan.variants:                               │
│    a. Render temp grading config to tmp/grading_cost_sweep/<name>/  │
│    b. Idempotency check: skip if grade JSON already cached          │
│    c. Cost-cap check: estimate variant cost, abort if cumulative > $80
│    d. Invoke step8_grade.py with --config <temp> --limit 3          │
│    e. Parse result JSON, append to results buffer                   │
│    f. Save partial progress (so re-run resumes)                     │
│ 4. Pareto-frontier selection                                        │
│ 5. Emit RESULTS.md + summary.json + winner_config.yaml              │
│ 6. Append CHANGELOG entry                                           │
└────────────────────────────────────────────────────────────────────┘
```

### 디렉토리 구조

```
tasks/0523_saturday/
├── TASK_GRADE_COST_SWEEP.md             ← 본 문서
├── grading_cost_sweep_plan.yaml         ← test matrix (sweep input)
└── cost_opt_results/
    └── 2026-05-24T12-00-00Z/
        ├── plan.snapshot.yaml           ← 실행 시점 plan 복사본 (재현용)
        ├── progress.json                ← 진행/캐시 (재개 가능)
        ├── runs/
        │   ├── A1_pro_minimal/
        │   │   ├── config.yaml
        │   │   └── grade.json
        │   ├── A1_pro_low/...
        │   └── ...
        ├── summary.json                  ← 모든 변종 metric
        ├── RESULTS.md                    ← human report
        └── winner_config.yaml            ← drop-in 후보
```

---

## Sweep Plan (테스트 매트릭스)

`tasks/0523_saturday/grading_cost_sweep_plan.yaml`:

```yaml
schema_version: "1.0"
plan_name: "cost_opt_sweep_v1"
fixed_benchmark:
  experiment_yaml_name: "exp998_smoke_baseline_sample"
  task_limit: 3                     # 고정 (94 rubric items)
  rubric_sha: "11e7900"             # 고정

global_constraints:
  cost_cap_usd: 80                  # 누적 비용 한도
  max_wall_clock_min: 240           # 전체 sweep 4시간 이내
  abort_on_first_quota_exceed: true # 429 폭증 시 즉시 중단

acceptance:
  avg_score_delta_pp: 2.0           # baseline 77.83% 기준 ±2.0
  critical_item_pass_rate_min: 1.0
  judge_error_rate_max: 0.05        # 5%
  precheck_pass_rate_min: 0.7

baseline:
  config_path: "batch-runner/grading_configs/default_gpt5pro.yaml"
  expected_metrics:
    avg_score_pct: 77.83
    judge_call_count: 84
    judge_total_latency_sec: 8530
    judge_error_rate: 0.0595

# ============================================================
# Phase A: Single-axis sweeps — find each variable's sweet spot
# ============================================================
phase_a_single_axis:
  # A1. reasoning_effort sweep (model fixed: gpt-5.4-pro)
  - name: "A1_pro_minimal"
    judge: { model: "gpt-5.4-pro", deployment: "gpt-5.4-pro", reasoning_effort: "minimal" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 1 }
  - name: "A1_pro_low"
    judge: { model: "gpt-5.4-pro", deployment: "gpt-5.4-pro", reasoning_effort: "low" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 1 }
  - name: "A1_pro_medium"
    judge: { model: "gpt-5.4-pro", deployment: "gpt-5.4-pro", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 1 }
  - name: "A1_pro_high"
    judge: { model: "gpt-5.4-pro", deployment: "gpt-5.4-pro", reasoning_effort: "high" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 1 }

  # A2. deliverable extract chars sweep (model: gpt-5.4 standard, effort: medium)
  - name: "A2_std_extract_1000"
    judge: { model: "gpt-5.4", deployment: "gpt-5.4", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1000, batch_size: 1 }
  - name: "A2_std_extract_1500"
    judge: { model: "gpt-5.4", deployment: "gpt-5.4", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 1 }
  - name: "A2_std_extract_2500"
    judge: { model: "gpt-5.4", deployment: "gpt-5.4", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 2500, batch_size: 1 }

  # A3. batch_size sweep (model: gpt-5.4 standard, effort: medium, extract 1500)
  - name: "A3_std_batch_1"
    judge: { model: "gpt-5.4", deployment: "gpt-5.4", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 1 }
  - name: "A3_std_batch_4"
    judge: { model: "gpt-5.4", deployment: "gpt-5.4", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 4 }
  - name: "A3_std_batch_8"
    judge: { model: "gpt-5.4", deployment: "gpt-5.4", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 8 }
  - name: "A3_std_batch_12"
    judge: { model: "gpt-5.4", deployment: "gpt-5.4", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 12 }

  # A4. model sweep (effort: medium, extract 1500, batch 1)
  - name: "A4_model_pro"
    judge: { model: "gpt-5.4-pro", deployment: "gpt-5.4-pro", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 1 }
  - name: "A4_model_std"
    judge: { model: "gpt-5.4", deployment: "gpt-5.4", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 1 }
  - name: "A4_model_mini"
    judge: { model: "gpt-5.4-mini", deployment: "gpt-5.4-mini", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 1 }
  - name: "A4_model_nano"
    judge: { model: "gpt-5.4-nano", deployment: "gpt-5.4-nano", reasoning_effort: "minimal" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 1 }

# ============================================================
# Phase B: Combinations — top performers from Phase A
# ============================================================
# Dispatcher가 Phase A 결과를 보고 Phase B 변종을 동적으로 생성한다.
# (정적 plan 일부 + Phase A 우승자 기반 동적 plan)
phase_b_combinations:
  # B1. baseline reference (현재 운영 config)
  - name: "B1_baseline_ref"
    inherit_from: "baseline"     # default_gpt5pro.yaml 그대로

  # B2. all-standard, medium, batch 8
  - name: "B2_std_med_b8"
    judge: { model: "gpt-5.4", deployment: "gpt-5.4", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 8 }

  # B3. Tiered: pro for weight>=4, std for rest, batch 8
  - name: "B3_tiered_pro_std_b8"
    judge_routing:
      tier_pro:
        model: "gpt-5.4-pro"
        deployment: "gpt-5.4-pro"
        reasoning_effort: "high"
        route_when: { weight_gte: 4 }
      tier_standard:
        model: "gpt-5.4"
        deployment: "gpt-5.4"
        reasoning_effort: "medium"
    grader: { deliverable_extract_max_chars: 1500, batch_size: 8 }

  # B4. Tiered + mini extended precheck
  - name: "B4_tiered_with_mini_b8"
    judge_routing:
      tier_pro:
        model: "gpt-5.4-pro"
        deployment: "gpt-5.4-pro"
        reasoning_effort: "high"
        route_when: { weight_gte: 4 }
      tier_standard:
        model: "gpt-5.4"
        deployment: "gpt-5.4"
        reasoning_effort: "medium"
      tier_mini:
        model: "gpt-5.4-mini"
        deployment: "gpt-5.4-mini"
        reasoning_effort: "minimal"
        criterion_pattern_match:
          - "executive summary"
          - "section titled"
          - "contains a header"
    grader: { deliverable_extract_max_chars: 1500, batch_size: 8 }

  # B5. Tiered + nano (더 공격적)
  - name: "B5_tiered_with_nano_b8"
    judge_routing:
      tier_pro:
        model: "gpt-5.4-pro"
        deployment: "gpt-5.4-pro"
        reasoning_effort: "high"
        route_when: { weight_gte: 4 }
      tier_standard:
        model: "gpt-5.4"
        deployment: "gpt-5.4"
        reasoning_effort: "medium"
      tier_mini:
        model: "gpt-5.4-nano"
        deployment: "gpt-5.4-nano"
        reasoning_effort: "minimal"
        criterion_pattern_match:
          - "executive summary"
          - "section titled"
          - "contains a header"
    grader: { deliverable_extract_max_chars: 1500, batch_size: 8 }

# ============================================================
# Phase C: Stability runs — top 2 from Phase B, 3 runs each
# ============================================================
phase_c_stability:
  repeat_count: 3
  pick_top_n_from_phase_b: 2
  variance_threshold:
    avg_score_pct_std: 1.5         # 3회 표준편차 ≤ 1.5pp 필요
    judge_error_rate_std: 0.02

# ============================================================
# Optional: Diversity validator (sanity, 1회만)
# ============================================================
diversity_validator:
  enabled: true
  variant:
    name: "DV_gpt4o_medium_b8"
    judge: { model: "gpt-4o", deployment: "gpt-4o", reasoning_effort: "medium" }
    grader: { deliverable_extract_max_chars: 1500, batch_size: 8 }
  purpose: |
    gpt-4o(다른 family) 결과와 우승자 결과의 verdict 일치율을 측정해
    family-bias 위험을 평가한다. 우승자 결정에는 영향 없음 (참고만).
```

---

## Dispatcher 스크립트 명세

`scripts/grading_cost_sweep.py`:

### Inputs
- `--plan PATH` (default `tasks/0523_saturday/grading_cost_sweep_plan.yaml`)
- `--output-dir PATH` (default `tasks/0523_saturday/cost_opt_results/<auto-ts>/`)
- `--resume PATH` (resume from existing output dir; skip cached variants)
- `--dry-run` (계산만 하고 실제 채점 호출 안 함)
- `--max-cost USD` (overrides plan cost_cap_usd)
- `--phases A,B,C` (subset 실행)

### Pseudocode

```python
def main():
    plan = load_plan(args.plan)
    output_dir = setup_output_dir(args.output_dir)
    snapshot(plan, output_dir / "plan.snapshot.yaml")
    progress = load_or_init_progress(output_dir / "progress.json")

    # ---- Validate ----
    validate_models_available(plan)          # endpoint에 deployment 존재 확인
    validate_tpm_caps(plan)                  # max_concurrent × call/min ≤ 70% TPM
    validate_acceptance_thresholds(plan)

    # ---- Phase A ----
    for variant in plan.phase_a_single_axis:
        if variant.name in progress.completed: continue
        cost_so_far = progress.cumulative_cost_usd
        est_cost = estimate_variant_cost(variant, plan.fixed_benchmark)
        if cost_so_far + est_cost > plan.cost_cap_usd:
            abort_with_message("cost_cap_exceeded", cost_so_far, est_cost)

        config_path = render_temp_config(variant, output_dir)
        result = run_step8_grade(config_path, plan.fixed_benchmark)
        metrics = extract_metrics(result)
        progress.append(variant.name, metrics)
        save_progress(progress)

        # Acceptance check (soft — 실패해도 sweep 계속, 표시만)
        annotate_acceptance(variant.name, metrics, plan.acceptance)

    # ---- Phase B (dynamic: depends on Phase A winners) ----
    phase_a_winners = pick_phase_a_winners(progress)  # 상위 3개 axis별
    augmented_phase_b = augment_phase_b(plan.phase_b_combinations, phase_a_winners)
    for variant in augmented_phase_b:
        (same loop as Phase A)

    # ---- Phase C (stability) ----
    top_b = pick_top_n(progress, plan.phase_c_stability.pick_top_n_from_phase_b)
    for variant in top_b:
        for rep in range(plan.phase_c_stability.repeat_count):
            run_variant(variant, suffix=f"_rep{rep}")

    # ---- Optional: diversity validator ----
    if plan.diversity_validator.enabled:
        run_variant(plan.diversity_validator.variant)
        diversity = measure_agreement(winner, plan.diversity_validator.variant)
        progress.diversity_agreement = diversity

    # ---- Selection ----
    winner = select_pareto_winner(progress, plan.acceptance)
    write_winner_config(winner, output_dir / "winner_config.yaml")

    # ---- Outputs ----
    write_summary_json(progress, output_dir / "summary.json")
    write_results_md(progress, winner, plan, output_dir / "RESULTS.md")
    append_changelog_entry(winner, plan, output_dir)

    print(f"[sweep] winner: {winner.name}")
    print(f"[sweep] cost spent: ${progress.cumulative_cost_usd:.2f}")
    print(f"[sweep] report: {output_dir / 'RESULTS.md'}")
    sys.exit(0 if winner else 1)
```

### Cost estimation (실측 기반)

```python
def estimate_variant_cost(variant, benchmark):
    """Predict variant cost from (model, effort, batch_size, items, deliverable_chars).

    근사식 (Phase 1 측정값 캘리브레이션):
      input_tok ≈ (deliverable_chars / 4) + (batch_size × criterion_avg_tok ≈ 120) + system ≈ 200
      output_tok ≈ batch_size × per_item_verdict_tok(effort) + reasoning_tok(effort)
        per_item_verdict_tok(minimal)=80, (low)=150, (medium)=400, (high)=800
        reasoning_tok(minimal)=20, (low)=200, (medium)=600, (high)=1200

      cost = (input_tok × in_rate + output_tok × out_rate) / 1e6 × N_calls
      where N_calls = ceil(judge_items / batch_size)
    """
```

### Winner selection (Pareto)

```python
def select_pareto_winner(progress, acceptance):
    # 1) Hard filter
    eligible = [v for v in progress.results if
                v.critical_item_pass_rate >= acceptance.critical_item_pass_rate_min and
                v.judge_error_rate <= acceptance.judge_error_rate_max and
                abs(v.avg_score_pct - 77.83) <= acceptance.avg_score_delta_pp]

    if not eligible:
        return None  # 실패 신호; RESULTS.md에 "no winner"로 기록

    # 2) Pareto frontier on (full_run_cost_usd, judge_error_rate, latency_sec)
    pareto = pareto_frontier(eligible, axes=["full_run_cost_usd", "judge_error_rate", "judge_total_latency_sec"])

    # 3) Tie-break: lowest full_run_cost_usd
    winner = min(pareto, key=lambda v: v.full_run_cost_usd)

    # 4) Stability check from Phase C
    if winner.has_phase_c_data and winner.avg_score_pct_std > 1.5:
        return select_pareto_winner_excluding(pareto, winner)  # 2위 시도

    return winner
```

### TPM cap validation (선행)

```python
def validate_tpm_caps(plan):
    """각 variant의 (model, max_concurrent)가 endpoint TPM의 70% 안에 드는지 확인"""
    TPM_AVAILABLE = {
        "gpt-5.4-pro":   100_000,
        "gpt-5.4-pro-2":  60_000,
        "gpt-5.4":       150_000,
        "gpt-5.4-mini":  150_000,
        "gpt-5.4-nano":  250_000,
        "gpt-4o":        100_000,
    }
    SAFE_FACTOR = 0.7
    for variant in plan.all_variants():
        model = variant.judge.model
        concurrent = variant.tpm_guard.max_concurrent
        per_call_tok = estimate_per_call_tok(variant)
        peak_tpm = concurrent * per_call_tok * (60 / estimated_call_duration_sec(variant))
        if peak_tpm > TPM_AVAILABLE[model] * SAFE_FACTOR:
            raise SweepValidationError(
                f"{variant.name}: peak {peak_tpm:.0f} TPM > 70% of {model} ({TPM_AVAILABLE[model]:,})"
            )
```

---

## RESULTS.md (자동 생성 명세)

```markdown
# Grading Cost Sweep — Results

**Run**: 2026-05-24T12:00:00Z
**Plan**: cost_opt_sweep_v1
**Benchmark**: exp998_smoke_baseline_sample, 3 tasks, 94 rubric items
**Baseline**: default_gpt5pro.yaml (gpt-5.4-pro high, batch=1, extract=4000)

## TL;DR

**Winner**: `B3_tiered_pro_std_b8`
- 풀런 예상 비용: **$58.4** (baseline $540 대비 −89.2%)
- avg_score_pct: 78.91 (baseline 77.83, delta +1.08pp ✓)
- critical_item_pass_rate: 1.00 ✓
- judge_error_rate: 3.1% ✓
- wall-clock (smoke): 28.4m (baseline 142m)

## Phase A: Single-axis sweep

### A1. reasoning_effort (gpt-5.4-pro)
| variant | effort | judge calls | latency (s) | err% | score delta | smoke $ | 풀런 $ |
|---|---|---|---|---|---|---|---|
| A1_pro_minimal | minimal | 84 | 1820 | 4.8 | -0.5 | $2.1 | ~$150 |
| A1_pro_low | low | 84 | 2980 | 4.2 | +0.3 | $3.0 | ~$220 |
| A1_pro_medium | medium | 84 | 5120 | 5.1 | -1.2 | $5.3 | ~$390 |
| A1_pro_high (baseline) | high | 84 | 8530 | 5.9 | 0.0 | $7.4 | ~$540 |

### A2. deliverable_extract_max_chars (gpt-5.4 std, medium)
...

### A3. batch_size (gpt-5.4 std, medium, extract 1500)
...

### A4. model sweep (medium, extract 1500, batch 1)
...

## Phase B: Combinations

| variant | judge calls | err% | score delta | smoke $ | 풀런 $ | Pareto? |
|---|---|---|---|---|---|---|
| B1_baseline_ref | 84 | 5.9 | 0.0 | $7.4 | $540 | — |
| B2_std_med_b8 | 12 | 3.5 | -0.8 | $0.9 | $66 | ✓ |
| B3_tiered_pro_std_b8 | 14 | 3.1 | +1.08 | $0.8 | $58 | **✓ WIN** |
| B4_tiered_with_mini_b8 | 14 | 4.7 | -1.4 | $0.7 | $51 | ✗ score delta |
| B5_tiered_with_nano_b8 | 14 | 7.2 | -2.1 | $0.6 | $44 | ✗ err & delta |

## Phase C: Stability (3 runs of top 2)

| variant | mean score | std (3 runs) | mean err | accepted? |
|---|---|---|---|---|
| B3_tiered_pro_std_b8 | 78.50 | 1.12 | 3.4% | ✓ |
| B2_std_med_b8 | 77.20 | 0.91 | 3.7% | ✓ |

## Diversity Validator

- gpt-4o vs winner verdict 일치율: 91.4% (89개 item 중 81개 일치)
- 가족 편향 위험: 낮음 (≥ 90% 임계 통과)

## Winner Config

→ `winner_config.yaml` 참고. 운영 적용 권장 절차:
1. `winner_config.yaml`을 `batch-runner/grading_configs/recommended_2026-05-24.yaml`로 복사
2. 풀런 1회 실측 (220 tasks) 비용/시간 baseline과 대조
3. 통과 시 `default_gpt5pro.yaml` 대체 PR 작성

## Caveats

- 비용은 토큰 기반 추정 (실측 청구액 ±20%)
- Phase A는 매트릭스 일부만 실행 (16 variants), full factorial 아님
- gpt-5.5는 본 sweep 시점 미승인 — 추후 별도 sweep 필요
```

---

## CHANGELOG 자동 추가 형식

```markdown
## [Unreleased]

### Added
- Grading cost sweep run 2026-05-24T12:00:00Z: winner `B3_tiered_pro_std_b8`
  reduces projected full-run cost $540 → $58 (−89%), avg_score +1.08pp,
  critical_pass 1.0 preserved, err 3.1%. See
  `tasks/0523_saturday/cost_opt_results/2026-05-24T12-00-00Z/RESULTS.md`.
```

---

## Acceptance (작업 완료 기준)

1. `scripts/grading_cost_sweep.py` 존재 + executable + unit test ≥ 3개 통과
   - `--dry-run`으로 전체 plan 검증 통과
   - cost estimator vs Phase 1 실측 오차 < 30%
   - TPM cap validator 거짓 양성 0
2. `tasks/0523_saturday/grading_cost_sweep_plan.yaml` 존재 + schema valid
3. **1회 실제 sweep 완료**:
   - 누적 비용 ≤ $80
   - wall-clock ≤ 240분
   - 16 (Phase A) + 5 (Phase B) + 6 (Phase C stability) + 1 (diversity) = ~28 variants 실행
4. `RESULTS.md` + `summary.json` + `winner_config.yaml` 생성
5. CHANGELOG `[Unreleased]` 자동 추가
6. **Winner config는 unit test로 schema 검증** (`validate_grading_config(winner)` 통과)
7. 사람 개입 0회 (전 과정 자율, 단 quota 초과/cost cap exceeded 시 중단 후 사람에게 신호)

---

## Failure Handling

| 상황 | 동작 |
|---|---|
| 한 variant grading 실패 (timeout/exception) | 해당 variant 결과 = `judge_error=1.0`, 다음으로 진행 |
| 429 발생 (해당 variant 내) | retry x3 (이미 기존 grader policy), 그래도 실패 시 variant fail-marked |
| 429 동일 모델에서 3 variants 연속 | abort sweep, partial RESULTS.md 작성 |
| cost_cap 초과 예측 | sweep 즉시 중단, 지금까지 결과로 partial RESULTS.md 작성 |
| Phase A 우승자 0 | Phase B 정적 정의만 실행, dynamic augmentation skip |
| 모든 variant가 acceptance 실패 | RESULTS.md에 "No winner" 명시, 가장 cost가 낮은 *eligible* 후보를 "best-effort"로 추천 (단 critical/err 위반 시 추천 안 함) |

---

## Open Questions (작업 시작 전 결정 — 자율 진행 가능)

이전 task와 달리, 자율 실행이므로 다음 항목은 **plan YAML의 default로 박아두고 진행**한다:

| 항목 | Default | Rationale |
|---|---|---|
| Critical 기준 | `weight_gte: 4` | rubric weight 분포 측정 결과 후 자동 조정 가능 |
| Batch size 후보 | 1, 4, 8, 12 | 작은 → 큰 순. 12 초과는 truncation 위험 |
| Mini 패턴 매칭 | "executive summary", "section titled", "contains a header" | 보수적 3개 키워드만 |
| Diversity model | gpt-4o | 다른 family에서 사용 가능한 유일 옵션 |
| `tpm_guard.max_concurrent` | 5 (model 별 자동 산출) | 70% TPM 룰 적용 |
| `min_delay_ms_between_calls` | 500 | 기존 값 유지 |

---

## Out of Scope

- gpt-5.5 도입 (quota 승인 후 별도 sweep)
- Azure Batch API SKU (`globalbatch`) 도입 (별도 task)
- Inference 단계 최적화
- Rubric 자체 슬림화 (item 제거)
- 풀런(220 tasks) 직접 실행 (smoke 결과로 외삽만)

---

## Files to Create

1. `tasks/0523_saturday/grading_cost_sweep_plan.yaml` (위 명세대로)
2. `scripts/grading_cost_sweep.py` (위 pseudocode 구현체)
3. `scripts/__tests__/test_grading_cost_sweep.py` (unit tests: estimator, TPM validator, Pareto)
4. `batch-runner/core/grader_batch.py` (신규 — prompt-level batching helper; `core/grader.py`는 보호)
5. `batch-runner/grading_configs/_sweep_template.yaml` (variant render 시 기반 템플릿)

## Files to Modify

- `batch-runner/core/grader.py`: `judge_routing` 필드 처리 + `batch_size` 인자 위임 (단, batch 로직 자체는 `grader_batch.py`로 분리하여 회귀 위험 최소화)
- `batch-runner/prompts/grader_judge.md`: batch 모드 분기 (단일/배치 동일 출력 형식 보장)
- `CHANGELOG.md`: sweep 결과 자동 추가

## Files NOT to Touch

- `batch-runner/schemas/grade.schema.json` (스키마 frozen)
- `batch-runner/step8_grade.py` 외 step* 파일 (cross-pipeline coupling 금지)
- `data/grades/*` (production output 보호 — sweep 결과는 `tasks/0523_saturday/cost_opt_results/`로만)
- `.github/workflows/grade-run.yml` (별도 sweep 워크플로우는 후속 task)
