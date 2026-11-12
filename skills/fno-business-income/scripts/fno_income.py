#!/usr/bin/env python3
"""Summarise closed F&O trades for the Indian business-income schedule: net profit,
charges, and turnover for the tax-audit test, computed under both readings in use.

CSV columns (one row per closed trade): kind,pnl[,charges][,sale_value]
  kind       future | option
  pnl        profit or loss on the trade before charges (sell value minus buy value)
  charges    brokerage and other costs on the trade (optional)
  sale_value options only: premium received on the sell leg (premium x quantity)
"""
import argparse
import csv
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

from marketcore.taxextras import fno_income  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--trades", required=True, help="CSV of closed F&O trades for one financial year")
    a = p.parse_args()
    try:
        rows = []
        with open(a.trades, newline="", encoding="utf-8-sig") as fh:
            for n, row in enumerate(csv.DictReader(fh), start=2):
                row = {k.strip().lower(): (v or "").strip().replace(",", "") for k, v in row.items() if k}
                try:
                    rows.append({"kind": row["kind"], "pnl": row["pnl"], "charges": row.get("charges") or 0,
                                 "sale_value": row.get("sale_value") or 0})
                except KeyError as exc:
                    raise ValueError(f"{a.trades} line {n}: missing column {exc}") from exc
        out = fno_income(rows)
    except (ValueError, OSError, ArithmeticError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["notes"] = [
        "F&O profit or loss is non-speculative business income, taxed at slab rates, and reported in ITR-3 (or ITR-4 under the presumptive scheme).",
        "TURNOVER IS SHOWN TWO WAYS because sources disagree on the ICAI guidance now in force: (1) the sum of absolute profits and "
        "losses; (2) that sum plus premium received on option sales. Earlier guidance added the premium, the 2022 edition was widely "
        "read as dropping it, and a 2025 revision is reported by some as restoring it. Confirm the method with a chartered accountant.",
        "Audit thresholds shown: Rs 1 crore generally, Rs 10 crore where cash receipts and cash payments are each within 5%. Whether "
        "an audit is required also depends on the presumptive-scheme rules and on declared profit, which are not evaluated here.",
        "A business loss must be reported in a return filed by the due date to be carried forward.",
        "The figures come from the rows supplied. Reconcile them with the broker's tax P&L statement.",
    ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
