# 201 — read_deliverable Tool Interface

> PR2 / 2 of 9. Depends on 200 env audit pass.

## 목적

Judge가 호출할 read-only file inspection tool 구현. SPEC §4.2.

## Tool API (6 operations)

```python
read_deliverable(op: str, path: str, **kwargs) -> dict
```

| op | 입력 | 출력 요약 |
|---|---|---|
| `inspect_structure` | path | 파일 타입, 시트/섹션/슬라이드 목록, 행렬 크기 |
| `read_content` | path, scope? (sheet name, page range) | text content (no truncation) |
| `inspect_formatting` | path, scope? | 서식 메타 (셀 fill/font/border, 병합, 컬럼 너비, 스타일, 차트 존재) |
| `render_to_image` | path, page/sheet | base64 PNG (vision 입력용) |
| `probe_audio` | path | sample rate, channels, duration, peak, LUFS, clipping, silence% |
| `probe_video` | path | codec, duration, resolution, fps, tracks |

## 설계 결정 (자율)

- 위치: `batch-runner/core/tools/read_deliverable.py` (새 모듈)
- 모든 op는 read-only — 파일 수정 없음
- path는 grading harness가 trusted base dir로 제한 (judge가 임의 경로 못 봄). `_normalize_path(path, base)` helper.
- 출력은 항상 dict (`{ok: bool, data?: any, error?: str}`) — tool calling 결과 직렬화 안전
- 큰 출력 (render_to_image base64)은 size cap (예: 5MB) + 초과 시 down-sample
- timeout per op (10s 객관, 30s vision render) — judge 무한 wait 방지

## 영향 파일

- `batch-runner/core/tools/__init__.py` (new)
- `batch-runner/core/tools/read_deliverable.py` (new)
- `batch-runner/tests/test_read_deliverable.py` (new)

## Acceptance

- 6 op 모두 단위 테스트 통과 (small fixtures: 1-sheet xlsx, 2-page docx, 30s wav)
- trusted path injection 테스트 (`../../etc/passwd` reject)
- size cap 테스트
