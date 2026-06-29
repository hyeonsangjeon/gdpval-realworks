---
name: data
title: Tabular Data Analysis
description: >-
  Spreadsheet / tabular analysis and charting. Use for any task with tabular
  reference files (.csv/.xlsx/.parquet/.tsv/.json) or that asks to analyze,
  aggregate, model, forecast, or visualize data. Wraps pandas, numpy,
  matplotlib, and scikit-learn for loading, describing, charting, correlation,
  and quick linear regression.
modalities: [data]
file_extensions: [".csv", ".tsv", ".xlsx", ".xls", ".parquet", ".json"]
keywords:
  [data, dataset, table, csv, excel, spreadsheet, dataframe, analysis,
   analytics, statistics, aggregate, pivot, chart, plot, graph, histogram,
   correlation, regression, forecast, trend, kpi, metric, model, predict]
requires: [pandas, numpy, matplotlib, scikit-learn]
version: 1.0.0
---

# Data Skill — analyze & visualize tables

Use this skill to load tabular reference files robustly and turn them into
analysis + charts for the deliverable.

A typical "data problem" workflow:

1. `df = data.read_table(path)` — load CSV/XLSX/Parquet/JSON into a DataFrame.
2. `summary = data.describe(df)` — shape, dtypes, numeric stats, nulls.
3. `data.quick_chart(df, x, y, kind="bar", out="chart.png")` — a shippable PNG.
4. (optional) `data.correlation(df)` / `data.linreg(df, x, y)` for modelling.

## Toolkit API

```python
from skills import data

data.read_table(path, **kw) -> pandas.DataFrame   # dispatch by extension
data.describe(df) -> dict        # {shape, columns, dtypes, numeric, null_counts}
data.quick_chart(df, x, y=None, kind="line", out="chart.png", title=None) -> str
data.correlation(df, out=None) -> dict   # numeric correlation matrix (+ optional PNG)
data.linreg(df, x, y) -> dict    # {slope, intercept, r2, predict_fn_repr}
```

Notes:
- `read_table` always returns a real `pandas.DataFrame` — inspect
  `df.columns`/`df.dtypes` before assuming names (never hardcode columns).
- Charts render headless (Agg backend); always `out=` to a file.
