# PR3 Step 3 — Paired quality v2 vs v1 (N=10)

## Per-task pct table

| task_id | v2 | v1h | v1m | Δ v2-h | Δ v2-m | crit v2 | crit v1h |
|---|--:|--:|--:|--:|--:|--:|--:|
| `17111c03` | 88.8 | 88.7 | 86.6 | +0.16 | +2.29 | 1.000 | 1.000 |
| `27e8912c` | 82.1 | 82.3 | 84.9 | -0.18 | -2.83 | 0.000 | 0.000 |
| `43dc9778` | 14.9 | 12.2 | 16.6 | +2.65 | -1.73 | 0.000 | 0.000 |
| `7b08cd4d` | 12.6 | 15.1 | 36.5 | -2.48 | -23.91 | 0.000 | 0.000 |
| `7d7fc9a7` | 41.6 | 42.0 | 35.7 | -0.42 | +5.90 | 0.000 | 0.000 |
| `83d10b06` | 50.6 | 50.0 | 40.8 | +0.63 | +9.84 | 0.000 | 0.000 |
| `a328feea` | 93.3 | 81.2 | 85.0 | +12.08 | +8.33 | 1.000 | 1.000 |
| `c44e9b62` | 61.9 | 57.0 | 66.6 | +4.88 | -4.79 | 0.667 | 0.667 |
| `ee09d943` | 59.0 | 58.0 | 46.6 | +1.01 | +12.37 | 1.000 | 1.000 |
| `f84ea6ac` | 90.0 | 85.6 | 77.1 | +4.40 | +12.93 | 0.667 | 0.667 |

## Aggregate

|  | mean Δ | 95% CI (bootstrap) | sign test (pos/neg) | sign p-value | Wilcoxon W+ |
|---|--:|---|--:|--:|--:|
| v2 − v1 hybrid | +2.27 | [+0.19, +5.02] | 7/3 | 0.344 | 44.0 |
| v2 − v1 mini   | +1.84 | [-5.16, +7.61] | 6/4 | 0.754 | 37.0 |

## Critical-item non-inferiority

- v2 mean crit pass rate: **0.433**
- v1 hybrid mean crit pass rate: 0.433  → non-inferior (margin 5pp): **True**
- v1 mini mean crit pass rate: 0.583  → non-inferior (margin 5pp): **False**

## Verdict

- **lift verdict: `inconclusive`**
- **critical_item_noninferior** (vs v1h): `True`
- **critical_item_noninferior** (vs v1m): `False`

Significance rule: `sign_p < 0.10 AND bootstrap_lower_CI > 0`.
Non-inferiority margin: 5pp absolute.