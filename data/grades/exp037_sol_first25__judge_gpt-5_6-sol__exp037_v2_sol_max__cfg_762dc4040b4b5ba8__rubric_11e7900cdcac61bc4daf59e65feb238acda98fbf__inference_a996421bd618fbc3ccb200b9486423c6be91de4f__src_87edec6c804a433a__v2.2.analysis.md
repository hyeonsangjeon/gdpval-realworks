# Grade Run Analysis — exp037_sol_first25

- file: `data/grades/exp037_sol_first25__judge_gpt-5_6-sol__exp037_v2_sol_max__cfg_762dc4040b4b5ba8__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_a996421bd618fbc3ccb200b9486423c6be91de4f__src_87edec6c804a433a__v2.2.json`
- config: `exp037_v2_sol_max` (model=gpt-5.6-sol, effort=max)
- tasks: 24/25 (errors=1)

## Quality
- avg_score_pct: **88.55**
- critical_item_pass_rate: **0.6716**
- judge_pass_rate: 0.7726
- judge_error_rate: 0.0207
- precheck_pass_rate: 0.0

## Wall-clock & latency
- first→last graded_at: 2026-11-12T16:14:51+00:00 → 2026-11-13T05:42:49+00:00
- **wall-clock**: 808.0 min
- sum judge latency: 455.4 min (concurrency factor ≈ 0.56x)
- per-task: avg=1093.0s, p50=836.5s, p95=2418.8s

## Volume
- total API calls: 2965 (main=2933, perception=32)  |  precheck decisions: 0  (judge share 100.0%)
- tokens: in=14,289,558  out=917,979
- main tokens: in=14,220,096 out=911,095; perception tokens: in=69,462 out=6,884
- render: calls=23, latency=0.2 min; usage_complete=False
- per-task avg (in,out): (571582, 36719)

## Task anchors
| task_id | wall (s) | main calls/tokens/latency | visual calls/tokens/latency | audio calls/tokens/latency | unknown perception calls/tokens/latency | judge errors |
|---|--:|---|---|---|---|---|
| `0ed38524-a4ad-405f-9dee-7b2252659aad` | 1371.79 | 71 / 242619,27688,165770 / 1366.28s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `01d7e53e-0513-4109-a242-8ccaf442cd21` | 996.17 | 132 / 854264,39049,286165 / 992.72s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `0112fc9b-c3b2-4084-8993-5a4abb1f54f1` | 738.41 | 113 / 390286,20735,242331 / 726.54s | 1 / 2701,141,0 / 8.04s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `38889c3b-e3d4-49c8-816a-3cc8e5313aba` | 1075.95 | 96 / 294374,23818,242752 / 1040.53s | 0 / 0,0,0 / 0.0s | 10 / 6063,701,0 / 31.89s | 0 / 0,0,0 / 0.0s | RateLimitError:2, audio_perception_failed:2 |
| `05389f78-589a-473c-a4ae-67c61050bfca` | 3085.36 | 151 / 500217,53092,334858 / 3080.76s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `02aa1805-c658-4069-8a6a-02dec146063a` | 2251.15 | 213 / 621706,45762,495744 / 2247.94s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | RateLimitError:2, required_visual_render_failed:2 |
| `0419f1c3-d669-45d0-81cd-f4d5923b06a5` | 2141.86 | 93 / 258836,30711,187657 / 2139.6s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | RateLimitError:18 |
| `105f8ad0-8dd2-422f-9e88-2be5fbd2b215` | 1395.9 | 158 / 912415,52318,489534 / 1372.56s | 1 / 2699,440,0 / 17.53s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `02314fc6-a24e-42f4-a8cd-362cae0f0ec1` | 497.33 | 58 / 567894,14324,149626 / 439.22s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `1d4672c8-b0a7-488f-905f-9ab4e25a19f7` | 1489.71 | 112 / 494479,44787,323494 / 1464.09s | 1 / 2709,233,0 / 10.51s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `11e1b169-5fb6-4d79-8a83-82ddf4987a85` | 0.0 | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `0353ee0c-18b5-4ad3-88e8-e001d223e1d7` | 2555.35 | 154 / 1455645,80635,366103 / 2409.39s | 1 / 2699,203,0 / 9.44s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `3a4c347c-4aec-43c7-9a54-eb1f816ab1f9` | 1211.0 | 117 / 531249,36019,279493 / 1207.23s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `11dcc268-cb07-4d3a-a184-c6d7a19349bc` | 838.49 | 85 / 255005,23655,201632 / 823.46s | 1 / 2699,281,0 / 13.05s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `0e386e32-df20-4d1f-b536-7159bc409ad5` | 885.98 | 201 / 1302449,67673,862936 / 1523.91s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `0818571f-5ff7-4d39-9d2c-ced5ae44299e` | 625.46 | 93 / 782947,32874,406884 / 568.53s | 2 / 5398,1636,0 / 25.27s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `1137e2bb-bdf9-4876-b572-f29b7de5e595` | 881.33 | 211 / 797956,40575,573982 / 878.94s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `045aba2e-4093-42aa-ab7f-159cc538278c` | 522.58 | 88 / 338842,28837,227925 / 495.89s | 3 / 8097,779,0 / 17.87s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `3600de06-3f71-4e48-9480-e4828c579924` | 620.7 | 90 / 371641,40792,204248 / 609.92s | 1 / 2940,320,0 / 5.78s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `17111c03-aac7-45c2-857d-c06d8223d6ad` | 530.84 | 115 / 417331,24987,282696 / 526.16s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `0ec25916-1b5c-4bfe-93d3-4e103d860f3a` | 797.34 | 126 / 495389,45162,366932 / 787.49s | 1 / 2777,248,0 / 5.24s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `3baa0009-5a60-4ae8-ae99-4955cb328ff3` | 530.04 | 98 / 292088,24752,212052 / 488.41s | 9 / 25329,1484,0 / 40.07s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `15ddd28d-8445-4baa-ac7f-f41372e1344e` | 600.66 | 96 / 420898,39715,202397 / 598.57s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `2c249e0f-4a8c-4f8e-b4f4-6508ba29b34f` | 616.96 | 107 / 966849,34841,242185 / 616.9s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |
| `0e4fe8cd-16d0-4f41-8247-6385b4762582` | 739.5 | 155 / 654717,38294,434687 / 728.07s | 1 / 5351,418,0 / 8.05s | 0 / 0,0,0 / 0.0s | 0 / 0,0,0 / 0.0s | none |

- judge_error_types: RateLimitError:22, audio_perception_failed:2, required_visual_render_failed:2
- projected_220_wall_hours: 66.0 (at_or_above_44h_envelope; method=task_count_fallback)

## Cost estimate
- raw: unpriced (gpt-5.6-sol,gpt-audio-1.5)
- effective (cached-discounted): unpriced (gpt-5.6-sol,gpt-audio-1.5)

## Top-5 slowest tasks
| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |
|---|--:|--:|--|--:|---|
| `05389f78-589a-473c-a4ae-67c61050bfca` | 3080.8 | 151 | (500217, 53092) | 93.94 | True |
| `0353ee0c-18b5-4ad3-88e8-e001d223e1d7` | 2418.8 | 155 | (1458344, 80838) | 98.76 | False |
| `02aa1805-c658-4069-8a6a-02dec146063a` | 2247.9 | 213 | (621706, 45762) | 98.54 | False |
| `0419f1c3-d669-45d0-81cd-f4d5923b06a5` | 2139.6 | 93 | (258836, 30711) | 86.14 | False |
| `0e386e32-df20-4d1f-b536-7159bc409ad5` | 1523.9 | 201 | (1302449, 67673) | 91.6 | False |
