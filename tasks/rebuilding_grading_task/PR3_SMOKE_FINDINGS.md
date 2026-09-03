# PR3 Smoke Findings — v2 first live run

> Pre-PR3 evidence from the very first live invocation of the v2 tool-calling
> grader on a 3-task smoke (`exp998_smoke_baseline_sample`, `default_v2.yaml`).

> **비용 부분은 [`PR3_COST_BUDGET.md`](./PR3_COST_BUDGET.md)가 대체한다 (302).**
> 아래 `$0.71 / 3 tasks → $52.1` 외삽은 **재현되지 않는다.** 그 $0.71은 이 실행의
> 토큰을 `gpt-5.4`의 어떤 공표 요율에 넣어도 나오지 않고, 한 규칙으로 다시 재면
> N=3은 과제당 비용을 **2.81배 낮게** 봤다. 실측값은 실행당 **$411.80 ~ $980.84**다.
> 이 문서의 나머지(과제별 토큰, 도구 사용, 실패 양상)는 그대로 유효하다.

## The run

- **Workflow run**: [`26677864500`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/26677864500)
- **Trigger**: `gh workflow run grade-run.yml --ref main -f experiment_yaml=exp998_smoke_baseline_sample -f grading_config=default_v2.yaml -f force=true -f tasks_limit=3`
- **Conclusion**: `success` (all 18 steps ✓, 0 retries)
- **Artifacts** (auto-committed on rc=0):
  - `data/grades/exp998_smoke_baseline_sample__judge_gpt-5_4__rubric_v2_tools.json`
  - `data/grades/exp998_smoke_baseline_sample__judge_gpt-5_4__rubric_v2_tools.analysis.md`

## Task 300 (gold-ceiling) — preliminary PASS criteria met

This smoke is on real model outputs, not gold deliverables. But the
smoke validates everything *task 300 actually checks first*:

| § | acceptance | observed | status |
|---|---|---|---|
| 7.1 | grader path runs end-to-end | 3/3 tasks graded, 0 grader errors | ✅ |
| schema | output validates against grade.schema.json v1.1 | file committed, 1571 LOC, no validator complaint | ✅ |
| evidence | tool-grounded, not fabricated | sample item evidence = `'"kind": "docx"'` — that is a literal `read_deliverable.inspect_structure` response field. Judge is genuinely quoting tool output. | ✅ |
| 7.4 | `judge_error_rate < 2%` | **1.19%** (1/84 judge calls) | ✅ |
| precheck | sign-aware aggregator from PR1 wired into v2 path | `precheck_pass_rate = 0.80`, `critical_fail` populated per task | ✅ |

The strict gold-ceiling check (avg_pct ≥ 90 on gold deliverables) still
needs the actual `openai/gdpval` gold-deliverable subset to be loaded
into a smoke experiment. That's the **next** PR3 task 300 step, not
something this smoke can answer.

## Task 302 (cost recheck) — ⚠️ BORDERLINE, stop+alert per user contract

```
$0.71 / 3 tasks = $0.237 per task average
220-task full extrapolation = $52.1
```

User contract clause: *"비용 결정 (PR3 task 302) per-run > $50 → 라우팅
강화 후 재추정"*.

**$52 is over the $50 threshold.** But:

1. The projection is linear from N=3. The heaviest task alone
   (`0419f1c3`, 49 judge calls, 211k tokens, 321s) drove the mean
   sharply up. A more honest read is heavy-tailed; the
   p50 task (`dfb4e0cd`) used 165k tokens and would project to
   $36/run on its own.
2. Token mix is **94% input / 6% output**. The bulk is the
   Responses-API tool-loop echo (each iteration re-sends the
   accumulated `function_call` + `function_call_output` history).
   Tightening `per_item_call_cap` (8 → 4–6) and/or
   `max_iterations` (10 → 6) should cut input tokens disproportionately.

## What I am NOT doing without user say-so

- ❌ **Not triggering full exp003 v2 grade-run** (task 301). At
  projected $52/run it crosses the user's stop+alert ceiling. The
  spec says "tighten routing + re-estimate" — but tightening risks
  quality regression with no measurement yet to ground it.
- ❌ **Not editing `default_v2.yaml`** caps yet. Same reason: no
  measurement to ground the new values.
- ❌ **Not flipping `grade-run.yml` default** to v2.

## Recommended next decisions (user pick one)

**Option A — strict contract: tighten then re-smoke.**
Bump `default_v2.yaml`:
- `per_item_call_cap`: 8 → 5
- `max_iterations`: 10 → 6
- `max_output_tokens`: 2400 → 1500
Re-trigger the same 3-task smoke. If projected cost drops below $40 AND
`judge_error_rate` stays under 2% AND `critical_item_pass_rate` stays
stable, then PROCEED to exp003 full.

**Option B — larger smoke first.**
Trigger the *same* `default_v2.yaml` on `exp998_smoke_baseline_sample`
with `tasks_limit=10` (~$2.4, ~30 min). N=3 → N=10 cuts the projection
variance by ~3×; if the larger sample says $35/run instead of $52, the
contract trigger was a small-sample artifact and the original caps
stand.

**Option C — accept the borderline + run exp003 full.**
$52 is 4% over the threshold; the user contract phrasing is "tighten
+ re-estimate", not "block". Decide that one $52 burn is worth getting
the exp003 head-to-head (task 301) and full-distribution cost data
(task 302 strict) in a single shot.

I am stopping here per the contract clause. Tell me A / B / C (or
your own) and I will execute.

## Notable side-observations (for the PR3 report)

- `critical_item_pass_rate = 0.0` in the wow block reads alarmingly
  low at a glance — but with only 3 tasks of which one has
  `critical_fail = True`, the aggregator is correctly computing
  "how many critical items pass across all critical items in this
  sample." Not actionable at N=3. Needs the larger sample to be
  diagnostic.
- The heaviest task (`0419f1c3`) is a 52-rubric-item .docx task that
  used 49 of its 52 items via tool calls. The routing/cap defaults
  are giving the judge plenty of rope; whether it's *productively*
  using it is what the tightening experiment would test.
- All judge evidence quotes inspected so far are real tool-response
  fragments. **No fabrication detected.** This is the single biggest
  qualitative signal that the v2 architecture is doing what SPEC §1
  said it should.
