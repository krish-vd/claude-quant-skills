#!/usr/bin/env python3
"""Upcoming company results (board meetings notified to NSE) and upcoming ex-dates
for dividends, bonuses and splits, for the whole market, an index, or a watchlist."""
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

from marketcore import corporate, journal  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import nse_index_members  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=14, help="look this many days ahead (default 14)")
    p.add_argument("--symbols", help="comma-separated watchlist")
    p.add_argument("--index", help="limit to an NSE index: nifty50, nifty100, nifty200, nifty500 ...")
    p.add_argument("--open-trades", action="store_true", help="limit to symbols with an open trade in the journal")
    p.add_argument("--journal", help="journal path (with --open-trades)")
    p.add_argument("--all-purposes", action="store_true", help="include board meetings that are not for results")
    a = p.parse_args()
    try:
        wanted = None
        if a.symbols:
            wanted = {s.strip().upper() for s in a.symbols.split(",") if s.strip()}
        if a.index:
            members = {m["symbol"] for m in nse_index_members(a.index)}
            wanted = members if wanted is None else wanted & members
        if a.open_trades:
            trades = journal.load(pathlib.Path(a.journal) if a.journal else None)
            held = {t["symbol"] for t in trades if t["status"] == "open"}
            wanted = held if wanted is None else wanted & held
        today, until = date.today(), date.today() + timedelta(days=a.days)
        meetings = [r for r in corporate.calendar() if today <= r["date"] <= until
                    and (a.all_purposes or r["is_results"]) and (wanted is None or r["symbol"] in wanted)]
        try:
            ex_dates = [r for r in corporate.actions() if today <= r["ex_date"] <= until and (wanted is None or r["symbol"] in wanted)
                        and r["type"] != "other"]
            ex_error = None
        except DataUnavailable as exc:
            ex_dates, ex_error = [], str(exc)
    except (ValueError, OSError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    by_day: dict[str, list] = {}
    for r in meetings:
        by_day.setdefault(r["date"].isoformat(), []).append({"symbol": r["symbol"], "company": r["company"], "purpose": r["purpose"]})
    notes = [
        "Dates are board-meeting dates notified to NSE. Results are usually announced that day, often after market hours, "
        "so the price reaction is typically the next session.",
        "Companies can reschedule; a meeting notified late will not appear until NSE lists it.",
        "Ex-date: a buyer on or after this date does not receive the dividend, bonus or split entitlement.",
    ]
    if ex_error:
        notes.append(f"Ex-dates unavailable: {ex_error}")
    print(json.dumps({
        "from": today.isoformat(), "to": until.isoformat(),
        "scope": "watchlist" if wanted is not None else "all NSE companies",
        "results_count": len(meetings),
        "results_by_day": by_day,
        "upcoming_ex_dates": [{"symbol": r["symbol"], "ex_date": r["ex_date"].isoformat(), "type": r["type"], "subject": r["subject"],
                               "amount": r["amount"], "ratio": r["ratio"]} for r in ex_dates],
        "source": [corporate.CALENDAR_URL, corporate.ACTIONS_URL],
        "notes": notes,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
