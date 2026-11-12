#!/usr/bin/env python3
"""Commodity regime: trend and range position of gold, silver, crude, natural gas,
copper, the dollar and USD/INR; key ratios; and the rupee value of international
prices for comparison with MCX."""
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

from marketcore import breadth, sectors  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import daily_bars  # noqa: E402

INSTRUMENTS = {
    "gold": "GC=F", "silver": "SI=F", "copper": "HG=F", "crude": "CL=F", "brent": "BZ=F",
    "natural_gas": "NG=F", "platinum": "PL=F", "dollar_index": "DX-Y.NYB", "usd_inr": "INR=X",
}
RATIOS = [("gold_to_silver", "gold", "silver"), ("gold_to_copper", "gold", "copper"),
          ("gold_to_crude", "gold", "crude"), ("brent_to_wti", "brent", "crude")]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mcx", action="append", default=[], metavar="COMMODITY=PRICE",
                   help="your MCX price to compare with the converted international price, e.g. gold=125000 "
                        "(gold per 10 g, silver per kg, copper per kg, crude per barrel, natural_gas per mmBtu)")
    a = p.parse_args()
    loaded, failed = {}, []
    for name, symbol in INSTRUMENTS.items():
        try:
            bars = daily_bars(symbol, "5y", "US")
            bars.symbol = symbol
            loaded[name] = bars
        except DataUnavailable:
            failed.append(name)
    if not loaded:
        print(json.dumps({"error": "no commodity data could be loaded"}, indent=2))
        return 2
    snapshot = {}
    for name, bars in loaded.items():
        trend = breadth.index_trend(bars)
        level = breadth.level_percentile(bars)
        snapshot[name] = {**trend, "percentile_in_1y_range": level["percentile_in_window"],
                          "low_1y": level["window_low"], "high_1y": level["window_high"]}
    ratios = [sectors.ratio_summary(label, loaded[x], loaded[y]) for label, x, y in RATIOS if x in loaded and y in loaded]

    parity = []
    try:
        mcx = {}
        for item in a.mcx:
            name, sep, value = item.partition("=")
            if not sep:
                p.error(f"--mcx must be COMMODITY=PRICE, got {item!r}")
            mcx[name.strip().lower()] = float(value)
        if "usd_inr" in loaded:
            fx = loaded["usd_inr"].close[-1]
            for commodity in sectors.CONVERSIONS:
                if commodity in loaded:
                    parity.append(sectors.import_parity(commodity, round(loaded[commodity].close[-1], 4), round(fx, 4), mcx.get(commodity)))
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    notes = [
        "International prices are front-month futures from an unofficial source (Yahoo), in US dollars. Unfinished sessions are excluded.",
        "converted_price is a currency-and-unit conversion only. MCX prices also carry import duty, taxes, freight and a local "
        "premium, and trade different contract months, so local_premium_pct is not an arbitrage measure.",
        "A ratio at a percentile extreme has, historically, sometimes stayed there for a long time. It describes; it does not predict.",
    ]
    if failed:
        notes.append(f"No data for: {', '.join(failed)}")
    print(json.dumps({"instruments": snapshot, "ratios": ratios, "rupee_conversion": parity, "notes": notes}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
