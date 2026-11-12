#!/usr/bin/env python3
"""Work out the Schedule FA (Table A3) figures for foreign shares held by an Indian
resident: cost, peak value and its date, closing value and sale proceeds for a
calendar year, in the foreign currency, converted to rupees with rates you supply.

Trades CSV: date,symbol,side,quantity,price      (price in the foreign currency)
Rates CSV : date,rate                            (SBI TT buying rate for that date)
"""
import argparse
import csv
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

from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import daily_bars  # noqa: E402
from marketcore.taxextras import schedule_fa_rows  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--trades", required=True)
    p.add_argument("--year", type=int, required=True, help="CALENDAR year to report, e.g. 2025 for the return filed in 2026")
    p.add_argument("--rates", help="CSV of SBI TT buying rates by date")
    a = p.parse_args()
    try:
        trades = []
        with open(a.trades, newline="", encoding="utf-8-sig") as fh:
            for n, row in enumerate(csv.DictReader(fh), start=2):
                row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
                try:
                    side = row["side"].lower()
                    if side not in ("buy", "sell"):
                        raise ValueError(f"side {side!r}")
                    trades.append({"symbol": row["symbol"], "date": date.fromisoformat(row["date"]), "side": side,
                                   "quantity": float(row["quantity"]), "price": float(row["price"])})
                except (KeyError, ValueError) as exc:
                    raise ValueError(f"{a.trades} line {n}: bad or missing value {exc}") from exc
        rates = {}
        if a.rates:
            with open(a.rates, newline="", encoding="utf-8-sig") as fh:
                rates = {date.fromisoformat(r["date"].strip()): float(r["rate"]) for r in csv.DictReader(fh)}
        prices, no_prices = {}, []
        for symbol in sorted({t["symbol"].upper() for t in trades}):
            try:
                bars = daily_bars(symbol, "10y", "US")
                prices[symbol] = (bars.dates, bars.close)
            except DataUnavailable:
                no_prices.append(symbol)
        out = schedule_fa_rows(trades, prices, a.year, rates)
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["symbols_without_price_history"] = no_prices
    out["notes"] = [
        f"Schedule FA uses the CALENDAR year (1 January to 31 December {a.year}), not the financial year.",
        "Rupee values use the telegraphic transfer buying rate on the relevant date: the purchase date for cost, the peak date for "
        "peak value, and the last day of the year for closing value. Supply those rates in --rates; dates still needed are listed "
        "in rates_needed. Nothing is converted at an estimated rate.",
        "initial_value is the cost of every purchase up to the year end. If part of the holding was sold in an earlier year, reduce "
        "it to the cost of the shares still held at the start of the year.",
        "Peak value is found from daily closing prices (an unofficial source) and the shares held each day. The true peak in rupees "
        "can fall on a different day when the exchange rate moves; if two days are close, check both.",
        "Prices are adjusted for splits, so the share counts in the trades file must be on the same post-split basis.",
        "Dividends (reported in Schedule FSI, with foreign tax credit in Schedule TR and Form 67) are not computed here.",
        "Sources disagree on whether lots of the same share are reported in one row or separately; purchase_lots lists them so either works.",
        "Reporting foreign assets wrongly or not at all carries heavy penalties. Have a chartered accountant review the schedule.",
    ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
