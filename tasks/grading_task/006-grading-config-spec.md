# 006 — `grading_configs/*.yaml` 명세

## 목적

Judge 모델, reasoning 설정, rubric 출처, prompt 버전, TPM 가드 등 grading
파이프라인의 모든 운영 파라미터를 단일 yaml로 박제. 4-tuple cache key의
`prompt_v` 외에 config 전체 해시도 grade JSON에 박제 (재현성).

## 위치

`batch-runner/grading_configs/<config_name>.yaml`

PR #1에서 다음 1개 파일 생성:
- `default_gpt5pro.yaml` (1차 표준 설정)

Phase B에서 추가 예정:
- `cross_claude.yaml` (Anthropic cross-family)
- `cross_gemini.yaml` (Google cross-family)

## YAML 스키마 (default_gpt5pro.yaml 풀 예시)

```yaml
# batch-runner/grading_configs/default_gpt5pro.yaml
schema_version: "1.0"
config_name: "default_gpt5pro"
description: |
  Default GDPval grading config — gpt-5.4-pro Responses API as judge,
  high reasoning effort, rubric from openai/gdpval @ main, prompt v1.

# ── Judge ──────────────────────────────────────────────────────────
judge:
  provider: "azure_openai"
  api: "responses"                    # gpt-5.4-pro requires Responses API
  model: "gpt-5.4-pro"                # ← change to gpt-5.5-pro if available
  deployment: "gpt-5.4-pro"
  api_version: "2025-04-01-preview"
  endpoint_env: "AZURE_OPENAI_ENDPOINT"  # read from env var
  timeout_sec: 600
  
  reasoning:
    effort: "high"                     # low | medium | high (Responses API)
  
  generation:
    temperature: 0
    seed: 42
    max_output_tokens: 4096

# ── Rubric source ──────────────────────────────────────────────────
rubric:
  source: "huggingface"
  repo_id: "openai/gdpval"
  revision: "main"                     # or pinned commit SHA
  cache_dir: "data/gdpval-local"

# ── Grader behavior ────────────────────────────────────────────────
grader:
  precheck_patterns_version: "v1"      # core/grader.py PRECHECK_PATTERNS revision
  evidence_max_chars: 200
  judge_max_retries: 1
  per_item_max_output_tokens: 800      # override generation.max for cost
  save_raw_responses: false             # debug; set true for postmortem
  fail_on_missing_evidence: true       # defensive default
  
  # Deliverable extraction limits (passed to file_reader)
  deliverable_extract_max_chars: 4000
  task_prompt_truncate_chars: 500

# ── TPM guard (P3 sequential) ──────────────────────────────────────
tpm_guard:
  max_concurrent: 1                    # Phase A; bump in Phase B
  min_delay_ms_between_calls: 500      # rate limit buffer
  retry_on_429:
    enabled: true
    max_retries: 3
    initial_backoff_sec: 2
    exponential_factor: 2.0

# ── Prompt template ────────────────────────────────────────────────
prompt:
  template: "prompts/grader_judge.md"
  version: "v1"                        # cache key component (prompt_v)

# ── Output policy ──────────────────────────────────────────────────
output:
  directory: "data/grades"
  filename_template: "{exp_id}__{judge_slug}__{rubric_short_sha}__{prompt_v}.json"
  partial_save_every_n_tasks: 10
  include_judge_raw: false             # mirrors grader.save_raw_responses
```

## 필수 vs 선택 키

**필수** (없으면 step8_grade.py가 즉시 종료):
- `schema_version`, `config_name`
- `judge.provider`, `judge.api`, `judge.model`, `judge.endpoint_env`
- `rubric.repo_id`, `rubric.revision`, `rubric.cache_dir`
- `prompt.template`, `prompt.version`
- `output.directory`, `output.filename_template`

**선택** (기본값 적용):
- `judge.timeout_sec` (600)
- `judge.reasoning.effort` ("high")
- `judge.generation.temperature` (0), `seed` (42), `max_output_tokens` (4096)
- `grader.*` (위 예시 값 그대로)
- `tpm_guard.max_concurrent` (1), `min_delay_ms_between_calls` (500)
- `tpm_guard.retry_on_429.*` (위 예시 값)
- `output.partial_save_every_n_tasks` (10), `include_judge_raw` (false)

## 환경 변수 참조

| Config key | ENV |
|---|---|
| `judge.endpoint_env: "AZURE_OPENAI_ENDPOINT"` | `AZURE_OPENAI_ENDPOINT` |
| (Azure OIDC는 azure/login@v2가 처리) | `AZURE_CLIENT_ID/TENANT_ID/SUBSCRIPTION_ID` |

API KEY env (예: `AZURE_OPENAI_API_KEY`)는 **요구 금지** — PR #40 회귀
방지.

## Config hash (재현성)

```python
import hashlib, yaml
def hash_config(path: str) -> str:
    """SHA-256(첫 16자)로 config 전체 해시. grade JSON에 박제."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]
```

→ grade JSON의 `judge.config_hash` 필드에 들어감 (007 schema). 같은
`prompt_v`라도 config의 다른 값(예: reasoning.effort)이 바뀌면 hash로 추적
가능. cache key에는 포함 안 함 (key가 너무 길어짐) — 운영상 변경 시
`prompt_v`를 bump하는 컨벤션 유지.

## Validation

Step8 시작 시 다음을 검증:

1. `schema_version` == "1.0" 일치
2. 필수 키 존재
3. `prompt.template` 파일 실제 존재
4. `rubric.repo_id` 형식 (`owner/name`)
5. `judge.model` ∈ {알려진 deployment 리스트} (warning만, 미등록 가능)
6. `tpm_guard.max_concurrent >= 1`

실패 시 즉시 exit 1.

## 테스트 (`tests/test_grading_config.py`)

- `test_default_config_loads_and_validates`
- `test_missing_required_key_fails`
- `test_schema_version_mismatch_fails`
- `test_template_path_must_exist`
- `test_config_hash_is_stable`
- `test_hash_changes_when_content_changes`

## Phase B용 예시 파일들 (PR #1엔 포함 X, 참고)

```yaml
# cross_claude.yaml — Phase B
judge:
  provider: "anthropic"
  api: "messages"
  model: "claude-opus-4"
  endpoint_env: "ANTHROPIC_API_KEY"   # API key env (different secret model)
  # reasoning effort는 Anthropic native param 없음 — prompt 측에서 처리
```

```yaml
# cross_gemini.yaml — Phase B
judge:
  provider: "google"
  api: "generateContent"
  model: "gemini-2.5-pro"
  endpoint_env: "GEMINI_API_KEY"
```

이런 cross-family config가 추후 들어와도 동일 `step8_grade.py`가 처리할
수 있도록, **Grader 클래스 내부에 provider switch** (`if
config["judge"]["provider"] == "azure_openai": ... elif "anthropic": ...`)
가 필요. PR #1엔 azure_openai만 구현, 나머지는 `NotImplementedError`.

## 의존성

- 002 (Grader가 본 config 소비)
- 004 (step8 CLI가 `--config`로 path 받음)
- 007 (config 내용이 grade JSON `judge` 섹션에 박제)

## 비고

- yaml에 secret 값을 직접 박지 말 것. 항상 `*_env` 키로 ENV 참조
- `gpt-5.4-pro` → `gpt-5.5-pro` 갈아끼우기는 `model` + `deployment` 두 줄
  변경 + 새 yaml로 분리 (`default_gpt55pro.yaml`)하는 게 깔끔 (캐시 분리)
