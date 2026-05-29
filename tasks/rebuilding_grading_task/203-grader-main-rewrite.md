# 203 — Main Grader Rewrite (Tool-Calling)

> PR2 / 4 of 9. The largest single change in PR2. Depends on 201, 202.

## 목적

`core/grader.py`의 main judge 호출 경로를 Responses API tool calling 루프로 전환. 사전 text 추출 제거.

## 핵심 변경

- 단일 judge: `gpt-5.4` reasoning_effort=`medium`. tier 분기 코드 제거 (207에서 마무리)
- Responses API: `client.responses.create(..., tools=[...])`, tool_call → tool_result 루프
- per-request timeout (NarrativeAnalyzer 교훈) — `httpx.Timeout` per call, NOT client-level
- 최대 tool 호출 횟수 cap (예: per item 8회, per task 30회) — 무한 루프 방지
- judge 응답 파싱: 기존 verdict/evidence 추출 로직 유지 + tool 호출 history는 ItemGrade.evidence에 요약 추가

## 결정 (자율)

- 기존 batch/tier 분기 코드 (`tier_pro`/`tier_standard`/`tier_mini`/`BatchJudge`)는 **이 task에서 신규 코드와 공존**, 207에서 한꺼번에 삭제
- new class `ToolCallingJudge` 추가 — 기존 `Judge` 옆에 신규
- `Grader.__init__`에 config switch: `judge.api=='responses'` AND `judge.tools` present → ToolCallingJudge, 그 외 기존 경로
- 새 default config (PR2 후속에서 생성)는 ToolCallingJudge 사용; 기존 sweep configs는 legacy 경로 그대로

## 영향 파일

- `batch-runner/core/grader.py` — new ToolCallingJudge class, Grader dispatch
- `batch-runner/tests/test_grader.py` — ToolCallingJudge unit tests (mocked Responses API)
- `batch-runner/tests/test_grader_tool_calling.py` (new) — tool loop end-to-end mock

## Acceptance

- 기존 batch/tier 코드 path 회귀 없음 (기존 grade JSON 재생성 일관)
- ToolCallingJudge mock 테스트: tool call → tool result → final verdict 흐름
- 무한 루프 방지 cap 작동 (forced tool call > cap 시 judge_error)
- per-request timeout 작동 (mock에서 sleep 시 retry/timeout)
