#!/usr/bin/env python3
"""One-page daily market posture: breadth, index trend, volatility, institutional
positioning (India) and sector leadership, with a rule-based checklist."""
import argparse
import json
import pathlib
import sys
from datetime import timedelta

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore import breadth, sectors  # noqa: E402
from marketcore import positioning as pos  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import daily_bars, load_universe  # noqa: E402

INDEX = {"IN": "^NSEI", "US": "^GSPC"}
VIX = {"IN": "^INDIAVIX", "US": "^VIX"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--index", default=None, help="India breadth universe (default nifty200)")
    p.add_argument("--symbols-file", help="breadth universe as a text file of symbols (required for US)")
    a = p.parse_args()
    problems = []
    try:
        symbols = pathlib.Path(a.symbols_file).read_text(encoding="utf-8").split() if a.symbols_file else None
        index_name = a.index or ("nifty200" if a.market == "IN" and not symbols else None)
        universe, failed, details = load_universe(a.market, symbols, index_name, "2y")
        measured = breadth.measure(universe, 20)
        index = breadth.index_trend(daily_bars(INDEX[a.market], "2y", "US"))
    except (ValueError, OSError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    try:
        volatility = breadth.level_percentile(daily_bars(VIX[a.market], "2y", "US"))
    except DataUnavailable as exc:
        volatility = None
        problems.append(f"volatility index unavailable: {exc}")

    fii_now = fii_before = None
    positioning = None
    if a.market == "IN":
        try:
            day, table = pos.latest_participant_oi()
            net = pos.net_positions(table)
            fii_now = net["FII"]["index_futures"]["long_pct"]
            earlier_day, earlier = pos.latest_participant_oi(day - timedelta(days=7))
            fii_before = pos.net_positions(earlier)["FII"]["index_futures"]["long_pct"]
            positioning = {"as_of": day.isoformat(), "fii_index_futures_long_pct": fii_now, "fii_index_futures_net": net["FII"]["index_futures"]["net"],
                           "compared_with": earlier_day.isoformat(), "fii_index_futures_long_pct_then": fii_before,
                           "client_index_futures_long_pct": net["Client"]["index_futures"]["long_pct"]}
            try:
                positioning["cash_market_rs_crore"] = pos.cash_flows()
            except DataUnavailable as exc:
                problems.append(f"FII/DII cash flows unavailable: {exc}")
        except DataUnavailable as exc:
            problems.append(f"participant positioning unavailable: {exc}")

    sector_view = None
    try:
        table = sectors.IN_SECTORS if a.market == "IN" else sectors.US_SECTORS
        benchmark = daily_bars(sectors.BENCHMARKS[a.market], "2y", "US")
        series = {}
        for name, symbol in table.items():
            try:
                series[name] = daily_bars(symbol, "2y", "US")
            except DataUnavailable:
                pass
        ranked = sectors.rank_groups(series, benchmark)
        sector_view = {"leaders": [r["group"] for r in ranked[:3]], "laggards": [r["group"] for r in ranked[-3:]],
                       "moving_up": [r["group"] for r in sorted(ranked, key=lambda r: -(r["rank_change"] or 0))[:3] if (r["rank_change"] or 0) > 0]}
    except DataUnavailable as exc:
        problems.append(f"sector data unavailable: {exc}")

    checklist = breadth.posture_checklist(measured, index, volatility, fii_now, fii_before)
    measured.pop("history", None)
    measured.pop("posture_rules", None)
    print(json.dumps({
        "market": a.market,
        "as_of": measured["as_of"],
        "posture": checklist,
        "index": index,
        "breadth": {"universe": index_name or f"{len(universe)} symbols supplied", **measured},
        "volatility_index": volatility,
        "positioning": positioning,
        "sectors": sector_view,
        "data_problems": problems + ([f"no price data for: {', '.join(failed)}"] if failed else []),
        "notes": [
            "The posture label counts fixed rules (see each checklist item). It describes conditions; it is not a forecast or an instruction to buy or sell.",
            "End-of-day data. Unfinished sessions are excluded, so before the close this describes the previous session.",
            "Prices from an unofficial source (Yahoo); positioning and flows from NSE's own files.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
