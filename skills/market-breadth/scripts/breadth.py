#!/usr/bin/env python3
"""Market breadth and regime: share of stocks above key averages, advances and
declines, new highs and lows, the index trend, and the volatility index level."""
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

from marketcore import breadth  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import daily_bars, load_universe  # noqa: E402

DEFAULTS = {"IN": {"index": "^NSEI", "vix": "^INDIAVIX"}, "US": {"index": "^GSPC", "vix": "^VIX"}}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--index", help="India universe: nifty50, nifty100, nifty200, nifty500, niftymidcap150, niftysmallcap250")
    p.add_argument("--symbols", help="comma-separated universe (required for US)")
    p.add_argument("--symbols-file", help="text file, one symbol per line")
    p.add_argument("--benchmark", help="index for the trend check (default ^NSEI or ^GSPC)")
    p.add_argument("--history-days", type=int, default=60)
    a = p.parse_args()
    try:
        symbols = a.symbols.split(",") if a.symbols else None
        if a.symbols_file:
            symbols = pathlib.Path(a.symbols_file).read_text(encoding="utf-8").split()
        if a.market == "IN" and not symbols and not a.index:
            a.index = "nifty500"
        universe, failed, details = load_universe(a.market, symbols, a.index, "2y")
        out = breadth.measure(universe, a.history_days)
        repair = details.get("__repair__", {})
        out["gaps_filled_from_official_nse_file"] = repair.get("repaired", [])
        out["gaps_not_filled"] = repair.get("unrepaired", [])
    except (ValueError, OSError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["universe"] = a.index or f"{len(universe)} symbols supplied"
    for key, symbol, fn in (("index_trend", a.benchmark or DEFAULTS[a.market]["index"], breadth.index_trend),
                            ("volatility_index", DEFAULTS[a.market]["vix"], breadth.level_percentile)):
        try:
            out[key] = fn(daily_bars(symbol, "2y", a.market if symbol.startswith("^") else "US"))
        except DataUnavailable as exc:
            out[key] = {"error": str(exc)}
    out["notes"] = [
        "Breadth describes current participation; it does not predict direction.",
        "The posture label follows the fixed thresholds in posture_rules.",
        "Prices are from an unofficial source (Yahoo). Unfinished sessions are excluded.",
    ]
    if a.index:
        out["notes"].append(f"The universe is today's {a.index} members.")
    if failed:
        out["notes"].append(f"No data for: {', '.join(failed)}")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
