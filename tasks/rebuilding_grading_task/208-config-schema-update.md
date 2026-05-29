# 208 — Config Schema + Validator Update

> PR2 / 9 of 9. Final task before PR2 closes.

## 목적

새 `judge.tools` / `judge.perception` 블록을 정식 schema로 받아들이고, `step8_grade.py::validate_grading_config`가 v2 config를 검증하게 함.

## 변경 사항

1. **새 default config**: `batch-runner/grading_configs/default_v2.yaml`
   - SPEC §8 YAML 그대로
   - `judge.model: gpt-5.4`, `reasoning_effort: medium`, `api: responses`
   - `judge.tools.read_deliverable.ops: [...]`
   - `judge.perception.visual.model: gpt-5.4` (vision: true)
   - `judge.perception.audio.model: gpt-audio-1.5`
   - `judge.critical.rule: abs_max_score_threshold`, `threshold: 4`
   - `judge.scoring.sign_aware_pct: true`, `handle_nonpositive_total_max: explicit`
   - `deliverable_extract_max_chars` 없음

2. **validator**: `validate_grading_config`에서 v2 블록 인식
   - `tools` 블록 있으면 `ops` array 필수
   - `perception` 블록 있으면 visual/audio sub-block 검증
   - `critical.rule` enum validation
   - 기존 v1 config (예: `default_gpt5pro.yaml`)도 validation pass — back compat
   - `schema_version: "2.0"` 도입 (config 수준; grade JSON schema는 별개 1.1)

3. **README** in `grading_configs/`: v1/v2 차이 + 어떤 걸 언제 쓰는지 짧은 표

4. **default config 교체**: `default_gpt5pro.yaml`를 v1 사용자가 명시적으로 호출하지 않는 한 v2 우선. grade-run.yml의 기본값 `default_v2.yaml`로 변경.

## 영향 파일

- `batch-runner/grading_configs/default_v2.yaml` (new)
- `batch-runner/grading_configs/README.md` (new or update)
- `batch-runner/step8_grade.py` — `validate_grading_config` 업데이트
- `batch-runner/tests/test_grading_config.py` — v2 validation 케이스
- `.github/workflows/grade-run.yml` — default input `grading_config: default_v2.yaml`

## Acceptance

- `python step8_grade.py exp998_smoke --config grading_configs/default_v2.yaml --dry-run` 성공
- 기존 v1 config 회귀 없음
- pytest 전체 green
- 새 v2 config로 exp998 smoke 1 task 실제 grading 성공 (mocked or live)
