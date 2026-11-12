#!/usr/bin/env python3
"""NSE F&O expiry calendar: every listed expiry for the indices or one symbol, with
weekday, days left, lot size and open interest, plus the current F&O ban list."""
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
from marketcore.data import DataUnavailable, http_get, nse  # noqa: E402

BAN_URL = "https://nsearchives.nseindia.com/content/fo/fo_secban.csv"


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
    p.add_argument("--symbol", help="one symbol (default: all index contracts)")
    p.add_argument("--within-days", type=int, help="only expiries within this many days")
    a = p.parse_args()
    try:
        day, rows = latest_fo(date.today())
        calendar = fnotools.expiry_calendar(rows, date.today(), a.symbol)
        if a.symbol and not calendar:
            raise DataUnavailable(f"{a.symbol.upper()} has no F&O contracts in the file for {day.isoformat()}")
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    calendar = [e for e in calendar if e["days_to_expiry"] >= 0]
    if a.within_days is not None:
        calendar = [e for e in calendar if e["days_to_expiry"] <= a.within_days]
    try:
        ban = fnotools.parse_ban_list(http_get(BAN_URL, "https://www.nseindia.com/").decode("utf-8", "replace"))
    except DataUnavailable as exc:
        ban = {"error": str(exc)}
    nearest = min(calendar, key=lambda e: e["days_to_expiry"]) if calendar else None
    print(json.dumps({
        "today": date.today().isoformat(),
        "contracts_as_listed_on": day.isoformat(),
        "nearest_expiry": nearest,
        "expiries": calendar,
        "fo_ban_list": ban,
        "source": nse.FO_URL.format(ymd=day.strftime("%Y%m%d")),
        "notes": [
            "Expiries are read from the contracts NSE listed in its latest F&O bhavcopy, so exchange changes to expiry days are picked up automatically.",
            "If an expiry day turns out to be a trading holiday the exchange moves it, normally to the previous trading day; the file reflects this once announced.",
            "Stocks in the ban list may only have positions reduced that day; new positions attract a penalty.",
            "Stock derivatives are physically settled: open in-the-money positions at expiry mean taking or giving delivery of shares.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
