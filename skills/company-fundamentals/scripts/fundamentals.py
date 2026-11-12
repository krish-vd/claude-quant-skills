#!/usr/bin/env python3
"""Company fundamentals from regulatory filings: quarterly results for NSE companies
(NSE integrated filings) and annual and quarterly figures for US companies (SEC),
with growth, margins, trailing earnings and price-to-earnings."""
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

from marketcore import fundamentals  # noqa: E402
from marketcore.data import DataUnavailable, nse, yahoo  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--symbol", required=True, action="append", help="repeat to compare companies")
    p.add_argument("--standalone", action="store_true", help="India: standalone results instead of consolidated")
    p.add_argument("--quarters", type=int, default=8, help="India: quarters of filings to read (default 8)")
    a = p.parse_args()
    results, errors = [], []
    for symbol in a.symbol:
        try:
            price, price_note = None, None
            if a.market == "IN":
                try:
                    quote = nse.equity_quote(symbol)
                    price, price_note = float(quote["close"]), f"NSE close {quote['date']}"
                except DataUnavailable:
                    price_note = "no NSE price found"
                out = fundamentals.india_summary(fundamentals.india_quarters(symbol, not a.standalone, a.quarters), price)
                out["source"] = "NSE integrated filings (company-filed XBRL)"
            else:
                try:
                    last = yahoo.last_close(symbol)
                    price, price_note = float(last["close"]), f"close {last['date']} (unofficial source)"
                except DataUnavailable:
                    price_note = "no price found"
                out = fundamentals.us_fundamentals(symbol, price)
            out["price_note"] = price_note
            results.append(out)
        except (DataUnavailable, ValueError) as exc:
            errors.append({"symbol": symbol.upper(), "error": str(exc)})
    if not results:
        print(json.dumps({"errors": errors}, indent=2))
        return 2
    print(json.dumps({
        "market": a.market, "companies": results, "errors": errors,
        "notes": [
            "Figures are as filed by the company with the regulator. Growth rates, margins, trailing totals and ratios are computed here from them.",
            "Growth is not reported when the earlier figure is zero or a loss.",
            "Price-to-earnings uses the sum of the last four quarters' diluted EPS. It ignores one-off items and says nothing about whether the price is fair.",
            "India: amounts are in rupees; the first quarters after late 2024 are available, older results are not read. "
            "Banks and financial companies report income differently; their 'revenue' is interest earned or total income.",
            "US: the fourth quarter is derived as the year minus three filed quarters. Fiscal years differ between companies.",
            "This is reported history, not a forecast or a recommendation.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
