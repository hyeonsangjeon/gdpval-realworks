# 200 — exp011 Env Audit

> PR2 / 1 of 9. Pure audit, no code change. Output is a matrix used to
> de-risk 201 (`read_deliverable` tool implementation).

## 목적

`read_deliverable` tool이 exp011 subprocess env에서 실제로 작동할 수 있는지 확인. SPEC §4.2가 새 샌드박스를 금지하므로 기존 환경에 라이브러리가 있어야 함. 없으면 201을 시작하기 전 plan 수정.

## 확인 대상 라이브러리

| 모달리티 | 라이브러리 | exp011 env 가용성 |
|---|---|---|
| Excel | `openpyxl` | ? |
| Word | `python-docx` | ? |
| PowerPoint | `python-pptx` | ? |
| PDF | `pdfplumber` | ? |
| 오디오 (probe) | `soundfile`, `ffmpeg` (system) | ? |
| 오디오 (process) | `pedalboard` | ? |
| 비디오 (probe) | `ffmpeg`, `ffprobe` | ? |
| 이미지 렌더 | `Pillow`, `matplotlib` (chart), `pandas.io.html`/Excel screenshot | ? |

## 작업

1. exp011의 dockerfile 또는 requirements 추적 (`batch-runner/experiments/exp011*.yaml` 또는 `batch-runner/core/subprocess_runner.py`의 env 정의)
2. `batch-runner/requirements.txt` 와 exp011 env 비교
3. 결과를 `tasks/rebuilding_grading_task/PR2_ENV_AUDIT.md`에 매트릭스로 commit
4. 누락된 라이브러리가 있으면 201 task md에 "라이브러리 X 추가 필요" 추가하고 진행

## 결정 룰

- 모든 modality 라이브러리 가용 → 201 그대로 진행
- 비디오 라이브러리만 누락 → 비디오 perception 후속 (objective probe만)
- 다중 누락 → 사용자에게 alert (자율 판단 한계)
