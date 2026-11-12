"""Point-in-time universes from NSE's daily bhavcopy archive.

Backtesting on today's index members is biased: the list already knows which
stocks grew large. This module rebuilds, for each past quarter, the stocks that
were the most heavily traded AT THAT TIME, using only bhavcopies dated before
the quarter starts.

What it fixes: stocks are chosen without hindsight, so companies that were
large and later shrank are included.

A stock that has since been delisted has no price history in the free price
source; ``bhavprices.adjusted_bars`` rebuilds those from NSE's own files.
"""
from __future__ import annotations

import csv
import io
import zipfile
from bisect import bisect_right
from datetime import date, timedelta
from typing import Optional

from . import DataUnavailable, cached_get
from .nse import CM_URL, REFERER

OLD_URL = "https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{mon}/cm{day:02d}{mon}{year}bhav.csv.zip"
_FOREVER = 10 * 365 * 86400.0


def _rows(url: str, cache_name: str) -> list[dict]:
    body = cached_get(url, cache_name, _FOREVER, REFERER)
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            text = archive.read(archive.namelist()[0]).decode("utf-8-sig", errors="replace")
    except zipfile.BadZipFile as exc:
        raise DataUnavailable(f"not a bhavcopy archive: {url}") from exc
    return list(csv.DictReader(io.StringIO(text)))


def turnover_table(day: date) -> dict[str, tuple[float, str]]:
    """{symbol: (traded value, ISIN)} for ordinary company shares on one trading day.

    Tries the current file format first, then the pre-July-2024 format. Only the EQ
    series and ISINs starting with INE (companies) are kept, which leaves out ETFs,
    bonds and trade-for-trade stocks.
    """
    ymd = day.strftime("%Y%m%d")
    try:
        rows = _rows(CM_URL.format(ymd=ymd), f"nse_cm_{ymd}.zip")
        return {r["TckrSymb"]: (float(r["TtlTrfVal"] or 0), r["ISIN"]) for r in rows
                if r["SctySrs"] == "EQ" and r["ISIN"].startswith("INE")}
    except DataUnavailable:
        pass
    mon = day.strftime("%b").upper()
    rows = _rows(OLD_URL.format(year=day.year, mon=mon, day=day.day), f"nse_cm_old_{ymd}.zip")
    out = {}
    for r in rows:
        r = {k.strip(): (v or "").strip() for k, v in r.items() if k}
        if r.get("SERIES") == "EQ" and r.get("ISIN", "").startswith("INE"):
            out[r["SYMBOL"]] = (float(r["TOTTRDVAL"] or 0), r["ISIN"])
    return out


def first_session_on_or_after(day: date, max_days: int = 10) -> tuple[date, dict]:
    """The first trading day at or after ``day`` and its turnover table."""
    cursor = day
    for _ in range(max_days):
        if cursor.weekday() < 5:
            try:
                return cursor, turnover_table(cursor)
            except DataUnavailable:
                pass
        cursor += timedelta(days=1)
    raise DataUnavailable(f"no bhavcopy found in the {max_days} days from {day.isoformat()}")


def nse_latest_turnover(lookback_days: int = 7) -> tuple[date, dict]:
    """The most recent published session and its turnover table (used to find today's symbols)."""
    cursor = date.today()
    for _ in range(lookback_days + 1):
        if cursor.weekday() < 5:
            try:
                return cursor, turnover_table(cursor)
            except DataUnavailable:
                pass
        cursor -= timedelta(days=1)
    raise DataUnavailable("no recent bhavcopy found")


def quarter_starts(start: date, end: date) -> list[date]:
    out, year, month = [], start.year, ((start.month - 1) // 3) * 3 + 1
    while date(year, month, 1) <= end:
        out.append(date(year, month, 1))
        month += 3
        if month > 12:
            year, month = year + 1, month - 12
    return out


def _month_before(day: date, months: int) -> date:
    total = day.year * 12 + day.month - 1 - months
    return date(total // 12, total % 12 + 1, 1)


def liquidity_membership(start: date, end: date, top_n: int = 100, fetch=first_session_on_or_after) -> dict:
    """{quarter start: [symbols]} - the ``top_n`` most traded company shares, ranked on the
    summed traded value of one session from each of the three months before the quarter.

    Every bhavcopy used is dated before the quarter it defines.
    Returns {"membership": {...}, "isin": {symbol: isin}, "skipped_quarters": [...]}.
    """
    membership: dict[date, list[str]] = {}
    isin: dict[str, str] = {}
    skipped: list[str] = []
    for quarter in quarter_starts(start, end):
        totals: dict[str, float] = {}
        samples = 0
        for back in (3, 2, 1):
            try:
                session, table = fetch(_month_before(quarter, back))
            except DataUnavailable:
                continue
            if session >= quarter:
                continue
            samples += 1
            for symbol, (value, code) in table.items():
                totals[symbol] = totals.get(symbol, 0.0) + value
                isin[symbol] = code
        if samples == 0:
            skipped.append(quarter.isoformat())
            continue
        ranked = sorted(totals, key=lambda s: -totals[s])[:top_n]
        membership[quarter] = sorted(ranked)
    if not membership:
        raise DataUnavailable("no point-in-time membership could be built for this period")
    return {"membership": membership, "isin": isin, "skipped_quarters": skipped}


def rename_to_current(symbols: set[str], isin: dict[str, str], current: dict[str, tuple[float, str]]) -> dict[str, str]:
    """Map historical symbols to today's symbol where the ISIN is unchanged but the ticker is not."""
    by_isin = {code: symbol for symbol, (_, code) in current.items()}
    out = {}
    for symbol in symbols:
        now = by_isin.get(isin.get(symbol, ""))
        if now and now != symbol and symbol not in current:
            out[symbol] = now
    return out


class Membership:
    """Callable lookup: ``membership(day)`` is the set in force on that day (the latest
    quarter start at or before it), or None before the first quarter."""

    def __init__(self, membership: dict[date, list[str]], rename: Optional[dict[str, str]] = None):
        rename = rename or {}
        self.keys = sorted(membership)
        self.sets = [frozenset(rename.get(s, s) for s in membership[k]) for k in self.keys]

    def __call__(self, day: date) -> Optional[frozenset]:
        i = bisect_right(self.keys, day) - 1
        return self.sets[i] if i >= 0 else None

    def all_symbols(self) -> set[str]:
        return set().union(*self.sets) if self.sets else set()
