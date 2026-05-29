# 206 — Audio Perception (gpt-audio-1.5)

> PR2 / 7 of 9. Depends on 201 (probe_audio) + 204 (audio routing).

## 목적

오디오 *지각* 품질 (믹싱, 음질, 음악성 등) 항목에 대해 audio 모델 호출.

## 결정 (자율)

- 위치: `batch-runner/core/perception/audio.py`
- 모델: `gpt-audio-1.5` Azure deployment. 별도 endpoint env (`AZURE_AUDIO_ENDPOINT`) — config에서 override 가능.
- 입력: 원본 audio file (read_deliverable로 path만 알려주고 모델이 직접 가져오는 게 어렵다면 base64 chunk 전송)
- duration cap: 첫 30초만 모델 입력 (cost bound). 30초 이상이면 sampling (예: 처음/중간/끝 10초씩).
- 객관 metrics (peak, LUFS, clipping)은 probe_audio가 제공 — 모델은 지각 항목만.
- 호출 cap: per task 3회.

## 영향 파일

- `batch-runner/core/perception/audio.py` (new)
- `batch-runner/tests/test_perception_audio.py` (new) — mocked
- `batch-runner/core/config.py` — `AZURE_AUDIO_ENDPOINT` 추가

## Acceptance

- 단위 테스트 mocked 흐름
- 30초 trim 동작 검증
- 모델 비가용 (endpoint 미설정) 시 graceful skip + warning (judge가 객관 metric만 사용)

## Out of scope

- 비디오 audio track 분리 (필요 시 후속)
- speaker diarization
