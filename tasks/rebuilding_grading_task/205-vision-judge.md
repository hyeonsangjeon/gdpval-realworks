# 205 — Vision Perception (gpt-5.4 vision)

> PR2 / 6 of 9. Depends on 201 (render_to_image) + 204 (visual routing).

## 목적

시각 판단 항목에 대해 deliverable을 이미지로 렌더링 후 gpt-5.4 vision (image input)으로 추가 검사.

## 결정 (자율)

- 위치: `batch-runner/core/perception/vision.py`
- 호출 방식: Responses API의 image input. base64 PNG 또는 URL. tool 호출 history에 vision verdict 첨부.
- 모델: gpt-5.4 (vision 활성). 별도 모델 키 분리 불필요 (같은 deployment).
- 어떤 항목이 vision 호출하는지: 204 routing에서 결정. main judge는 vision verdict를 평가 근거로 종합.
- 이미지 캐시: 같은 (path, page) 쌍은 한 task 안에 1번만 render (`@lru_cache`).
- vision 호출 cap: per task 5회 (cost bound).

## 영향 파일

- `batch-runner/core/perception/__init__.py` (new)
- `batch-runner/core/perception/vision.py` (new)
- `batch-runner/tests/test_perception_vision.py` (new) — mocked API

## Acceptance

- vision 단위 테스트: mocked image → verdict 흐름
- cap 작동 (6번째 호출 시 cached or refused)
- 잘못된 파일 (corrupt PNG) → judge_error로 graceful fallback
