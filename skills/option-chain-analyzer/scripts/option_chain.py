#!/usr/bin/env python3
"""Analyse an NSE option chain from the official end-of-day F&O bhavcopy:
put/call ratios, max pain, implied forward, at-the-money implied volatility,
the straddle-implied move, and where open interest sits and is being added."""
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

from marketcore import optionchain  # noqa: E402
from marketcore.data import DataUnavailable, nse  # noqa: E402


def latest_fo(day):
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
    p.add_argument("symbol", help="NIFTY, BANKNIFTY, FINNIFTY, or an F&O stock symbol")
    p.add_argument("--expiry", help="YYYY-MM-DD (default: nearest). Use --list-expiries to see them")
    p.add_argument("--date", help="bhavcopy date YYYY-MM-DD (default: latest published)")
    p.add_argument("--rate", type=float, default=0.0, help="risk-free rate as a decimal, used for implied volatility")
    p.add_argument("--top", type=int, default=5, help="strikes to list in each ranking")
    p.add_argument("--list-expiries", action="store_true")
    a = p.parse_args()
    try:
        if a.date:
            day = date.fromisoformat(a.date)
            rows = nse.fo_bhavcopy(day)
        else:
            day, rows = latest_fo(date.today())
        listed = optionchain.expiries(rows, a.symbol)
        if not listed:
            raise DataUnavailable(f"{a.symbol.upper()} has no options in the F&O bhavcopy for {day.isoformat()}")
        if a.list_expiries:
            print(json.dumps({"symbol": a.symbol.upper(), "as_of": day.isoformat(), "expiries": listed}, indent=2))
            return 0
        expiry = a.expiry or next((e for e in listed if e >= day.isoformat()), listed[0])
        out = optionchain.analyse(rows, a.symbol, expiry, day, a.rate, a.top)
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["source"] = nse.FO_URL.format(ymd=day.strftime("%Y%m%d"))
    out["notes"] = [
        "End-of-day data from the official NSE bhavcopy, not live. Settlement prices are used.",
        "Open interest is in units of the underlying; oi_lots divides by the lot size.",
        "Open interest shows where positions sit, not who holds them or which way they lean: a high call OI strike has as many buyers as sellers.",
        "Max pain and OI levels are descriptive. They are not price targets.",
    ]
    if out["days_to_expiry"] <= 1:
        out["notes"].append("Expiry is today or tomorrow: implied volatility is unstable this close to expiry.")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
