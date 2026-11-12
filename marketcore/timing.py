"""Market-timing signals in the style of the classic index price-and-volume rules.

* Distribution day: the index closes down at least 0.2% on higher volume than the
  previous session. It drops out of the count after 25 sessions, or once the index
  closes 5% or more above that day's close.
* Rally attempt and follow-through day: after a decline, day 1 is the first up close
  off the low. A follow-through day is a close up at least 1.25% on higher volume
  than the previous session, on day 4 or later of the attempt. The attempt fails if
  the index closes below the rally low.
* Market-top checklist: a fixed set of warning conditions, counted.

These are descriptive rules with fixed, stated thresholds. Their record as signals is
mixed: many follow-through days fail, and distribution clusters do not always lead to
declines.
"""
from __future__ import annotations

from typing import Optional

from . import indicators as ind
from .backtest import Bars


def distribution_days(bars: Bars, window: int = 25, min_drop_pct: float = 0.2, expiry_gain_pct: float = 5.0) -> dict:
    """Active distribution days in the last ``window`` sessions."""
    c, v = bars.close, bars.volume
    n = len(c)
    active, expired = [], []
    for i in range(max(1, n - window), n):
        change = (c[i] / c[i - 1] - 1) * 100
        if change <= -min_drop_pct and v[i] > v[i - 1] > 0:
            later_high = max(c[i + 1:], default=c[i])
            row = {"date": bars.dates[i].isoformat(), "change_pct": round(change, 2), "sessions_ago": n - 1 - i}
            if (later_high / c[i] - 1) * 100 >= expiry_gain_pct:
                expired.append({**row, "reason": f"index later closed {expiry_gain_pct}% or more above it"})
            else:
                active.append(row)
    return {"window_sessions": window, "count": len(active), "days": active, "expired_by_rally": expired}


def rally_status(bars: Bars, min_gain_pct: float = 1.25, earliest_day: int = 4, lookback: int = 60, min_decline_pct: float = 5.0) -> dict:
    """Where the index stands in the rally-attempt / follow-through cycle.

    The search starts from the lowest close in the last ``lookback`` sessions, provided
    the index had fallen at least ``min_decline_pct`` from its prior high to reach it.
    """
    c, v, dates = bars.close, bars.volume, bars.dates
    n = len(c)
    start = max(0, n - lookback)
    low_i = min(range(start, n), key=lambda i: c[i])
    prior_high = max(c[max(0, low_i - 120):low_i + 1])
    decline = (1 - c[low_i] / prior_high) * 100
    if decline < min_decline_pct:
        return {"state": "no_correction", "detail": f"the index has not fallen {min_decline_pct}% or more from its high in the window",
                "decline_from_high_pct": round(decline, 2)}
    out = {"rally_low_date": dates[low_i].isoformat(), "rally_low": round(c[low_i], 2), "decline_from_high_pct": round(decline, 2)}
    day1: Optional[int] = None
    for i in range(low_i + 1, n):
        if c[i] < c[low_i]:
            return {**out, "state": "attempt_failed", "detail": f"closed below the rally low on {dates[i].isoformat()}"}
        if day1 is None and c[i] > c[i - 1]:
            day1 = i
        if day1 is not None:
            day_number = i - day1 + 1
            gain = (c[i] / c[i - 1] - 1) * 100
            if day_number >= earliest_day and gain >= min_gain_pct and v[i] > v[i - 1] > 0:
                undercut = any(c[j] < c[low_i] for j in range(i + 1, n))
                return {**out, "state": "follow_through" if not undercut else "follow_through_failed",
                        "day1_date": dates[day1].isoformat(), "follow_through_date": dates[i].isoformat(),
                        "follow_through_day_number": day_number, "follow_through_gain_pct": round(gain, 2),
                        "sessions_since": n - 1 - i,
                        "gain_since_follow_through_pct": round((c[-1] / c[i] - 1) * 100, 2)}
    if day1 is None:
        return {**out, "state": "no_rally_attempt", "detail": "no up close since the low"}
    return {**out, "state": "rally_attempt", "day1_date": dates[day1].isoformat(), "day_number": n - day1,
            "detail": f"day {n - day1} of a rally attempt with no qualifying follow-through yet"}


def top_checklist(bars: Bars, distribution_count: int, pct_above_sma50: Optional[float] = None) -> dict:
    """Count fixed warning signs of a market top."""
    c = bars.close
    s50, s200 = ind.sma(c, 50)[-1], ind.sma(c, 200)[-1]
    e21 = ind.ema(c, 21)[-1]
    high = max(c[-252:])
    items = [
        ("distribution_cluster", distribution_count >= 5, f"{distribution_count} distribution days in 25 sessions (5 or more is a warning)"),
        ("below_21_day_ema", e21 is not None and c[-1] < e21, "index closed below its 21-day exponential average"),
        ("below_50_day_average", s50 is not None and c[-1] < s50, "index closed below its 50-day average"),
        ("50_day_below_200_day", s50 is not None and s200 is not None and s50 < s200, "50-day average below the 200-day"),
        ("off_high_by_7pct", c[-1] <= high * 0.93, f"{round((1 - c[-1] / high) * 100, 2)}% below the 52-week closing high (7% or more is a warning)"),
    ]
    if pct_above_sma50 is not None:
        items.append(("narrow_participation", pct_above_sma50 < 40, f"{pct_above_sma50}% of stocks above their 50-day average (under 40% is a warning)"))
    warnings = [name for name, hit, _ in items if hit]
    level = "high" if len(warnings) >= 4 else "elevated" if len(warnings) >= 2 else "low"
    return {"warning_count": len(warnings), "items_checked": len(items), "level": level,
            "checklist": [{"item": name, "warning": hit, "detail": detail} for name, hit, detail in items]}
