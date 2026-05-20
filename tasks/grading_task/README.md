# Grading Task — 명세 패키지

OpenAI가 evals.openai.com 호스팅 채점을 종료하고 GDPval v2 rubric을
오픈소스화([openai/gdpval](https://huggingface.co/datasets/openai/gdpval))함에
따라, gdpval-realworks 자체 채점 파이프라인을 신설한다.

## 한 줄 컨셉

> **가중 체크리스트 rubric을 1차 기준으로, 결정 가능한 항목은 코드 pre-check,
> 판단 항목은 LLM-judge(`gpt-5.4-pro`)가 evidence quote와 함께 0~1 partial로
> 채점. 결과는 정규화된 % + 가중 합산 + WOW 메트릭으로 dashboard에 노출.**

## Inference와 분리된 별도 파이프라인

- Inference (`batch-run.yml`)와 cadence/비용/secrets/timeout이 다르므로
  분리. Grading은 별도 `grade-run.yml`로 운영.
- Judge 모델 교체·rubric 업데이트 시 inference 재실행 없이 채점만 재가동.

## 명세 파일 인덱스

| # | 파일 | 대상 산출물 | PR |
|---|---|---|---|
| 000 | [000-OVERVIEW.md](000-OVERVIEW.md) | 컨셉 합의문 + 아키텍처 | — |
| 001 | [001-rubric-loader.md](001-rubric-loader.md) | `batch-runner/core/rubric_loader.py` | #1 |
| 002 | [002-grader-engine.md](002-grader-engine.md) | `batch-runner/core/grader.py` | #1 |
| 003 | [003-judge-prompt.md](003-judge-prompt.md) | `batch-runner/prompts/grader_judge.md` | #1 |
| 004 | [004-step8-cli.md](004-step8-cli.md) | `batch-runner/step8_grade.py` | #1 |
| 005 | [005-grade-run-workflow.md](005-grade-run-workflow.md) | `.github/workflows/grade-run.yml` | #1 |
| 006 | [006-grading-config-spec.md](006-grading-config-spec.md) | `batch-runner/grading_configs/*.yaml` | #1 |
| 007 | [007-grade-schema.md](007-grade-schema.md) | `data/grades/*.json` schema v1.0 | #1 |
| 008 | [008-narrative-integration.md](008-narrative-integration.md) | `core/narrative_analyzer.py`, `step6_report.py` | #2 |
| 009 | [009-dashboard-wow-metrics.md](009-dashboard-wow-metrics.md) | `scripts/aggregate-grades.mjs`, `src/pages/*`, `src/components/*` | #2 |
| 010 | [010-evals-submitter-removal.md](010-evals-submitter-removal.md) | `core/evals_submitter.py` 삭제 | #1 |
| 011 | [011-grading-agent-persona.md](011-grading-agent-persona.md) | `.github/agents/grading-engineer.md` | #1 |
| 012 | [012-rollout-plan.md](012-rollout-plan.md) | 검증 단계 + 운영 절차 | — |

## PR 분할 (확정)

- **PR #1 (Phase A core)** — 001, 002, 003, 004, 005, 006, 007, 010, 011
  - smoke 검증: `exp998_smoke_baseline_sample` (3 tasks)
  - 통과 시 exp025 (220 tasks) 실 채점
- **PR #2 (Phase A wow)** — 008, 009 — narrative 통합 + WOW dashboard
- **PR #3 (Phase B, 추후)** — cross-family calibration, human pairwise,
  automatic `workflow_run` chain

## 핵심 사실 (모든 명세의 전제)

다음은 [openai/gdpval](https://huggingface.co/datasets/openai/gdpval) v2
parquet 분석으로 확정된 사실이다. 명세 작성 시 이 가정을 깨지 말 것.

1. **220 / 220 tasks have `rubric_json`** — rubric은 모든 태스크에 존재
2. **0 / 220 tasks have `deliverable_files` (gold)** — gold는 비어있음.
   채점은 rubric만으로 수행 가능하도록 rubric 자체가 self-contained하게
   설계됨 (예: "Excel workbook basename = 'Sample'", "worksheet named
   exactly 'Sample Size Calculation'" 등 deliverable만 보고 결정 가능)
3. **0 / 220 rubric items have `required=true`** — `critical_fail` 로직은
   현재 dataset에서 발화하지 않음. 단순 가중 합산만 적용. 단, 미래 버전에서
   `required=true`가 등장할 수 있으므로 처리 로직은 schema에 유지.
4. Rubric item 분포 (sample): 평균 ~30 items/task, 최대 60 items (163점),
   최소 ~15 items. 합산 만점은 태스크마다 다르므로 **% 정규화 필수**.
5. OpenAI 호스팅이 주던 더미 grade JSON은 **task-level binary × 3
   graders** 만 노출 (rubric item별 detail 없음). 우리는 item-level partial
   채점으로 10배 풍부한 데이터를 노출 — 이게 WOW의 본질.

## Quick start (개발자용)

```bash
# 1차 검증
cd batch-runner
python step8_grade.py exp998_smoke_baseline_sample \
  --config grading_configs/default_gpt5pro.yaml

# 결과 확인
cat ../data/grades/exp998_smoke_baseline_sample__gpt-5.4-pro__<rubric_sha>__v1.json | jq .summary

# 실 채점
python step8_grade.py exp025_GPT54_high_postfix \
  --config grading_configs/default_gpt5pro.yaml
```
