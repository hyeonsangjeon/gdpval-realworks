# 002 — `core/grader.py`

## 목적

단일 태스크를 받아 rubric item별로 채점한다.
- precheckable 항목 → 결정론적 검증
- judgement 항목 → LLM-judge 호출 (`gpt-5.4-pro` Responses API)
- evidence quote 의무화
- task-level 합산, % 정규화, critical_fail 플래그

## 위치

`batch-runner/core/grader.py`

## 외부 의존성

- `openai` (AzureOpenAI, Responses API — `narrative_analyzer.py` 패턴 차용)
- `azure-identity` (OIDC, DefaultAzureCredential)
- `openpyxl`, `python-docx`, `pypdf` (precheck file inspection — 이미
  `core/file_reader.py`에서 사용 중인 라이브러리)
- `re` (precheck pattern 매칭)

## 공개 API

```python
from dataclasses import dataclass, field
from typing import Literal, Optional
from core.rubric_loader import TaskRubric, RubricItem

Verdict = Literal["pass", "partial", "fail", "judge_error"]
DecidedBy = Literal["precheck", "judge"]

@dataclass
class ItemGrade:
    rubric_item_id: str
    criterion: str
    max_score: int
    awarded_score: float       # 0 ~ max_score (float for partial)
    verdict: Verdict
    decided_by: DecidedBy
    required: Optional[bool]
    evidence: str              # ≤ 200 chars
    judge_confidence: Optional[float] = None  # judge only, 0~1
    judge_latency_ms: Optional[float] = None
    judge_raw_response: Optional[str] = None  # debug, optional

@dataclass
class TaskGrade:
    task_id: str
    sector: str
    occupation: str
    items: list[ItemGrade]
    total_awarded: float
    total_max: int
    pct: float                 # 0~100
    critical_fail: bool        # any required item failed
    gold_referenced: bool      # False for current dataset
    judge_call_count: int
    precheck_count: int
    error: Optional[str] = None  # task-level error (e.g., deliverables not found)

class Grader:
    def __init__(
        self,
        config: dict,           # parsed grading_configs/*.yaml
        rubric_loader,          # core.rubric_loader.RubricLoader instance
    ):
        """Init AzureOpenAI client (Responses API) using config.
        Use DefaultAzureCredential like narrative_analyzer.py."""
    
    def grade_task(
        self,
        task: TaskRubric,
        deliverable_dir: str,   # absolute path to our LLM's output files
    ) -> TaskGrade:
        """Grade a single task. Never raises — captures errors in TaskGrade."""
```

## 동작 명세

### Step 1: rubric item 분류

```python
PRECHECK_PATTERNS = [
    # 파일 존재 / 형식 / 확장자
    (r"\b(file|workbook|document|pdf|deliverable).*(named|basename|filename|extension|exists?|is a|is an|single|exactly one)\b", "file_exists_or_name"),
    (r"\b(\.xlsx|\.xls|\.xlsm|\.pdf|\.docx?|\.pptx?|\.txt|\.csv|\.json|\.wav|\.mp3|\.mp4|\.png|\.jpg)\b", "file_extension"),
    # 워크시트 / 시트
    (r"\bworksheet\b.*(named|exactly|contains|present)", "worksheet_name"),
    # 행/열 카운트
    (r"\b(at least|exactly|no more than|fewer than)\s+\d+\b.*(rows?|columns?|pages?|sheets?|sections?|items?|files?)\b", "count_check"),
    # 페이지 수
    (r"\bpage(s)?\b.*\b(at least|exactly)\s+\d+\b", "page_count"),
    # 단어 수
    (r"\bword(s)?\b.*\b(at least|exactly|approximately)\s+\d+\b", "word_count"),
]

def _classify(item: RubricItem) -> tuple[str, Optional[str]]:
    """Returns ("precheck", pattern_id) or ("judge", None)."""
    for pattern, pid in PRECHECK_PATTERNS:
        if re.search(pattern, item.criterion, re.I):
            return "precheck", pid
    return "judge", None
```

### Step 2: precheck handler dispatch

각 `pattern_id`마다 handler 함수:
- `_precheck_file_exists_or_name(item, deliverable_dir)`
- `_precheck_file_extension(item, deliverable_dir)`
- `_precheck_worksheet_name(item, deliverable_dir)` (openpyxl)
- `_precheck_count_check(item, deliverable_dir)` (file_reader.py 재사용)
- `_precheck_page_count(item, deliverable_dir)` (pypdf)
- `_precheck_word_count(item, deliverable_dir)` (python-docx)

handler 반환: `(verdict: Verdict, evidence: str)`. 패턴은 맞았지만 데이터
추출이 모호하면 `verdict="fail"`이 아니라 **fallback to judge** (handler가
`None` 반환). Grader가 None 받으면 judge로 라우팅.

### Step 3: LLM judge

```python
def _judge(
    self,
    task: TaskRubric,
    item: RubricItem,
    deliverable_dir: str,
) -> ItemGrade:
    # 1. file_reader.py로 deliverable 텍스트/구조 추출 (요약 ≤ 4000자)
    # 2. prompt = self._build_prompt(task, item, deliverable_summary)
    #    (prompts/grader_judge.md 템플릿 사용)
    # 3. self.client.responses.create(...)  # Responses API
    # 4. JSON 파싱 ({verdict, partial, evidence, confidence})
    # 5. evidence 누락 → verdict=fail (defensive)
    # 6. JSON 파싱 실패 1회 재시도, 그래도 실패 → verdict=judge_error
```

### Step 4: 합산

```python
def _aggregate(items: list[ItemGrade], task: TaskRubric) -> TaskGrade:
    total_awarded = sum(it.awarded_score for it in items)
    total_max = task.max_score
    pct = (total_awarded / total_max * 100) if total_max else 0.0
    critical_fail = any(
        it.required and it.verdict in ("fail", "judge_error")
        for it in items
    )
    return TaskGrade(...)
```

### Reasoning settings (gpt-5.4-pro Responses API)

config에서 읽은 값을 `responses.create()`에 전달:
```python
self.client.responses.create(
    model=self.config["judge"]["model"],
    input=[{"role": "user", "content": prompt}],
    reasoning={"effort": self.config["judge"]["reasoning"]["effort"]},
    temperature=self.config["judge"]["generation"]["temperature"],
    max_output_tokens=self.config["judge"]["generation"]["max_output_tokens"],
)
```

## 실패 모드

| 케이스 | 동작 |
|---|---|
| deliverable_dir 없음 / 비어있음 | `TaskGrade.error="no_deliverables"`, 모든 file_exists 항목 fail, judgement 항목은 "deliverable absent" evidence로 자동 fail |
| precheck handler 예외 | judge로 fallback, warning log |
| judge JSON parse 실패 | 1회 재시도 → `verdict=judge_error`, awarded=0 |
| judge API 429/5xx | exponential backoff (3회), 최종 실패 시 `verdict=judge_error` |
| TPM 한도 | `tpm_guard.min_delay_ms_between_calls` 만큼 sleep |

## 테스트 (`tests/test_grader.py`)

- `test_classify_file_exists_pattern` — "file basename 'Sample'" → precheck
- `test_classify_falls_back_to_judge` — "audit conclusion correctly identifies..." → judge
- `test_precheck_file_extension_pass` / `fail`
- `test_precheck_worksheet_name_pass` — 실제 xlsx 픽스처
- `test_judge_missing_evidence_marks_fail` — mock LLM response, no evidence
- `test_judge_parse_retry_then_judge_error` — mock 2회 실패
- `test_aggregate_pct_calculation` — 63점 만점 중 42점 → 66.67%
- `test_critical_fail_flag` — required=true mock, fail → critical_fail=true
- `test_grade_task_no_deliverables_graceful` — empty dir → error="no_deliverables"

## 의존성

- 입력: 001 (rubric_loader), 003 (prompt template), 006 (config)
- 출력: 004 (step8 CLI가 호출)

## 비고

- `core/llm_client.py`를 사용하지 않는다. `gpt-5.4-pro`는 Chat Completions
  미지원, Responses API 전용. `narrative_analyzer.py`와 같이 standalone
  client.
- `judge_raw_response`는 debug용. 운영에선 config의
  `grader.save_raw_responses: false`로 비활성 (디스크 절약).
