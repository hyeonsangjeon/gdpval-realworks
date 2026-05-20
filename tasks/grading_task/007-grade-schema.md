# 007 — `data/grades/*.json` Schema v1.0

## 목적

Grading 결과 JSON의 단일 source-of-truth 스키마. Dashboard, NarrativeAnalyzer,
aggregate-grades.mjs 모두 이 스키마를 신뢰.

## 파일명 규약 (Q7 확정)

```
data/grades/<exp_id>__<judge_slug>__<rubric_short_sha>__<prompt_v>.json
```

예시:
```
data/grades/exp025_GPT54_high_postfix__gpt-5_4-pro__11e7900__v1.json
data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json
```

규칙:
- `judge_slug`: `judge.model`을 `.` → `_`로 치환
- `rubric_short_sha`: HF dataset commit SHA의 첫 7자
- `prompt_v`: prompt 템플릿 frontmatter의 `prompt_version` 문자열

## 전체 스키마 (JSON Schema-ish)

```json
{
  "schema_version": "1.0",
  
  "experiment_id": "exp025_GPT54_high_postfix",
  "experiment_yaml_name": "exp025_GPT54_high_postfix",
  "inference_model": "gpt-5.4",
  "inference_completed_at": "2026-05-19T07:02:37Z",
  
  "judge": {
    "provider": "azure_openai",
    "api": "responses",
    "model": "gpt-5.4-pro",
    "deployment": "gpt-5.4-pro",
    "api_version": "2025-04-01-preview",
    "reasoning_effort": "high",
    "temperature": 0,
    "seed": 42,
    "config_name": "default_gpt5pro",
    "config_hash": "ab12cd34ef567890"
  },
  
  "rubric": {
    "source": "huggingface",
    "repo_id": "openai/gdpval",
    "revision": "main",
    "commit_sha": "11e7900cdcac61bc4daf59e65feb238acda98fbf",
    "short_sha": "11e7900"
  },
  
  "prompt": {
    "template": "prompts/grader_judge.md",
    "version": "v1"
  },
  
  "graded_at": "2026-05-20T12:34:56Z",
  "graded_by": "step8_grade.py",
  "graded_by_version": "0.1.0",
  
  "tasks": [
    {
      "task_id": "83d10b06-26d1-4636-a32c-23f92c57f30b",
      "sector": "Professional, Scientific, and Technical Services",
      "occupation": "Accountants and Auditors",
      
      "items": [
        {
          "rubric_item_id": "1d43f1eb-4011-47ac-8ad...",
          "criterion": "The submitted deliverable is an Excel workbook file whose basename is 'Sample'...",
          "max_score": 2,
          "awarded_score": 2.0,
          "verdict": "pass",
          "decided_by": "precheck",
          "required": null,
          "evidence": "Filename observed: 'Sample.xlsx'",
          "judge_confidence": null,
          "judge_latency_ms": null,
          "precheck_pattern_id": "file_exists_or_name"
        },
        {
          "rubric_item_id": "...",
          "criterion": "The audit conclusion correctly identifies the population sampling deficiency",
          "max_score": 3,
          "awarded_score": 2.0,
          "verdict": "partial",
          "decided_by": "judge",
          "required": null,
          "evidence": "Stated 'sampling rate of 22 of 100 records'; misses formal name of the deficiency",
          "judge_confidence": 0.82,
          "judge_latency_ms": 4321.5,
          "precheck_pattern_id": null,
          "judge_raw_response": null
        }
      ],
      
      "total_awarded": 42.5,
      "total_max": 63,
      "pct": 67.46,
      "critical_fail": false,
      "gold_referenced": false,
      
      "judge_call_count": 21,
      "precheck_count": 17,
      "judge_total_latency_ms": 89234.1,
      "judge_input_tokens": 24123,
      "judge_output_tokens": 6210,
      
      "error": null,
      "graded_at": "2026-05-20T12:34:56Z"
    }
  ],
  
  "summary": {
    "total_tasks": 220,
    "graded_tasks": 219,
    "error_tasks": 1,
    
    "openai_compat": {
      "avg_score_pct": 67.46,
      "ci_pct": 4.2,
      "perfect_count": 88,
      "zero_count": 12,
      "partial_count": 119,
      "inconsistent_count": 0
    },
    
    "wow": {
      "rubric_item_coverage_avg": 0.78,
      "critical_item_pass_rate": 0.71,
      "precheck_pass_rate": 0.92,
      "judge_pass_rate": 0.64,
      "judge_error_rate": 0.003,
      
      "by_sector": {
        "Information": {
          "task_count": 30,
          "avg_pct": 71.2,
          "critical_item_pass_rate": 0.75,
          "precheck_pass_rate": 0.91,
          "judge_pass_rate": 0.68
        }
      },
      
      "by_rubric_category": {
        "file_structure": {"items": 1456, "pass_rate": 0.94},
        "content_quality": {"items": 2103, "pass_rate": 0.61},
        "domain_accuracy": {"items": 1287, "pass_rate": 0.58}
      },
      
      "score_density_histogram": [
        {"bucket": "0-10%", "count": 12},
        {"bucket": "10-20%", "count": 8},
        ...
      ],
      
      "rubric_severity_curve": [
        {"weight": 1, "n_items": 4521, "pass_rate": 0.86},
        {"weight": 2, "n_items": 3812, "pass_rate": 0.79},
        {"weight": 3, "n_items": 1290, "pass_rate": 0.71},
        ...
      ]
    },
    
    "cost": {
      "total_judge_calls": 4567,
      "total_input_tokens": 13420000,
      "total_output_tokens": 3650000,
      "estimated_cost_usd": 73.45,
      "total_judge_latency_sec": 14523.1
    }
  }
}
```

## 핵심 필드 의미 (i 풍선 사용)

| 필드 | 의미 | i 풍선 텍스트 (Q3) |
|---|---|---|
| `summary.openai_compat.avg_score_pct` | task별 pct의 평균 | "Task별 (총 가중점수 획득률) 의 산술 평균" |
| `summary.openai_compat.ci_pct` | 95% CI 반경 | "Average Score의 95% 신뢰구간 반경 (binomial CI)" |
| `summary.openai_compat.perfect_count` | pct ≥ 99 인 task 수 | "전체 rubric 항목 모두 통과한 태스크 수" |
| `summary.openai_compat.zero_count` | pct ≤ 1 인 task 수 | "전체 rubric 항목 모두 실패한 태스크 수" |
| `summary.wow.rubric_item_coverage_avg` | (통과 item) / (전체 item) | "OpenAI의 task-level binary가 아닌, item-level 통과율" |
| `summary.wow.critical_item_pass_rate` | weight ≥ 3 항목 통과율 | "가중치 3점 이상의 핵심 요구사항 통과율" |
| `summary.wow.precheck_pass_rate` vs `judge_pass_rate` | precheck vs judge 항목 통과율 | "결정론적 검증 vs LLM 판단의 성공률 분리" |

## Validation (JSON Schema)

PR #1에 다음 파일 추가:
- `batch-runner/schemas/grade.schema.json` — JSON Schema draft 2020-12
- Step8이 저장 직전에 `jsonschema.validate()` 호출
- aggregate-grades.mjs도 동일 schema로 검증

## Backward compat (OpenAI 더미 → 우리 v1.0)

기존 [data/grades/dummy_gpt5_baseline.json](../../data/grades/dummy_gpt5_baseline.json)
는 `_meta.is_dummy=true`로 식별. Dashboard는 두 형식을 모두 읽되:
- `is_dummy=true` 또는 `schema_version`이 없는 파일 → "OpenAI legacy
  format" 배지
- `schema_version="1.0"` → 풀 WOW 시각화

## Schema 진화 정책

- `schema_version`을 major.minor로 관리 (semver)
- minor bump (1.0 → 1.1): 추가 필드만, 기존 필드 의미 불변
- major bump (1.0 → 2.0): breaking change. dashboard 마이그레이션 동반
  필요
- Schema 변경은 별도 amendment 문서 + 사용자 승인 필요

## 테스트 (`tests/test_grade_schema.py`)

- `test_minimal_valid_grade_passes_schema`
- `test_missing_required_field_fails`
- `test_unknown_verdict_fails`
- `test_pct_must_be_0_to_100`
- `test_actual_smoke_output_passes_schema` (002 통합 테스트)

## 의존성

- 002 (Grader가 이 schema 산출)
- 004 (step8이 저장 + validate)
- 009 (dashboard aggregate가 이 schema 소비)
- 008 (NarrativeAnalyzer가 이 schema 소비)
