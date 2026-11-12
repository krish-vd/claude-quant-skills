#!/usr/bin/env python3
"""Rank sectors by relative strength against the market, show which are gaining or
losing rank, and (India) the breadth inside each industry of an index."""
import argparse
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

from marketcore import sectors  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import daily_bars, load_universe  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--benchmark", help="default ^NSEI (India) or SPY (US)")
    p.add_argument("--shift", type=int, default=21, help="sessions back for the earlier ranking (default 21, about a month)")
    p.add_argument("--industry-breadth", metavar="INDEX", help="India: also show breadth by industry within nifty200, nifty500 ...")
    a = p.parse_args()
    table = sectors.IN_SECTORS if a.market == "IN" else sectors.US_SECTORS
    benchmark_symbol = a.benchmark or sectors.BENCHMARKS[a.market]
    try:
        benchmark = daily_bars(benchmark_symbol, "2y", "US")
        series, failed = {}, []
        for name, symbol in table.items():
            try:
                bars = daily_bars(symbol, "2y", "US")   # "US": these are full Yahoo symbols, no suffix to add
                bars.symbol = symbol
                series[name] = bars
            except DataUnavailable:
                failed.append(name)
        if not series:
            raise DataUnavailable("no sector series could be loaded")
        rows = sectors.rank_groups(series, benchmark, a.shift)
        out = {
            "market": a.market, "benchmark": benchmark_symbol, "as_of": benchmark.dates[-1].isoformat(),
            "ranked_sectors": rows,
            "leaders": [r["group"] for r in rows[:3]],
            "laggards": [r["group"] for r in rows[-3:]],
            "biggest_rank_gainers": [r["group"] for r in sorted(rows, key=lambda r: -(r["rank_change"] or 0))[:3] if (r["rank_change"] or 0) > 0],
            "biggest_rank_losers": [r["group"] for r in sorted(rows, key=lambda r: (r["rank_change"] or 0))[:3] if (r["rank_change"] or 0) < 0],
        }
        if a.industry_breadth:
            universe, _, details = load_universe("IN", None, a.industry_breadth, "2y")
            out["industry_breadth"] = {"index": a.industry_breadth, "industries": sectors.industry_breadth(universe, details)}
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["notes"] = [
        "relative_strength_score = 0.2 x 1-month + 0.4 x 3-month + 0.2 x 6-month + 0.2 x 12-month return in excess of the benchmark, in percentage points.",
        f"rank_change compares today's rank with {a.shift} sessions ago; positive means the sector moved up.",
        "Sector leadership changes, sometimes abruptly. Strength so far is not a forecast.",
        "Prices are from an unofficial source (Yahoo): sector indices for India, sector ETFs for the US. Unfinished sessions are excluded.",
    ]
    if failed:
        out["notes"].append(f"No data for: {', '.join(failed)}")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
