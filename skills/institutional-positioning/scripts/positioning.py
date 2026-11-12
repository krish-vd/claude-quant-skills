#!/usr/bin/env python3
"""FII, DII, proprietary and client positioning in Indian equity derivatives, and
FII/DII cash-market flows, from NSE's own published files."""
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

from marketcore import positioning as pos  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", help="YYYY-MM-DD (default: latest published)")
    p.add_argument("--history-days", type=int, default=10, help="trading days of FII index-futures history to show")
    p.add_argument("--no-cash", action="store_true", help="skip the FII/DII cash-market figures")
    a = p.parse_args()
    try:
        day, table = pos.latest_participant_oi(date.fromisoformat(a.date) if a.date else None)
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out = {"as_of": day.isoformat(), "positions": pos.net_positions(table), "source": pos.OI_URL.format(dmy=day.strftime("%d%m%Y"))}

    history, cursor, previous = [], day, None
    while len(history) < a.history_days and (day - cursor).days < a.history_days * 2 + 10:
        if cursor.weekday() < 5:
            try:
                net = pos.net_positions(pos.participant_oi(cursor))
                if previous is None and cursor != day:
                    previous = cursor
                fii, client = net["FII"]["index_futures"], net["Client"]["index_futures"]
                history.append({"date": cursor.isoformat(), "fii_index_futures_net": fii["net"],
                                "fii_index_futures_long_pct": fii["long_pct"], "client_index_futures_long_pct": client["long_pct"]})
            except DataUnavailable:
                pass
        cursor -= timedelta(days=1)
    out["fii_index_futures_history"] = list(reversed(history))
    if previous:
        out["change_in_net_since_previous_session"] = {"previous_session": previous.isoformat(),
                                                       **pos.compare(table, pos.participant_oi(previous))}
    if not a.no_cash:
        try:
            flow = pos.cash_flows()
            log = pos.log_cash_flows(flow)
            out["cash_market_rs_crore"] = flow
            out["cash_market_history"] = log[-a.history_days:]
            out["cash_market_history_note"] = (f"{len(log)} day(s) logged locally. NSE publishes only the latest day, "
                                               "so the history grows each day this is run.")
        except DataUnavailable as exc:
            out["cash_market_rs_crore"] = {"error": str(exc)}
    out["notes"] = [
        "Derivative figures are open interest in contracts at the end of the day, from NSE's participant-wise file.",
        "long_pct is longs as a share of that participant's own longs plus shorts in the group.",
        "FIIs use index futures to hedge cash holdings as well as to speculate: a net short is not necessarily a bearish bet.",
        "Positioning describes what is held. It is not a forecast, and extremes can persist for weeks.",
    ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
