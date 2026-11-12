"""Stock screens computed from daily bars. These rank candidates for research;
they are not buy signals.

* Relative strength: a weighted 3/6/9/12-month rate of change, ranked as a
  percentile within the universe screened.
* Trend template: the eight trend conditions published by Mark Minervini.
* Breakout: a close at a new 52-week closing high on above-average volume.
"""
from __future__ import annotations

from typing import Optional

from . import indicators as ind
from .backtest import Bars

YEAR, MIN_BARS = 252, 253


def rs_raw(bars: Bars) -> Optional[float]:
    """0.4 x 3-month + 0.2 x 6-month + 0.2 x 9-month + 0.2 x 12-month return. Needs 253 bars."""
    c = bars.close
    if len(c) < MIN_BARS:
        return None
    last = c[-1]
    return (0.4 * (last / c[-64] - 1) + 0.2 * (last / c[-127] - 1)
            + 0.2 * (last / c[-190] - 1) + 0.2 * (last / c[-253] - 1))


def percentile_ranks(scores: dict[str, Optional[float]]) -> dict[str, Optional[int]]:
    """Rank 1-99 within the universe: the percent of other symbols with a lower score."""
    valid = {k: v for k, v in scores.items() if v is not None}
    out: dict[str, Optional[int]] = {k: None for k in scores}
    n = len(valid)
    if n == 1:
        out[next(iter(valid))] = 50
    for key, value in valid.items():
        if n > 1:
            below = sum(1 for v in valid.values() if v < value)
            out[key] = max(1, min(99, round(below / (n - 1) * 100)))
    return out


def analyse(bars: Bars, rs_rank: Optional[int] = None) -> Optional[dict]:
    """All screen measures for one symbol at its latest bar, or None if history is too short."""
    if len(bars) < MIN_BARS:
        return None
    c, v = bars.close, bars.volume
    s50, s150, s200 = ind.sma(c, 50)[-1], ind.sma(c, 150)[-1], ind.sma(c, 200)[-1]
    s200_month_ago = ind.sma(c, 200)[-22]
    high_52w, low_52w = max(bars.high[-YEAR:]), min(bars.low[-YEAR:])
    prior_close_high = max(c[-YEAR - 1 : -1])
    avg_vol_50 = sum(v[-51:-1]) / 50
    last = c[-1]
    volume_ratio = v[-1] / avg_vol_50 if avg_vol_50 > 0 else None
    turnover_20d = sum(c[i] * v[i] for i in range(-20, 0)) / 20

    conditions = {
        "price_above_sma150_and_sma200": last > s150 and last > s200,
        "sma150_above_sma200": s150 > s200,
        "sma200_rising_1_month": s200_month_ago is not None and s200 > s200_month_ago,
        "sma50_above_sma150_and_sma200": s50 > s150 and s50 > s200,
        "price_above_sma50": last > s50,
        "at_least_30pct_above_52w_low": last >= 1.30 * low_52w,
        "within_25pct_of_52w_high": last >= 0.75 * high_52w,
        "rs_rank_70_or_more": rs_rank is not None and rs_rank >= 70,
    }
    return {
        "symbol": bars.symbol,
        "date": bars.dates[-1].isoformat(),
        "close": round(last, 2),
        "rs_rank": rs_rank,
        "pct_below_52w_high": round((1 - last / high_52w) * 100, 2),
        "pct_above_52w_low": round((last / low_52w - 1) * 100, 2),
        "sma50": round(s50, 2),
        "sma150": round(s150, 2),
        "sma200": round(s200, 2),
        "volume_ratio_vs_50d": None if volume_ratio is None else round(volume_ratio, 2),
        "avg_daily_turnover_20d": round(turnover_20d),
        "trend_template_passed": sum(conditions.values()),
        "trend_template": all(conditions.values()),
        "trend_template_conditions": conditions,
        "breakout": last > prior_close_high and volume_ratio is not None and volume_ratio >= 1.5,
        "new_52w_closing_high": last > prior_close_high,
        **contraction(bars, s50, s200, high_52w),
    }


def contraction(bars: Bars, s50: float, s200: float, high_52w: float) -> dict:
    """Volatility contraction: a tight, quiet range near the highs of an uptrend.

    Passes when all hold: close > SMA50 > SMA200; within 15% of the 52-week high;
    the last 10 sessions span at most 8% of the price and less than half the span of
    the last 40; and average volume over those 10 sessions is under 80% of the
    50-day average. The pivot is the high of the 10-session range.
    """
    c, v = bars.close, bars.volume
    last = c[-1]
    high_10, low_10 = max(bars.high[-10:]), min(bars.low[-10:])
    high_40, low_40 = max(bars.high[-40:]), min(bars.low[-40:])
    range_10, range_40 = (high_10 - low_10) / last, (high_40 - low_40) / last
    avg_vol_10, avg_vol_50 = sum(v[-10:]) / 10, sum(v[-50:]) / 50
    dry_up = avg_vol_10 / avg_vol_50 if avg_vol_50 > 0 else None
    checks = {
        "uptrend": last > s50 > s200,
        "near_52w_high": last >= 0.85 * high_52w,
        "tight_range": range_10 <= 0.08 and range_10 < 0.5 * range_40,
        "volume_dry_up": dry_up is not None and dry_up < 0.8,
    }
    return {
        "contraction": all(checks.values()),
        "contraction_checks": checks,
        "range_10d_pct": round(range_10 * 100, 2),
        "range_40d_pct": round(range_40 * 100, 2),
        "volume_10d_vs_50d": None if dry_up is None else round(dry_up, 2),
        "pivot": round(high_10, 2),
        "pct_below_pivot": round((1 - last / high_10) * 100, 2),
    }


def screen(universe: dict[str, Bars]) -> list[dict]:
    """Analyse every symbol; relative-strength ranks are within this universe."""
    ranks = percentile_ranks({s: rs_raw(b) for s, b in universe.items()})
    rows = [analyse(b, ranks[s]) for s, b in universe.items()]
    return [r for r in rows if r is not None]
