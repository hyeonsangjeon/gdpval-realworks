# 008 — NarrativeAnalyzer + step6_report에 Grade 통합 (N1, N2, N3)

> **PR 분할**: PR #2 (Phase A wow). PR #1엔 포함 X.

## 목적

`data/grades/<exp_id>__...json` (007 schema)를 NarrativeAnalyzer의 추가
input으로 받아, narrative summary에 rubric-based 채점 결과를 자연어로
서술. Dashboard의 narrative 섹션이 풍부해짐.

## 변경 파일

| 파일 | 변경 |
|---|---|
| `batch-runner/core/narrative_analyzer.py` | `analyze()` 시그니처 + prompt 생성 로직 |
| `batch-runner/step6_report.py` | grade 파일 로드 + analyzer 호출 시 전달 |

## N1 — analyze() 시그니처 변경

**기존**:
```python
def analyze(
    self,
    data: dict,
    summary: dict,
    sector_breakdown: list[dict],
    task_results: list[dict],
    error_tasks: list[dict],
) -> NarrativeResult: ...
```

**변경 후**:
```python
def analyze(
    self,
    data: dict,
    summary: dict,
    sector_breakdown: list[dict],
    task_results: list[dict],
    error_tasks: list[dict],
    grade: dict | None = None,   # ← 신규: data/grades/*.json 로드 결과
) -> NarrativeResult: ...
```

기본값 `None` — backward compat 유지. PR #2 머지 후에도 grade 파일 없는
실험은 기존대로 동작.

## N2 — 프롬프트 가드 조건부화

### 기존 (narrative_analyzer.py L186 + step6_report.py L240)

```
- Grading scores do NOT exist yet. Do NOT mention or predict grades.
```

### 변경

```python
def _build_grading_guard_clause(grade: dict | None) -> str:
    if grade is None:
        return (
            "- Grading scores do NOT exist yet. Do NOT mention or predict "
            "grades. Focus only on execution metrics and Self-QA scores."
        )
    # grade is present — instruct narrative to use it
    return f"""
- Grading scores ARE available (see GRADING RESULTS section below).
- Source: rubric-based LLM-judge ({grade['judge']['model']}, reasoning_effort={grade['judge']['reasoning_effort']}).
- This is NOT human expert evaluation — it is an automated LLM-judge
  score against open-sourced GDPval rubrics ({grade['rubric']['repo_id']}
  @ {grade['rubric']['short_sha']}).
- Refer to scores as "LLM-judge grade" or "rubric-based score", never
  "human evaluation" or "official OpenAI grade".
- Highlight: weakest sector, strongest sector, critical_item_pass_rate,
  precheck vs judge breakdown.
"""
```

이걸 Call 1 & Call 2 prompt 양쪽에 주입.

## N3 — Rubric 출처 + 모델 안내 명시 (사용자 요청)

`overview` 섹션의 narrative는 다음 문구를 의무 포함:

> The grading shown is automated via LLM-judge ({{judge.model}}) against
> open-sourced GDPval rubrics ([openai/gdpval](https://huggingface.co/datasets/openai/gdpval),
> commit `{{rubric.short_sha}}`). This is NOT an official OpenAI human
> evaluation — OpenAI ended hosted grading and open-sourced their rubrics
> for community self-evaluation.

prompt에 다음 instruction 추가:
```
- In the "overview" field, you MUST include exactly one paragraph
  explaining that grading is automated LLM-judge based, citing the judge
  model and the rubric source/commit. Use the verbatim format above.
```

## step6_report.py 변경

`_generate_narrative()` 또는 NarrativeAnalyzer 호출 직전:

```python
def _load_grade_for_experiment(exp_id: str) -> dict | None:
    """Load the most recent grade JSON for an experiment.
    Returns None if no grade file exists yet (Grading In Progress).
    """
    candidates = sorted(
        Path("data/grades").glob(f"{exp_id}__*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None
    
    # Skip dummy files
    for path in candidates:
        with open(path) as f:
            grade = json.load(f)
        if grade.get("_meta", {}).get("is_dummy"):
            continue
        if grade.get("schema_version") == "1.0":
            return grade
    return None
```

호출:
```python
grade = _load_grade_for_experiment(exp_id)
result = analyzer.analyze(
    data, summary, sector_breakdown, task_results, error_tasks,
    grade=grade,  # may be None
)
```

## GRADING RESULTS prompt 섹션 (grade is not None 일 때만)

Call 2 (deep analysis)의 user_prompt 끝에 다음 섹션 주입:

```
## GRADING RESULTS (LLM-judge, rubric-based)

Judge: {{judge.model}} (reasoning_effort={{judge.reasoning_effort}}, temperature={{judge.temperature}})
Rubric source: {{rubric.repo_id}} @ {{rubric.short_sha}}

Overall:
  - Average score: {{summary.openai_compat.avg_score_pct}}% (± {{ci_pct}}%)
  - Perfect tasks (100%): {{perfect_count}}/{{total_tasks}}
  - Zero tasks (0%): {{zero_count}}/{{total_tasks}}
  - Critical item pass rate: {{wow.critical_item_pass_rate}}
  - Precheck pass rate: {{wow.precheck_pass_rate}}
  - Judge pass rate: {{wow.judge_pass_rate}}

By sector (top 3 weakest):
  {{sector_breakdown_weakest_3_with_pct_and_pass_rates}}

By sector (top 3 strongest):
  {{sector_breakdown_strongest_3_with_pct_and_pass_rates}}

Failure pattern hint (precheck vs judge):
  - Precheck failures dominate: deliverable structure issues (file naming, format)
  - Judge failures dominate: content quality / domain reasoning issues
  - Mixed: see by_rubric_category
```

NarrativeAnalyzer의 Call 2 input 토큰이 늘어남 (~+1500 tokens) — gpt-5.4-pro
context window 충분.

## NarrativeResult 변경

```python
@dataclass
class NarrativeResult:
    overview: str = ""
    quality_analysis: str = ""
    failure_patterns: str = ""
    recommendations: str = ""
    call_1_latency_ms: float = 0.0
    call_2_latency_ms: float = 0.0
    total_tokens: dict = field(default_factory=lambda: {"input": 0, "output": 0})
    
    # 신규 — narrative가 grade를 봤는지 박제
    grading_referenced: bool = False
    grade_source: dict | None = None  # {model, rubric_sha, prompt_v, graded_at}
```

`report_data.json`에도 동일 필드 추가.

## 테스트 (`tests/test_narrative_grade_integration.py`)

- `test_analyze_without_grade_uses_legacy_guard`
- `test_analyze_with_grade_includes_grading_results_section`
- `test_overview_mentions_judge_model_and_rubric_source` (N3)
- `test_overview_does_not_claim_human_evaluation` (N3 negative)
- `test_load_grade_skips_dummy_files`
- `test_load_grade_returns_none_when_missing`
- `test_load_grade_picks_most_recent`

## 의존성

- 007 (schema)
- step6_report.py (기존)
- NarrativeAnalyzer (기존, 변경됨)

## 비고

- PR #2에서 진행. PR #1엔 grade 파일 생성까지만, narrative 통합은 별도
- prompt token 증가로 Call 2 비용 약 5% 증가 (gpt-5.4-pro 가격 기준 무시
  가능 수준)
- "external grading pipeline" 문구를 dashboard에서 제거하는 작업(C2)은
  009 (dashboard) 명세에서 다룸. narrative_analyzer는 코드 내 prompt 수정만.
