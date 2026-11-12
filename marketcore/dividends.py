"""Dividend history measures: trailing yield, payment record and growth.

Dividend amounts come from the Yahoo chart endpoint (unofficial), adjusted for
splits and bonuses. They are per share, in the stock's currency.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from .data import DataUnavailable, cached_get
from .data.history import CHART_URL, yahoo_symbol


def parse_dividends(payload: dict) -> tuple[list[tuple[date, float]], Optional[float], Optional[date]]:
    """(dividends oldest first, last close, date of last close)."""
    try:
        result = payload["chart"]["result"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise DataUnavailable("no chart data") from exc
    offset = result.get("meta", {}).get("gmtoffset", 0)
    events = result.get("events", {}).get("dividends", {}) or {}
    rows = sorted(
        (datetime.fromtimestamp(v["date"] + offset, tz=timezone.utc).date(), float(v["amount"]))
        for v in events.values() if v.get("amount")
    )
    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close") or []
    stamps = result.get("timestamp") or []
    last_close = last_date = None
    for ts, c in zip(reversed(stamps), reversed(closes)):
        if c:
            last_close, last_date = float(c), datetime.fromtimestamp(ts + offset, tz=timezone.utc).date()
            break
    return rows, last_close, last_date


def fetch(symbol: str, market: str) -> tuple[list[tuple[date, float]], Optional[float], Optional[date]]:
    ysym = yahoo_symbol(symbol, market)
    url = CHART_URL.format(symbol=urllib.parse.quote(ysym), range="10y")
    name = "yh_" + re.sub(r"[^A-Za-z0-9]", "_", ysym) + "_10y.json"
    try:
        return parse_dividends(json.loads(cached_get(url, name, 12 * 3600.0)))
    except ValueError as exc:
        raise DataUnavailable(f"unreadable dividend data for {symbol}") from exc


def summarise(symbol: str, dividends: list[tuple[date, float]], close: Optional[float], as_of: date) -> dict:
    """Trailing-12-month yield, calendar-year totals, growth and consistency."""
    year_ago = as_of - timedelta(days=365)
    ttm = [(d, a) for d, a in dividends if year_ago < d <= as_of]
    by_year: dict[int, float] = {}
    for d, a in dividends:
        by_year[d.year] = by_year.get(d.year, 0.0) + a
    complete = sorted(y for y in by_year if y < as_of.year)  # the current year is still in progress
    span = list(range(complete[0], as_of.year)) if complete else []
    paid_years = sum(1 for y in span if by_year.get(y, 0) > 0)

    streak = 0
    for y in reversed(span):
        if by_year.get(y, 0) > 0:
            streak += 1
        else:
            break
    growth_streak = 0
    for later, earlier in zip(reversed(span), reversed(span[:-1])):
        if by_year.get(later, 0) > by_year.get(earlier, 0) > 0:
            growth_streak += 1
        else:
            break

    def cagr(years: int) -> Optional[float]:
        if len(span) <= years:
            return None
        end, start = by_year.get(span[-1], 0), by_year.get(span[-1 - years], 0)
        if start <= 0 or end <= 0:
            return None
        return round(((end / start) ** (1 / years) - 1) * 100, 2)

    ttm_total = sum(a for _, a in ttm)
    return {
        "symbol": symbol.upper(),
        "as_of": as_of.isoformat(),
        "close": None if close is None else round(close, 2),
        "dividends_ttm": round(ttm_total, 4),
        "payments_ttm": len(ttm),
        "yield_ttm_pct": round(ttm_total / close * 100, 2) if close and ttm_total else (0.0 if close else None),
        "last_dividend": {"date": dividends[-1][0].isoformat(), "amount": dividends[-1][1]} if dividends else None,
        "annual_totals": {str(y): round(by_year.get(y, 0.0), 4) for y in span[-6:]},
        "years_of_history": len(span),
        "years_paid": paid_years,
        "consecutive_years_paid": streak,
        "consecutive_years_of_increase": growth_streak,
        "dividend_cagr_3y_pct": cagr(3),
        "dividend_cagr_5y_pct": cagr(5),
    }
