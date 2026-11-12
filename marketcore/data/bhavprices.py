"""Daily bars for stocks the price source no longer serves, rebuilt from official NSE files.

Why this exists: Yahoo has no history for most stocks that were delisted or merged away.
A point-in-time universe still names them (they were large once), so without their
prices the backtest silently drops exactly the stocks that did worst. This module
rebuilds those bars from NSE's daily bhavcopy archive and adjusts them for splits and
bonus issues using NSE's corporate-actions feed.

What it does
  1. Reads every trading day's bhavcopy in the period (cached forever once downloaded).
  2. Collects open, high, low, close and volume for the wanted symbols (EQ series, or
     BE/BZ when the stock was moved to trade-for-trade, which is common before delisting).
  3. Divides earlier prices (and multiplies earlier volume) for each split or bonus.

What it does not do
  * Dividends, rights issues, demergers and mergers are not adjusted. A demerger or
    rights issue shows up as a price drop that never happened to holders. Every such
    event, and every one-day move above ``SUSPECT_JUMP`` after adjusting, is returned
    so the caller can show it instead of hiding it.
  * A day whose file could not be downloaded is indistinguishable from a holiday.
    The count of days without a file is returned; about 15 a year is normal.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Callable, Optional

from ..backtest import Bars
from . import DataUnavailable, cache_dir
from .pit import OLD_URL, _rows
from .nse import CM_URL

UDIFF_FROM = date(2024, 7, 8)   # NSE's new file format starts here
SERIES = ("EQ", "BE", "BZ")      # BZ and BE are trade-for-trade segments
SUSPECT_JUMP = 0.35              # one-day close-to-close move that deserves a second look
_SERIES_RANK = {"EQ": 0, "BE": 1, "BZ": 2}


def session_rows(day: date) -> dict[str, tuple]:
    """{symbol: (open, high, low, close, volume, isin)} for one trading day.

    Raises DataUnavailable on a day with no file (holiday, or not yet published).
    """
    ymd = day.strftime("%Y%m%d")
    mon = day.strftime("%b").upper()

    def new_format() -> list[dict]:
        return _rows(CM_URL.format(ymd=ymd), f"nse_cm_{ymd}.zip")

    def old_format() -> list[dict]:
        return _rows(OLD_URL.format(year=day.year, mon=mon, day=day.day), f"nse_cm_old_{ymd}.zip")

    marker = cache_dir() / f"nse_cm_none_{ymd}"
    if marker.exists():
        raise DataUnavailable(f"no bhavcopy for {day.isoformat()} (NSE had no session; remembered)")
    order = (new_format, old_format) if day >= UDIFF_FROM else (old_format, new_format)
    rows, errors = None, []
    for attempt in order:
        try:
            rows = attempt()
            break
        except DataUnavailable as exc:
            errors.append(str(exc))
    if rows is None:
        # Remember a holiday only when NSE answered "not found" for both formats and the day is
        # old enough that a late publication is not possible. A dropped connection is never remembered.
        if day < date.today() - timedelta(days=7) and all("404" in e for e in errors):
            try:
                marker.write_text("no session", encoding="utf-8")
            except OSError:
                pass
        raise DataUnavailable(f"no bhavcopy for {day.isoformat()}")

    best: dict[str, tuple[int, tuple]] = {}
    for r in rows:
        r = {k.strip(): (v or "").strip() for k, v in r.items() if k}
        symbol = r.get("TckrSymb") or r.get("SYMBOL")
        series = r.get("SctySrs") or r.get("SERIES")
        if not symbol or series not in SERIES:
            continue
        try:
            if "TckrSymb" in r:
                bar = (float(r["OpnPric"]), float(r["HghPric"]), float(r["LwPric"]), float(r["ClsPric"]),
                       float(r["TtlTradgVol"] or 0), r.get("ISIN", ""))
            else:
                bar = (float(r["OPEN"]), float(r["HIGH"]), float(r["LOW"]), float(r["CLOSE"]),
                       float(r["TOTTRDQTY"] or 0), r.get("ISIN", ""))
        except (KeyError, ValueError):
            continue
        if min(bar[:4]) <= 0:
            continue
        rank = _SERIES_RANK[series]
        if symbol not in best or rank < best[symbol][0]:
            best[symbol] = (rank, bar)
    return {s: bar for s, (_, bar) in best.items()}


def weekdays(start: date, end: date) -> list[date]:
    out, cursor = [], start
    while cursor <= end:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor += timedelta(days=1)
    return out


def collect(symbols: set[str], start: date, end: date, fetch: Callable[[date], dict] = session_rows,
            workers: int = 4, progress: bool = False) -> tuple[dict[str, list[tuple]], dict]:
    """Walk every weekday from ``start`` to ``end``; return ({symbol: [(date, o, h, l, c, volume)]}, info)."""
    days = weekdays(start, end)
    rows: dict[str, list[tuple]] = {s: [] for s in symbols}
    sessions, without_file = 0, []

    def load(day: date):
        for attempt in (0, 1):  # one retry: a dropped connection must not look like a holiday
            try:
                return day, fetch(day)
            except DataUnavailable:
                if attempt:
                    return day, None
        return day, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for n, (day, table) in enumerate(pool.map(load, days), 1):
            if table is None:
                without_file.append(day)
            else:
                sessions += 1
                for s in symbols:
                    bar = table.get(s)
                    if bar:
                        rows[s].append((day, *bar[:5]))
            if progress and n % 250 == 0:
                print(f"  bhavcopies read: {n}/{len(days)}", file=sys.stderr, flush=True)
    return rows, {"sessions_read": sessions, "days_without_file": len(without_file)}


def usable_actions(actions: list[dict]) -> tuple[list[dict], list[str]]:
    """Split NSE corporate-action rows into those that can be applied (split, bonus) and notes on the rest."""
    apply, notes, seen = [], [], set()
    for a in actions:
        kind = a.get("type")
        key = (a["ex_date"], kind, a.get("ratio"))
        if key in seen:
            continue
        seen.add(key)
        if kind in ("split", "bonus") and a.get("ratio") and a["ratio"] > 0:
            apply.append(a)
        elif kind in ("demerger", "rights", "unparsed_bonus_or_split", "buyback"):
            notes.append(f"{a['ex_date'].isoformat()} {kind}: {a.get('subject', '')[:90]}")
    return sorted(apply, key=lambda a: a["ex_date"]), notes


_SCHEME_WORDS = ("demerger", "arrangement", "amalgamation", "spin")


def scheme_dates(actions: list[dict]) -> list[date]:
    """Ex-dates of demergers and schemes of arrangement: events that move value to other shares."""
    return sorted({a["ex_date"] for a in actions
                   if a.get("type") == "demerger" or any(w in (a.get("subject") or "").lower() for w in _SCHEME_WORDS)})


def successor(symbol: str, last_day: date, fetch: Callable[[date], dict] = session_rows, horizon: int = 10) -> Optional[str]:
    """The symbol a stock continued under after a rename, found by its unchanged ISIN on the next session.

    Returns None if the stock is still listed under its old name (a gap), if its ISIN
    changed (a face-value split usually does this) or if no session follows.
    """
    try:
        isin = fetch(last_day)[symbol][5]
    except (DataUnavailable, KeyError, IndexError):
        return None
    cursor = last_day
    for _ in range(horizon):
        cursor += timedelta(days=1)
        if cursor.weekday() >= 5:
            continue
        try:
            table = fetch(cursor)
        except DataUnavailable:
            continue
        if symbol in table or not isin:
            return None
        return next((s for s, bar in table.items() if len(bar) > 5 and bar[5] == isin), None)
    return None


def adjust(symbol: str, raw: list[tuple], actions: list[dict], schemes: "list[date] | tuple" = ()) -> tuple[Bars, list[str], list[str]]:
    """Build adjusted Bars from raw (date, o, h, l, c, volume) rows.

    Splits and bonuses rescale earlier prices. For each date in ``schemes`` (a demerger or
    scheme of arrangement) whose day-over-day move, within 3 days of the date, exceeds
    ``SUSPECT_JUMP`` after that, the move is removed: holders were given shares of the
    other company worth the drop, so counting it as a loss would be wrong. A fall with no
    such event on the day is a real fall and is kept.

    Returns (bars, applied notes, suspect one-day jumps remaining after adjustment).
    """
    if not raw:
        raise DataUnavailable(f"no bhavcopy rows for {symbol}")
    raw = sorted(raw, key=lambda r: r[0])
    n = len(raw)
    price_factor = [1.0] * n
    applied: list[str] = []
    for a in actions:
        if a["ex_date"] > raw[-1][0]:
            continue  # after the last session (e.g. delisted first): no later prices to stay consistent with
        factor = 1.0 / a["ratio"] if a["type"] == "split" else 1.0 / (1.0 + a["ratio"])
        touched = 0
        for i in range(n):
            if raw[i][0] < a["ex_date"]:
                price_factor[i] *= factor
                touched += 1
        if 0 < touched < n:
            applied.append(f"{a['ex_date'].isoformat()} {a['type']} x{a['ratio']:g}")
    for event in sorted(schemes, reverse=True):  # latest first, so earlier events see the rescaled history
        i = next((k for k in range(1, n) if event <= raw[k][0] <= event + timedelta(days=3)), None)
        if i is None:
            continue
        move = (raw[i][4] * price_factor[i]) / (raw[i - 1][4] * price_factor[i - 1])
        if abs(move - 1.0) > SUSPECT_JUMP:
            for j in range(i):
                price_factor[j] *= move
            applied.append(f"{raw[i][0].isoformat()} demerger/scheme: {move - 1.0:+.0%} move treated as a transfer of value")
    bars = Bars(symbol, [], [], [], [], [], [])
    for (d, o, h, l, c, v), f in zip(raw, price_factor):
        bars.dates.append(d)
        bars.open.append(o * f)
        bars.high.append(h * f)
        bars.low.append(l * f)
        bars.close.append(c * f)
        bars.volume.append(v / f)
    jumps = [f"{bars.dates[i].isoformat()} {bars.close[i] / bars.close[i - 1] - 1:+.0%}"
             for i in range(1, n)
             if abs(bars.close[i] / bars.close[i - 1] - 1.0) > SUSPECT_JUMP and (bars.dates[i] - bars.dates[i - 1]).days <= 5]
    return bars, applied, jumps


def adjusted_bars(symbols: set[str], start: date, end: date,
                  get_actions: Optional[Callable[[str], list[dict]]] = None,
                  fetch: Callable[[date], dict] = session_rows, workers: int = 4,
                  progress: bool = False) -> tuple[dict[str, Bars], dict]:
    """Adjusted daily bars for ``symbols`` from NSE bhavcopies.

    ``get_actions(symbol)`` returns NSE corporate-action rows (see ``corporate.actions``);
    the default asks NSE. The info dict reports, per symbol, what was adjusted, what was
    not (demergers, rights) and any remaining one-day jump above ``SUSPECT_JUMP``.
    """
    if get_actions is None:
        from .. import corporate

        def get_actions(symbol: str) -> list[dict]:
            return corporate.actions(symbol, start, end)

    raw, info = collect(set(symbols), start, end, fetch, workers, progress)
    out: dict[str, Bars] = {}
    report: dict[str, dict] = {}
    not_found: list[str] = []
    for symbol in sorted(symbols):
        rows = raw.get(symbol)
        if not rows:
            not_found.append(symbol)
            continue
        chain = [symbol]
        while len(chain) < 4 and rows[-1][0] < end - timedelta(days=10):
            nxt = successor(chain[-1], rows[-1][0], fetch)
            if not nxt or nxt in chain:
                break
            more, _ = collect({nxt}, rows[-1][0] + timedelta(days=1), end, fetch, workers)
            if not more[nxt]:
                break
            rows, chain = rows + more[nxt], chain + [nxt]
        actions_all: list[dict] = []
        action_error = None
        for name in chain:
            try:
                actions_all += get_actions(name)
            except DataUnavailable as exc:
                action_error = str(exc)
        actions, unhandled = usable_actions(actions_all)
        bars, applied, jumps = adjust(symbol, rows, actions, scheme_dates(actions_all))
        out[symbol] = bars
        entry = {"first": bars.dates[0].isoformat(), "last": bars.dates[-1].isoformat(), "bars": len(bars),
                 "adjusted_for": applied, "not_adjusted": unhandled, "suspect_jumps": jumps}
        if len(chain) > 1:
            entry["continued_as"] = chain[1:]
        if action_error:
            entry["corporate_actions_unavailable"] = action_error
        report[symbol] = entry
    info.update(symbols=report, not_in_bhavcopies=not_found)
    return out, info
