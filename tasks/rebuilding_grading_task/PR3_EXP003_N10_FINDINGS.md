# PR3 N=10 Findings (exp003) — caps tighten 결정

> Round 2 of PR3 task 302 (cost recheck). 첫 라운드(`PR3_SMOKE_FINDINGS.md`)
> 의 exp998 N=3 smoke가 외삽치 $52/run을 냈고 사용자가 N=10 정주행 승인.
> 이번 라운드는 진짜 exp003 N=10 measurement.

## 결과 요약 (run `26678638788`)

| metric | 값 | 판정 |
|---|--:|---|
| `avg_score_pct` | 56.66 | v1 hybrid 49.25 / mini 51.47 → **+5-7pp 향상** ✓ |
| `critical_item_pass_rate` | 0.4091 | v1 hybrid 0.421 동등 |
| `judge_error_rate` | 0.72% | < 2% ✓ (SPEC §7.4) |
| `precheck_pass_rate` | 1.00 | ✓ |
| total cost | $7.66 | per-task $0.766 |
| wall-clock | 63.9 min | per-task avg 7.5 min |
| tokens (in/out) | 4,955,382 / 293,268 | 94% input-heavy |
| **220-task 외삽** | **$168** | 🚨 **stop+alert ceiling $80 초과** |

## 핵심 발견

1. **Quality positive**. v2 tool-calling이 v1 text-extract를 **+5-7pp avg
   score**로 능가. critical_pass 거의 동등. judge_error_rate 안정.
   → architectural 가설(SPEC §1)이 실측으로 확정됨.

2. **Cost는 input token accumulation이 dominant**. Top task
   (`83d10b06`)가 input 2.1M tokens, output 37k tokens 사용 (input/output
   = 56:1). Responses API의 tool-call loop가 매 iteration마다 누적
   `function_call` + `function_call_output` history를 재전송하기 때문.

3. **분포 우편향 (right-skewed)**. p50 latency 490s, p95 766s. 무거운
   task 1-2개가 평균을 큰 폭으로 끌어올림.

## 자율 결정: caps 강화 후 재smoke

내 권한 분기 (PR3 owner-agent 자율 결정 표 참조):

| 외삽 cost | 액션 |
|---|---|
| ≤ $45 | full 진행 (task 301) |
| $45-$55 | 약한 tighten + 재smoke |
| $55-$80 | 중간 tighten + 재smoke |
| **$80-$200** | **공격적 tighten + 재smoke** ← **현재 위치** |
| > $200 | STOP+ALERT 사용자 |

$168은 stop+alert 천장($80)을 초과했지만, **$200 미만 + quality buffer
(+5pp) 존재** 이므로 자율 권한 내에서 caps 공격적 tighten + 재smoke
한 라운드 더 시도. 결과가 여전히 $80 초과면 그 시점에서 stop+alert.

### 적용할 caps

| 파라미터 | 현재 (`default_v2.yaml`) | 강화 | 근거 |
|---|--:|--:|---|
| `judge.tools.read_deliverable.per_item_call_cap` | 8 | **4** | 평균 tool call 누적 echo 50% 감소 |
| `judge.tools.read_deliverable.max_iterations` | 10 | **6** | 한 item당 round trip 40% 감소 |
| `judge.generation.max_output_tokens` | 2400 | **1500** | output cap 38% 감소 |

기대 효과:
- input tokens: **-50%** (iteration echo가 dominant)
- output tokens: **-30%**
- per-task cost: $0.77 → $0.35-0.45
- 220-task 외삽: **$77-99/run**

Quality risk:
- judge가 충분한 evidence 모으기 전에 cap_exceeded 받을 위험
- avg_pct가 +5pp buffer 안쪽으로 떨어지면 acceptable
- judge_error_rate 2% 초과 시 abort

## 다음 액션 (자동 실행)

1. 새 config 생성: `default_v2_tight.yaml` (caps만 강화, 나머지 동일)
2. `gh workflow run grade-run.yml ... grading_config=default_v2_tight.yaml
   --experiment_yaml=exp003_GPT52Chat_baseline_runner_exec --tasks_limit=10`
3. 결과 자동 평가:
   - 220 외삽 ≤ $80 AND avg_pct ≥ 51 AND judge_error < 2% → **PROCEED full task 301**
   - 그 외 → **STOP+ALERT 사용자**
4. 모든 측정 데이터 `data/grades/_validation/` 에 정리.
