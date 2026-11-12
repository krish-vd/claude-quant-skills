"""How a stock has reacted to its results: the gap and the move on the first session
that could react, and the drift over the following sessions, against the index.

India: announcement times come from the company's filings with NSE (the broadcast
time). A result broadcast after 15:30 IST can only move the next session.
US: announcement times come from 8-K filings with item 2.02 (results of operations)
in the SEC's filing index. A filing after 16:00 New York time moves the next session.
"""
from __future__ import annotations

import json
from bisect import bisect_left
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .backtest import Bars
from .data import DataUnavailable, cached_get
from .fundamentals import SEC_FACTS, _sec_get, india_filings, sec_cik

NSE_REFERER = "https://www.nseindia.com/"
NSE_OLD_RESULTS = "https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly&symbol={symbol}"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
IST = timezone(timedelta(hours=5, minutes=30))


def india_events(symbol: str) -> list[dict]:
    """Results announcements for an NSE company: {period_end, announced (IST datetime)}, oldest first.
    For each quarter the earliest broadcast of either basis is used."""
    times: dict[str, datetime] = {}

    def add(period: Optional[str], stamp: Optional[str], fmt: str, period_fmt: str) -> None:
        if not period or not stamp:
            return
        try:
            when = datetime.strptime(stamp.strip(), fmt).replace(tzinfo=IST)
            end = datetime.strptime(period.strip(), period_fmt).date().isoformat()
        except ValueError:
            return
        if end not in times or when < times[end]:
            times[end] = when

    try:
        for r in india_filings(symbol):
            add(r.get("qe_Date"), r.get("broadcast_Date"), "%d-%b-%Y %H:%M:%S", "%d-%b-%Y")
    except DataUnavailable:
        pass
    try:
        body = cached_get(NSE_OLD_RESULTS.format(symbol=symbol.upper()), f"nse_oldresults_{symbol.upper()}.json", 7 * 86400.0, NSE_REFERER)
        for r in json.loads(body):
            add(r.get("toDate"), r.get("broadCastDate"), "%d-%b-%Y %H:%M:%S", "%d-%b-%Y")
    except (DataUnavailable, ValueError):
        pass
    if not times:
        raise DataUnavailable(f"no results announcements found for {symbol.upper()}")
    return [{"period_end": k, "announced": v} for k, v in sorted(times.items(), key=lambda kv: kv[1])]


def us_events(ticker: str) -> list[dict]:
    """Results announcements for a US company from its 8-K item 2.02 filings, oldest first."""
    cik, _ = sec_cik(ticker)
    body = _sec_get(SEC_SUBMISSIONS.format(cik=cik), f"sec_sub_{cik}.json", 12 * 3600.0)
    try:
        recent = json.loads(body)["filings"]["recent"]
    except (ValueError, KeyError) as exc:
        raise DataUnavailable(f"SEC filing index for {ticker} was not readable") from exc
    out = []
    for form, items, stamp in zip(recent["form"], recent.get("items", []), recent["acceptanceDateTime"]):
        if form == "8-K" and "2.02" in str(items):
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            out.append({"period_end": None, "announced": when})
    if not out:
        raise DataUnavailable(f"no results filings (8-K item 2.02) found for {ticker.upper()}")
    return sorted(out, key=lambda e: e["announced"])


def reaction_index(dates: list[date], announced: datetime, market: str) -> Optional[int]:
    """Index of the first session whose close reflects the announcement."""
    if market == "IN":
        local = announced.astimezone(IST)
        after_close = (local.hour, local.minute) >= (15, 30)
    else:
        # New York close 16:00; offset -5 (winter) or -4 (summer). Use -4 to be conservative about "after close".
        local = announced.astimezone(timezone(timedelta(hours=-4)))
        after_close = local.hour >= 16
    day = local.date() + (timedelta(days=1) if after_close else timedelta(days=0))
    i = bisect_left(dates, day)
    return i if i < len(dates) else None


def reactions(bars: Bars, events: list[dict], market: str, index_bars: Optional[Bars] = None, drift_days: tuple = (5, 20)) -> list[dict]:
    idx_close = dict(zip(index_bars.dates, index_bars.close)) if index_bars else {}
    rows = []
    for ev in events:
        i = reaction_index(bars.dates, ev["announced"], market)
        if i is None or i < 1:
            continue
        prev_close, d0 = bars.close[i - 1], bars.dates[i]
        row = {
            "period_end": ev["period_end"],
            "announced": ev["announced"].isoformat(timespec="minutes"),
            "reaction_date": d0.isoformat(),
            "gap_pct": round((bars.open[i] / prev_close - 1) * 100, 2),
            "day_move_pct": round((bars.close[i] / prev_close - 1) * 100, 2),
            "volume_vs_20d": round(bars.volume[i] / (sum(bars.volume[max(0, i - 20):i]) / max(1, min(20, i))), 2) if i > 0 and sum(bars.volume[max(0, i - 20):i]) > 0 else None,
        }
        d_prev = bars.dates[i - 1]
        if idx_close.get(d0) and idx_close.get(d_prev):
            row["day_move_vs_index_pct"] = round(row["day_move_pct"] - (idx_close[d0] / idx_close[d_prev] - 1) * 100, 2)
        for k in drift_days:
            j = i + k
            if j < len(bars):
                drift = (bars.close[j] / bars.close[i] - 1) * 100
                row[f"drift_{k}d_pct"] = round(drift, 2)
                dj = bars.dates[j]
                if idx_close.get(dj) and idx_close.get(d0):
                    row[f"drift_{k}d_vs_index_pct"] = round(drift - (idx_close[dj] / idx_close[d0] - 1) * 100, 2)
        rows.append(row)
    return rows


def summarise(rows: list[dict]) -> dict:
    """Average behaviour after results, and split by up and down reactions."""
    def avg(values: list) -> Optional[float]:
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 2) if values else None

    ups = [r for r in rows if r["day_move_pct"] > 0]
    downs = [r for r in rows if r["day_move_pct"] < 0]
    return {
        "events": len(rows),
        "average_absolute_day_move_pct": avg([abs(r["day_move_pct"]) for r in rows]),
        "average_absolute_gap_pct": avg([abs(r["gap_pct"]) for r in rows]),
        "up_reactions": len(ups), "down_reactions": len(downs),
        "after_up_reactions_avg_drift_20d_vs_index_pct": avg([r.get("drift_20d_vs_index_pct") for r in ups]),
        "after_down_reactions_avg_drift_20d_vs_index_pct": avg([r.get("drift_20d_vs_index_pct") for r in downs]),
        "largest_day_move_pct": max((r["day_move_pct"] for r in rows), key=abs, default=None),
    }
