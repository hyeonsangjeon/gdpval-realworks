# PR3 Step 3 — Paired quality v2 vs v1 (N=10)

## Per-task pct table

| task_id | v2 | v1h | v1m | Δ v2-h | Δ v2-m | crit v2 | crit v1h |
|---|--:|--:|--:|--:|--:|--:|--:|
| `17111c03` | 90.3 | 85.6 | 86.6 | +4.76 | +3.77 | 1.000 | 1.000 |
| `27e8912c` | 83.4 | 76.4 | 84.9 | +6.98 | -1.51 | 0.000 | 0.000 |
| `43dc9778` | 10.8 | 11.2 | 16.6 | -0.33 | -5.78 | 0.000 | 0.000 |
| `7b08cd4d` | 13.0 | 46.5 | 36.5 | -33.48 | -23.51 | 0.000 | 0.000 |
| `7d7fc9a7` | 44.1 | 31.2 | 35.7 | +12.95 | +8.43 | 0.000 | 0.000 |
| `83d10b06` | 53.3 | 27.8 | 40.8 | +25.55 | +12.54 | 0.000 | 0.000 |
| `a328feea` | 83.8 | 81.7 | 85.0 | +2.08 | -1.25 | 1.000 | 1.000 |
| `c44e9b62` | 55.4 | 64.8 | 66.6 | -9.35 | -11.23 | 0.583 | 0.750 |
| `ee09d943` | 48.2 | 39.8 | 46.6 | +8.47 | +1.61 | 0.000 | 0.000 |
| `f84ea6ac` | 84.2 | 77.4 | 77.1 | +6.79 | +7.15 | 0.667 | 0.667 |

## Aggregate

|  | mean Δ | 95% CI (bootstrap) | sign test (pos/neg) | sign p-value | Wilcoxon W+ |
|---|--:|---|--:|--:|--:|
| v2 − v1 hybrid | +2.44 | [-7.20, +10.67] | 7/3 | 0.344 | 37.0 |
| v2 − v1 mini   | -0.98 | [-7.47, +4.69] | 5/5 | 1.000 | 29.0 |

## Critical-item non-inferiority

- v2 mean crit pass rate: **0.325**
- v1 hybrid mean crit pass rate: 0.342  → non-inferior (margin 5pp): **True**
- v1 mini mean crit pass rate: 0.583  → non-inferior (margin 5pp): **False**

## Verdict

- **lift verdict: `inconclusive`**
- **critical_item_noninferior** (vs v1h): `True`
- **critical_item_noninferior** (vs v1m): `False`

Significance rule: `sign_p < 0.10 AND bootstrap_lower_CI > 0`.
Non-inferiority margin: 5pp absolute.