"""Option-chain analysis from the NSE F&O bhavcopy (end of day).

For one underlying and expiry: open interest by strike, put/call ratios, max
pain, the forward price implied by put-call parity, at-the-money implied
volatility, the straddle-implied move, and the heaviest open-interest strikes.

In the bhavcopy, open interest is in UNITS of the underlying (lots x lot size)
and traded volume is in CONTRACTS.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .options import implied_volatility


@dataclass
class StrikeRow:
    strike: float
    call_price: Optional[float] = None
    call_oi: int = 0
    call_oi_change: int = 0
    call_volume: int = 0
    put_price: Optional[float] = None
    put_oi: int = 0
    put_oi_change: int = 0
    put_volume: int = 0


def expiries(rows: list[dict], symbol: str) -> list[str]:
    """Option expiry dates listed for ``symbol``, nearest first."""
    wanted = symbol.upper()
    return sorted({r["XpryDt"] for r in rows if r["TckrSymb"] == wanted and r["FinInstrmTp"] in ("IDO", "STO")})


def build_chain(rows: list[dict], symbol: str, expiry: str) -> tuple[list[StrikeRow], dict]:
    """Strike rows for one expiry, plus {spot, lot_size, futures: {expiry: price}}."""
    wanted = symbol.upper()
    strikes: dict[float, StrikeRow] = {}
    info: dict = {"spot": None, "lot_size": None, "futures": {}}
    for r in rows:
        if r["TckrSymb"] != wanted:
            continue
        kind = r["FinInstrmTp"]
        if kind in ("IDF", "STF"):
            info["futures"][r["XpryDt"]] = float(r["SttlmPric"] or r["ClsPric"])
            continue
        if kind not in ("IDO", "STO") or r["XpryDt"] != expiry:
            continue
        if r.get("UndrlygPric"):
            info["spot"] = float(r["UndrlygPric"])
        if r.get("NewBrdLotQty"):
            info["lot_size"] = int(float(r["NewBrdLotQty"]))
        strike = float(r["StrkPric"])
        row = strikes.setdefault(strike, StrikeRow(strike))
        price = float(r["SttlmPric"] or r["ClsPric"] or 0)
        oi, change, volume = int(float(r["OpnIntrst"] or 0)), int(float(r["ChngInOpnIntrst"] or 0)), int(float(r["TtlTradgVol"] or 0))
        if r["OptnTp"] == "CE":
            row.call_price, row.call_oi, row.call_oi_change, row.call_volume = price, oi, change, volume
        elif r["OptnTp"] == "PE":
            row.put_price, row.put_oi, row.put_oi_change, row.put_volume = price, oi, change, volume
    return [strikes[k] for k in sorted(strikes)], info


def max_pain(chain: list[StrikeRow]) -> Optional[float]:
    """The strike at which option buyers, in total, would be paid the least at expiry.

    For each candidate strike K: sum of call OI x max(K - strike, 0) plus put OI x max(strike - K, 0).
    """
    best, best_value = None, None
    for candidate in chain:
        k = candidate.strike
        total = sum(r.call_oi * max(k - r.strike, 0.0) + r.put_oi * max(r.strike - k, 0.0) for r in chain)
        if best_value is None or total < best_value:
            best, best_value = k, total
    return best


def parity_forward(chain: list[StrikeRow], t: float, rate: float) -> Optional[tuple[float, float]]:
    """Forward price implied by put-call parity, F = K + (C - P) x e^(rT), taken at the
    strike where call and put prices are closest (the most liquid, least biased point).
    Returns (forward, strike used). Only strikes that actually traded are considered."""
    candidates = [
        r for r in chain
        if r.call_price and r.put_price and r.call_volume > 0 and r.put_volume > 0
    ]
    if not candidates:
        return None
    row = min(candidates, key=lambda r: abs(r.call_price - r.put_price))
    return row.strike + (row.call_price - row.put_price) * math.exp(rate * t), row.strike


def analyse(rows: list[dict], symbol: str, expiry: str, as_of: date, rate: float = 0.0, top: int = 5) -> dict:
    """Full chain summary for one expiry as of the bhavcopy date."""
    chain, info = build_chain(rows, symbol, expiry)
    if not chain:
        raise ValueError(f"no option rows for {symbol.upper()} expiring {expiry}")
    days = (date.fromisoformat(expiry) - as_of).days
    t = max(days, 0) / 365.0
    lot = info["lot_size"] or 1

    call_oi, put_oi = sum(r.call_oi for r in chain), sum(r.put_oi for r in chain)
    call_vol, put_vol = sum(r.call_volume for r in chain), sum(r.put_volume for r in chain)

    forward, forward_source, parity_strike = None, None, None
    if expiry in info["futures"]:
        forward, forward_source = info["futures"][expiry], "futures settlement price for the same expiry"
    else:
        parity = parity_forward(chain, t, rate)
        if parity:
            forward, parity_strike = parity
            forward_source = f"put-call parity at the {parity_strike:g} strike (no future lists for this expiry)"

    atm = iv_call = iv_put = straddle = None
    if forward is not None:
        both = [r for r in chain if r.call_price and r.put_price]
        if both:
            atm_row = min(both, key=lambda r: abs(r.strike - forward))
            atm, straddle = atm_row.strike, atm_row.call_price + atm_row.put_price
            if t > 0:
                iv_call = implied_volatility("call", atm_row.call_price, forward, atm, t, rate)
                iv_put = implied_volatility("put", atm_row.put_price, forward, atm, t, rate)

    def ranked(attr: str) -> list[dict]:
        ordered = sorted(chain, key=lambda r: -getattr(r, attr))[:top]
        return [{"strike": r.strike, "oi_units": getattr(r, attr), "oi_lots": getattr(r, attr) // lot,
                 "oi_change_units": getattr(r, attr + "_change")} for r in ordered if getattr(r, attr) > 0]

    ivs = [v for v in (iv_call, iv_put) if v is not None]
    return {
        "symbol": symbol.upper(),
        "expiry": expiry,
        "as_of": as_of.isoformat(),
        "days_to_expiry": days,
        "spot": info["spot"],
        "lot_size": info["lot_size"],
        "forward": None if forward is None else round(forward, 2),
        "forward_source": forward_source,
        "strikes_listed": len(chain),
        "total_call_oi_units": call_oi,
        "total_put_oi_units": put_oi,
        "pcr_open_interest": round(put_oi / call_oi, 3) if call_oi else None,
        "pcr_volume": round(put_vol / call_vol, 3) if call_vol else None,
        "max_pain": max_pain(chain),
        "atm_strike": atm,
        "atm_straddle_price": None if straddle is None else round(straddle, 2),
        "straddle_implied_move_pct": None if straddle is None or not forward else round(straddle / forward * 100, 2),
        "atm_iv_call_pct": None if iv_call is None else round(iv_call * 100, 2),
        "atm_iv_put_pct": None if iv_put is None else round(iv_put * 100, 2),
        "atm_iv_pct": round(sum(ivs) / len(ivs) * 100, 2) if ivs else None,
        "highest_call_oi": ranked("call_oi"),
        "highest_put_oi": ranked("put_oi"),
        "largest_call_oi_additions": [
            {"strike": r.strike, "oi_change_units": r.call_oi_change}
            for r in sorted(chain, key=lambda r: -r.call_oi_change)[:top] if r.call_oi_change > 0
        ],
        "largest_put_oi_additions": [
            {"strike": r.strike, "oi_change_units": r.put_oi_change}
            for r in sorted(chain, key=lambda r: -r.put_oi_change)[:top] if r.put_oi_change > 0
        ],
    }
