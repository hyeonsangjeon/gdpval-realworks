# 202 — Judge Prompt v2 (Tool-Aware)

> PR2 / 3 of 9. Depends on 201 (tool surface).

## 목적

`prompts/grader_judge.md` v1 → v2 개정. tool calling 지시 추가.

## 핵심 변경

- "텍스트 추출된 deliverable이 아래 있다" 섹션 삭제
- "여기 루브릭 + 파일 경로다. `read_deliverable` tool로 직접 확인 후 채점하라" 지시 추가
- evidence는 tool 호출로 *관찰한 사실* 기반이어야 함 — fabricate 금지
- 같은 item을 두 번 채점 금지 (tool 호출 후 단일 verdict)

## 결정 (자율)

- v1을 archive로 보존: `prompts/grader_judge_v1_archive.md`. v1 grade JSON 재생산 가능성 유지.
- prompt_version bump: `<!-- prompt_version: v2 -->`
- tool catalog (6 op) 프롬프트 안에 inline 명시 — judge가 어떤 tool을 부를지 알게
- modality hint 추가: 만약 criterion에 "format/style" → `inspect_formatting` 우선, "audio quality" → `probe_audio` 우선

## 영향 파일

- `prompts/grader_judge.md` (rewrite, prompt_version=v2)
- `prompts/grader_judge_v1_archive.md` (rename from current grader_judge.md)
- `batch-runner/tests/test_grader.py` — prompt_version v2 assertion update

## Acceptance

- prompt v2가 6 tool op를 모두 명시
- v1 archive 파일 존재
- 단위 테스트: prompt_version 추출이 'v2' 반환
