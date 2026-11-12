#!/usr/bin/env python3
"""Find NSE stocks with an unusual jump in delivered quantity, from the exchange's
official security-wise delivery file."""
import argparse
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

from marketcore import delivery  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", help="YYYY-MM-DD (default: latest published)")
    p.add_argument("--sessions", type=int, default=10, help="earlier sessions to average over (default 10)")
    p.add_argument("--min-ratio", type=float, default=2.0, help="delivered quantity vs its average (default 2x)")
    p.add_argument("--min-turnover-lakh", type=float, default=500.0, help="minimum turnover that day, Rs lakh (default 500 = Rs 5 crore)")
    p.add_argument("--direction", choices=["up", "down", "any"], default="any", help="filter on the day's price change")
    p.add_argument("--top", type=int, default=25)
    a = p.parse_args()
    try:
        tables = delivery.recent_tables(a.sessions + 1, date.fromisoformat(a.date) if a.date else None)
        rows = delivery.screen(tables, a.min_turnover_lakh, a.min_ratio)
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    if a.direction == "up":
        rows = [r for r in rows if (r["price_change_pct"] or 0) > 0]
    elif a.direction == "down":
        rows = [r for r in rows if (r["price_change_pct"] or 0) < 0]
    print(json.dumps({
        "as_of": tables[-1][0].isoformat(),
        "sessions_averaged": len(tables) - 1,
        "average_window": f"{tables[0][0].isoformat()} to {tables[-2][0].isoformat()}",
        "matches": len(rows),
        "results": rows[: a.top],
        "source": delivery.URL.format(dmy=tables[-1][0].strftime("%d%m%Y")),
        "notes": [
            "Official NSE end-of-day data, EQ series only.",
            "A delivery spike shows more shares settled into demat than usual. It does not show who bought or sold, or why: "
            "block deals, index changes, results and promoter transactions all cause spikes.",
            "Candidates for research, not recommendations.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
