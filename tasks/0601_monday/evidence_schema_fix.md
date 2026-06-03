# EVIDENCE/SCHEMA FIX + gold 20 재실채점

## 한 줄 결론
원인은 case A: `split_children` 부모 item이 child evidence들을 `|`로 한 문자열에 다시 합치면서 schema `evidence.maxLength=200`을 넘긴 것. child evidence는 이미 `child_grades[]`에 분리 저장되고 있었으므로, 부모 evidence를 짧은 child 참조로 바꿨다. truncate로 때우지 않았고 schema maxLength도 올리지 않았다. gold 20 실채점은 20/20 완료, grade JSON 생성, audit/selector/split 검증 통과. 220은 안 갔다.

## PHASE 1 진단

Evidence 조립 경로:
- `batch-runner/core/grader.py:648` `_judge_split_children(...)`
- child별 judge 결과는 `child_grades[]`에 이미 분리 저장됨:
  - `target_id`
  - `selected_paths`
  - `verdict`
  - `awarded_score`
  - `evidence`
  - `judge_confidence`
- 문제는 `batch-runner/core/grader.py:715`에서 부모 `item.evidence`를 `target_id: child evidence | target_id: child evidence`로 다시 합친 점.

Schema 제한:
- `batch-runner/schemas/grade.schema.json:125`
- parent `items[].evidence`는 기존 Phase A 시절부터 `maxLength: 200`.
- selector audit 필드 추가 후에도 이 제한은 그대로 남아 있었다.

추가 발견:
- `_truncate(value, 200)`는 현재 `value[:200] + "..."`라 실제 203자를 만들 수 있다.
- 이번 실패 evidence 길이도 203자였다.
- 그러나 이번 해법은 `_truncate`를 더 세게 적용하는 것이 아니라, split parent에 child evidence를 중복 저장하지 않는 구조 수정이다.

단일 파일 evidence:
- 단일 judge evidence는 기존 경로에서 `evidence_max_chars=200`으로 잘려 schema 안에 들어간다.
- 이번 실패는 단일 파일 evidence 자체가 아니라, split parent에서 여러 child evidence를 합친 부작용이었다.

## PHASE 2 수정

수정 파일:
- `batch-runner/core/grader.py:715`
- `batch-runner/tests/test_grader_selector_integration.py:168`

변경:
- split parent `item.evidence`:
  - before: child evidence들을 ` | `로 연결
  - after: `split_children: see child_grades for N per-target evidence entries`
- child별 evidence:
  - `child_grades[]` 안에 그대로 유지
- `aggregation_rule`, score 계산, verdict 계산, selector logic은 불변.
- schema `maxLength: 200`은 건드리지 않음.
- evidence truncate로 해결하지 않음.

Regression test:
- split child evidence 두 개가 합치면 200자를 넘는 fixture를 추가.
- parent evidence는 200자 이하의 참조 문자열인지 확인.
- child evidence는 `child_grades[0/1].evidence`에 보존되는지 확인.

## 테스트

```text
PYTHONPATH=batch-runner .venv/bin/python -m pytest batch-runner/tests/test_grader_selector_integration.py -q
3 passed
```

```text
cd batch-runner
PYTHONPATH=. ../.venv/bin/python -m pytest tests/test_grader_selector_integration.py tests/test_deliverable_selector.py tests/test_grade_schema.py -q
15 passed
```

```text
cd batch-runner
PYTHONPATH=. ../.venv/bin/python -m pytest tests -q
580 passed, 3 skipped, 37 deselected
```

## PHASE 3 재실채점

Authentication:
- `.env` 파일은 수정하지 않음.
- 현재 셸에서만 `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` unset.
- `AzureCliCredential` and `DefaultAzureCredential` token test 통과.

Run:
- gold 20 only.
- output: `tasks/0601_monday/smoke_regrade_outputs/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__selector_smoke_gold20.json`
- completed: 20/20
- avg pct: 59.14
- schema validation: pass
- parent evidence > 200: 0
- task audit missing fields: 0
- item audit missing fields: 0
- selection status: 20 `ok`

## Bug2 파일 선택

| task | selected primary | refs excluded | match |
|---|---|---:|---|
| `7d7fc9a7` | `Aurisic_Prepaid_Amortization_Schedule_Through_Apr2025.xlsx` | 6 | yes |
| `43dc9778` | `Smith_2024_Form_1040_Draft.pdf` | 15 | yes |
| `ee09d943` | `Aurisic_Financials_4-25-1.xlsx` | 17 | yes |
| `99ac6944` | `West_Coast_Tour_IEM_Mobile_Setup.pdf` | 0 | yes |

## Split 집계

| task | children | aggregation | child scores |
|---|---:|---|---|
| `27e8912c` | 2 | `blocking_min_else_mean` | `organizational_ergonomic_action_items=3.5`, `workstation_ergonomics_checklist=5.0` |
| `a74ead3b` | 2 | `blocking_min_else_mean` | `session_13_nurturing_parenting_recovery=2.0`, `session_14_nurturing_parenting_recovery=5.0` |
| `bbe0a93b` | 3 | `blocking_min_else_mean` | `kent_county_community_resource_guide=5.0`, `kent_county_needs_assessment_english=3.5`, `kent_county_needs_assessment_espanol=4.0` |
| `6dcae3f5` | 2 | `blocking_min_else_mean` | `chief_key_indicator_5_year=2.0`, `email_to_pd_key_indicator_analysis=1.5` |

Additional observed split:
- `0419f1c3` also produced `split_children` with 2 children and `blocking_min_else_mean`.

## Score vs gold

Owner gold scores were not found in the repo. The HITL HTML currently embeds `owner_score: null`, and no exported `overall_style_v1` gold JSON is present. Therefore the smoke can verify file selection/audit/split behavior, but cannot compute model-vs-owner agreement yet.

## 다음

Gold 20 smoke passed on infrastructure/selector/audit/split. Next: owner-provided gold JSON if score accuracy comparison is required, then OIDC relay 220 재채점 1회.
