"""Commitments of Traders: who holds US futures, from the CFTC's weekly report.

Source: CFTC public reporting API, legacy futures-only report (dataset 6dca-aqww).
Non-commercials are large speculators (funds); commercials are hedgers (producers,
users, dealers). Positions are contracts, as of the Tuesday before publication
(normally Friday).
"""
from __future__ import annotations

import json
import urllib.parse
from datetime import date
from typing import Optional

from .data import DataUnavailable, cached_get

URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"

# Contract market codes, each checked against the live report on 2026-11-12.
MARKETS = {
    "gold": "088691", "silver": "084691", "copper": "085692", "crude_wti": "067651", "natural_gas": "023651",
    "sp500_emini": "13874A", "nasdaq100_emini": "209742", "us_10y_note": "043602", "us_dollar_index": "098662",
    "euro_fx": "099741", "japanese_yen": "097741", "bitcoin": "133741",
}


def fetch(code: str, weeks: int = 156) -> list[dict]:
    query = urllib.parse.urlencode({"$limit": weeks, "$order": "report_date_as_yyyy_mm_dd DESC", "cftc_contract_market_code": code})
    body = cached_get(f"{URL}?{query}", f"cftc_{code}_{weeks}.json", 12 * 3600.0)
    try:
        rows = json.loads(body)
    except ValueError as exc:
        raise DataUnavailable("CFTC response was not readable") from exc
    if not isinstance(rows, list) or not rows:
        raise DataUnavailable(f"no CFTC report rows for contract code {code}")
    return rows


def search(text: str) -> list[dict]:
    """Contract markets whose name contains ``text`` in the latest reports."""
    query = urllib.parse.urlencode({"$select": "market_and_exchange_names,cftc_contract_market_code,max(report_date_as_yyyy_mm_dd)",
                                    "$group": "market_and_exchange_names,cftc_contract_market_code",
                                    "$where": f"upper(market_and_exchange_names) like '%{text.upper().replace(chr(39), '')}%'",
                                    "$limit": 50})
    body = cached_get(f"{URL}?{query}", f"cftc_search_{text.upper()}.json", 7 * 86400.0)
    rows = json.loads(body)
    return [{"market": r["market_and_exchange_names"], "code": r["cftc_contract_market_code"],
             "latest_report": r.get("max_report_date_as_yyyy_mm_dd", "")[:10]} for r in rows]


def analyse(rows: list[dict]) -> dict:
    """Net positions, their history position (COT index) and the latest change. ``rows`` newest first."""
    def num(r: dict, key: str) -> float:
        return float(r.get(key) or 0)

    series = []
    for r in rows:
        oi = num(r, "open_interest_all")
        spec = num(r, "noncomm_positions_long_all") - num(r, "noncomm_positions_short_all")
        comm = num(r, "comm_positions_long_all") - num(r, "comm_positions_short_all")
        small = num(r, "nonrept_positions_long_all") - num(r, "nonrept_positions_short_all")
        series.append({"date": r["report_date_as_yyyy_mm_dd"][:10], "open_interest": oi, "speculator_net": spec,
                       "commercial_net": comm, "small_trader_net": small})
    latest = series[0]

    def index(key: str) -> Optional[float]:
        values = [s[key] for s in series]
        lo, hi = min(values), max(values)
        return round((latest[key] - lo) / (hi - lo) * 100, 1) if hi > lo else None

    prev = series[1] if len(series) > 1 else None
    return {
        "market": rows[0].get("market_and_exchange_names"),
        "report_date": latest["date"],
        "weeks_of_history": len(series),
        "open_interest": int(latest["open_interest"]),
        "speculator_net": int(latest["speculator_net"]),
        "speculator_net_pct_of_oi": round(latest["speculator_net"] / latest["open_interest"] * 100, 2) if latest["open_interest"] else None,
        "speculator_cot_index": index("speculator_net"),
        "commercial_net": int(latest["commercial_net"]),
        "commercial_cot_index": index("commercial_net"),
        "small_trader_net": int(latest["small_trader_net"]),
        "speculator_net_change_1w": int(latest["speculator_net"] - prev["speculator_net"]) if prev else None,
        "speculator_net_change_4w": int(latest["speculator_net"] - series[4]["speculator_net"]) if len(series) > 4 else None,
        "history": [{k: (int(v) if isinstance(v, float) else v) for k, v in s.items()} for s in reversed(series[:12])],
    }
