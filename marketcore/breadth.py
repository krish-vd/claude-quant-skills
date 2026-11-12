"""Market breadth: how many stocks in a universe are participating in a move.

Measures are computed for the latest session shared by the universe, with a
short history so the direction of breadth is visible. The posture label uses
fixed, stated thresholds; it describes conditions and predicts nothing.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from . import indicators as ind
from .backtest import Bars

THRESHOLDS = {
    "broad_uptrend": "at least 60% of stocks above their 200-day average and at least 50% above their 50-day",
    "broad_downtrend": "at most 40% above their 200-day average and at most 50% above their 50-day",
    "washed_out": "20% or fewer above their 50-day average",
    "stretched": "85% or more above their 50-day average",
}


def _pct(part: int, whole: int) -> Optional[float]:
    return round(part / whole * 100, 1) if whole else None


def measure(universe: dict[str, Bars], history_days: int = 60) -> dict:
    """Breadth for the latest session and a daily history of the two trend measures."""
    if not universe:
        raise ValueError("empty universe")
    latest = max(b.dates[-1] for b in universe.values() if len(b))
    current = {s: b for s, b in universe.items() if len(b) and b.dates[-1] == latest}
    stale = sorted(set(universe) - set(current))

    averages = {s: {n: ind.sma(b.close, n) for n in (20, 50, 200)} for s, b in current.items()}
    counts = {n: [0, 0] for n in (20, 50, 200)}  # [above, eligible]
    advances = declines = unchanged = new_highs = new_lows = 0
    for s, b in current.items():
        last = b.close[-1]
        for n in (20, 50, 200):
            value = averages[s][n][-1]
            if value is not None:
                counts[n][1] += 1
                counts[n][0] += last > value
        if len(b) >= 2:
            change = last - b.close[-2]
            advances += change > 0
            declines += change < 0
            unchanged += change == 0
        if len(b) >= 253:
            window = b.close[-253:-1]
            new_highs += last > max(window)
            new_lows += last < min(window)

    all_dates = sorted({d for b in current.values() for d in b.dates})[-max(history_days, 21):]
    position = {s: {d: i for i, d in enumerate(b.dates)} for s, b in current.items()}
    history = []
    for day in all_dates:
        above = {50: [0, 0], 200: [0, 0]}
        for s, b in current.items():
            i = position[s].get(day)
            if i is None:
                continue
            for n in (50, 200):
                value = averages[s][n][i]
                if value is not None:
                    above[n][1] += 1
                    above[n][0] += b.close[i] > value
        history.append({"date": day.isoformat(), "pct_above_sma50": _pct(*above[50]), "pct_above_sma200": _pct(*above[200])})

    p50, p200 = _pct(*counts[50]), _pct(*counts[200])
    posture, flags = "mixed", []
    if p50 is not None and p200 is not None:
        if p200 >= 60 and p50 >= 50:
            posture = "broad_uptrend"
        elif p200 <= 40 and p50 <= 50:
            posture = "broad_downtrend"
        if p50 <= 20:
            flags.append("washed_out")
        if p50 >= 85:
            flags.append("stretched")
    earlier = next((h["pct_above_sma50"] for h in history[-21:-20]), None) if len(history) >= 21 else None
    return {
        "as_of": latest.isoformat(),
        "stocks_measured": len(current),
        "pct_above_sma20": _pct(*counts[20]),
        "pct_above_sma50": p50,
        "pct_above_sma200": p200,
        "pct_above_sma50_20_sessions_ago": earlier,
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "advance_decline_ratio": round(advances / declines, 2) if declines else None,
        "new_52w_highs": new_highs,
        "new_52w_lows": new_lows,
        "net_new_highs": new_highs - new_lows,
        "posture": posture,
        "flags": flags,
        "posture_rules": THRESHOLDS,
        "history": history[-history_days:],
        "excluded_stale_symbols": stale,
    }


def index_trend(bars: Bars) -> dict:
    """Where an index sits against its own averages and 52-week range."""
    c = bars.close
    s50, s200 = ind.sma(c, 50)[-1], ind.sma(c, 200)[-1]
    year = c[-252:]
    return {
        "symbol": bars.symbol,
        "as_of": bars.dates[-1].isoformat(),
        "close": round(c[-1], 2),
        "above_sma50": None if s50 is None else c[-1] > s50,
        "above_sma200": None if s200 is None else c[-1] > s200,
        "sma50_above_sma200": None if s50 is None or s200 is None else s50 > s200,
        "pct_from_52w_high": round((c[-1] / max(year) - 1) * 100, 2),
        "return_1m_pct": round((c[-1] / c[-22] - 1) * 100, 2) if len(c) > 22 else None,
        "return_3m_pct": round((c[-1] / c[-64] - 1) * 100, 2) if len(c) > 64 else None,
    }


def level_percentile(bars: Bars, window: int = 252) -> dict:
    """Latest close of a series (for example a volatility index) and its percentile within the window."""
    recent = bars.close[-window:]
    last = recent[-1]
    below = sum(1 for v in recent if v < last)
    return {
        "symbol": bars.symbol,
        "as_of": bars.dates[-1].isoformat(),
        "level": round(last, 2),
        "percentile_in_window": round(below / len(recent) * 100, 1),
        "window_sessions": len(recent),
        "window_low": round(min(recent), 2),
        "window_high": round(max(recent), 2),
    }


def posture_checklist(
    breadth_now: dict, index: dict, volatility: Optional[dict] = None,
    fii_long_pct_now: Optional[float] = None, fii_long_pct_before: Optional[float] = None,
) -> dict:
    """Market conditions as a checklist of fixed rules. Each item is supportive, a
    caution, or neutral; unavailable inputs are skipped.

    Label: ``constructive`` when at least five items are supportive and at most one
    is a caution; ``defensive`` when four or more are cautions; otherwise ``mixed``.
    The label summarises conditions. It is not a prediction or an instruction.
    """
    items: list[dict] = []

    def add(name: str, status: Optional[str], detail: str) -> None:
        if status is not None:
            items.append({"item": name, "status": status, "detail": detail})

    def flag(value: Optional[bool]) -> Optional[str]:
        return None if value is None else ("supportive" if value else "caution")

    add("index_above_200_day_average", flag(index.get("above_sma200")), f"{index.get('symbol')} at {index.get('close')}")
    add("index_50_day_above_200_day", flag(index.get("sma50_above_sma200")), "medium-term average against long-term average")

    p200 = breadth_now.get("pct_above_sma200")
    if p200 is not None:
        add("stocks_above_200_day_average", "supportive" if p200 >= 50 else "caution" if p200 <= 40 else "neutral",
            f"{p200}% (50% or more is supportive, 40% or less is a caution)")
    p50, earlier = breadth_now.get("pct_above_sma50"), breadth_now.get("pct_above_sma50_20_sessions_ago")
    if p50 is not None and earlier is not None:
        add("breadth_direction", "supportive" if p50 > earlier else "caution" if p50 < earlier else "neutral",
            f"{p50}% above the 50-day now against {earlier}% twenty sessions ago")
    net = breadth_now.get("net_new_highs")
    if net is not None:
        add("net_new_highs", "supportive" if net > 0 else "caution" if net < 0 else "neutral",
            f"{breadth_now.get('new_52w_highs')} new highs, {breadth_now.get('new_52w_lows')} new lows")
    if volatility and volatility.get("percentile_in_window") is not None:
        pct = volatility["percentile_in_window"]
        add("volatility_index", "caution" if pct >= 80 else "supportive" if pct <= 50 else "neutral",
            f"{volatility.get('symbol')} at {volatility.get('level')}, {pct} percentile of the past year "
            "(80 or above is a caution, 50 or below is supportive)")
    if fii_long_pct_now is not None and fii_long_pct_before is not None:
        add("fii_index_futures_positioning",
            "supportive" if fii_long_pct_now > fii_long_pct_before else "caution" if fii_long_pct_now < fii_long_pct_before else "neutral",
            f"FII long share of index futures {fii_long_pct_now}% against {fii_long_pct_before}% at the start of the window")

    supportive = sum(1 for i in items if i["status"] == "supportive")
    cautions = sum(1 for i in items if i["status"] == "caution")
    label = "constructive" if supportive >= 5 and cautions <= 1 else "defensive" if cautions >= 4 else "mixed"
    return {"label": label, "supportive": supportive, "cautions": cautions,
            "neutral": len(items) - supportive - cautions, "items_checked": len(items), "checklist": items}
