"""Price levels a chart reader looks at, computed from data: swing highs and lows,
support and resistance zones where several swings cluster, moving averages, the
52-week range, average true range, and recent trend structure.
"""
from __future__ import annotations

from typing import Optional

from . import indicators as ind
from .backtest import Bars


def swings(bars: Bars, k: int = 5) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Swing highs and lows: a bar whose high (low) is the highest (lowest) of the k bars on each side."""
    highs, lows = [], []
    h, l = bars.high, bars.low
    for i in range(k, len(bars) - k):
        window_h = h[i - k:i + k + 1]
        window_l = l[i - k:i + k + 1]
        if h[i] == max(window_h) and window_h.count(h[i]) == 1:
            highs.append((i, h[i]))
        if l[i] == min(window_l) and window_l.count(l[i]) == 1:
            lows.append((i, l[i]))
    return highs, lows


def zones(points: list[tuple[int, float]], tolerance_pct: float = 1.5) -> list[dict]:
    """Group swing prices within ``tolerance_pct`` of each other into zones."""
    out: list[dict] = []
    for i, price in sorted(points, key=lambda p: p[1]):
        if out and price <= out[-1]["low"] * (1 + tolerance_pct / 100):
            z = out[-1]
            z["high"] = max(z["high"], price)
            z["touches"] += 1
            z["last_index"] = max(z["last_index"], i)
        else:
            out.append({"low": price, "high": price, "touches": 1, "last_index": i})
    return out


def analyse(bars: Bars, k: int = 5, tolerance_pct: float = 1.5, max_zones: int = 4) -> dict:
    c = bars.close
    last = c[-1]
    highs, lows = swings(bars, k)
    all_zones = zones(highs + lows, tolerance_pct)
    for z in all_zones:
        z["mid"] = round((z["low"] + z["high"]) / 2, 2)
        z["distance_pct"] = round((z["mid"] / last - 1) * 100, 2)
        z["last_touched"] = bars.dates[z.pop("last_index")].isoformat()
        z["low"], z["high"] = round(z["low"], 2), round(z["high"], 2)
    support = sorted((z for z in all_zones if z["high"] < last), key=lambda z: -z["mid"])[:max_zones]
    resistance = sorted((z for z in all_zones if z["low"] > last), key=lambda z: z["mid"])[:max_zones]

    def last_swings(points: list) -> list[float]:
        return [round(p, 2) for _, p in points[-3:]]

    hh = last_swings(highs)
    ll = last_swings(lows)
    if len(hh) >= 2 and len(ll) >= 2:
        if hh[-1] > hh[-2] and ll[-1] > ll[-2]:
            structure = "higher highs and higher lows"
        elif hh[-1] < hh[-2] and ll[-1] < ll[-2]:
            structure = "lower highs and lower lows"
        else:
            structure = "mixed"
    else:
        structure = "not enough swings"

    def ma(n: int) -> Optional[float]:
        v = ind.sma(c, n)[-1]
        return None if v is None else round(v, 2)

    atr = ind.atr(bars.high, bars.low, c, 14)[-1]
    year = bars.close[-252:]
    return {
        "symbol": bars.symbol, "as_of": bars.dates[-1].isoformat(), "close": round(last, 2),
        "moving_averages": {"sma20": ma(20), "sma50": ma(50), "sma200": ma(200)},
        "atr14": None if atr is None else round(atr, 2),
        "atr14_pct": None if atr is None else round(atr / last * 100, 2),
        "high_52w": round(max(year), 2), "low_52w": round(min(year), 2),
        "pct_from_52w_high": round((last / max(year) - 1) * 100, 2),
        "support_zones": support, "resistance_zones": resistance,
        "recent_swing_highs": hh, "recent_swing_lows": ll,
        "structure": structure,
        "method": f"swing points are bars higher (lower) than the {k} bars either side; zones group swings within {tolerance_pct}%",
    }
