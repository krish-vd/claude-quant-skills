"""Apply splits and bonus issues to a trade history, and rebalance a portfolio to targets.

Corporate actions change the number of shares without a trade, so a tradebook
alone gives wrong lots after one. Two actions are handled:

* split: every share becomes ``ratio`` shares. Earlier trades are restated:
  quantity x ratio, price / ratio. Cost and purchase dates are unchanged.
* bonus: ``ratio`` new shares for each share held. The new shares form a new lot
  acquired on the action date at zero cost.

Demergers, mergers, rights issues and buybacks are not handled.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Iterable, Optional

from .charges import D, Number
from .tax_india import Trade


def apply_actions(trades: Iterable[Trade], actions: list[dict]) -> tuple[list[Trade], list[str]]:
    """Restate ``trades`` for the given actions. Each action is
    {"symbol", "date" (ex-date), "type": "split"|"bonus", "ratio"}.

    ``ratio`` for a split is new shares per old share (a 1:5 split, one share
    becoming five, is 5; a face-value split from 10 to 2 is also 5). For a bonus
    it is bonus shares per share held (a 1:1 bonus is 1; a 1:2 bonus, one for
    every two held, is 0.5). Actions are applied in date order.
    """
    out = sorted(trades, key=lambda t: (t.trade_date, 0 if t.side == "buy" else 1))
    notes: list[str] = []
    for action in sorted(actions, key=lambda a: a["date"]):
        symbol, ex_date, kind = action["symbol"].upper(), action["date"], action["type"].lower()
        ratio = D(action["ratio"])
        if ratio <= 0:
            raise ValueError(f"{symbol} {ex_date}: ratio must be positive")
        if kind == "split":
            touched = 0
            for i, t in enumerate(out):
                if t.symbol.upper() == symbol and t.trade_date < ex_date:
                    out[i] = replace(t, quantity=D(t.quantity) * ratio, price=D(t.price) / ratio)
                    touched += 1
            notes.append(f"{symbol}: split x{ratio} on {ex_date.isoformat()} restated {touched} earlier trade(s).")
        elif kind == "bonus":
            held = Decimal(0)
            for t in out:
                if t.symbol.upper() == symbol and t.trade_date < ex_date:
                    held += D(t.quantity) if t.side == "buy" else -D(t.quantity)
            if held < 0:
                raise ValueError(f"{symbol}: sells exceed buys before {ex_date.isoformat()}; the history is incomplete")
            bonus = (held * ratio).to_integral_value(rounding=ROUND_FLOOR)
            if bonus > 0:
                asset_class = next((t.asset_class for t in out if t.symbol.upper() == symbol), "listed_equity")
                out.append(Trade(ex_date, symbol, "buy", bonus, 0, asset_class, 0))
                out.sort(key=lambda t: (t.trade_date, 0 if t.side == "buy" else 1))
            dropped = held * ratio - bonus
            notes.append(f"{symbol}: bonus {ratio} per share on {ex_date.isoformat()} added {bonus} share(s) at zero cost "
                         f"on a holding of {held}." + (f" Fractional entitlement of {dropped} was not added." if dropped else ""))
        else:
            raise ValueError(f"{symbol}: action type {action['type']!r} is not supported (use split or bonus)")
    return out, notes


def rebalance(
    holdings: dict[str, Number], targets: dict[str, Number], new_money: Number = 0,
    band_pct: Number = 0, sell_allowed: bool = True,
) -> dict:
    """Trades that move ``holdings`` (current value per asset) to ``targets`` (percent weights).

    ``new_money`` is cash being added (negative to withdraw). ``band_pct``: assets
    whose weight is within this many percentage points of target are left alone.
    With ``sell_allowed=False`` only the new money is used, spread over the assets
    furthest below target, so nothing is sold and no tax is triggered.
    """
    weights = {k: D(v) for k, v in targets.items()}
    if abs(sum(weights.values()) - 100) > Decimal("0.01"):
        raise ValueError(f"target weights must add to 100; they add to {sum(weights.values())}")
    values = {k: D(v) for k, v in holdings.items()}
    if any(v < 0 for v in values.values()) or any(w < 0 for w in weights.values()):
        raise ValueError("values and weights cannot be negative")
    cash = D(new_money)
    assets = sorted(set(values) | set(weights))
    current_total = sum(values.values(), Decimal(0))
    total = current_total + cash
    if total <= 0:
        raise ValueError("portfolio value after the cash flow must be positive")
    if not sell_allowed and cash < 0:
        raise ValueError("a withdrawal needs sales; set sell_allowed")

    rows, gaps = [], {}
    for a in assets:
        value, weight = values.get(a, Decimal(0)), weights.get(a, Decimal(0))
        current_pct = value / current_total * 100 if current_total > 0 else Decimal(0)
        target_value = total * weight / 100
        gaps[a] = target_value - value
        rows.append({"asset": a, "value": value, "current_pct": current_pct, "target_pct": weight,
                     "drift_pct_points": current_pct - weight, "target_value": target_value})

    trades = {a: Decimal(0) for a in assets}
    if sell_allowed:
        band = D(band_pct)
        outside = [r["asset"] for r in rows if abs(r["drift_pct_points"]) > band or band == 0]
        for a in outside:
            trades[a] = gaps[a]
        # Assets left inside the band keep their value, so the others absorb the difference pro rata.
        residual = cash - sum(trades.values(), Decimal(0))
        if residual != 0 and outside:
            weight_sum = sum(weights.get(a, Decimal(0)) for a in outside)
            for a in outside:
                share = weights.get(a, Decimal(0)) / weight_sum if weight_sum > 0 else Decimal(1) / len(outside)
                trades[a] += residual * share
    else:
        remaining = cash
        below = sorted((a for a in assets if gaps[a] > 0), key=lambda a: -gaps[a])
        need = sum((gaps[a] for a in below), Decimal(0))
        for a in below:
            trades[a] = remaining * gaps[a] / need if need > remaining else gaps[a]
        leftover = cash - sum(trades.values(), Decimal(0))
        if leftover > 0:
            for a in assets:  # everything is at or above target: add the rest in target proportion
                trades[a] += leftover * weights.get(a, Decimal(0)) / 100

    q = Decimal("0.01")
    out_rows = []
    for r in rows:
        a = r["asset"]
        after = r["value"] + trades[a]
        out_rows.append({
            "asset": a,
            "value": str(r["value"].quantize(q)),
            "current_pct": str(r["current_pct"].quantize(q)),
            "target_pct": str(r["target_pct"].quantize(q)),
            "drift_pct_points": str(r["drift_pct_points"].quantize(q)),
            "trade": str(trades[a].quantize(q)),
            "action": "buy" if trades[a] > 0 else "sell" if trades[a] < 0 else "hold",
            "value_after": str(after.quantize(q)),
            "pct_after": str((after / total * 100).quantize(q)),
        })
    return {
        "portfolio_value_before": str(current_total.quantize(q)),
        "new_money": str(cash.quantize(q)),
        "portfolio_value_after": str(total.quantize(q)),
        "total_bought": str(sum((t for t in trades.values() if t > 0), Decimal(0)).quantize(q)),
        "total_sold": str((-sum((t for t in trades.values() if t < 0), Decimal(0))).quantize(q)),
        "largest_drift_pct_points": str(max((abs(r["drift_pct_points"]) for r in rows), default=Decimal(0)).quantize(q)),
        "assets": out_rows,
    }
