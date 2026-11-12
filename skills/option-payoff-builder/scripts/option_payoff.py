#!/usr/bin/env python3
"""Expiry payoff of a multi-leg option position: breakevens, maximum profit and loss.

Each leg is  SIDE:KIND:STRIKE:PRICE:QUANTITY
  SIDE buy|sell   KIND call|put|underlying   PRICE premium (or entry price of the underlying)
  QUANTITY units = lots x lot size.  STRIKE is ignored for underlying (use 0).

Example, a Nifty bull call spread (lot 65):
  --leg buy:call:25000:200:65 --leg sell:call:25300:80:65
"""
import argparse
import json
import pathlib
import sys

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore.options import Leg, payoff_at, payoff_profile  # noqa: E402


def parse_leg(text: str) -> Leg:
    parts = text.split(":")
    if len(parts) != 5:
        raise ValueError(f"leg {text!r} must be SIDE:KIND:STRIKE:PRICE:QUANTITY")
    side, kind, strike, price, quantity = parts
    leg = Leg(kind.lower(), side.lower(), float(quantity), float(price), float(strike))
    if leg.quantity <= 0 or leg.price < 0:
        raise ValueError(f"leg {text!r}: quantity must be positive and price not negative (use SIDE for direction)")
    leg.payoff(1.0)  # validates kind and side
    return leg


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--leg", action="append", required=True, help="repeat for each leg")
    p.add_argument("--costs", type=float, default=0.0, help="total charges for the whole position (from trade-cost-calculator)")
    p.add_argument("--at", help="comma-separated underlying prices to evaluate, e.g. 24500,25000,25500")
    a = p.parse_args()
    try:
        legs = [parse_leg(text) for text in a.leg]
        profile = payoff_profile(legs, a.costs)
        table = None
        if a.at:
            table = [{"price": float(x), "pnl": round(payoff_at(legs, float(x)) - a.costs, 2)} for x in a.at.split(",")]
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    risk_reward = None
    if profile["max_profit"] is not None and profile["max_loss"] not in (None, 0):
        risk_reward = round(profile["max_profit"] / abs(profile["max_loss"]), 3)
    warnings = []
    if profile["unlimited_loss"]:
        warnings.append("Loss is unlimited if the price rises: this position has a net short call or short underlying exposure.")
    short_puts = sum(l.quantity for l in legs if l.kind == "put" and l.side == "sell")
    long_puts = sum(l.quantity for l in legs if l.kind == "put" and l.side == "buy")
    if short_puts > long_puts:
        warnings.append("Net short puts: the loss grows all the way down to a price of zero (see payoff_at_zero).")
    print(json.dumps({
        "legs": [vars(l) for l in legs],
        **profile,
        "reward_to_risk": risk_reward,
        "payoff_table": table,
        "costs_included": a.costs,
        "warnings": warnings,
        "notes": [
            "Profit and loss AT EXPIRY. Before expiry the value also depends on time and volatility (use option-pricer).",
            "In-the-money bought options that are exercised pay STT on intrinsic value in India; this is not included unless added to --costs.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
