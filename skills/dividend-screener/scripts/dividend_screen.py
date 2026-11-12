#!/usr/bin/env python3
"""Rank stocks by dividend yield, payment record and dividend growth."""
import argparse
import json
import pathlib
import sys
import time

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore import dividends  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import nse_index_members  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--index", help="India: nifty50, nifty100, nifty200, nifty500 ...")
    p.add_argument("--symbols", help="comma-separated symbols")
    p.add_argument("--symbols-file", help="text file, one symbol per line")
    p.add_argument("--min-yield", type=float, default=0.0, help="minimum trailing 12-month yield, percent")
    p.add_argument("--min-years-paid", type=int, default=0, help="minimum consecutive complete years with a dividend")
    p.add_argument("--min-growth", type=float, help="minimum 3-year dividend growth, percent a year")
    p.add_argument("--sort", choices=["yield", "growth", "streak"], default="yield")
    p.add_argument("--top", type=int, default=25)
    a = p.parse_args()
    try:
        details = {}
        symbols = a.symbols.split(",") if a.symbols else None
        if a.symbols_file:
            symbols = pathlib.Path(a.symbols_file).read_text(encoding="utf-8").split()
        if a.index:
            if a.market != "IN":
                p.error("--index is available for India only")
            members = nse_index_members(a.index)
            details = {m["symbol"]: m for m in members}
            symbols = [m["symbol"] for m in members]
        if not symbols:
            p.error("give --index, --symbols or --symbols-file")
    except (ValueError, OSError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    rows, failed = [], []
    for symbol in dict.fromkeys(s.strip().upper() for s in symbols if s.strip()):
        try:
            history, close, last_date = dividends.fetch(symbol, a.market)
            if close is None or last_date is None:
                raise DataUnavailable("no price")
            row = dividends.summarise(symbol, history, close, last_date)
            if symbol in details:
                row["company"], row["industry"] = details[symbol]["company"], details[symbol]["industry"]
            rows.append(row)
        except DataUnavailable:
            failed.append(symbol)
        time.sleep(0.05)
    passed = [
        r for r in rows
        if (r["yield_ttm_pct"] or 0) >= a.min_yield and r["consecutive_years_paid"] >= a.min_years_paid
        and (a.min_growth is None or (r["dividend_cagr_3y_pct"] is not None and r["dividend_cagr_3y_pct"] >= a.min_growth))
    ]
    key = {"yield": lambda r: -(r["yield_ttm_pct"] or 0), "growth": lambda r: -(r["dividend_cagr_3y_pct"] or -1e9),
           "streak": lambda r: (-r["consecutive_years_of_increase"], -r["consecutive_years_paid"])}[a.sort]
    passed.sort(key=key)
    notes = [
        "Dividend amounts are from an unofficial source (Yahoo), adjusted for splits and bonuses. Verify against company announcements.",
        "Yield is the last 12 months of dividends divided by the latest close. A high yield can come from a one-off special "
        "dividend or from a falling share price; check annual_totals for both.",
        "Up to ten years of history. Dividends are not guaranteed and can be cut.",
        "Candidates for research, not recommendations. No payout ratio or earnings cover is checked.",
    ]
    if failed:
        notes.append(f"No data for: {', '.join(failed)}")
    print(json.dumps({"market": a.market, "universe_size": len(rows), "passed": len(passed),
                      "results": passed[: a.top], "notes": notes}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
