#!/usr/bin/env python3
"""Compare the standard option structures for a view (bullish, bearish, neutral,
volatile) on one expiry: cost, maximum profit and loss, breakevens, reward to risk,
probability of profit at the implied volatility, and position greeks.

With --symbol (NSE), the forward, implied volatility, lot size and leg prices come
from the official end-of-day F&O file. Otherwise give --forward and --iv.
"""
import argparse
import json
import pathlib
import sys
from datetime import date, timedelta

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore import optionchain, optstrategy  # noqa: E402
from marketcore.data import DataUnavailable, nse  # noqa: E402


def latest_fo():
    day = date.today()
    for _ in range(8):
        if day.weekday() < 5:
            try:
                return day, nse.fo_bhavcopy(day)
            except DataUnavailable:
                pass
        day -= timedelta(days=1)
    raise DataUnavailable("no F&O bhavcopy found in the last week")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--view", choices=optstrategy.VIEWS, required=True)
    p.add_argument("--symbol", help="NSE symbol, e.g. NIFTY: use the official chain")
    p.add_argument("--expiry", help="YYYY-MM-DD (with --symbol; default nearest with at least 3 days left)")
    p.add_argument("--forward", type=float, help="underlying futures price (without --symbol)")
    p.add_argument("--iv", type=float, help="implied volatility as a decimal, e.g. 0.15 (without --symbol)")
    p.add_argument("--days", type=float, help="days to expiry (without --symbol)")
    p.add_argument("--quantity", type=float, help="units per leg: lots x lot size (default one lot with --symbol)")
    p.add_argument("--strike-step", type=float, help="strike interval (default from the chain, or 1% of forward)")
    p.add_argument("--rate", type=float, default=0.0)
    a = p.parse_args()
    lookup, context = None, {}
    try:
        if a.symbol:
            day, rows = latest_fo()
            listed = optionchain.expiries(rows, a.symbol)
            expiry = a.expiry or next((e for e in listed if (date.fromisoformat(e) - day).days >= 3), None)
            if not expiry:
                raise DataUnavailable(f"no suitable expiry for {a.symbol}")
            summary = optionchain.analyse(rows, a.symbol, expiry, day, a.rate)
            chain, _ = optionchain.build_chain(rows, a.symbol, expiry)
            forward, sigma, days = summary["forward"], (summary["atm_iv_pct"] or 0) / 100, summary["days_to_expiry"]
            if not forward or not sigma:
                raise DataUnavailable("could not derive the forward or implied volatility from the chain")
            strikes = sorted(r.strike for r in chain)
            step = a.strike_step or min((b - x for x, b in zip(strikes, strikes[1:]) if b > x), default=forward * 0.01)
            prices = {("call", r.strike): r.call_price for r in chain if r.call_price and r.call_volume > 0}
            prices.update({("put", r.strike): r.put_price for r in chain if r.put_price and r.put_volume > 0})
            lookup = lambda kind, strike: prices.get((kind, strike))  # noqa: E731
            quantity = a.quantity or summary["lot_size"] or 1
            context = {"symbol": summary["symbol"], "as_of": summary["as_of"], "expiry": expiry, "forward_source": summary["forward_source"],
                       "lot_size": summary["lot_size"], "atm_iv_pct": summary["atm_iv_pct"]}
        else:
            if None in (a.forward, a.iv, a.days):
                p.error("without --symbol, give --forward, --iv and --days")
            forward, sigma, days = a.forward, a.iv, a.days
            step = a.strike_step or round(forward * 0.01, 2)
            quantity = a.quantity or 1
        results = optstrategy.compare(a.view, forward, sigma, days, quantity, step, a.rate, lookup)
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    print(json.dumps({
        "view": a.view, "forward": forward, "implied_volatility": round(sigma, 4), "days_to_expiry": days,
        "quantity_per_leg": quantity, "strike_step": step, **context,
        "expected_move_1sd": round(forward * sigma * (days / 365) ** 0.5, 2),
        "structures": results,
        "notes": [
            "Strikes are placed at the money and at half, one and one-and-a-half expected moves (one standard deviation at the implied volatility).",
            "pricing 'market' uses official settlement prices for strikes that traded; 'model' uses Black-76 at the at-the-money implied "
            "volatility, which ignores the skew, so out-of-the-money puts are usually dearer in reality.",
            "Probability of profit is at expiry under the implied volatility (risk-neutral). It is not a forecast, and a high probability "
            "usually comes with a large maximum loss.",
            "Costs and margin are not included. Short options need margin far above the premium; check the broker's calculator.",
            "This compares structures for the user's own view. It does not say which view is right or which trade to take.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
