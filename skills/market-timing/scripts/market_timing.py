#!/usr/bin/env python3
"""Index price-and-volume timing signals: distribution days, rally attempt and
follow-through day status, and a market-top warning checklist."""
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

from marketcore import breadth, timing  # noqa: E402
from marketcore.backtest import Bars  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import daily_bars, load_universe  # noqa: E402

INDEX = {"IN": "^NSEI", "US": "^GSPC"}


def india_volume_proxy(index: Bars) -> tuple[Bars, str]:
    """Nifty 50 has no reliable index volume in the free source: use the combined
    traded value of its member stocks each day instead."""
    universe, _, _ = load_universe("IN", None, "nifty50", "2y")
    total: dict = {}
    for b in universe.values():
        for d, c, v in zip(b.dates, b.close, b.volume):
            total[d] = total.get(d, 0.0) + c * v
    vol = [total.get(d, 0.0) for d in index.dates]
    proxied = Bars(index.symbol, index.dates, index.open, index.high, index.low, index.close, vol)
    return proxied, "Volume is the combined traded value of the Nifty 50 member stocks (the index itself has no volume in the free data)."


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--index", help="override the index symbol (default ^NSEI or ^GSPC)")
    p.add_argument("--min-ftd-gain", type=float, default=1.25, help="minimum follow-through gain, percent (default 1.25)")
    p.add_argument("--with-breadth", action="store_true", help="add the share of stocks above their 50-day average to the top checklist (slower)")
    a = p.parse_args()
    notes = []
    try:
        index = daily_bars(a.index or INDEX[a.market], "2y", "US")
        if a.market == "IN" and not a.index:
            index, note = india_volume_proxy(index)
            notes.append(note)
        dist = timing.distribution_days(index)
        rally = timing.rally_status(index, a.min_ftd_gain)
        pct50 = None
        if a.with_breadth:
            universe, _, _ = load_universe(a.market, None, "nifty200", "2y") if a.market == "IN" else (None, None, None)
            if universe:
                pct50 = breadth.measure(universe, 1)["pct_above_sma50"]
        top = timing.top_checklist(index, dist["count"], pct50)
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    print(json.dumps({
        "market": a.market, "index": index.symbol, "as_of": index.dates[-1].isoformat(), "close": round(index.close[-1], 2),
        "distribution": dist, "rally": rally, "top_checklist": top,
        "notes": notes + [
            "Rules: distribution day = close down 0.2% or more on higher volume, counted over 25 sessions and dropped once the "
            "index closes 5% above it; follow-through = a close up 1.25% or more on higher volume on day 4 or later of a rally attempt.",
            "These are descriptive rules. Many follow-through days fail and distribution clusters do not always precede declines. "
            "Use them as context for position size and new entries, not as buy or sell signals.",
            "End-of-day data from an unofficial source; unfinished sessions are excluded.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
