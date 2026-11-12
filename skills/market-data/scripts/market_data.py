#!/usr/bin/env python3
"""Free, keyless market data: NSE official bhavcopy, NSE F&O lot sizes, AMFI NAVs,
and (unofficial) Yahoo daily prices for US stocks, futures and anything else."""
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
from marketcore.data import DataUnavailable, amfi, nse, yahoo  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("nse-quote", help="official NSE OHLC and close for a symbol")
    q.add_argument("symbol")
    q.add_argument("--date", help="YYYY-MM-DD (default: latest published)")
    q.add_argument("--series", default="EQ")
    lot = sub.add_parser("nse-lot", help="NSE F&O lot size")
    lot.add_argument("symbol")
    lot.add_argument("--expiry-month", help="e.g. NOV-26")
    m = sub.add_parser("mf-search", help="find mutual fund schemes by name, plan and option")
    m.add_argument("query")
    m.add_argument("--limit", type=int, default=20)
    n = sub.add_parser("mf-nav", help="latest NAV by AMFI scheme code or ISIN")
    n.add_argument("--scheme-code")
    n.add_argument("--isin")
    y = sub.add_parser("yahoo", help="unofficial daily prices: AAPL, SPY, GC=F, CL=F, RELIANCE.NS ...")
    y.add_argument("symbol")
    y.add_argument("--range", default="5d", help="5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max")
    c = sub.add_parser("contract", help="futures contract spec from the rulebook")
    c.add_argument("symbol")
    a = p.parse_args()
    try:
        if a.cmd == "nse-quote":
            out = nse.equity_quote(a.symbol, date.fromisoformat(a.date) if a.date else None, a.series)
        elif a.cmd == "nse-lot":
            out = nse.lot_size(a.symbol, a.expiry_month)
        elif a.cmd == "mf-search":
            out = amfi.find_schemes(a.query, a.limit)
        elif a.cmd == "mf-nav":
            out = amfi.nav(a.scheme_code, a.isin)
        elif a.cmd == "yahoo":
            out = yahoo.daily_history(a.symbol, a.range)
        else:
            out = rules.contract(a.symbol)
    except (DataUnavailable, rules.RuleNotCovered, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
