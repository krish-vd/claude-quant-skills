#!/usr/bin/env python3
"""Price a European option, compute its greeks, or back out implied volatility.

Give --vol to get the theoretical price and greeks, or --price to get the
implied volatility (and the greeks at that volatility).
"""
import argparse
import json
import pathlib
import sys
from datetime import date

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore.options import black_76, black_scholes, implied_volatility  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", choices=["call", "put"], required=True)
    p.add_argument("--model", choices=["black_76", "black_scholes"], default="black_76",
                   help="black_76: --underlying is the FUTURES price (index options, options on futures). "
                        "black_scholes: --underlying is the SPOT price")
    p.add_argument("--underlying", type=float, required=True)
    p.add_argument("--strike", type=float, required=True)
    p.add_argument("--expiry", help="expiry date YYYY-MM-DD")
    p.add_argument("--days", type=float, help="calendar days to expiry (alternative to --expiry)")
    p.add_argument("--as-of", default=date.today().isoformat(), help="valuation date (default today)")
    p.add_argument("--rate", type=float, default=0.0, help="risk-free rate as a decimal, e.g. 0.065 (default 0)")
    p.add_argument("--dividend-yield", type=float, default=0.0, help="black_scholes only, as a decimal")
    p.add_argument("--vol", type=float, help="volatility as a decimal, e.g. 0.14")
    p.add_argument("--price", type=float, help="market premium, to solve for implied volatility")
    p.add_argument("--quantity", type=float, default=1.0, help="units held (lots x lot size; negative if sold) to scale the greeks")
    a = p.parse_args()
    if (a.vol is None) == (a.price is None):
        p.error("give exactly one of --vol or --price")
    if (a.expiry is None) == (a.days is None):
        p.error("give exactly one of --expiry or --days")
    try:
        days = a.days if a.days is not None else (date.fromisoformat(a.expiry) - date.fromisoformat(a.as_of)).days
        if days < 0:
            raise ValueError("the option has already expired")
        t = days / 365.0
        vol, iv = a.vol, None
        if a.price is not None:
            iv = implied_volatility(a.kind, a.price, a.underlying, a.strike, t, a.rate, a.model, a.dividend_yield)
            if iv is None:
                print(json.dumps({"error": "No implied volatility exists for this premium: it is below intrinsic value, "
                                           "above the no-arbitrage limit, or the option has expired. Check the inputs "
                                           "(stale quote, wrong underlying price, or spot used where the future is needed)."}, indent=2))
                return 2
            vol = iv
        g = (black_76(a.kind, a.underlying, a.strike, t, a.rate, vol) if a.model == "black_76"
             else black_scholes(a.kind, a.underlying, a.strike, t, a.rate, vol, a.dividend_yield))
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    unit = g.per_day_and_point()
    intrinsic = max((a.underlying - a.strike) if a.kind == "call" else (a.strike - a.underlying), 0.0)
    out = {
        "model": a.model,
        "inputs": {"kind": a.kind, "underlying": a.underlying, "strike": a.strike, "days_to_expiry": days,
                   "rate": a.rate, "dividend_yield": a.dividend_yield, "volatility": vol},
        "implied_volatility_pct": None if iv is None else round(iv * 100, 4),
        "theoretical_price": round(g.price, 4),
        "intrinsic_value": round(intrinsic, 4),
        "time_value": round((a.price if a.price is not None else g.price) - intrinsic, 4),
        "greeks_per_unit": {k: round(v, 6) for k, v in unit.items() if k != "price"},
        "greeks_for_position": {k: round(v * a.quantity, 4) for k, v in unit.items() if k != "price"},
        "position_quantity": a.quantity,
        "notes": [
            "European exercise, constant volatility and rate. Calendar days / 365.",
            "theta_per_day is the value lost per calendar day, all else equal; vega is per 1 volatility point.",
        ],
    }
    if a.rate == 0.0:
        out["notes"].append("Rate was left at 0. Pass --rate (for example the 91-day T-bill yield) for longer-dated options.")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
