# TASK_GRADE_COST_OPTIMIZATION — judge 비용/시간 압축 (smoke 142m → 30m 이내, 풀런 $540 → $80~120)

## TL;DR

exp998 smoke run 실측 기준 채점 한 번에 **84 judge calls / 142분 / 22.7만 토큰**이 드는 상태. 220-task 풀런 외삽 시 **~$540/회**로 반복적인 benchmark 실행이 운영상 비현실적이다.

원인: (1) rubric item 1개 = judge 호출 1회, (2) `max_concurrent: 1` 직렬 실행, (3) `reasoning_effort: high` + `gpt-5.4-pro` 조합으로 호출당 100s+, (4) precheck 비중이 10/94 = 10.6%로 낮음.

본 task는 정확도 회귀 ±2pt 이내 + `critical_item_pass_rate` 1.0 보존을 제약으로, **풀런 비용 ~6× 압축**과 **wall-clock ~5× 단축**을 목표로 한다.

---

## Background & Measurement

### 실측 (exp998_smoke_baseline_sample, 2026-05-23)

| | Task 1 | Task 2 | Task 3 | 합계 |
|---|---|---|---|---|
| rubric items | 16 | 26 | 52 | 94 |
| judge items | 15 | 20 | 49 | **84** |
| precheck items | 1 | 6 | 3 | 10 |
| judge latency 합 | 1,572s | 1,334s | 5,625s | **8,531s (142m)** |
| 입력/출력 tok | - | - | - | 137,756 / 89,263 |

### 비용 추정 (gpt-5.4-pro, $15/$60 per 1M tok 가정)
- smoke 1회: **~$7.4**
- 220-task 풀런 외삽 (×73): **~$540/회**
- 현재 per-run 비용으로는 반복 benchmark 실행이 제한됨

### 운영 제약 (확정)
- Azure OpenAI **PAYG (Global Standard)** 가정. quota 추가 신청 진행 중 (gpt-5.5 = 300 kTPM).
- `Judge ≠ Inference` 무결성 규칙 유지 (selection bias 방지).
- temperature=0 / seed 고정 / 4-tuple 캐시 키 reproducibility 비-협상.

---

## Goal

| 지표 | 현재 | 목표 |
|---|---|---|
| 풀런 비용 (220 tasks) | ~$540 | **≤ $120** |
| 풀런 wall-clock | ~52h (외삽) | **≤ 6h** |
| judge calls per task | ~28 | **≤ 10** |
| precheck 비중 | 10.6% | **≥ 30%** |
| avg_score_pct 변화 | base | **±2pt 이내** |
| critical_item_pass_rate | 1.0 | **1.0 유지** |

---

## Architecture: Tiered Judging (정정안)

> **이전 제안에서 "gpt-5-mini를 main judge로"는 과한 다운그레이드였음. 본 task는 mini를 main이 아닌 *Extended Precheck* 역할로 재배치.**

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 0: PRECHECK (deterministic, regex/구조)                  │
│   - file_exists, file_extension, worksheet_name,             │
│     page_count, count_check                                  │
│   - 추가: header_present, regex_match, row_count_range,      │
│     date_format, link_presence, slide_count                  │
│   목표 비중: 30%+                                            │
└────────────────┬────────────────────────────────────────────┘
                 │ (regex 매칭 실패 시 위임)
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ Tier 1: EXTENDED PRECHECK via gpt-5-mini                     │
│   - fuzzy 패턴 (executive summary 존재 여부, 의미 있는        │
│     섹션 헤더 인식 등)                                         │
│   - 단순 binary verdict + 짧은 evidence 추출만                │
│   - max_output_tokens: 400, reasoning_effort: minimal        │
│   목표 비중: 15~20%                                          │
└────────────────┬────────────────────────────────────────────┘
                 │ (item의 reasoning complexity 가 높으면)
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ Tier 2: STANDARD JUDGE — gpt-5.5 (또는 gpt-5.4 standard)     │
│   - 대다수 weight 1~3 reasoning 항목                          │
│   - reasoning_effort: medium                                 │
│   목표 비중: 40~50%                                          │
└────────────────┬────────────────────────────────────────────┘
                 │ (item.weight >= 4 또는 critical 플래그)
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ Tier 3: PRO JUDGE — gpt-5.4-pro (또는 gpt-5.5-pro)           │
│   - critical 항목 전용                                        │
│   - reasoning_effort: high                                   │
│   목표 비중: 10~15%                                          │
└─────────────────────────────────────────────────────────────┘
```

### 왜 mini를 "main judge"로 안 쓰는가
- GDPVal rubric에는 "expert weighing of trade-offs", "domain-specific correctness" 같은 reasoning-heavy 항목 다수.
- mini는 짧고 명확한 binary check (precheck 대체)는 가능하지만, **다단 추론과 도메인 판단에선 일관성 손상** → calibration 깨짐.
- 대신 mini를 **regex로는 못 잡는 fuzzy precheck 패턴**(예: "executive summary 섹션 존재")에 배치하여 **Tier 2 호출 자체를 줄임**.

---

## Levers (effort 순)

### L1. `reasoning_effort: high → medium` (5분, 즉시 효과)

- **파일**: `batch-runner/grading_configs/default_gpt5pro.yaml`
- **변경**: `judge.reasoning.effort: high` → `medium`
- **예상 효과**: 호출당 latency −30~50%, output tokens −20~40%
- **위험**: 일부 reasoning-heavy 항목 verdict 흔들림 → critical만 high 유지하는 splittable config 필요할 수 있음.
- **검증**: exp998 재실행, 항목별 verdict diff 측정. avg_score_pct 변화 ±2pt 이내, critical_item_pass_rate 1.0 보존.

### L2. `deliverable_extract_max_chars: 4000 → 1500~2000` (5분)

- **파일**: 동일 YAML
- **이유**: 84 calls × 4000 chars = 336K chars/run 입력 → 절반으로 줄여도 verdict 유지 가능성 높음 (judge가 deliverable 전체를 다 읽지 않음).
- **위험**: 일부 항목에서 evidence 누락 → "no evidence" 처리. 단계적으로 3000→2000→1500 시험.

### L3. Precheck 패턴 확장 (반나절)

- **파일**: `batch-runner/core/grader.py` (`_classify`, `_run_precheck`, 신규 precheck 메서드들)
- **현재 패턴**: `file_exists_or_name`, `file_extension`, `worksheet_name`, `count_check`, `page_count` (5개)
- **추가 후보**:
  - `header_present`: rubric criterion이 "include a section titled X" / "with header Y" 형태일 때
  - `regex_match`: "must contain Z" 패턴 + 단순 substring/regex
  - `row_count_range`: "spreadsheet has between N and M rows"
  - `date_format_iso`: "dates in YYYY-MM-DD format"
  - `link_present`: "contains a hyperlink to X"
  - `slide_count`: "presentation has at most N slides"
- **목표**: precheck 비중 10.6% → **30%+**. 매 항목 추가는 PRECHECK_PATTERNS 정규식 + 단위 테스트 필수.

### L4. Item batching (1~2일)

- **파일**: `batch-runner/prompts/grader_judge.md`, `batch-runner/core/grader.py`
- **변경**: 현재 1 item = 1 call → **1 task의 N items를 1 call로 묶어서 JSON 배열 verdict 요청**
- **프롬프트 설계**:
  - System: rubric items list + deliverable + "return JSON array, one verdict per item"
  - Structured output (JSON Schema strict mode) 강제
  - max_output_tokens: 4096 → 8192 (배치 출력 길이 증가 대응)
- **호출 수**: 84 → 3~5 calls/task. 풀런 호출 수 ~6,000 → ~500.
- **위험**:
  - 출력 길이 증가 → reasoning_token 폭증 가능. 한 batch에 너무 많은 item 묶지 말 것 (max 8~10 권장).
  - 한 batch의 일부 item 출력이 truncate되면 batch 전체 재시도 필요 → fine-grained retry 로직 필요.
  - judge가 item 간 "echo" 응답 (이전 verdict에 영향 받기) → 항목 독립 평가 보장 프롬프트 필요.
- **검증**: 동일 task를 단일/배치로 채점한 verdict 일치율 ≥ 95%.

### L5. Tiered judge routing (L4 완료 후, 2~3일)

- **파일**: `default_gpt5pro.yaml`, `core/grader.py`, 새 `grading_configs/tiered_default.yaml`
- **신규 config 필드**:
  ```yaml
  judge_routing:
    tier_mini:
      model: "gpt-5-mini"
      deployment: "gpt-5-mini"
      reasoning_effort: "minimal"
      max_output_tokens: 400
      criterion_match:
        - "executive summary"
        - "section titled"
        - "header"
        # 패턴 매칭 후 precheck 실패 시에만 사용
    tier_standard:
      model: "gpt-5.5"             # 신청 진행 중
      deployment: "gpt-5.5"
      reasoning_effort: "medium"
      max_output_tokens: 4096
    tier_pro:
      model: "gpt-5.4-pro"
      deployment: "gpt-5.4-pro"
      reasoning_effort: "high"
      max_output_tokens: 4096
      route_when:
        weight_gte: 4
        # or item.required == true
  ```
- **검증**:
  - critical_item_pass_rate 1.0 유지 (가장 중요)
  - pro vs standard 동일 항목 verdict 일치율 측정 (90% 이상이면 standard 채택, 아니면 tier 재정의)

### L6. Concurrency 상향 (L1~L5 결과 안정화 후, 5분)

- **파일**: `default_gpt5pro.yaml`
- **변경**: `tpm_guard.max_concurrent: 1 → 5` (1차) → `10` (2차)
- **선행조건**:
  - gpt-5.5 300 kTPM quota 승인 완료
  - 429 retry 정책 동작 확인 (현재 max_retries=3, exponential backoff)
- **효과**: **wall-clock만 단축** (5~10× ↓), 비용 영향 없음.
- **위험**: PTU 한도 충돌 시 전체 fail. 단계적 적용.

### L7. Response cache (smoke/dev only, 옵션)

- **파일**: `core/grader.py` (캐시 데코레이터 추가)
- **키**: `(rubric_item_id, deliverable_sha256, judge_model, prompt_v)`
- **저장소**: `batch-runner/.judge_cache/` (gitignore)
- **활성화**: `--cache-enabled` 플래그로 opt-in. prod run은 cache miss 전제 (reproducibility).
- **효과**: 동일 deliverable 반복 채점 0원 (CI 회귀 테스트 등).

---

## Phased Execution Plan

각 단계는 **이전 단계 검증 통과 후에만** 다음으로 진행. 한 PR에 묶지 말 것 (회귀 추적 불가).

### Phase 1 (당일, 30분)
- **변경**: L1 (effort medium) + L2 (extract 1500 chars)
- **검증**: exp998 재실행 → avg_score 변화 ±2pt, critical 1.0 보존, judge_error_rate ≤ 7%
- **예상**: wall-clock 142m → ~80m, smoke 비용 $7.4 → ~$4

### Phase 2 (반나절)
- **변경**: L3 (precheck 5개 패턴 추가)
- **검증**: precheck 비중 ≥ 25%, score 회귀 없음
- **예상**: judge calls 84 → ~60

### Phase 3 (1~2일)
- **변경**: L4 (item batching, 단일 모델 유지)
- **검증**: 단일/배치 verdict 일치율 ≥ 95%
- **예상**: judge calls 60 → ~15, smoke 비용 ~$4 → ~$1.5

### Phase 4 (2~3일, gpt-5.5 quota 승인 후)
- **변경**: L5 (tiered routing)
- **검증**: critical 1.0, 전체 score ±2pt, 풀런 비용 시뮬레이션 ≤ $120
- **예상**: 풀런 비용 ~$540 → ~$100

### Phase 5 (단발)
- **변경**: L6 (concurrency 5 → 10)
- **검증**: 429 발생률 < 1%, quota 사용량 < 80%
- **예상**: 풀런 wall-clock 52h → ~6h

### Phase 6 (옵션)
- L7 캐시 도입. dev 워크플로 가속용.

---

## Acceptance Criteria

Phase 1~5 모두 통과 후:

1. exp998_smoke_baseline_sample 재실행:
   - judge_calls ≤ 15
   - total_judge_latency_sec ≤ 1800 (30m)
   - total_input_tokens ≤ 60,000
   - total_output_tokens ≤ 35,000
   - judge_error_rate ≤ 5%
2. 풀런 비용 시뮬레이션 ≤ $120 (220 tasks 외삽)
3. avg_score_pct 변화 ±2pt 이내 (baseline 77.83% → 75.83~79.83%)
4. critical_item_pass_rate = 1.0 유지
5. precheck_pass_rate ≥ 80% (현재 수준 유지)
6. 풀런 wall-clock ≤ 6h (concurrency 10 가정)
7. `data/grades/<exp_id>__*.json` 스키마 v1.0 준수 (변경 금지)
8. CHANGELOG.md `[Unreleased]`에 Phase별 엔트리 기록

---

## Risks

| 위험 | 영향 | 완화 |
|---|---|---|
| Batching 시 verdict 흔들림 | calibration 손상 | Phase 3 verdict 일치율 < 95% 시 batch size 축소 또는 롤백 |
| mini가 fuzzy precheck에서도 부적합 | error_rate 증가 | mini 적용 항목을 보수적으로 (3~5개 패턴만) 시작 |
| gpt-5.5 quota 미승인 / 지연 | Phase 4 차단 | gpt-5.4 standard로 대체 가능 (조금 비싼 standard tier) |
| Concurrency 5+에서 429 폭증 | run 중단 | retry+backoff 이미 존재. 안 되면 concurrency 3으로 후퇴 |
| Precheck 정규식 false positive | 점수 조작 | 신규 precheck 패턴마다 unit test 필수 |

---

## Out of Scope

- Inference 단계 비용 최적화 (별도 task)
- Judge 모델 교체 (gpt-5.4-pro/5.5 외 family) — Phase 4 이후 별도 evaluation
- Cross-pipeline coupling (step1~step7 수정 금지)
- 외부 hosted grading 도입

---

## Files Touched (예상)

- `batch-runner/grading_configs/default_gpt5pro.yaml` (L1, L2, L6)
- `batch-runner/grading_configs/tiered_default.yaml` (L5, 신규)
- `batch-runner/core/grader.py` (L3, L4, L5, L7)
- `batch-runner/prompts/grader_judge.md` (L4)
- `batch-runner/schemas/grade.schema.json` (변경 없음 — 강제)
- `CHANGELOG.md` (각 Phase 기록)

---

## Verification Commands

```bash
# Phase 1 검증
cd batch-runner
python step8_grade.py --exp exp998_smoke_baseline_sample --limit 3
python -c "
import json
d = json.load(open('../data/grades/exp998_smoke_baseline_sample__*.json'.replace('*','...')))
c = d['summary_v1']['cost']; w = d['summary_v1']['wow']
print(f\"calls={c['total_judge_calls']}, latency={c['total_judge_latency_sec']/60:.1f}m\")
print(f\"err={w['judge_error_rate']*100:.1f}%, critical={w['critical_item_pass_rate']*100:.1f}%\")
"

# Phase 3 일치율 측정
python scripts/grading_batch_vs_single.py --tasks 3  # 신규 스크립트 필요
```

---

## Open Questions (작업 전 결정 필요)

1. **gpt-5.5 quota 승인 ETA?** 미승인 시 Phase 4를 gpt-5.4 standard로 대체할지.
2. **Batching size**: 한 call에 묶을 최대 item 수 — 8? 10? 15? (출력 truncation 위험과 호출수 trade-off)
3. **Critical 판정 기준**: 현재 `weight≥3`이 적절한지, rubric의 weight 분포 먼저 측정 필요. 측정 스크립트:
   ```bash
   python -c "
   from batch-runner.core.rubric_loader import load_rubric
   r = load_rubric()
   from collections import Counter
   print(Counter(item.weight for task in r for item in task.rubric_items))
   "
   ```
4. **Smoke의 의미 재정의**: smoke run을 mini-only로 돌려 0.5분 / $0.1 수준으로 만들지, 아니면 정식 sampling으로 유지할지.
