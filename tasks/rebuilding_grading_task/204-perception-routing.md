# 204 — Perception Routing

> PR2 / 5 of 9. Depends on 203 (ToolCallingJudge surface).

## 목적

Criterion 단위로 modality를 분류하고, 시각/오디오 항목만 vision/audio 모델 경로로 라우팅. 모든 호출을 full agentic 루프로 돌리지 않음 (비용 bound). SPEC §4.3.

## 라우팅 규칙 (자율 결정)

| criterion 텍스트 패턴 | modality | judge 추가 호출 |
|---|---|---|
| `chart|graph|visual|appearance|render|color|font|layout` | visual | `render_to_image` + vision model |
| `audio|sound|music|voice|mix|loudness|silence` | audio | `probe_audio` + audio model |
| `format|style|structure` (시각 키워드 없음) | text+formatting | `inspect_formatting` 만 |
| 그 외 (content, columns, includes, etc.) | text | `read_content`, `inspect_structure` |

- 라우팅은 main judge 호출 *전* 결정 (criterion 텍스트 기반).
- 라우팅 결과는 main judge prompt에 "for this item, prefer tool X" hint.

## 영향 파일

- `batch-runner/core/grader_routing.py` (new) — `classify_criterion(text) -> Modality`
- `batch-runner/core/grader.py` — ToolCallingJudge가 routing hint를 prompt에 inject
- `batch-runner/tests/test_grader_routing.py` (existing 파일 update)

## Acceptance

- 12개 sample criterion에 대해 분류 매트릭스 테스트
- exp003 220 task의 critical item 분포: visual ?%, audio ?%, formatting ?%, text ?% — 단순 inventory (204 commit에 포함)
