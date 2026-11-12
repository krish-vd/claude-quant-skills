#!/usr/bin/env python3
"""Indian capital gains from a trade CSV: FIFO lots, short/long term, grandfathering, special-rate tax.

CSV columns: date,symbol,side,quantity,price[,asset_class][,charges]
  date YYYY-MM-DD; side buy|sell; asset_class defaults to listed_equity; charges exclude STT.
FMV CSV (optional, for shares bought before 1 Feb 2018): symbol,fmv
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

from marketcore import rules  # noqa: E402
from marketcore.tax_india import Trade, realised_gains, summarise  # noqa: E402


def read_trades(path: str) -> list:
    trades = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            try:
                trades.append(
                    Trade(
                        date.fromisoformat(row["date"]), row["symbol"], row["side"].lower(),
                        row["quantity"], row["price"],
                        row.get("asset_class") or "listed_equity", row.get("charges") or 0,
                    )
                )
            except (KeyError, ValueError) as exc:
                raise ValueError(f"{path} line {n}: bad or missing value {exc}") from exc
    return trades


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--trades", required=True, help="CSV of buys and sells, full history per symbol")
    p.add_argument("--fmv", help="CSV of 31-Jan-2018 fair market values per symbol")
    p.add_argument("--lots", action="store_true", help="include every matched lot in the output")
    a = p.parse_args()
    try:
        trades = read_trades(a.trades)
        fmv = None
        if a.fmv:
            with open(a.fmv, newline="", encoding="utf-8-sig") as fh:
                fmv = {r["symbol"].strip(): r["fmv"].strip() for r in csv.DictReader(fh)}
        lots, warnings = realised_gains(trades, fmv)
        years = summarise(lots)
    except (ValueError, KeyError, OSError, ArithmeticError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    book = rules.load("in_tax")
    out = {
        "years": [y.to_dict() for y in years],
        "warnings": warnings,
        "not_handled": book["not_handled"],
        "coverage_from": book["coverage_from"],
    }
    if a.lots:
        out["lots"] = [
            {k: (v.isoformat() if isinstance(v, date) else str(v)) for k, v in vars(lot).items()} for lot in lots
        ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
