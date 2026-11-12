"""Futures tools from the NSE F&O bhavcopy: expiry calendar, basis and rollover.

Open interest is in units of the underlying. Basis is futures price minus the
underlying's closing price in the same file.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

FUT = ("IDF", "STF")
OPT = ("IDO", "STO")


def expiry_calendar(rows: list[dict], as_of: date, symbol: Optional[str] = None) -> list[dict]:
    """Every listed expiry for one symbol (or for all index contracts when ``symbol`` is None)."""
    wanted = symbol.upper() if symbol else None
    seen: dict[tuple, dict] = {}
    for r in rows:
        kind = r["FinInstrmTp"]
        if kind not in FUT + OPT:
            continue
        if wanted and r["TckrSymb"] != wanted:
            continue
        if not wanted and kind not in ("IDF", "IDO"):
            continue
        key = (r["TckrSymb"], r["XpryDt"])
        entry = seen.setdefault(key, {"symbol": r["TckrSymb"], "expiry": r["XpryDt"], "futures": False, "options": False,
                                      "lot_size": None, "open_interest_units": 0})
        entry["futures" if kind in FUT else "options"] = True
        if r.get("NewBrdLotQty"):
            entry["lot_size"] = int(float(r["NewBrdLotQty"]))
        entry["open_interest_units"] += int(float(r["OpnIntrst"] or 0))
    out = []
    for entry in seen.values():
        expiry = date.fromisoformat(entry["expiry"])
        entry["weekday"] = expiry.strftime("%A")
        entry["days_to_expiry"] = (expiry - as_of).days
        out.append(entry)
    out.sort(key=lambda e: (e["symbol"], e["expiry"]))
    return out


def futures_curve(rows: list[dict], symbol: str, as_of: date) -> dict:
    """Each futures expiry for ``symbol``: price, basis to spot, annualised basis and open interest."""
    wanted = symbol.upper()
    legs, spot = [], None
    for r in rows:
        if r["TckrSymb"] != wanted or r["FinInstrmTp"] not in FUT:
            continue
        if r.get("UndrlygPric"):
            spot = float(r["UndrlygPric"])
        legs.append({
            "expiry": r["XpryDt"],
            "price": float(r["SttlmPric"] or r["ClsPric"]),
            "open_interest_units": int(float(r["OpnIntrst"] or 0)),
            "oi_change_units": int(float(r["ChngInOpnIntrst"] or 0)),
            "volume_contracts": int(float(r["TtlTradgVol"] or 0)),
        })
    if not legs:
        raise ValueError(f"no futures for {wanted} in this file")
    legs.sort(key=lambda leg: leg["expiry"])
    total_oi = sum(leg["open_interest_units"] for leg in legs)
    for leg in legs:
        days = (date.fromisoformat(leg["expiry"]) - as_of).days
        leg["days_to_expiry"] = days
        if spot:
            basis = leg["price"] - spot
            leg["basis"] = round(basis, 2)
            leg["basis_pct"] = round(basis / spot * 100, 3)
            leg["annualised_basis_pct"] = round(basis / spot * 365 / days * 100, 2) if days > 0 else None
        leg["share_of_open_interest_pct"] = round(leg["open_interest_units"] / total_oi * 100, 2) if total_oi else None
    beyond_near = sum(leg["open_interest_units"] for leg in legs[1:])
    calendar_spread = round(legs[1]["price"] - legs[0]["price"], 2) if len(legs) > 1 else None
    return {
        "symbol": wanted,
        "as_of": as_of.isoformat(),
        "spot": spot,
        "contracts": legs,
        "total_open_interest_units": total_oi,
        "rollover_pct": round(beyond_near / total_oi * 100, 2) if total_oi else None,
        "near_to_next_spread": calendar_spread,
    }


def rollover_table(rows: list[dict], as_of: date, min_oi_units: int = 0) -> list[dict]:
    """Rollover and near-month basis for every stock and index with futures, highest rollover first."""
    symbols = sorted({r["TckrSymb"] for r in rows if r["FinInstrmTp"] in FUT})
    out = []
    for symbol in symbols:
        curve = futures_curve(rows, symbol, as_of)
        if curve["total_open_interest_units"] < min_oi_units or curve["rollover_pct"] is None:
            continue
        near = curve["contracts"][0]
        out.append({
            "symbol": symbol,
            "rollover_pct": curve["rollover_pct"],
            "near_expiry": near["expiry"],
            "near_basis_pct": near.get("basis_pct"),
            "near_annualised_basis_pct": near.get("annualised_basis_pct"),
            "total_open_interest_units": curve["total_open_interest_units"],
        })
    out.sort(key=lambda r: -r["rollover_pct"])
    return out


def parse_ban_list(text: str) -> dict:
    """NSE's F&O ban list: {"trade_date": "...", "symbols": [...]}."""
    lines = [line.strip() for line in text.lstrip("﻿").splitlines() if line.strip()]
    trade_date = lines[0].split(":")[0].replace("Securities in Ban For Trade Date", "").strip() if lines else ""
    symbols = [line.split(",", 1)[1].strip() for line in lines[1:] if "," in line and line.split(",", 1)[0].strip().isdigit()]
    return {"trade_date": trade_date, "symbols": symbols}
