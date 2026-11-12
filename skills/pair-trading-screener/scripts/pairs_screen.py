#!/usr/bin/env python3
"""Find cointegrated pairs among a list of stocks (or analyse one pair): hedge ratio,
Engle-Granger test, half-life of mean reversion and the current spread z-score."""
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

from marketcore import pairs  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import load_universe  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--symbols", required=True, help="comma-separated, ideally stocks in the same industry (2 to 30)")
    p.add_argument("--range", default="2y", choices=["1y", "2y", "5y"])
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--entry-z", type=float, default=2.0, help="flag pairs whose spread is at least this many standard deviations out")
    a = p.parse_args()
    symbols = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    if len(symbols) < 2:
        p.error("give at least two symbols")
    try:
        data, failed, _ = load_universe(a.market, symbols, None, a.range)
        rows = pairs.screen_pairs({s: (b.dates, b.close) for s, b in data.items()})
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    cointegrated = [r for r in rows if r["cointegrated_at"]]
    stretched = [r for r in cointegrated if abs(r["spread_zscore"]) >= a.entry_z]
    print(json.dumps({
        "pairs_tested": len(rows), "cointegrated": len(cointegrated),
        "stretched_now": [{"a": r["a"], "b": r["b"], "spread_zscore": r["spread_zscore"],
                           "spread_direction": f"{r['a']} rich relative to {r['b']}" if r["spread_zscore"] > 0 else f"{r['a']} cheap relative to {r['b']}"}
                          for r in stretched],
        "results": rows[: a.top],
        "notes": [
            "Spread = log(A) - hedge_ratio x log(B) - intercept, fitted over the whole period. z-score uses the last 60 sessions.",
            "cointegrated_at: the Engle-Granger test rejects 'no long-run relation' at that level. With many pairs tested some pass "
            "by chance (about 5 in 100 at 5%), so prefer pairs with an economic link and a 1% result.",
            "Half-life: sessions for a gap to halve. Very long half-lives tie up capital; very short ones may not survive costs.",
            "Relationships break: mergers, regulation or a change in one business can end a pair. Re-test before every trade.",
            "A pair trade needs a short leg: in India that means stock futures (lots, margin, expiry) since cash shorts must be closed the same day.",
            "Prices from an unofficial source, split-adjusted. Candidates for research, not recommendations.",
        ] + ([f"No data for: {', '.join(failed)}"] if failed else []),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
