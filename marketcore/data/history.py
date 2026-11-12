"""Daily price history for backtests and screens, plus index member lists.

Prices come from the Yahoo chart endpoint (unofficial, keyless). Open, high,
low and close are adjusted for splits and bonus issues but NOT for dividends.
NSE symbols take a ``.NS`` suffix on Yahoo; ``yahoo_symbol`` adds it.

Index members come from NSE's own constituent files.
"""
from __future__ import annotations

import csv
import io
import json
import re
import urllib.parse
from datetime import datetime, timezone

from ..backtest import Bars
from . import DataUnavailable, cached_get

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={range}&interval=1d&events=div%2Csplits"
NSE_INDEX_URL = "https://nsearchives.nseindia.com/content/indices/{file}.csv"
NSE_INDEX_FILES = {
    "nifty50": "ind_nifty50list",
    "niftynext50": "ind_niftynext50list",
    "nifty100": "ind_nifty100list",
    "nifty200": "ind_nifty200list",
    "nifty500": "ind_nifty500list",
    "niftymidcap150": "ind_niftymidcap150list",
    "niftysmallcap250": "ind_niftysmallcap250list",
}
RANGES = ("1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max")


def yahoo_symbol(symbol: str, market: str) -> str:
    """Map a plain symbol to Yahoo's: NSE stocks get ``.NS``; US symbols are unchanged."""
    s = symbol.upper()
    if market.upper() == "IN" and not s.endswith((".NS", ".BO")) and not s.startswith("^") and "=" not in s:
        return f"{s}.NS"
    return s


def parse_chart(payload: dict, symbol: str) -> Bars:
    try:
        result = payload["chart"]["result"][0]
        quote = result["indicators"]["quote"][0]
        stamps = result["timestamp"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DataUnavailable(f"No price history for {symbol}") from exc
    bars = Bars(symbol, [], [], [], [], [], [])
    for i, ts in enumerate(stamps):
        o, h, l, c = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i]
        if None in (o, h, l, c) or min(o, h, l, c) <= 0:
            continue  # holiday placeholder or bad row
        day = datetime.fromtimestamp(ts + result["meta"].get("gmtoffset", 0), tz=timezone.utc).date()
        if bars.dates and day <= bars.dates[-1]:
            continue
        bars.dates.append(day)
        bars.open.append(float(o))
        bars.high.append(float(max(h, o, c)))
        bars.low.append(float(min(l, o, c)))
        bars.close.append(float(c))
        bars.volume.append(float(quote["volume"][i] or 0))
    if not bars.dates:
        raise DataUnavailable(f"Empty price history for {symbol}")
    return bars


# Minutes after midnight UTC by which a session's daily bar is final (close plus a margin).
# NSE closes 15:30 IST = 10:00 UTC. US closes 16:00 ET = 21:00 UTC in winter (20:00 in summer).
_FINAL_AFTER_UTC_MINUTES = {"IN": 10 * 60 + 15, "US": 21 * 60 + 15, "CRYPTO": 24 * 60 + 15}


def drop_unfinished_bar(bars: Bars, market: str, now_utc: "datetime | None" = None) -> Bars:
    """Remove the last bar if its session has not finished, so nothing is computed on a partial day."""
    now = now_utc or datetime.now(timezone.utc)
    if not bars.dates:
        return bars
    minutes = _FINAL_AFTER_UTC_MINUTES.get(market.upper(), 21 * 60 + 15)
    last = bars.dates[-1]
    final_at = datetime(last.year, last.month, last.day, tzinfo=timezone.utc).timestamp() + minutes * 60
    if now.timestamp() < final_at:
        return bars.slice(len(bars) - 1)
    return bars


def daily_bars(symbol: str, range_: str = "5y", market: str = "US", max_age_hours: float = 12.0) -> Bars:
    """Split-adjusted daily bars, cached on disk. An unfinished current session is dropped."""
    if range_ not in RANGES:
        raise ValueError(f"range must be one of {RANGES}")
    ysym = yahoo_symbol(symbol, market)
    url = CHART_URL.format(symbol=urllib.parse.quote(ysym), range=range_)
    name = "yh_" + re.sub(r"[^A-Za-z0-9]", "_", ysym) + f"_{range_}.json"
    body = cached_get(url, name, max_age_hours * 3600.0)
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise DataUnavailable(f"Unreadable price response for {symbol}") from exc
    bars = drop_unfinished_bar(parse_chart(payload, symbol.upper()), market)
    if not bars.dates:
        raise DataUnavailable(f"No completed sessions for {symbol}")
    return bars


def nse_index_members(index: str = "nifty500") -> list[dict]:
    """Current members of an NSE index: symbol, company, industry, ISIN (official file, cached 24 h)."""
    key = index.lower().replace(" ", "").replace("_", "")
    if key not in NSE_INDEX_FILES:
        raise ValueError(f"index must be one of {sorted(NSE_INDEX_FILES)}")
    url = NSE_INDEX_URL.format(file=NSE_INDEX_FILES[key])
    body = cached_get(url, f"nse_{key}.csv", 24 * 3600.0, "https://www.nseindia.com/")
    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig", errors="replace"))))
    members = [
        {"symbol": r["Symbol"].strip(), "company": r["Company Name"].strip(),
         "industry": r["Industry"].strip(), "isin": r["ISIN Code"].strip()}
        for r in rows if r.get("Symbol")
    ]
    if not members:
        raise DataUnavailable(f"NSE index file for {index} returned no members")
    return members


def load_universe(
    market: str,
    symbols: "list[str] | None" = None,
    index: "str | None" = None,
    range_: str = "5y",
    pause_seconds: float = 0.05,
) -> "tuple[dict[str, Bars], list[str], dict[str, dict]]":
    """Fetch bars for a symbol list or an NSE index.

    Returns (bars by symbol, symbols that could not be loaded, member details by symbol).
    """
    import time

    details: dict[str, dict] = {}
    if index:
        if market.upper() != "IN":
            raise ValueError("--index is available for India only; pass a symbol list for US")
        members = nse_index_members(index)
        details = {m["symbol"]: m for m in members}
        symbols = [m["symbol"] for m in members]
    if not symbols:
        raise ValueError("give symbols or an index")
    data: dict[str, Bars] = {}
    failed: list[str] = []
    for sym in dict.fromkeys(s.strip().upper() for s in symbols if s.strip()):
        try:
            data[sym] = daily_bars(sym, range_, market)
        except DataUnavailable:
            failed.append(sym)
        time.sleep(pause_seconds)
    if market.upper() == "IN" and len(data) >= 2:
        report = repair_recent_gaps_from_nse(data)
        if report["repaired"] or report["unrepaired"]:
            details["__repair__"] = report
    return data, failed, details


def repair_recent_gaps_from_nse(universe: "dict[str, Bars]", sessions: int = 3, max_jump: float = 0.25) -> dict:
    """Fill bars missing from the last few sessions using the official NSE bhavcopy.

    The unofficial price source sometimes has an empty row for a stock on a day it
    traded. For each of the last ``sessions`` dates seen in the universe, a symbol
    without that date gets the official open, high, low, close and volume.

    A bhavcopy price is unadjusted, so a bar is inserted only if its close is within
    ``max_jump`` of the neighbouring close. A larger jump suggests a split or bonus on
    that date, where an unadjusted bar would corrupt the series; those are reported
    as unrepaired instead.
    """
    from . import nse  # local import: nse does not depend on this module

    calendar = sorted({d for b in universe.values() for d in b.dates})[-sessions:]
    repaired: list[str] = []
    unrepaired: list[str] = []
    tables: dict = {}
    for day in calendar:
        missing = [s for s, b in universe.items() if b.dates and day not in set(b.dates[-(sessions + 5):]) and b.dates[0] < day]
        if not missing:
            continue
        if day not in tables:
            try:
                tables[day] = {r["TckrSymb"]: r for r in nse.cm_bhavcopy(day) if r["SctySrs"] in ("EQ", "BE")}
            except DataUnavailable:
                tables[day] = None
        table = tables[day]
        for sym in missing:
            row = table.get(sym) if table else None
            bars = universe[sym]
            if row is None:
                unrepaired.append(f"{sym} {day.isoformat()} (not in the NSE file)")
                continue
            o, h, l, c = (float(row[k]) for k in ("OpnPric", "HghPric", "LwPric", "ClsPric"))
            position = next((i for i, d in enumerate(bars.dates) if d > day), len(bars.dates))
            neighbour = bars.close[position - 1] if position > 0 else bars.close[position]
            if min(o, h, l, c) <= 0 or abs(c / neighbour - 1.0) > max_jump:
                unrepaired.append(f"{sym} {day.isoformat()} (price jump, possible corporate action)")
                continue
            bars.dates.insert(position, day)
            bars.open.insert(position, o)
            bars.high.insert(position, h)
            bars.low.insert(position, l)
            bars.close.insert(position, c)
            bars.volume.insert(position, float(row["TtlTradgVol"] or 0))
            repaired.append(f"{sym} {day.isoformat()}")
    return {"repaired": repaired, "unrepaired": unrepaired}
