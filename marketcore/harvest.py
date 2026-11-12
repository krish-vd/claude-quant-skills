"""Year-end tax planning on open equity positions (Indian resident, listed equity).

Shares leave a demat account first-in-first-out, so you cannot pick which lot to
sell: a sale always takes the oldest shares of that symbol. Everything here
respects that order.

* Gain harvesting: long-term gains up to the yearly exemption are tax-free, so
  realising them (and buying back) raises the cost base at no tax.
* Loss harvesting: realising a loss creates a loss that can be set off.
* Waiting: a short-term gain close to turning long-term is taxed at a lower rate
  if the sale waits.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from . import rules
from .charges import D, Number
from .tax_india import GRANDFATHER_CUTOFF, Trade, add_months, financial_year, is_long_term, realised_gains, summarise


def open_lots(trades: Iterable[Trade]) -> dict[str, list[dict]]:
    """Lots still held after matching every sell FIFO: {symbol: [{date, qty, unit_cost, asset_class}]}."""
    book: dict[str, deque] = defaultdict(deque)
    for t in sorted(trades, key=lambda t: (t.trade_date, 0 if t.side == "buy" else 1)):
        key, qty = t.symbol.upper(), D(t.quantity)
        if t.side == "buy":
            book[key].append({"date": t.trade_date, "qty": qty, "unit_cost": D(t.price) + D(t.charges) / qty,
                              "asset_class": t.asset_class})
            continue
        remaining = qty
        while remaining > 0:
            if not book[key]:
                raise ValueError(f"{t.symbol}: sell on {t.trade_date} exceeds the buys supplied")
            lot = book[key][0]
            take = min(remaining, lot["qty"])
            lot["qty"] -= take
            remaining -= take
            if lot["qty"] == 0:
                book[key].popleft()
    return {s: list(lots) for s, lots in book.items() if lots}


def plan(
    trades: list[Trade],
    prices: dict[str, Number],
    today: date,
    fmv_31jan2018: Optional[dict[str, Number]] = None,
    wait_window_days: int = 60,
) -> dict:
    """Harvesting picture for the financial year containing ``today``.

    ``prices`` are current prices per symbol. Only ``listed_equity`` lots are
    planned; other asset classes are listed as not covered.
    """
    book = rules.load("in_tax")
    rule = book["asset_classes"]["listed_equity"]
    months = rule["long_term_after_months"]
    exemption = Decimal(rule["ltcg"]["exemption_per_fy"])
    lt_rate, st_rate = Decimal(rule["ltcg"]["rate"]), Decimal(rule["stcg"]["rate"])
    cess = Decimal(book["cess_rate"])
    fy = financial_year(today)
    px = {k.upper(): D(v) for k, v in prices.items()}
    fmv = {k.upper(): D(v) for k, v in (fmv_31jan2018 or {}).items()}

    realised, warnings = realised_gains(trades, fmv_31jan2018)
    year = next((y for y in summarise(realised) if y.fy == fy), None)
    realised_lt = realised_st = Decimal(0)
    if year:
        for b in year.buckets:
            if b.asset_class == "listed_equity":
                if b.term == "long":
                    realised_lt = b.net
                else:
                    realised_st = b.net
    exemption_left = max(Decimal(0), exemption - max(Decimal(0), realised_lt))

    symbols, not_covered, missing_price = [], [], []
    for symbol, lots in sorted(open_lots(trades).items()):
        if any(l["asset_class"] != "listed_equity" for l in lots):
            not_covered.append(symbol)
            continue
        if symbol not in px:
            missing_price.append(symbol)
            continue
        price = px[symbol]
        rows, front_long_term = [], True
        for position, lot in enumerate(lots):
            cost = lot["unit_cost"]
            if lot["date"] < GRANDFATHER_CUTOFF and symbol in fmv:
                cost = max(cost, min(fmv[symbol], price))
            long_term = is_long_term(lot["date"], today, months)
            first_lt = add_months(lot["date"], months) + timedelta(days=1)
            gain = (price - cost) * lot["qty"]
            reachable_as_long_term = front_long_term and long_term
            front_long_term = reachable_as_long_term
            rows.append({
                "fifo_position": position + 1,
                "buy_date": lot["date"].isoformat(),
                "quantity": str(lot["qty"]),
                "unit_cost": str(cost.quantize(Decimal("0.0001"))),
                "term_if_sold_today": "long" if long_term else "short",
                "first_long_term_date": first_lt.isoformat(),
                "days_until_long_term": max((first_lt - today).days, 0),
                "unrealised_gain": str(gain.quantize(Decimal("0.01"))),
                "gain_per_unit": str((price - cost).quantize(Decimal("0.0001"))),
                "sellable_now_as_long_term": reachable_as_long_term,
            })
        symbols.append({"symbol": symbol, "price": str(price), "lots": rows})

    # Gain harvesting: long-term lots at the FRONT of each symbol's queue, largest gain per unit first.
    candidates = []
    for s in symbols:
        for lot in s["lots"]:
            if not lot["sellable_now_as_long_term"]:
                break
            if Decimal(lot["gain_per_unit"]) > 0:
                candidates.append((s["symbol"], lot))
            # a front lot at a loss still has to be sold before later lots; stop harvesting gains past it
            else:
                break
    gain_plan, room = [], exemption_left
    for symbol, lot in sorted(candidates, key=lambda c: (c[0], c[1]["fifo_position"])):
        if room <= 0:
            break
        per_unit, qty = Decimal(lot["gain_per_unit"]), Decimal(lot["quantity"])
        units = min(qty, Decimal(math.floor(room / per_unit)))
        if units <= 0:
            continue
        gain = units * per_unit
        room -= gain
        gain_plan.append({"symbol": symbol, "buy_date": lot["buy_date"], "units_to_sell": str(units),
                          "long_term_gain_realised": str(gain.quantize(Decimal("0.01")))})
    harvested = exemption_left - room

    loss_lots, wait_lots = [], []
    for s in symbols:
        blocked = False
        for lot in s["lots"]:
            gain = Decimal(lot["unrealised_gain"])
            if gain < 0 and not blocked:
                loss_lots.append({"symbol": s["symbol"], "buy_date": lot["buy_date"], "quantity": lot["quantity"],
                                  "term": lot["term_if_sold_today"], "loss": lot["unrealised_gain"]})
            else:
                blocked = True  # later lots cannot be sold without first selling this one
            if lot["term_if_sold_today"] == "short" and gain > 0 and lot["days_until_long_term"] <= wait_window_days:
                saving = gain * (st_rate - lt_rate) * (1 + cess)
                wait_lots.append({"symbol": s["symbol"], "buy_date": lot["buy_date"], "quantity": lot["quantity"],
                                  "unrealised_gain": lot["unrealised_gain"],
                                  "first_long_term_date": lot["first_long_term_date"],
                                  "days_until_long_term": lot["days_until_long_term"],
                                  "tax_rate_difference_on_this_gain": str(saving.quantize(Decimal("0.01")))})

    return {
        "financial_year": fy,
        "as_of": today.isoformat(),
        "realised_long_term_gain_so_far": str(realised_lt),
        "realised_short_term_gain_so_far": str(realised_st),
        "ltcg_exemption": str(exemption),
        "ltcg_exemption_left": str(exemption_left),
        "gain_harvest": {
            "sales": gain_plan,
            "long_term_gain_realised": str(harvested.quantize(Decimal("0.01"))),
            "exemption_left_after": str(room.quantize(Decimal("0.01"))),
            "future_tax_avoided": str((harvested * lt_rate * (1 + cess)).quantize(Decimal("0.01"))),
        },
        "loss_harvest_candidates": loss_lots,
        "wait_for_long_term": wait_lots,
        "positions": symbols,
        "symbols_without_a_price": missing_price,
        "symbols_not_covered": not_covered,
        "warnings": warnings,
    }
