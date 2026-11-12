#!/usr/bin/env python3
"""Key chart levels from price data: support and resistance zones from clustered
swing points, recent swing structure, moving averages, 52-week range and ATR.
Use it to check a chart reading against the actual numbers."""
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

from marketcore import levels  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import daily_bars  # noqa: E402


def weekly(bars):
    from marketcore.backtest import Bars
    out = Bars(bars.symbol, [], [], [], [], [], [])
    for d, o, h, l, c, v in zip(bars.dates, bars.open, bars.high, bars.low, bars.close, bars.volume):
        key = d.isocalendar()[:2]
        if out.dates and out.dates[-1].isocalendar()[:2] == key:
            out.high[-1], out.low[-1] = max(out.high[-1], h), min(out.low[-1], l)
            out.close[-1], out.volume[-1], out.dates[-1] = c, out.volume[-1] + v, d
        else:
            out.dates.append(d), out.open.append(o), out.high.append(h), out.low.append(l), out.close.append(c), out.volume.append(v)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("symbol", help="RELIANCE (with --market IN), AAPL, ^NSEI, GC=F ...")
    p.add_argument("--market", choices=["IN", "US", "CRYPTO"], default="US")
    p.add_argument("--timeframe", choices=["daily", "weekly"], default="daily")
    p.add_argument("--swing", type=int, default=5, help="bars on each side that define a swing point (default 5)")
    p.add_argument("--zone-pct", type=float, default=1.5, help="swings within this percent form one zone")
    a = p.parse_args()
    try:
        bars = daily_bars(a.symbol, "5y" if a.timeframe == "weekly" else "2y", a.market)
        if a.timeframe == "weekly":
            bars = weekly(bars)
        out = levels.analyse(bars, a.swing, a.zone_pct)
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["timeframe"] = a.timeframe
    out["notes"] = [
        "Support and resistance are zones where price has turned before; touches counts how many swings fall in the zone. "
        "They are areas of interest, not prices where a reversal is assured.",
        "52-week figures use closing prices; zones use highs and lows.",
        "Prices from an unofficial source, split-adjusted; the unfinished session is excluded.",
    ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
