# 220-Task Criterion Modality Distribution

## One-Line Verdict

**visual+audio 비중은 작음**: 전체 rubric item 기준 **534/10,453 = 5.11%**, critical item 기준 **29/483 = 6.00%**. 따라서 기존 19-item hand-grade는 **한계적**이다. visual/audio slice의 정확도 sanity check로는 값어치가 있지만, v2 default flip을 정당화하는 benchmark-wide 근거로는 작다.

## Source And Method

- Source rubric surface: `data/grades/exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-mini__11e7900__v1__v2sm.json` from existing full-220 exp003 grade JSON. All four full-220 exp003 grade JSONs have the same **220 tasks / 10,453 rubric items / 483 critical items**.
- Classifier: imported `classify_criterion` directly from `batch-runner/core/grader_routing.py`; no keyword replication. `grader_routing.py` has no diff between `main` and current `feat/wire-perception` branch.
- Critical rule: `abs(max_score) >= 4`.
- Routing priority: visual > audio > formatting > text, exactly as `classify_criterion` implements.

## Overall Distribution

| modality | count | share |
|---|--:|--:|
| visual | 414 | 3.96% |
| audio | 120 | 1.15% |
| formatting | 539 | 5.16% |
| text | 9,380 | 89.74% |
| **visual+audio** | **534** | **5.11%** |

## Critical-Item Distribution

| modality | count | share |
|---|--:|--:|
| visual | 12 | 2.48% |
| audio | 17 | 3.52% |
| formatting | 157 | 32.51% |
| text | 297 | 61.49% |
| **visual+audio** | **29** | **6.00%** |

## Visual/Audio Task Coverage

| coverage | tasks | share of 220 |
|---|--:|--:|
| any visual item | 98 | 44.55% |
| any audio item | 28 | 12.73% |
| any visual or audio item | **106** | **48.18%** |
| both visual and audio items | 20 | 9.09% |
| any critical visual/audio item | 7 | 3.18% |

Among the 106 tasks with at least one visual/audio criterion, per-task visual+audio item counts are: `1 item`=34, `2 items`=21, `3-5`=26, `6-10`=13, `>10`=12. Median covered task has **2** visual/audio items. Critical visual/audio is concentrated in **7 tasks** (5 visual-critical tasks, 2 audio-critical tasks, no overlap).

## Sector Top 5 By Visual+Audio Share

| sector | visual+audio | total items | VA share | visual | audio | VA tasks / tasks | critical VA / critical |
|---|--:|--:|--:|--:|--:|--:|--:|
| Information | 199 | 1,045 | 19.04% | 101 | 98 | 21/25 | 22/85 (25.88%) |
| Health Care and Social Assistance | 65 | 1,261 | 5.15% | 58 | 7 | 14/25 | 0/36 (0.00%) |
| Government | 51 | 1,097 | 4.65% | 50 | 1 | 6/25 | 5/62 (8.06%) |
| Wholesale Trade | 51 | 1,243 | 4.10% | 50 | 1 | 13/25 | 0/34 (0.00%) |
| Manufacturing | 53 | 1,348 | 3.93% | 53 | 0 | 13/25 | 0/51 (0.00%) |

## Occupation Top 5 By Visual+Audio Share

| occupation | visual+audio | total items | VA share | visual | audio | VA tasks / tasks | critical VA / critical |
|---|--:|--:|--:|--:|--:|--:|--:|
| Audio and Video Technicians | 80 | 191 | 41.88% | 27 | 53 | 5/5 | 16/21 (76.19%) |
| Producers and Directors | 48 | 194 | 24.74% | 41 | 7 | 5/5 | 4/38 (10.53%) |
| Film and Video Editors | 36 | 180 | 20.00% | 8 | 28 | 5/5 | 0/12 (0.00%) |
| Recreation Workers | 37 | 222 | 16.67% | 36 | 1 | 3/5 | 0/11 (0.00%) |
| Sales Managers | 24 | 201 | 11.94% | 24 | 0 | 2/5 | 0/5 (0.00%) |

## Interpretation

- The benchmark is overwhelmingly text/formatting by item count: text alone is **89.74%**, and text+formatting is **94.89%**.
- Perception-relevant visual/audio items are broadly scattered across tasks (**106/220** tasks), but usually shallow: median covered task has **2** such items.
- Critical visual/audio is tiny and concentrated: **29** items across **7** tasks. By contrast, critical formatting alone has **157** items (**32.51%** of critical), which perception sub-judges do not address.
- If hand-grading proceeds, the candidate set should be revised toward the **29 critical visual/audio items across the 7 affected tasks**, especially the Information/audio cluster, rather than treating the old 19-item shared-slice set as benchmark-representative.
