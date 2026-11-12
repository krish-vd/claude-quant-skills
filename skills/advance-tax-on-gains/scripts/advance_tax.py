#!/usr/bin/env python3
"""Advance-tax instalments on capital gains realised during an Indian financial year:
how much should have been paid by 15 June, 15 September, 15 December and 15 March,
given when each gain arose."""
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

from marketcore.tax_india import Trade, financial_year, realised_gains  # noqa: E402
from marketcore.taxextras import advance_tax_schedule  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trades", required=True, help="standard trade CSV with full history")
    p.add_argument("--fy", help="financial year such as 2026-27 (default: the current one)")
    p.add_argument("--fmv", help="CSV symbol,fmv with 31-Jan-2018 values")
    p.add_argument("--paid", action="append", default=[], metavar="DUE_DATE=AMOUNT",
                   help="advance tax already paid for an instalment, e.g. 2026-06-15=5000; repeatable")
    a = p.parse_args()
    try:
        trades = []
        with open(a.trades, newline="", encoding="utf-8-sig") as fh:
            for n, row in enumerate(csv.DictReader(fh), start=2):
                row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
                try:
                    trades.append(Trade(date.fromisoformat(row["date"]), row["symbol"], row["side"].lower(), row["quantity"],
                                        row["price"], row.get("asset_class") or "listed_equity", row.get("charges") or 0))
                except (KeyError, ValueError) as exc:
                    raise ValueError(f"{a.trades} line {n}: bad or missing value {exc}") from exc
        fmv = None
        if a.fmv:
            with open(a.fmv, newline="", encoding="utf-8-sig") as fh:
                fmv = {r["symbol"].strip(): r["fmv"].strip() for r in csv.DictReader(fh)}
        paid = {}
        for item in a.paid:
            when, sep, amount = item.partition("=")
            if not sep:
                p.error(f"--paid must be DUE_DATE=AMOUNT, got {item!r}")
            paid[date.fromisoformat(when.strip())] = amount.strip()
        lots, warnings = realised_gains(trades, fmv)
        fy = a.fy or financial_year(date.today())
        out = advance_tax_schedule(lots, fy, paid)
    except (ValueError, KeyError, OSError, ArithmeticError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["today"] = date.today().isoformat()
    out["next_due"] = next((r for r in out["instalments"] if r["due_date"] >= date.today().isoformat()), None)
    out["warnings"] = warnings
    out["notes"] = [
        "Covers tax on the 20% and 12.5% capital-gains buckets with 4% cess only. Slab-rate gains, salary, business and other "
        "income, TDS already deducted, and surcharge are not included: the real advance-tax position is for all income together.",
        "By each due date the amount due is that date's percentage of the tax on gains realised up to then. Tax on a later gain "
        "falls into the later instalments; tax on gains after 15 March is due by 31 March.",
        "Advance tax is required only when total tax for the year, after TDS, is Rs 10,000 or more.",
        "Interest for shortfalls is not computed. The instalment percentages and the capital-gains relief are from secondary "
        "sources; confirm with a tax professional before paying.",
    ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
