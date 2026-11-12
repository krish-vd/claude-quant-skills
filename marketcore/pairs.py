"""Pair analysis: hedge ratio, cointegration test, half-life and spread z-score.

Engle-Granger two-step method on log prices: regress log(A) on log(B), then run an
augmented Dickey-Fuller test (constant, one lagged difference) on the residual. The
statistic is compared with the asymptotic Engle-Granger critical values for two
variables with a constant (MacKinnon): 1% -3.90, 5% -3.34, 10% -3.05.

Pure Python, no external libraries.
"""
from __future__ import annotations

import math
from itertools import combinations
from typing import Optional

CRITICAL = {"1%": -3.90, "5%": -3.34, "10%": -3.05}


def ols(y: list[float], xs: list[list[float]]) -> tuple[list[float], list[float], list[float]]:
    """Least squares with an intercept. Returns (coefficients [intercept, b1, ...], standard errors, residuals)."""
    n, k = len(y), len(xs) + 1
    rows = [[1.0] + [x[i] for x in xs] for i in range(n)]
    xtx = [[sum(r[a] * r[b] for r in rows) for b in range(k)] for a in range(k)]
    xty = [sum(r[a] * y[i] for i, r in enumerate(rows)) for a in range(k)]
    inv = _invert(xtx)
    beta = [sum(inv[a][b] * xty[b] for b in range(k)) for a in range(k)]
    resid = [y[i] - sum(beta[a] * rows[i][a] for a in range(k)) for i in range(n)]
    dof = n - k
    s2 = sum(e * e for e in resid) / dof if dof > 0 else float("nan")
    se = [math.sqrt(max(inv[a][a] * s2, 0.0)) for a in range(k)]
    return beta, se, resid


def _invert(m: list[list[float]]) -> list[list[float]]:
    size = len(m)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(size)] for i, row in enumerate(m)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-15:
            raise ValueError("singular matrix: the series are constant or perfectly collinear")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        p = aug[col][col]
        aug[col] = [v / p for v in aug[col]]
        for r in range(size):
            if r != col and aug[r][col]:
                f = aug[r][col]
                aug[r] = [a - f * b for a, b in zip(aug[r], aug[col])]
    return [row[size:] for row in aug]


def adf_statistic(series: list[float]) -> float:
    """t-statistic of gamma in: diff(e)_t = c + gamma * e_{t-1} + phi * diff(e)_{t-1}."""
    d = [series[i] - series[i - 1] for i in range(1, len(series))]
    y = d[1:]
    lag_level = series[1:-1]
    lag_diff = d[:-1]
    beta, se, _ = ols(y, [lag_level, lag_diff])
    return beta[1] / se[1] if se[1] > 0 else float("nan")


def half_life(spread: list[float]) -> Optional[float]:
    """Sessions for a deviation to halve, from diff(s)_t = c + k * s_{t-1}. None if not mean-reverting."""
    d = [spread[i] - spread[i - 1] for i in range(1, len(spread))]
    beta, _, _ = ols(d, [spread[:-1]])
    k = beta[1]
    if k >= 0:
        return None
    return math.log(2) / -math.log(1 + k) if k > -1 else 0.0


def analyse_pair(a: list[float], b: list[float], zscore_window: int = 60) -> dict:
    """Cointegration of two aligned price series (positive)."""
    if len(a) != len(b) or len(a) < max(100, zscore_window + 10):
        raise ValueError("need two aligned series of at least 100 points")
    la, lb = [math.log(x) for x in a], [math.log(x) for x in b]
    beta, _, resid = ols(la, [lb])
    stat = adf_statistic(resid)
    recent = resid[-zscore_window:]
    mean = sum(recent) / len(recent)
    sd = math.sqrt(sum((r - mean) ** 2 for r in recent) / (len(recent) - 1))
    z = (resid[-1] - mean) / sd if sd > 0 else 0.0
    n = len(la)
    ra = [la[i] - la[i - 1] for i in range(1, n)]
    rb = [lb[i] - lb[i - 1] for i in range(1, n)]
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    corr = cov / math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    level = next((lvl for lvl, crit in CRITICAL.items() if stat < crit), None)
    return {
        "observations": n,
        "hedge_ratio": round(beta[1], 4),
        "intercept": round(beta[0], 4),
        "adf_statistic": round(stat, 3),
        "cointegrated_at": level,
        "critical_values": CRITICAL,
        "half_life_sessions": None if (h := half_life(resid)) is None else round(h, 1),
        "spread_zscore": round(z, 2),
        "return_correlation": round(corr, 3),
    }


def screen_pairs(series: dict[str, tuple[list, list[float]]], min_overlap: int = 250, max_pairs: int = 500) -> list[dict]:
    """Test every pair of symbols on their common dates. ``series``: {symbol: (dates, closes)}."""
    names = sorted(series)
    pairs = list(combinations(names, 2))
    if len(pairs) > max_pairs:
        raise ValueError(f"{len(pairs)} pairs exceeds the limit of {max_pairs}; use fewer symbols")
    lookup = {s: dict(zip(*series[s])) for s in names}
    rows = []
    for x, y in pairs:
        common = sorted(set(lookup[x]) & set(lookup[y]))
        if len(common) < min_overlap:
            continue
        try:
            result = analyse_pair([lookup[x][d] for d in common], [lookup[y][d] for d in common])
        except ValueError:
            continue
        rows.append({"a": x, "b": y, "from": common[0].isoformat(), "to": common[-1].isoformat(), **result})
    rows.sort(key=lambda r: r["adf_statistic"])
    return rows
