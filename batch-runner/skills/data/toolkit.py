"""Data skill toolkit — load / describe / chart / model tabular data.

Heavy libraries (pandas, numpy, matplotlib, scikit-learn) are imported lazily so
importing this module never fails.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from skills import _require

__all__ = [
    "read_table",
    "describe",
    "quick_chart",
    "correlation",
    "linreg",
]


def read_table(path: str, **kw):
    """Load a tabular file into a pandas DataFrame, dispatching by extension."""
    pd = _require("pandas", "pandas")
    ext = Path(path).suffix.lower()
    if ext in (".csv", ".tsv"):
        sep = "\t" if ext == ".tsv" else kw.pop("sep", ",")
        return pd.read_csv(path, sep=sep, **kw)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path, **kw)
    if ext == ".parquet":
        return pd.read_parquet(path, **kw)
    if ext == ".json":
        return pd.read_json(path, **kw)
    return pd.read_csv(path, **kw)


def describe(df) -> dict:
    """Compact, JSON-friendly summary of a DataFrame."""
    numeric = df.select_dtypes("number")
    return {
        "shape": list(df.shape),
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(c): str(t) for c, t in df.dtypes.items()},
        "numeric": {
            str(c): {
                "min": float(numeric[c].min()) if not numeric[c].empty else None,
                "max": float(numeric[c].max()) if not numeric[c].empty else None,
                "mean": float(numeric[c].mean()) if not numeric[c].empty else None,
            }
            for c in numeric.columns
        },
        "null_counts": {str(c): int(df[c].isna().sum()) for c in df.columns},
    }


def quick_chart(df, x, y=None, kind: str = "line", out: str = "chart.png",
                title: Optional[str] = None) -> str:
    """Render a quick chart to PNG and return its path."""
    _require("matplotlib", "matplotlib")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))
    if kind == "hist":
        df[x].plot(kind="hist", ax=ax)
    elif y is None:
        df[x].plot(kind=kind, ax=ax)
    else:
        df.plot(x=x, y=y, kind=kind, ax=ax)
    ax.set_title(title or f"{kind} chart")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def correlation(df, out: Optional[str] = None) -> dict:
    """Numeric correlation matrix, optionally rendered to a heatmap PNG."""
    numeric = df.select_dtypes("number")
    corr = numeric.corr()
    if out:
        _require("matplotlib", "matplotlib")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 7))
        im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=90)
        ax.set_yticks(range(len(corr.columns)))
        ax.set_yticklabels(corr.columns)
        fig.colorbar(im, ax=ax)
        fig.tight_layout()
        fig.savefig(out, dpi=120)
        plt.close(fig)
    return {str(c): {str(k): round(float(v), 4) for k, v in row.items()}
            for c, row in corr.to_dict().items()}


def linreg(df, x, y) -> dict:
    """Fit a 1-D ordinary least squares regression of ``y`` on ``x``."""
    np = _require("numpy", "numpy")
    _require("sklearn", "scikit-learn")
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import r2_score

    sub = df[[x, y]].dropna()
    xv = sub[[x]].to_numpy(dtype=float)
    yv = sub[y].to_numpy(dtype=float)
    model = LinearRegression().fit(xv, yv)
    pred = model.predict(xv)
    return {
        "slope": float(model.coef_[0]),
        "intercept": float(model.intercept_),
        "r2": float(r2_score(yv, pred)),
        "n": int(len(sub)),
        "predict_fn_repr": f"y = {float(model.coef_[0]):.6g} * {x} + {float(model.intercept_):.6g}",
    }
