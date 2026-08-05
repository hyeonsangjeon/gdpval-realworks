# FULL REGRADE 220 — gpt-5.4-mini selector+audit baseline

> **검증된 역사 기록.** 이 재채점은 2026-06-03~04 UTC에 완료됐다. 이 문서는
> 처음에는 gold 입력을 기다리는 pre-run 상태로 체크인됐고, 2026-08-05에 보존된
> GitHub Actions 실행, Git commit, 최종 grade JSON, owner gold 20건, 후속 GPT-5.4
> 및 vision 분석을 다시 열어 완료 상태로 교정했다. 이번 문서 복구에서는 모델 호출,
> 재채점, grading workflow dispatch를 실행하지 않았다.

## 한 줄 결론

`default_v2_mini.yaml`의 220-task 재채점은 네 번의 순차 workflow run으로
완료됐다. selector는 `ok 194 / wrong_format_primary 20 /
no_generated_candidate 1 / selection_error 5`였고, reference file이 있던 113개
task에서도 reference fallback은 없었다. 최종 결과는 215 graded / 5 error,
평균 54.1%, critical item pass rate 0.528이었다. owner gold 20건의 Overall Style
비교는 bias -0.1625/5, MAE 1.2125/5였다.

이 결과는 **reference-selection 오염을 제거한 selector+audit baseline**이지
오류 없는 측정은 아니다. 10,453개 rubric item 중 `judge_error`가 355개였고,
그중 100개(max score 합계 164)가 53개 scored task에서 0점으로 남았다. 따라서
headline score는 이 오류 영향을 포함한다.

## 실행 및 provenance

| chunk | GitHub Actions run | workflow input head | 보존 output commit | 누적 task | 결과 |
|---:|---|---|---|---:|---|
| 0 | [`26905838943`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/26905838943) | `b6912ba` | `9c10cfb` | 46 | success |
| 1 | [`26918082612`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/26918082612) | `9c10cfb` | `31901ec` | 112 | success |
| 2 | [`26927591014`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/26927591014) | `31901ec` | `110f3bf` | 162 | success |
| 3 | [`26936567108`](https://github.com/hyeonsangjeon/gdpval-realworks/actions/runs/26936567108) | `110f3bf` | `cd085ea` | 220 | success |

- Workflow/config: `grade-run.yml` / `default_v2_mini.yaml`.
- Final grade JSON:
	[`data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json`](../../data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json).
- Auto-analysis:
	[`data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.analysis.md`](../../data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.analysis.md),
	commit `4d9a622`.
- Chunk 2의 보존 commit과 pushed head는
	`110f3bf604f62029fe12e5737b777687439e4b15`이다.

### 최종 규모와 비용 재구성

| metric | value |
|---|---:|
| total / graded / error tasks | 220 / 215 / 5 |
| judge calls | 8,904 |
| input / output tokens | 130,092,056 / 5,523,697 |
| cached input tokens | 70,480,128 |
| public-price raw estimate | $38.05 |
| cached-effective estimate | $29.24 |

비용은 grade JSON의 token usage와 당시 공개 단가로 auto-analysis가 재구성한
추정치다. JSON의 legacy `estimated_cost_usd` 필드는 0이므로 실제 청구액으로
해석하지 않는다.

## Selector 결과

### 전체 selection 분포

| status | tasks | interpretation |
|---|---:|---|
| `ok` | 194 | 생성된 deliverable target을 선택 |
| `wrong_format_primary` | 20 | 생성 파일은 있으나 요청 primary 형식과 불일치 |
| `no_generated_candidate` | 1 | reference set-diff 뒤 생성 후보 없음 |
| `selection_error` | 5 | harness가 결정적으로 선택하지 못해 task error 처리 |

### Reference file이 있던 113개 task

| subset | tasks |
|---|---:|
| `ok` generated target selected | 99 |
| `wrong_format_primary` | 10 |
| `selection_error` | 4 |

Reference files는 `reference_files_excluded`에 기록됐고 candidate deliverable로
fallback되지 않았다. 이것이 이 실험에서 말하는 “clean selector”의 정확한 범위다.

### Wrong-format primary 20개

`ff85ee58`, `e222075d`, `c94452e4`, `75401f7c`, `a941b6d8`,
`c7d83f01`, `b39a5aa7`, `327fbc21`, `a95a5829`, `9e39df84`,
`1752cb53`, `d4525420`, `a0552909`, `1e5a1d7f`, `6074bba3`,
`11593a50`, `a69be28f`, `15d37511`, `6a900a40`, `552b7dd0`.

| population | tasks | weighted pct | task-average pct |
|---|---:|---:|---:|
| all non-selection-error tasks | 215 | 53.09 | 55.36 |
| `ok` only | 194 | 58.46 | 61.35 |

두 population의 차이는 historical old-vs-new delta가 아니다. 같은 run에서
wrong/no-generated primary 실패를 score accounting에 포함했을 때의 차이다.

## Judge-error 한계

| category | items | score treatment |
|---|---:|---|
| `selection_error` task 내부 | 243 | excluded |
| `wrong_format_primary` task 내부 | 12 | excluded |
| `ok` task 내부 | 100 | **included as 0** |
| total | 355 | 255 excluded / 100 included |

Score-included judge error 100개는 53개 task에 분포하며 max score 합계는 164다.
따라서 이 baseline은 selector 동작과 audit 복구를 입증하지만, judge runtime 오류가
없는 품질 기준선은 아니다.

## Owner gold 20건 비교

Gold source는
[`docs/human-in-the-loop/overall-style-gold.json`](../../docs/human-in-the-loop/overall-style-gold.json)의
`overall_style_v1` 20건이다. 아래 `selected kind`는 gold의 `kind` 필드가 아니라
실제 `selected_paths` 확장자 조합이다.

| task | selected kind | owner | mini | delta | target scope | selected path(s) |
|---|---|---:|---:|---:|---|---|
| `83d10b06` | xlsx | 2.5 | 1.5 | -1.0 | file_target | `Sample.xlsx` |
| `7b08cd4d` | xlsx | 2.0 | 3.0 | +1.0 | file_target | `2024_Fall_Music_Tour_PnL_As_of_2024-12-31.xlsx` |
| `7d7fc9a7` | xlsx | 3.0 | 2.0 | -1.0 | file_target | `Aurisic_Prepaid_Amortization_Schedule_Through_Apr2025.xlsx` |
| `43dc9778` | pdf | 3.0 | 2.5 | -0.5 | file_target | `Smith_2024_Form_1040_Draft.pdf` |
| `ee09d943` | xlsx | 3.0 | 4.0 | +1.0 | file_target | `Aurisic_Financials_4-25-1.xlsx` |
| `27e8912c` | docx+pdf | 3.5 | 5.0 | +1.5 | split_children | `Organizational_Ergonomic_Action_Items.docx`; `Workstation_Ergonomics_Checklist.pdf` |
| `99ac6944` | pdf | 2.5 | 0.0 | -2.5 | file_target | `West_Coast_Tour_IEM_Mobile_Setup.pdf` |
| `7bbfcfe9` | xlsx | 4.0 | 2.0 | -2.0 | file_target | `SCRA_Compliance_Test_Questions.xlsx` |
| `f9a1c16c` | pdf | 3.0 | 3.0 | 0.0 | file_target | `Tour_Stage_Plot.pdf` |
| `bbe0a93b` | pdf | 3.0 | 0.0 | -3.0 | split_children | `Kent_County_Community_Resource_Guide.pdf`; `Kent_County_Needs_Assessment_English.pdf`; `Kent_County_Needs_Assessment_Espanol.pdf` |
| `85d95ce5` | pdf | 2.5 | 5.0 | +2.5 | file_target | `J.S..pdf` |
| `1b1ade2d` | docx | 4.0 | 5.0 | +1.0 | file_target | `Revised_Sourcing_and_Nomination_Workflow_Lamp_Assemblies.docx` |
| `93b336f3` | docx | 4.0 | 5.0 | +1.0 | file_target | `EV_Battery_Assembly_Localisation_Partnership_Proposal.docx` |
| `575f8679` | docx | 4.0 | 5.0 | +1.0 | file_target | `Immigration_and_Family_Stress_Evaluation_Plan.docx` |
| `0419f1c3` | docx | 4.0 | 5.0 | +1.0 | file_target | `Performance Improvement Plan – John Miller (07-13-2025).docx` |
| `6dcae3f5` | docx+xlsx | 2.0 | 1.75 | -0.25 | split_children | `Chief Key Indicator 5-Year.xlsx`; `Email_to_PD_Key_Indicator_Analysis.docx` |
| `a74ead3b` | pptx | 3.0 | 2.75 | -0.25 | split_children | `Session_13_Nurturing_Parenting_Recovery.pptx`; `Session_14_Nurturing_Parenting_Recovery.pptx` |
| `ec591973` | pptx | 2.5 | 3.0 | +0.5 | file_target | `Differentiated_Distribution_Strategy_Slide.pptx` |
| `9a0d8d36` | pptx | 3.5 | 2.0 | -1.5 | file_target | `ISO_vs_NQSO_Tax_Comparison.pptx` |
| `403b9234` | pptx | 3.5 | 1.75 | -1.75 | file_target | `Chamber_of_Commerce_Partnership_Proposal.pptx` |

Overall bias는 -0.1625/5, MAE는 1.2125/5다. 평균 bias가 작아 보이는 것은
under/over-score가 상쇄되기 때문이며 개별 오차는 크다.

| selected kind | n | owner mean | mini mean | bias | MAE |
|---|---:|---:|---:|---:|---:|
| docx | 4 | 4.00 | 5.00 | +1.00 | 1.00 |
| docx+pdf | 1 | 3.50 | 5.00 | +1.50 | 1.50 |
| docx+xlsx | 1 | 2.00 | 1.75 | -0.25 | 0.25 |
| pdf | 5 | 2.80 | 2.10 | -0.70 | 1.70 |
| pptx | 4 | 3.12 | 2.38 | -0.75 | 1.00 |
| xlsx | 5 | 2.90 | 2.50 | -0.40 | 1.20 |

## Perception 범위와 후속 실험

이 run의 routing 분포는 text 8,034 / formatting 415 / visual 337 / audio 58 /
unclassified 1,609였다. `perception_called=false`는 formatting 415개 전체,
visual 337개 중 232개, audio 58개 전체였다. 이는 visual/audio perception call이
없었다는 뜻이지, judge가 반드시 “metadata only”였다는 뜻은 아니다. tool loop는
`read_deliverable`의 content/structure/formatting 관찰을 사용할 수 있었다.

당시의 광범위 render 확대 가설은 후속 측정에서 지지되지 않았다.

- [`vision_validation.md`](../0607_sunday/vision_validation.md): 동일 GPT-5.4에서
	meta-only MAE 0.852 → render+vision 0.848(Δ -0.004, 사실상 null). XLSX는
	+0.100 악화, PPTX는 -0.062 개선이었다. 따라서 전체 modality 렌더가 아니라
	PPTX 선별 검토와 XLSX 렌더 범위 개선이 후속 결론이다.
- [`full_regrade_220_gpt54.md`](../0607_sunday/full_regrade_220_gpt54.md):
	GPT-5.4 full baseline도 동일 selector 분포를 재현했다. 결과는 215/220,
	평균 53.3%, critical pass 0.501, gold Overall Style MAE 1.261이었다. 즉 모델만
	바꾸어 full-pipeline MAE가 자동 개선되지는 않았다.
- 현재 production grading default는 `default_v2_sol_max.yaml`의 GPT-5.6 Sol Max다.
	이 mini run은 현재 정책이 아니라 역사 비교 baseline이다.

## Audit 완전성

Task-level 필수 필드 `selected_deliverables`, `reference_files_excluded`,
`selection_rule`, `selection_status`는 220개 모두 존재한다.

10,453개 item에서 `target_scope`, `target_ids`, `child_grades`,
`aggregation_rule`, `selected_paths`, `support_paths_visible`,
`selection_status`, `score_excluded` 누락은 모두 0이다.

| target scope | items |
|---|---:|
| file_target | 7,224 |
| selection_error | 1,207 |
| primary_bundle | 1,082 |
| manifest | 918 |
| split_children | 22 |

22개 split item은 모두 `child_grades`와
`aggregation_rule=blocking_min_else_mean`을 보존한다. 이 audit surface로 당시
judge가 어떤 target을 보았는지 후속 분석에서 재구성할 수 있다.

## 역사적 사용 지침

1. 이 JSON은 reference fallback을 제거한 mini selector+audit baseline으로 보존한다.
2. 54.1% headline에는 100개의 score-included judge error가 포함돼 있으므로 오류 없는
	 judge 품질 수치로 인용하지 않는다.
3. old contaminated v2 headline과 apples-to-apples delta로 비교하지 않는다.
4. broad render rollout과 “다음에 GPT-5.4 실행”은 이미 후속 실험으로 해소됐으므로
	 미완료 action으로 남기지 않는다.
5. 재현 시 historical identity인 `default_v2_mini.yaml`을 명시적으로 선택한다.
