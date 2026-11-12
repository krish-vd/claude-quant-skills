#!/usr/bin/env python3
"""Risk-based position size for cash equities, futures and bought options (India and US)."""
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

from marketcore import rules  # noqa: E402
from marketcore.data import DataUnavailable, nse  # noqa: E402
from marketcore.sizing import size_cash, size_futures, size_long_option  # noqa: E402


def resolve_contract(symbol, expiry_month, explicit):
    """Return (multiplier, description). Order: explicit value, rulebook table, live NSE lot file."""
    if explicit:
        return explicit, {"multiplier": explicit, "source": "user supplied"}
    if not symbol:
        raise ValueError("give --symbol, or the multiplier / lot size explicitly")
    try:
        c = rules.contract(symbol)
        return c["multiplier"], {
            "symbol": c["symbol"], "name": c["name"], "multiplier": c["multiplier"],
            "currency": c["currency"], "source": c["source_title"], "source_kind": c["source_kind"],
        }
    except rules.RuleNotCovered:
        lot = nse.lot_size(symbol, expiry_month)
        return str(lot["lot_size"]), {
            "symbol": lot["symbol"], "expiry_month": lot["expiry_month"], "multiplier": str(lot["lot_size"]),
            "currency": "INR", "source": lot["source"], "source_kind": "primary (live NSE lot file)",
        }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--instrument", choices=["cash", "futures", "option"], required=True)
    p.add_argument("--account", required=True, help="account equity in the instrument's currency")
    p.add_argument("--risk-pct", default="1", help="percent of account to risk (default 1)")
    p.add_argument("--entry", help="entry price (cash, futures)")
    p.add_argument("--stop", help="stop price (cash, futures)")
    p.add_argument("--max-position-pct", help="cash: cap position value at this percent of account")
    p.add_argument("--cost-per-unit", default="0", help="round-trip cost per share, contract or lot")
    p.add_argument("--fractional-step", help="cash: allow fractional shares, e.g. 0.0001")
    p.add_argument("--symbol", help="futures/option: an NSE F&O symbol (lot read live from NSE) or a rulebook contract (GOLD, CRUDEOIL, GC, CL, ES ...)")
    p.add_argument("--expiry-month", help="NSE symbols: e.g. NOV-26 (default nearest)")
    p.add_argument("--multiplier", help="futures: override; value of a 1.0 price move per contract")
    p.add_argument("--margin-per-contract", help="futures: margin from the broker's margin calculator")
    p.add_argument("--premium", help="option: premium per unit")
    p.add_argument("--stop-premium", default="0", help="option: planned exit premium (default 0 = full premium at risk)")
    p.add_argument("--lot-size", help="option: override lot size")
    a = p.parse_args()

    spec = None
    try:
        if a.instrument == "cash":
            if not (a.entry and a.stop):
                p.error("--entry and --stop are required")
            result = size_cash(a.account, a.risk_pct, a.entry, a.stop, a.max_position_pct, a.cost_per_unit, a.fractional_step)
        elif a.instrument == "futures":
            if not (a.entry and a.stop):
                p.error("--entry and --stop are required")
            multiplier, spec = resolve_contract(a.symbol, a.expiry_month, a.multiplier)
            result = size_futures(a.account, a.risk_pct, a.entry, a.stop, multiplier, a.margin_per_contract, a.cost_per_unit)
        else:
            if not a.premium:
                p.error("--premium is required for options")
            lot, spec = resolve_contract(a.symbol, a.expiry_month, a.lot_size)
            result = size_long_option(a.account, a.risk_pct, a.premium, lot, a.stop_premium, a.cost_per_unit)
    except (ValueError, TypeError, ArithmeticError, DataUnavailable, rules.RuleNotCovered) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out = result.to_dict()
    if spec:
        out["contract"] = spec
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
