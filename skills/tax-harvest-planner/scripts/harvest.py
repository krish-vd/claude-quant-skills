#!/usr/bin/env python3
"""Year-end tax planning for listed Indian equity: how much of the long-term gains
exemption is left, which shares could be sold to use it, which losses could be
realised, and which short-term gains are close to turning long-term."""
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

from marketcore import harvest  # noqa: E402
from marketcore.data import DataUnavailable, nse  # noqa: E402
from marketcore.tax_india import Trade  # noqa: E402


def read_trades(path: str) -> list:
    trades = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            try:
                trades.append(Trade(date.fromisoformat(row["date"]), row["symbol"], row["side"].lower(), row["quantity"],
                                    row["price"], row.get("asset_class") or "listed_equity", row.get("charges") or 0))
            except (KeyError, ValueError) as exc:
                raise ValueError(f"{path} line {n}: bad or missing value {exc}") from exc
    return trades


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trades", required=True, help="standard trade CSV with the full history of every holding")
    p.add_argument("--prices", help="CSV symbol,price to use instead of the latest NSE close")
    p.add_argument("--fmv", help="CSV symbol,fmv with 31-Jan-2018 values for shares bought before 1 Feb 2018")
    p.add_argument("--date", default=date.today().isoformat(), help="planning date (default today)")
    p.add_argument("--wait-window-days", type=int, default=60, help="flag short-term gains turning long-term within this many days")
    a = p.parse_args()
    try:
        trades = read_trades(a.trades)
        today = date.fromisoformat(a.date)
        held = harvest.open_lots(trades)
        prices, price_source = {}, None
        if a.prices:
            with open(a.prices, newline="", encoding="utf-8-sig") as fh:
                prices = {r["symbol"].strip().upper(): r["price"].strip() for r in csv.DictReader(fh)}
            price_source = a.prices
        else:
            day, rows = nse.latest_cm_bhavcopy(today)
            table = {r["TckrSymb"]: r["ClsPric"] for r in rows if r["SctySrs"] in ("EQ", "BE")}
            prices = {s: table[s] for s in held if s in table}
            price_source = f"NSE bhavcopy close for {day.isoformat()}"
        fmv = None
        if a.fmv:
            with open(a.fmv, newline="", encoding="utf-8-sig") as fh:
                fmv = {r["symbol"].strip(): r["fmv"].strip() for r in csv.DictReader(fh)}
        out = harvest.plan(trades, prices, today, fmv, a.wait_window_days)
    except (ValueError, KeyError, OSError, ArithmeticError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["price_source"] = price_source
    out["notes"] = [
        "Shares are sold oldest-first within each symbol, so only the lots at the front of each queue can be harvested.",
        "Selling and buying back resets the cost and the holding period, and costs brokerage, STT and other charges on both trades.",
        "Prices move between planning and execution; recompute on the day you act.",
        "Losses and gains from other asset classes, surcharge, and carried-forward losses are not included.",
        "This is a computation aid. Confirm with a tax professional before acting, especially near 31 March.",
    ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
