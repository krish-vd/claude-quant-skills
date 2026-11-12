"""Delivery-volume screen from NSE's security-wise delivery file.

NSE publishes, for every stock and day, how many of the traded shares were
actually delivered (settled into demat) rather than squared off intraday. A jump
in delivered quantity means more shares changed hands for keeps. It does not say
whether the buyers or the sellers were the informed side.
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from typing import Optional

from .data import DataUnavailable, cached_get

URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{dmy}.csv"
REFERER = "https://www.nseindia.com/"


def parse(text: str) -> dict[str, dict]:
    """{symbol: {close, prev_close, volume, turnover_lakh, delivered, delivery_pct}} for the EQ series."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = [h.strip().upper() for h in next(reader, [])]
    needed = ("SYMBOL", "SERIES", "PREV_CLOSE", "CLOSE_PRICE", "TTL_TRD_QNTY", "TURNOVER_LACS", "DELIV_QTY", "DELIV_PER")
    if any(n not in header for n in needed):
        raise DataUnavailable("delivery file has an unexpected layout")
    idx = {n: header.index(n) for n in needed}
    out = {}
    for row in reader:
        if len(row) < len(header):
            continue
        cell = {n: row[i].strip() for n, i in idx.items()}
        if cell["SERIES"] != "EQ" or cell["DELIV_QTY"] in ("-", ""):
            continue
        try:
            out[cell["SYMBOL"]] = {
                "close": float(cell["CLOSE_PRICE"]), "prev_close": float(cell["PREV_CLOSE"]),
                "volume": float(cell["TTL_TRD_QNTY"]), "turnover_lakh": float(cell["TURNOVER_LACS"]),
                "delivered": float(cell["DELIV_QTY"]), "delivery_pct": float(cell["DELIV_PER"]),
            }
        except ValueError:
            continue
    return out


def day_table(day: date) -> dict[str, dict]:
    body = cached_get(URL.format(dmy=day.strftime("%d%m%Y")), f"nse_deliv_{day:%Y%m%d}.csv", 10 * 365 * 86400.0, REFERER)
    text = body.decode("utf-8-sig", errors="replace")
    if "DELIV_QTY" not in text[:400].upper():
        raise DataUnavailable(f"No delivery file for {day.isoformat()}")
    return parse(text)


def recent_tables(sessions: int, on_or_before: Optional[date] = None) -> list[tuple[date, dict]]:
    """The latest ``sessions`` trading days that have a delivery file, oldest first."""
    cursor, found = on_or_before or date.today(), []
    for _ in range(sessions * 2 + 12):
        if len(found) == sessions:
            break
        if cursor.weekday() < 5:
            try:
                found.append((cursor, day_table(cursor)))
            except DataUnavailable:
                pass
        cursor -= timedelta(days=1)
    if len(found) < 2:
        raise DataUnavailable("fewer than two delivery files are available")
    return list(reversed(found))


def screen(tables: list[tuple[date, dict]], min_turnover_lakh: float = 500.0, min_ratio: float = 2.0) -> list[dict]:
    """Stocks whose delivered quantity on the latest day is at least ``min_ratio`` times
    their average over the earlier days supplied. Needs a figure on every earlier day."""
    latest_day, latest = tables[-1]
    history = tables[:-1]
    rows = []
    for symbol, now in latest.items():
        past = [t[symbol] for _, t in history if symbol in t]
        if len(past) < len(history) or now["turnover_lakh"] < min_turnover_lakh:
            continue
        avg_delivered = sum(p["delivered"] for p in past) / len(past)
        avg_pct = sum(p["delivery_pct"] for p in past) / len(past)
        if avg_delivered <= 0:
            continue
        ratio = now["delivered"] / avg_delivered
        if ratio < min_ratio:
            continue
        change = (now["close"] / now["prev_close"] - 1) * 100 if now["prev_close"] else None
        rows.append({
            "symbol": symbol,
            "date": latest_day.isoformat(),
            "close": now["close"],
            "price_change_pct": None if change is None else round(change, 2),
            "delivered_qty": int(now["delivered"]),
            "avg_delivered_qty": int(avg_delivered),
            "delivery_ratio": round(ratio, 2),
            "delivery_pct": now["delivery_pct"],
            "avg_delivery_pct": round(avg_pct, 2),
            "turnover_lakh": now["turnover_lakh"],
            "sessions_in_average": len(past),
        })
    rows.sort(key=lambda r: -r["delivery_ratio"])
    return rows
