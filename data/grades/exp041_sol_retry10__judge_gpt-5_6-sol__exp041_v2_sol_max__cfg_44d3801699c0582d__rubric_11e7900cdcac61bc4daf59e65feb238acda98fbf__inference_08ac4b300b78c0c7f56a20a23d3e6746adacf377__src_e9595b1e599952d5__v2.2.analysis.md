# Grade Run Analysis — exp041_sol_retry10

- file: `data/grades/exp041_sol_retry10__judge_gpt-5_6-sol__exp041_v2_sol_max__cfg_44d3801699c0582d__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_08ac4b300b78c0c7f56a20a23d3e6746adacf377__src_e9595b1e599952d5__v2.2.json`
- config: `exp041_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 10/10 (errors=0)

## Quality
- avg_score_pct: **89.57**
- critical_item_pass_rate: **0.8333**
- judge_pass_rate: 0.84
- judge_error_rate: 0.0018
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-11-27T10:23:06+00:00 → 2026-11-27T12:54:11+00:00
- **wall-clock**: 151.1 min
- sum judge latency: 157.0 min (concurrency factor ≈ 1.04x)
- per-task: avg=942.0s, p50=936.1s, p95=1449.6s

## Volume
- total API calls: 1569 (main=1533, perception=36)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=7,804,053  out=517,990
- main tokens: in=7,703,732 out=507,363; perception tokens: in=100,321 out=10,627
- render: calls=36, latency=0.7 min; usage_complete=True
- per-task avg (in,out): (780405, 51799)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `2fa8e956-7b35-4c13-95dc-027f02be318b` | 431.22 | 68 / 308077,20982,180674 / 402.82s | 3 / 8150,1091,0 / 22.53s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `46b34f78-6c06-4416-87e2-77b6d8b20ce9` | 860.18 | 115 / 732050,50941,297414 / 831.2s | 3 / 8141,822,0 / 21.19s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `4c18ebae-dfaa-4b76-b10c-61fcdf26734c` | 965.42 | 135 / 1357237,58164,639729 / 955.52s | 1 / 2709,254,0 / 5.41s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | required_visual_perception_failed:1 |
| `5a2d70da-0a42-4a6b-a3ca-763e03f070a5` | 1267.34 | 209 / 878123,70165,535981 / 1266.09s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `efca245f-c24f-4f75-a9d5-59201330ab7a` | 1454.86 | 207 / 1268291,82217,568646 / 1442.18s | 1 / 5212,417,0 / 7.39s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `f1be6436-ffff-4fee-9e66-d550291a1735` | 1135.82 | 138 / 697307,60161,441698 / 1010.38s | 17 / 46236,3891,0 / 95.53s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `f2986c1f-2bbf-4b83-bc93-624a9d617f45` | 916.27 | 222 / 717743,38393,506647 / 890.16s | 3 / 8162,1060,0 / 21.04s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `f3351922-dbdd-45da-85c5-e7110696bbe5` | 721.58 | 149 / 562919,36951,314403 / 721.52s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `f5d428fd-b38e-41f0-8783-35423dab80f6` | 586.14 | 84 / 384356,27950,208669 / 514.98s | 7 / 19012,2751,0 / 59.13s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `f841ddcf-2a28-4f6d-bac3-61b607219d3e` | 1156.42 | 206 / 797629,61439,535393 / 1144.23s | 1 / 2699,341,0 / 9.16s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |

- judge_error_types: required_visual_perception_failed:1
- projected_220_wall_hours: 58.03 (at_or_above_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol)
- effective (cached-discounted): unpriced (gpt-5.6-sol)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `efca245f-c24f-4f75-a9d5-59201330ab7a` | 1449.6 | 208 | (1273503, 82634) | 97.55 | False |
| `5a2d70da-0a42-4a6b-a3ca-763e03f070a5` | 1266.1 | 209 | (878123, 70165) | 90.38 | False |
| `f841ddcf-2a28-4f6d-bac3-61b607219d3e` | 1153.4 | 207 | (800328, 61780) | 97.5 | False |
| `f1be6436-ffff-4fee-9e66-d550291a1735` | 1105.9 | 155 | (743543, 64052) | 69.32 | False |
| `4c18ebae-dfaa-4b76-b10c-61fcdf26734c` | 960.9 | 136 | (1359946, 58418) | 92.9 | False |
