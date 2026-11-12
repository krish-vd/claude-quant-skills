"""Who holds what in Indian equity derivatives, and institutional cash flows.

Sources (all NSE's own):
* Participant-wise open interest: one CSV per trading day in the exchange archive,
  with long and short contracts for Clients, DIIs, FIIs and Proprietary desks.
* FII/DII cash-market buy and sell values: NSE publishes only the latest day, so
  each run can append it to a local log to build a history.

Open interest here is in CONTRACTS. Every long has a matching short, so the four
participant groups net to zero in each column pair, apart from occasional
one-contract rounding differences in the published file itself.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from .data import DataUnavailable, cache_dir, cached_get, http_get

REFERER = "https://www.nseindia.com/"
OI_URL = "https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{dmy}.csv"
CASH_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
PARTICIPANTS = ("Client", "DII", "FII", "Pro")
PAIRS = {
    "index_futures": ("Future Index Long", "Future Index Short"),
    "stock_futures": ("Future Stock Long", "Future Stock Short"),
    "index_calls": ("Option Index Call Long", "Option Index Call Short"),
    "index_puts": ("Option Index Put Long", "Option Index Put Short"),
    "stock_calls": ("Option Stock Call Long", "Option Stock Call Short"),
    "stock_puts": ("Option Stock Put Long", "Option Stock Put Short"),
}


def parse_participant_oi(text: str) -> dict[str, dict[str, int]]:
    """{participant: {column: contracts}} from the participant-wise OI file."""
    lines = text.lstrip("﻿").splitlines()
    start = next((i for i, line in enumerate(lines) if line.lower().startswith("client type")), None)
    if start is None:
        raise DataUnavailable("participant OI file has no 'Client Type' header")
    reader = csv.reader(io.StringIO("\n".join(lines[start:])))
    header = [h.strip() for h in next(reader)]
    out: dict[str, dict[str, int]] = {}
    for row in reader:
        if not row or not row[0].strip():
            continue
        name = row[0].strip()
        out[name] = {header[i]: int(float(v)) for i, v in enumerate(row[1:], start=1) if i < len(header) and v.strip()}
    if not all(p in out for p in PARTICIPANTS):
        raise DataUnavailable(f"participant OI file is missing a participant; found {sorted(out)}")
    return out


def participant_oi(day: date) -> dict[str, dict[str, int]]:
    body = cached_get(OI_URL.format(dmy=day.strftime("%d%m%Y")), f"nse_part_oi_{day:%Y%m%d}.csv", 10 * 365 * 86400.0, REFERER)
    text = body.decode("utf-8-sig", errors="replace")
    if "client type" not in text.lower():
        raise DataUnavailable(f"No participant OI file for {day.isoformat()} (holiday, weekend or not yet published)")
    return parse_participant_oi(text)


def latest_participant_oi(on_or_before: Optional[date] = None, lookback_days: int = 7) -> tuple[date, dict]:
    day = on_or_before or date.today()
    for _ in range(lookback_days + 1):
        if day.weekday() < 5:
            try:
                return day, participant_oi(day)
            except DataUnavailable:
                pass
        day -= timedelta(days=1)
    raise DataUnavailable("no participant OI file found in the last week")


def net_positions(table: dict[str, dict[str, int]]) -> dict[str, dict[str, dict]]:
    """For each participant and instrument group: long, short, net and long share of their own book."""
    out: dict[str, dict[str, dict]] = {}
    for who in PARTICIPANTS:
        row, groups = table[who], {}
        for group, (long_col, short_col) in PAIRS.items():
            long_, short = row.get(long_col, 0), row.get(short_col, 0)
            total = long_ + short
            groups[group] = {
                "long": long_, "short": short, "net": long_ - short,
                "long_pct": round(long_ / total * 100, 2) if total else None,
            }
        out[who] = groups
    return out


def compare(current: dict, previous: dict) -> dict[str, dict[str, int]]:
    """Change in net position per participant and group between two days."""
    now, before = net_positions(current), net_positions(previous)
    return {who: {g: now[who][g]["net"] - before[who][g]["net"] for g in PAIRS} for who in PARTICIPANTS}


def parse_cash_flows(payload: list) -> dict:
    """Latest FII and DII cash-market figures, in Rs crore."""
    out: dict = {}
    for row in payload:
        category = str(row.get("category", "")).upper()
        key = "FII" if category.startswith("FII") else "DII" if category.startswith("DII") else None
        if key is None:
            continue
        out[key] = {"buy": float(row["buyValue"]), "sell": float(row["sellValue"]), "net": float(row["netValue"])}
        out["date"] = datetime.strptime(row["date"], "%d-%b-%Y").date().isoformat()
    if "FII" not in out or "DII" not in out:
        raise DataUnavailable("FII/DII response did not contain both categories")
    return out


def cash_flows() -> dict:
    """Latest published FII/DII cash-market activity (Rs crore)."""
    try:
        payload = json.loads(http_get(CASH_URL, REFERER))
    except ValueError as exc:
        raise DataUnavailable("NSE FII/DII response was not readable (the site may be blocking automated requests)") from exc
    return parse_cash_flows(payload)


def log_cash_flows(flow: dict, path: Optional[Path] = None) -> list[dict]:
    """Add ``flow`` to the local history (one row per date) and return the full history, oldest first."""
    path = path or (cache_dir() / "fii_dii_cash_log.json")
    history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    by_date = {row["date"]: row for row in history}
    by_date[flow["date"]] = {"date": flow["date"], "fii_net": flow["FII"]["net"], "dii_net": flow["DII"]["net"]}
    history = [by_date[d] for d in sorted(by_date)]
    path.write_text(json.dumps(history, indent=1), encoding="utf-8")
    return history
