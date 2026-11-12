#!/usr/bin/env python3
"""Screen Indian or US stocks: relative strength rank, trend template, 52-week-high breakouts.

Output is a ranked list of candidates for research, with the measures behind each one.
"""
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

from marketcore.data import DataUnavailable, nse  # noqa: E402
from marketcore.data.history import load_universe  # noqa: E402
from marketcore.screens import screen  # noqa: E402

SCREENS = {
    "rs": lambda r: r["rs_rank"] is not None,
    "trend_template": lambda r: r["trend_template"],
    "breakout": lambda r: r["breakout"],
    "new_high": lambda r: r["new_52w_closing_high"],
    "contraction": lambda r: r["contraction"],
}


def official_close_check(rows):
    """Compare each Indian row's close with the NSE bhavcopy for the same date."""
    by_date = {}
    for row in rows:
        day = date.fromisoformat(row["date"])
        if day not in by_date:
            try:
                by_date[day] = {r["TckrSymb"]: float(r["ClsPric"]) for r in nse.cm_bhavcopy(day) if r["SctySrs"] in ("EQ", "BE")}
            except DataUnavailable:
                by_date[day] = None
        table = by_date[day]
        if table is None or row["symbol"] not in table:
            row["official_close"] = None
            row["close_check"] = "not available"
            continue
        official = table[row["symbol"]]
        row["official_close"] = official
        diff = abs(row["close"] / official - 1) * 100
        row["close_check"] = "matches" if diff <= 0.5 else f"differs by {diff:.2f}% from the NSE close"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--symbols", help="comma-separated symbols")
    p.add_argument("--symbols-file", help="text file, one symbol per line")
    p.add_argument("--index", help="India: nifty50, niftynext50, nifty100, nifty200, nifty500, niftymidcap150, niftysmallcap250")
    p.add_argument("--screen", choices=sorted(SCREENS), default="trend_template")
    p.add_argument("--top", type=int, default=25, help="rows to return (default 25)")
    p.add_argument("--min-price", type=float, default=0.0)
    p.add_argument("--min-turnover", type=float, default=0.0, help="minimum 20-day average daily traded value")
    p.add_argument("--min-rs", type=int, default=0, help="minimum relative-strength rank (1-99)")
    a = p.parse_args()
    try:
        symbols = a.symbols.split(",") if a.symbols else None
        if a.symbols_file:
            symbols = pathlib.Path(a.symbols_file).read_text(encoding="utf-8").split()
        data, failed, details = load_universe(a.market, symbols, a.index, "2y")
        rows = screen(data)
    except (ValueError, OSError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2

    too_short = sorted(set(data) - {r["symbol"] for r in rows})
    latest = max((r["date"] for r in rows), default=None)
    stale = sorted(r["symbol"] for r in rows if r["date"] != latest)
    passed = [
        r for r in rows
        if SCREENS[a.screen](r) and r["close"] >= a.min_price
        and r["avg_daily_turnover_20d"] >= a.min_turnover and (r["rs_rank"] or 0) >= a.min_rs
        and r["date"] == latest
    ]
    passed.sort(key=lambda r: (-(r["rs_rank"] or 0), r["pct_below_52w_high"]))
    top = passed[: a.top]
    for row in top:
        if row["symbol"] in details:
            row["company"] = details[row["symbol"]]["company"]
            row["industry"] = details[row["symbol"]]["industry"]
    if a.market == "IN" and top:
        official_close_check(top)

    notes = [
        "Candidates for research, not recommendations. A screen says nothing about valuation, results dates or news.",
        f"Relative-strength ranks are within the {len(rows)} symbols screened, not the whole market.",
        "Prices are from an unofficial source (Yahoo), adjusted for splits and bonuses.",
    ]
    if a.market == "IN":
        notes.append("close_check compares each close with the official NSE bhavcopy for the same date.")
    repair = details.get("__repair__", {})
    if repair.get("repaired"):
        notes.append(f"Gaps in the price source filled from the official NSE bhavcopy: {', '.join(repair['repaired'])}")
    if repair.get("unrepaired"):
        notes.append(f"Gaps that could not be filled: {', '.join(repair['unrepaired'])}")
    if failed:
        notes.append(f"No data for: {', '.join(failed)}")
    if too_short:
        notes.append(f"Less than a year of history, not screened: {', '.join(too_short)}")
    if stale:
        notes.append(f"Latest bar is older than {latest}, excluded: {', '.join(stale)}")
    print(json.dumps({
        "screen": a.screen, "market": a.market, "as_of": latest,
        "universe_size": len(data), "passed": len(passed), "shown": len(top),
        "results": top, "notes": notes,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
