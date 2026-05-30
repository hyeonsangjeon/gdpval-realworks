# PR3 Step 3 — Paired quality v2 vs v1 (N=10)

## Per-task pct table

| task_id | v2 | v1h | v1m | Δ v2-h | Δ v2-m | crit v2 | crit v1h |
|---|--:|--:|--:|--:|--:|--:|--:|
| `17111c03` | 88.7 | 85.6 | 86.6 | +3.12 | +2.13 | 1.000 | 1.000 |
| `27e8912c` | 82.3 | 76.4 | 84.9 | +5.84 | -2.65 | 0.000 | 0.000 |
| `43dc9778` | 12.2 | 11.2 | 16.6 | +1.07 | -4.38 | 0.000 | 0.000 |
| `7b08cd4d` | 15.1 | 46.5 | 36.5 | -31.40 | -21.43 | 0.000 | 0.000 |
| `7d7fc9a7` | 42.0 | 31.2 | 35.7 | +10.84 | +6.32 | 0.000 | 0.000 |
| `83d10b06` | 50.0 | 27.8 | 40.8 | +22.22 | +9.21 | 0.000 | 0.000 |
| `a328feea` | 81.2 | 81.7 | 85.0 | -0.42 | -3.75 | 1.000 | 1.000 |
| `c44e9b62` | 57.0 | 64.8 | 66.6 | -7.79 | -9.67 | 0.667 | 0.750 |
| `ee09d943` | 58.0 | 39.8 | 46.6 | +18.22 | +11.36 | 1.000 | 0.000 |
| `f84ea6ac` | 85.6 | 77.4 | 77.1 | +8.17 | +8.53 | 0.667 | 0.667 |

## Aggregate

|  | mean Δ | 95% CI (bootstrap) | sign test (pos/neg) | sign p-value | Wilcoxon W+ |
|---|--:|---|--:|--:|--:|
| v2 − v1 hybrid | +2.99 | [-6.23, +10.87] | 7/3 | 0.344 | 39.0 |
| v2 − v1 mini   | -0.43 | [-6.66, +5.10] | 5/5 | 1.000 | 28.0 |

## Critical-item non-inferiority

- v2 mean crit pass rate: **0.433**
- v1 hybrid mean crit pass rate: 0.342  → non-inferior (margin 5pp): **True**
- v1 mini mean crit pass rate: 0.583  → non-inferior (margin 5pp): **False**

## Verdict

- **lift verdict: `inconclusive`**
- **critical_item_noninferior** (vs v1h): `True`
- **critical_item_noninferior** (vs v1m): `False`

Significance rule: `sign_p < 0.10 AND bootstrap_lower_CI > 0`.
Non-inferiority margin: 5pp absolute.