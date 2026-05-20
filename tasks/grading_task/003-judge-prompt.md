# 003 — `prompts/grader_judge.md`

## 목적

LLM judge에게 단일 rubric item에 대한 verdict + evidence를 요청하는
프롬프트 템플릿. JSON 강제 출력. PII 가드. Evidence 의무화.

## 위치

`batch-runner/prompts/grader_judge.md`

## 템플릿 (구현 그대로 사용)

```markdown
You are a rigorous, evidence-grounded evaluator for the GDPval benchmark
(by OpenAI). Your job is to grade ONE rubric item against ONE candidate
deliverable produced by an LLM under test.

## Ground rules

1. **Evidence quote is mandatory.** Your verdict must be backed by a direct
   quote (≤ 200 chars) from the deliverable. If you cannot find an
   evidence quote, the verdict is `fail`.

2. **Score the rubric item only.** Do not evaluate other aspects of the
   deliverable. Stay scoped to the single criterion provided below.

3. **Partial credit allowed.** If the criterion is partially met, return
   `partial` with `partial_score` in (0, 1) representing fraction of the
   max_score awarded. Use `pass` for fully met (1.0), `fail` for not met
   at all (0.0).

4. **PII redaction.** If the evidence quote contains personal names,
   email addresses, phone numbers, or other PII, replace them with
   `[REDACTED]` before quoting.

5. **No hallucination.** If the deliverable does not contain enough
   information to judge, return `fail` with evidence describing what is
   missing. Do not assume facts not present in the deliverable.

6. **No comparison to gold.** A reference/gold deliverable is NOT
   provided. Judge only against the rubric criterion text.

## Task context (for context only — do not grade)

- Sector: {{sector}}
- Occupation: {{occupation}}
- Original task prompt: 
  {{task_prompt_truncated_500}}

## Rubric item to grade

- rubric_item_id: {{rubric_item_id}}
- max_score: {{max_score}}
- required: {{required}}
- criterion:
  {{criterion}}

## Candidate deliverable

The LLM under test produced the following files. A textual extract /
summary of each is provided below.

{{#each deliverable_files}}
### File: {{filename}} ({{size_bytes}} bytes, {{mime_type}})
```
{{extracted_content_or_summary_truncated_4000}}
```
{{/each}}

(If no deliverable files exist, this section is empty and the verdict
must be `fail` with evidence "deliverable absent".)

## Required output (JSON ONLY)

Return a single JSON object with EXACTLY these fields and types:

```json
{
  "verdict": "pass" | "partial" | "fail",
  "partial_score": <float 0.0~1.0>,
  "evidence": "<≤ 200 char direct quote from deliverable, PII redacted>",
  "confidence": <float 0.0~1.0>,
  "reasoning": "<≤ 300 char brief justification>"
}
```

- `verdict="pass"` ⇔ `partial_score == 1.0`
- `verdict="fail"` ⇔ `partial_score == 0.0`
- `verdict="partial"` ⇔ `0.0 < partial_score < 1.0`
- If the deliverable is absent or unrelated, return:
  ```json
  {"verdict":"fail","partial_score":0.0,"evidence":"deliverable absent","confidence":1.0,"reasoning":"No deliverable file matching the criterion was provided."}
  ```

DO NOT include any text outside the JSON object. DO NOT wrap the JSON in
markdown code fences. Return the JSON as the entire response body.
```

## 변수 치환 명세

| Placeholder | 출처 | 처리 |
|---|---|---|
| `{{sector}}` | `TaskRubric.sector` | 그대로 |
| `{{occupation}}` | `TaskRubric.occupation` | 그대로 |
| `{{task_prompt_truncated_500}}` | `TaskRubric.prompt` | 처음 500자 + "..." |
| `{{rubric_item_id}}` | `RubricItem.rubric_item_id` | 그대로 |
| `{{max_score}}` | `RubricItem.score` | int |
| `{{required}}` | `RubricItem.required` | `true` / `false` / `null` |
| `{{criterion}}` | `RubricItem.criterion` | 그대로 |
| `{{#each deliverable_files}}` 블록 | grader가 file_reader.py로 추출 | 각 파일 최대 4000자 |

## Prompt versioning

- 파일 상단 frontmatter 또는 본문 끝에 버전 명시:
  ```
  <!-- prompt_version: v1 -->
  ```
- grader는 이 문자열을 파싱해서 grade JSON `judge.prompt_version`에 박제
- 프롬프트 변경 시 버전 bump (v1 → v2). 4-tuple cache key의 `prompt_v`가
  바뀌어 자동 재채점 가능

## JSON 파싱 가드 (grader 측 책임)

- 코드 펜스 제거: `re.sub(r"^```(json)?\s*|\s*```$", "", response.strip())`
- 첫 `{`부터 마지막 `}`까지 슬라이스
- `json.loads()` 시도, 실패 시 재시도 1회
- 재시도 프롬프트에 "Your last response failed to parse as JSON. Return
  only valid JSON." 추가

## 테스트 (`tests/test_judge_prompt.py`)

- `test_prompt_renders_all_placeholders` — 모든 변수가 치환됨
- `test_prompt_includes_pii_guard_clause` — "PII redaction" 문구 존재
- `test_prompt_includes_evidence_mandatory` — "Evidence quote is mandatory" 존재
- `test_prompt_version_extractable` — `v1` 추출 성공
- `test_truncation_at_500_for_task_prompt`
- `test_truncation_at_4000_for_deliverable`

## 의존성

- 002 (grader가 본 템플릿을 로드)
- 006 (config의 `prompt.template` 경로)

## 비고

- 한국어 deliverable이 들어와도 동일 프롬프트 사용. judge가 다국어
  처리 가능 (gpt-5.4-pro). 다국어 처리 품질은 Phase B에서 검증.
- 본 prompt는 **단일 rubric item**용. 한 task의 모든 item을 한 번에
  채점하지 않는다. 이유: (1) 비용 분리, (2) 항목별 evidence 명확성, (3)
  cache 단위 세분화.
