# SMOKE REGRADE — gold 20 실채점

## 한 줄 결론
gold 20 실채점 완료. stale SP env를 현재 셸에서 unset해 CLI credential이 잡히는 것을 확인했고, 20/20을 실제 Azure judge로 채점했다. grade JSON 생성 및 schema validation 통과. 파일선택 Bug2 4/4 owner-target 일치, audit 필드 기록 확인, split 집계 기록 확인. 220은 안 갔다.

## 인증

`az account show`:

```text
subscription: <SUBSCRIPTION_NAME>
tenant: <AZURE_TENANT_ID>
user: <USER_UPN>
```

`.env` 파일 자체는 수정하지 않았다. 실행 셸에서만:

```text
unset AZURE_CLIENT_ID AZURE_CLIENT_SECRET AZURE_TENANT_ID
```

채점 전 토큰 확인:

```text
AzureCliCredential: token_ok
DefaultAzureCredential: token_ok
```

## 결과 파일

```text
tasks/0601_monday/smoke_regrade_outputs/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__selector_smoke_gold20.json
```

Summary:

```text
tasks: 20
avg_pct: 59.14
selection_status: ok 20/20
schema validation: pass
task audit missing fields: 0
item audit missing fields: 0
parent evidence > 200 chars: 0
```

## 파일 선택

Bug2 4건은 모두 올바른 primary candidate를 봤다.

| task | selected primary | refs excluded | match |
|---|---|---:|---|
| `7d7fc9a7` | `Aurisic_Prepaid_Amortization_Schedule_Through_Apr2025.xlsx` | 6 | yes |
| `43dc9778` | `Smith_2024_Form_1040_Draft.pdf` | 15 | yes |
| `ee09d943` | `Aurisic_Financials_4-25-1.xlsx` | 17 | yes |
| `99ac6944` | `West_Coast_Tour_IEM_Mobile_Setup.pdf` | 0 | yes |

## Audit 필드

Task-level audit fields present:
- `selected_deliverables`
- `reference_files_excluded`
- `selection_rule`
- `selection_status`

Item-level audit fields present:
- `target_scope`
- `target_ids`
- `child_grades`
- `aggregation_rule`
- `selected_paths`
- `support_paths_visible`
- `selection_status`
- `score_excluded`

Target scope distribution:

| target_scope | count |
|---|---:|
| `file_target` | 757 |
| `primary_bundle` | 146 |
| `manifest` | 90 |
| `split_children` | 5 |

## Split 집계

Separate-equivalent 확인 대상 4건은 모두 `split_children`로 child별 judge 후 `blocking_min_else_mean`이 기록됐다.

| task | children | aggregation | child scores |
|---|---:|---|---|
| `27e8912c` | 2 | `blocking_min_else_mean` | `organizational_ergonomic_action_items=3.5`, `workstation_ergonomics_checklist=5.0` |
| `a74ead3b` | 2 | `blocking_min_else_mean` | `session_13_nurturing_parenting_recovery=2.0`, `session_14_nurturing_parenting_recovery=5.0` |
| `bbe0a93b` | 3 | `blocking_min_else_mean` | `kent_county_community_resource_guide=5.0`, `kent_county_needs_assessment_english=3.5`, `kent_county_needs_assessment_espanol=4.0` |
| `6dcae3f5` | 2 | `blocking_min_else_mean` | `chief_key_indicator_5_year=2.0`, `email_to_pd_key_indicator_analysis=1.5` |

Additional observed split:
- `0419f1c3` also produced `split_children` with 2 children and `blocking_min_else_mean`.

## 점수 vs gold

Owner gold score JSON은 repo에서 찾지 못했다. `docs/human-in-the-loop/overall-style-gold-grading-sheet.html`의 embedded data도 `owner_score: null` 상태다. 따라서 이번 smoke는 점수 정확도 비교가 아니라 selector/audit/split 인프라 검증으로 판정한다.

Overall-style smoke scores:

| task | task pct | style score | style scope |
|---|---:|---:|---|
| `83d10b06` | 48.81% | 1.25/5 | `file_target` |
| `7b08cd4d` | 13.48% | 3.00/5 | `file_target` |
| `7d7fc9a7` | 30.95% | 0.00/5 | `file_target` |
| `43dc9778` | 13.64% | 3.00/5 | `file_target` |
| `ee09d943` | 63.47% | 5.00/5 | `file_target` |
| `27e8912c` | 81.60% | 4.25/5 | `split_children` |
| `99ac6944` | 51.59% | 2.50/5 | `file_target` |
| `f9a1c16c` | 64.56% | 2.00/5 | `file_target` |
| `1b1ade2d` | 72.38% | 5.00/5 | `file_target` |
| `93b336f3` | 66.38% | 4.25/5 | `file_target` |
| `575f8679` | 78.92% | 5.00/5 | `file_target` |
| `a74ead3b` | 48.82% | 3.50/5 | `split_children` |
| `bbe0a93b` | 87.24% | 4.17/5 | `split_children` |
| `85d95ce5` | 67.41% | 3.50/5 | `file_target` |
| `7bbfcfe9` | 37.92% | 2.00/5 | `file_target` |
| `ec591973` | 48.31% | 2.00/5 | `file_target` |
| `6dcae3f5` | 51.57% | 1.75/5 | `split_children` |
| `9a0d8d36` | 83.46% | 2.50/5 | `file_target` |
| `0419f1c3` | 80.24% | 4.50/5 | `split_children` |
| `403b9234` | 92.04% | 2.00/5 | `file_target` |

## 다음

스모크는 selector/audit/split 관점에서 통과. 점수 정확도 비교는 owner gold export JSON이 필요하다. 그다음 OIDC relay로 220 재채점 1회.
