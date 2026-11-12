#!/usr/bin/env python3
"""Cost of a trade (one leg or a round trip) in India (NSE, BSE cash, MCX) or the US."""
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

from marketcore import rules  # noqa: E402
from marketcore.charges import (  # noqa: E402
    IN_SEGMENTS,
    Brokerage,
    india_leg,
    india_round_trip,
    us_equity_leg,
    us_round_trip,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--segment", choices=IN_SEGMENTS, help="India only")
    p.add_argument("--exchange", choices=["NSE", "BSE", "MCX"], help="India only; default NSE, or MCX for commodities")
    p.add_argument("--side", choices=["buy", "sell"], help="one leg; omit when giving --buy-price and --sell-price")
    p.add_argument("--price", help="price for a single leg (premium for options)")
    p.add_argument("--buy-price")
    p.add_argument("--sell-price")
    p.add_argument("--quantity", required=True, help="shares or units: lots x lot size; lots x multiplier for MCX")
    p.add_argument("--date", default=date.today().isoformat(), help="trade date YYYY-MM-DD (default today)")
    p.add_argument("--sell-date", help="round trip only; default same as --date")
    p.add_argument("--brokerage-flat", default="0", help="per order")
    p.add_argument("--brokerage-pct", default="0", help="fraction of turnover, e.g. 0.0003 for 0.03 percent")
    p.add_argument("--brokerage-cap", help="maximum brokerage per order")
    p.add_argument("--dp-charge", default="0", help="India delivery sell: depository charge incl. GST")
    p.add_argument("--agri", action="store_true", help="agricultural commodity (no CTT)")
    p.add_argument("--commission", default="0", help="US: commission per order")
    a = p.parse_args()

    trade_date = date.fromisoformat(a.date)
    sell_date = date.fromisoformat(a.sell_date) if a.sell_date else None
    round_trip = bool(a.buy_price and a.sell_price)
    if not round_trip and not (a.side and a.price):
        p.error("give --side and --price, or both --buy-price and --sell-price")
    try:
        if a.market == "IN":
            if not a.segment:
                p.error("--segment is required for India")
            common = dict(
                exchange=a.exchange,
                agri=a.agri,
                brokerage=Brokerage(a.brokerage_flat, a.brokerage_pct, a.brokerage_cap),
            )
            if round_trip:
                result = india_round_trip(
                    a.segment, a.buy_price, a.sell_price, a.quantity, trade_date, sell_date,
                    dp_charge=a.dp_charge, **common,
                ).to_dict()
            else:
                result = india_leg(
                    a.segment, a.side, a.price, a.quantity, trade_date, dp_charge=a.dp_charge, **common
                ).to_dict()
        elif round_trip:
            result = us_round_trip(a.buy_price, a.sell_price, a.quantity, trade_date, sell_date, a.commission).to_dict()
        else:
            result = us_equity_leg(a.side, a.price, a.quantity, trade_date, a.commission).to_dict()
    except (rules.RuleNotCovered, ValueError, ArithmeticError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
