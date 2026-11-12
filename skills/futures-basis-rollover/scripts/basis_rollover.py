#!/usr/bin/env python3
"""Futures basis (premium or discount to spot), annualised cost of carry and rollover
for an NSE index or stock, or a market-wide rollover table."""
import argparse
import json
import pathlib
import sys
from datetime import date, timedelta

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore import fnotools  # noqa: E402
from marketcore.data import DataUnavailable, nse  # noqa: E402


def session_on_or_before(day):
    for _ in range(8):
        if day.weekday() < 5:
            try:
                return day, nse.fo_bhavcopy(day)
            except DataUnavailable:
                pass
        day -= timedelta(days=1)
    raise DataUnavailable("no F&O bhavcopy found in the last week")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", help="NIFTY, BANKNIFTY or an F&O stock (omit for the market-wide table)")
    p.add_argument("--date", help="YYYY-MM-DD (default: latest published)")
    p.add_argument("--top", type=int, default=20, help="rows in the market-wide table")
    p.add_argument("--min-oi-units", type=int, default=0)
    a = p.parse_args()
    try:
        day, rows = session_on_or_before(date.fromisoformat(a.date) if a.date else date.today())
        if a.symbol:
            out = fnotools.futures_curve(rows, a.symbol, day)
            try:
                prev_day, prev_rows = session_on_or_before(day - timedelta(days=1))
                before = fnotools.futures_curve(prev_rows, a.symbol, prev_day)
                out["previous_session"] = {
                    "date": prev_day.isoformat(), "rollover_pct": before["rollover_pct"],
                    "near_basis_pct": before["contracts"][0].get("basis_pct"),
                    "total_open_interest_units": before["total_open_interest_units"],
                }
            except (DataUnavailable, ValueError):
                out["previous_session"] = None
        else:
            table = fnotools.rollover_table(rows, day, a.min_oi_units)
            out = {"as_of": day.isoformat(), "symbols": len(table), "highest_rollover": table[: a.top],
                   "lowest_rollover": table[-a.top:][::-1],
                   "deepest_discount": sorted((r for r in table if r["near_basis_pct"] is not None), key=lambda r: r["near_basis_pct"])[: a.top],
                   "highest_premium": sorted((r for r in table if r["near_basis_pct"] is not None), key=lambda r: -r["near_basis_pct"])[: a.top]}
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["source"] = nse.FO_URL.format(ymd=day.strftime("%Y%m%d"))
    out["notes"] = [
        "End-of-day settlement prices from the official NSE F&O bhavcopy. Basis = futures price minus the underlying's close.",
        "rollover_pct is open interest beyond the near month as a share of all open interest. It rises through the expiry week "
        "as positions are carried forward; compare it with the same day of earlier expiries, not with yesterday alone.",
        "A stock future normally trades at a premium reflecting interest cost, less any dividend before expiry. A discount often "
        "just means a dividend is due, so check the ex-dividend date before reading it as bearish.",
        "Annualised basis is unstable in the last few days before expiry.",
    ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
