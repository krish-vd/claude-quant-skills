"""Convert a broker tradebook into the standard trade CSV used by the tax engine.

Three jobs:

1. Find the date, symbol, side, quantity and price columns, whatever the broker calls them.
2. Keep only cash-equity rows; derivatives are set aside (they are business income).
3. Separate intraday trades. Shares bought and sold on the same day in the same
   scrip never reach the demat account: that part is speculative business income,
   not a capital gain, and must not enter the FIFO lots.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

SYNONYMS = {
    "date": ["trade_date", "trade date", "date", "execution date and time", "execution date", "order_execution_time",
             "trade time", "date/time", "tradedate", "transaction date", "time"],
    "symbol": ["symbol", "tradingsymbol", "trading symbol", "scrip", "scrip name", "stock name", "security", "ticker", "instrument"],
    "side": ["trade_type", "trade type", "type", "side", "buy/sell", "transaction type", "action", "b/s"],
    "quantity": ["quantity", "qty", "shares", "filled qty", "traded qty", "units"],
    "price": ["price", "trade price", "avg price", "average price", "rate", "t. price", "traded price"],
    "segment": ["segment", "product", "asset class", "instrument type"],
    "isin": ["isin"],
}
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d %b %Y", "%Y/%m/%d")
DERIVATIVE_MARKERS = ("FO", "F&O", "FUT", "OPT", "NFO", "CDS", "MCX", "COM", "BFO", "DERIV")
PRESETS = {
    # Zerodha Console tradebook export. Column names are from memory of that export, not
    # re-verified against a current file; auto-detection finds the same columns either way.
    "zerodha": {"date": "trade_date", "symbol": "symbol", "side": "trade_type", "quantity": "quantity",
                "price": "price", "segment": "segment", "isin": "isin"},
}


@dataclass
class Fill:
    trade_date: date
    symbol: str
    side: str
    quantity: float
    price: float
    line: int


def detect_columns(header: list[str], overrides: Optional[dict] = None) -> dict:
    """Map our field names to the file's column names. Raises if a required one is missing."""
    lower = {h.strip().lower(): h for h in header if h}
    found: dict[str, str] = {}
    for field, names in SYNONYMS.items():
        for name in names:
            if name in lower:
                found[field] = lower[name]
                break
    for field, column in (overrides or {}).items():
        if column.strip().lower() not in lower:
            raise ValueError(f"column {column!r} (for {field}) is not in the file. Columns: {', '.join(header)}")
        found[field] = lower[column.strip().lower()]
    missing = [f for f in ("date", "symbol", "side", "quantity", "price") if f not in found]
    if missing:
        raise ValueError(f"could not find column(s) for: {', '.join(missing)}. Columns in the file: {', '.join(header)}. "
                         f"Name them with a mapping, for example date=TradeDate.")
    return found


def parse_date(text: str, fmt: Optional[str] = None) -> date:
    value = text.strip()
    if fmt:
        return datetime.strptime(value, fmt).date()
    head = value.replace("T", " ").split(" ")[0] if value[:4].isdigit() or value[2:3] in "-/" else value
    for candidate in (head, value):
        for pattern in DATE_FORMATS:
            try:
                return datetime.strptime(candidate, pattern).date()
            except ValueError:
                continue
    raise ValueError(f"unrecognised date {text!r}; pass an explicit date format")


def parse_side(text: str) -> str:
    value = text.strip().lower()
    if value in ("buy", "b", "bought", "purchase"):
        return "buy"
    if value in ("sell", "s", "sold", "sale"):
        return "sell"
    raise ValueError(f"unrecognised side {text!r}")


def read_fills(text: str, overrides: Optional[dict] = None, date_format: Optional[str] = None) -> tuple[list[Fill], dict]:
    """Parse a tradebook CSV. Returns (equity fills in file order, report)."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if not reader.fieldnames:
        raise ValueError("the file has no header row")
    cols = detect_columns(list(reader.fieldnames), overrides)
    fills: list[Fill] = []
    skipped_derivatives, bad_rows = 0, []
    for n, row in enumerate(reader, start=2):
        if not any((v or "").strip() for v in row.values()):
            continue
        segment = (row.get(cols.get("segment", ""), "") or "").upper()
        if any(marker in segment for marker in DERIVATIVE_MARKERS):
            skipped_derivatives += 1
            continue
        try:
            quantity = float(str(row[cols["quantity"]]).replace(",", ""))
            price = float(str(row[cols["price"]]).replace(",", ""))
            if quantity <= 0 or price < 0:
                raise ValueError("quantity must be positive and price not negative")
            fills.append(Fill(parse_date(row[cols["date"]], date_format), row[cols["symbol"]].strip().upper(),
                              parse_side(row[cols["side"]]), quantity, price, n))
        except (ValueError, KeyError, AttributeError) as exc:
            bad_rows.append(f"line {n}: {exc}")
    return fills, {"columns_used": cols, "derivative_rows_skipped": skipped_derivatives, "unreadable_rows": bad_rows}


def split_intraday(fills: list[Fill]) -> tuple[list[Fill], list[dict]]:
    """Separate same-day round trips from delivery trades.

    For each symbol and day the intraday quantity is the smaller of the day's buys
    and sells. It is matched first-in-first-out against both sides, in file order;
    what remains on either side is a delivery trade.
    """
    by_key: dict[tuple, list[Fill]] = defaultdict(list)
    for f in fills:
        by_key[(f.symbol, f.trade_date)].append(f)

    delivery: list[Fill] = []
    intraday: list[dict] = []
    for (symbol, day), group in by_key.items():
        bought = sum(f.quantity for f in group if f.side == "buy")
        sold = sum(f.quantity for f in group if f.side == "sell")
        matched = min(bought, sold)
        if matched <= 0:
            delivery.extend(group)
            continue
        value = {"buy": 0.0, "sell": 0.0}
        left = {"buy": matched, "sell": matched}
        for f in group:
            take = min(f.quantity, left[f.side])
            left[f.side] -= take
            value[f.side] += take * f.price
            if f.quantity - take > 1e-9:
                delivery.append(Fill(f.trade_date, f.symbol, f.side, f.quantity - take, f.price, f.line))
        intraday.append({
            "date": day.isoformat(), "symbol": symbol, "quantity": matched,
            "buy_value": round(value["buy"], 2), "sell_value": round(value["sell"], 2),
            "pnl_before_charges": round(value["sell"] - value["buy"], 2),
        })
    delivery.sort(key=lambda f: (f.trade_date, f.line))
    intraday.sort(key=lambda r: (r["date"], r["symbol"]))
    return delivery, intraday


def to_standard_csv(fills: list[Fill], asset_class: str = "listed_equity") -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["date", "symbol", "side", "quantity", "price", "asset_class", "charges"])
    for f in fills:
        quantity = int(f.quantity) if float(f.quantity).is_integer() else f.quantity
        writer.writerow([f.trade_date.isoformat(), f.symbol, f.side, quantity, f.price, asset_class, 0])
    return out.getvalue()
