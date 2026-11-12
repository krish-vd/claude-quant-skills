#!/usr/bin/env python3
"""XIRR (annualised money-weighted return) from dated cash flows.

CSV columns: date,amount   (investments negative; redemptions and dividends positive)
Add the current value with --current-value, or value mutual fund units from the
official AMFI NAV with --units and --scheme-code.
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

from marketcore.data import DataUnavailable, amfi  # noqa: E402
from marketcore.xirr import XirrError, xirr  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cashflows", required=True, help="CSV with date,amount")
    p.add_argument("--current-value", type=float, help="value of the holding, added as a final inflow")
    p.add_argument("--as-of", default=date.today().isoformat(), help="date of the current value (default today)")
    p.add_argument("--units", type=float, help="mutual fund units held (with --scheme-code)")
    p.add_argument("--scheme-code", help="AMFI scheme code; current value = units x latest NAV")
    a = p.parse_args()
    if a.scheme_code and a.units is None:
        p.error("--units is required with --scheme-code")
    try:
        flows = []
        with open(a.cashflows, newline="", encoding="utf-8-sig") as fh:
            for n, row in enumerate(csv.DictReader(fh), start=2):
                row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
                try:
                    flows.append((date.fromisoformat(row["date"]), float(row["amount"].replace(",", ""))))
                except (KeyError, ValueError) as exc:
                    raise ValueError(f"{a.cashflows} line {n}: bad or missing value {exc}") from exc
        valuation = None
        if a.scheme_code:
            scheme = amfi.nav(scheme_code=a.scheme_code)
            valuation = {
                "scheme": scheme["scheme_name"], "plan": scheme["plan"], "option": scheme["option"],
                "nav": scheme["nav"], "nav_date": scheme["nav_date"], "units": a.units,
                "value": round(a.units * scheme["nav"], 2), "source": scheme["source"],
            }
            flows.append((date.fromisoformat(scheme["nav_date"]), valuation["value"]))
        elif a.current_value is not None:
            flows.append((date.fromisoformat(a.as_of), a.current_value))
        rate = xirr(flows)
    except (ValueError, OSError, XirrError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    invested = -sum(x for _, x in flows if x < 0)
    received = sum(x for _, x in flows if x > 0)
    print(
        json.dumps(
            {
                "xirr": rate,
                "xirr_pct": round(rate * 100, 4),
                "total_invested": round(invested, 2),
                "total_received_incl_current_value": round(received, 2),
                "absolute_gain": round(received - invested, 2),
                "first_flow": min(d for d, _ in flows).isoformat(),
                "last_flow": max(d for d, _ in flows).isoformat(),
                "cash_flow_count": len(flows),
                "valuation": valuation,
                "convention": "actual days / 365, same as spreadsheet XIRR",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
