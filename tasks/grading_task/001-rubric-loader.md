# 001 — `core/rubric_loader.py`

## 목적

openai/gdpval HF dataset에서 task별 rubric_json (그리고 있다면 gold
deliverable_files)을 다운로드/캐시/조회하는 단일 모듈.

## 위치

`batch-runner/core/rubric_loader.py`

## 외부 의존성

- `huggingface_hub` (이미 requirements.txt에 있음)
- `pandas`, `pyarrow` (parquet 읽기, 기존 의존성)
- 캐시 위치: `data/gdpval-local/` (기존 step0_bootstrap 캐시 재사용)

## 공개 API

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class RubricItem:
    rubric_item_id: str
    criterion: str           # 평가 기준 텍스트
    score: int               # 만점 가중치 (양수, 음수 가능 — 데이터셋 spec)
    required: Optional[bool] # 현재 dataset은 전부 None

@dataclass(frozen=True)
class TaskRubric:
    task_id: str
    sector: str
    occupation: str
    prompt: str              # 원본 task instruction
    rubric_items: list[RubricItem]
    rubric_pretty: str       # 사람용 텍스트
    reference_files: list[str]   # HF 상대 경로
    gold_deliverable_files: list[str]  # 현재 dataset 전부 [] but 필드는 유지
    
    @property
    def max_score(self) -> int:
        return sum(it.score for it in self.rubric_items)

class RubricLoader:
    """openai/gdpval HF rubric loader with local cache."""
    
    DEFAULT_REPO_ID = "openai/gdpval"
    DEFAULT_CACHE_DIR = "data/gdpval-local"
    
    def __init__(
        self,
        repo_id: str = DEFAULT_REPO_ID,
        revision: str = "main",
        cache_dir: str = DEFAULT_CACHE_DIR,
    ):
        """Initialize loader. Lazily downloads on first access."""
    
    def load_all(self) -> list[TaskRubric]:
        """Load all 220 task rubrics. Reads from parquet."""
    
    def load(self, task_id: str) -> TaskRubric:
        """Load a single task rubric. Raises KeyError if not found."""
    
    @property
    def rubric_sha(self) -> str:
        """Resolved HF commit SHA of the dataset.
        Used for cache key + reproducibility박제."""
    
    @property
    def rubric_short_sha(self) -> str:
        """First 7 chars of rubric_sha for filename use."""
    
    def download_reference_files(self, task: TaskRubric) -> dict[str, str]:
        """Download reference files for a task into local cache.
        Returns {hf_path: local_absolute_path}."""
    
    def download_gold_files(self, task: TaskRubric) -> dict[str, str]:
        """Download gold deliverable files (currently empty for all tasks).
        Returns {hf_path: local_absolute_path}. Empty dict if none."""
```

## 동작 명세

### 캐시 정책
- HF에서 parquet 다운로드는 `huggingface_hub.snapshot_download(allow_patterns=["data/*.parquet"])`
- 첫 호출 시 lazy download, 이후 캐시 hit
- `revision="main"` 이면 매 호출마다 etag 체크 (HF 표준 동작)
- explicit commit SHA를 받으면 immutable

### rubric_sha 해석
- `huggingface_hub.HfApi().dataset_info(repo_id, revision)` 호출로 SHA 획득
- 결과는 `self._sha` 인스턴스 변수에 캐싱

### parquet 파싱
- 컬럼: `task_id, sector, occupation, prompt, reference_files,
  reference_file_urls, reference_file_hf_uris, deliverable_files,
  deliverable_file_urls, deliverable_file_hf_uris, rubric_pretty, rubric_json`
- `rubric_json`은 list of dict (이미 parsed). string으로 올 경우 `json.loads`로
  방어적 파싱

### 파일 다운로드
- HF 경로 예: `reference_files/cc78.../Population%20v2.xlsx`
- `hf_hub_download(repo_id, filename=..., revision=...)` 사용
- 캐시 hit 시 재다운로드 X (HF lib 기본 동작)

## 실패 모드

| 케이스 | 동작 |
|---|---|
| HF 네트워크 실패 (초기) | raise `RuntimeError`, 호출자가 처리 |
| HF 네트워크 실패 (캐시 있음) | 캐시 hit, warning log |
| `task_id` not found | raise `KeyError(task_id)` |
| `rubric_json` 파싱 실패 | raise `ValueError(f"rubric_json parse failed: {task_id}")` |
| 파일 다운로드 실패 | warning log + return 경로 dict에서 누락 |

## 테스트 (`tests/test_rubric_loader.py`)

- `test_load_all_returns_220_tasks` — 정확히 220 rows
- `test_all_have_rubric_items` — 220개 모두 `len(rubric_items) > 0`
- `test_gold_is_empty_in_v2` — `sum(len(t.gold_deliverable_files) for t in all) == 0`
  (현재 dataset 가정 박제)
- `test_rubric_sha_is_stable` — 두 번 호출해도 같은 SHA
- `test_load_single_task` — 알려진 task_id로 단일 로드 성공
- `test_load_unknown_task_raises` — `KeyError`
- HF 다운로드는 mock (network 없이)

## 의존성

- 다른 명세에 input: 002 (grader), 004 (step8 CLI), 006 (config)

## 비고

- `rubric_short_sha`는 grade 파일명에 들어가므로 7자로 고정
- step0_bootstrap이 이미 `data/gdpval-local/`에 dataset을 미러링 중. 캐시
  디렉토리를 같이 쓰면 중복 다운로드 방지. 단, openai/gdpval v2 (현재
  rubric 포함된 버전)를 step0이 받는지 확인 후 일치시킬 것.
