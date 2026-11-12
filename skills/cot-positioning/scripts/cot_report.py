#!/usr/bin/env python3
"""Who holds US futures: large speculators, commercial hedgers and small traders,
from the CFTC's weekly Commitments of Traders report, with net positions, their
3-year range position (COT index) and recent changes."""
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

from marketcore import cot  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--market", choices=sorted(cot.MARKETS), action="append", help="repeatable")
    g.add_argument("--code", help="a CFTC contract market code")
    g.add_argument("--search", help="find contract codes by name, e.g. 'SOYBEAN'")
    g.add_argument("--all", action="store_true", help="every market in the built-in list")
    p.add_argument("--weeks", type=int, default=156, help="history for the COT index (default 156 = 3 years)")
    a = p.parse_args()
    try:
        if a.search:
            print(json.dumps({"matches": cot.search(a.search)}, indent=2))
            return 0
        targets = {a.code: a.code} if a.code else {m: cot.MARKETS[m] for m in (sorted(cot.MARKETS) if a.all else a.market)}
        results, errors = {}, {}
        for name, code in targets.items():
            try:
                out = cot.analyse(cot.fetch(code, a.weeks))
                if a.all or (a.market and len(a.market) > 1):
                    out.pop("history", None)
                results[name] = out
            except DataUnavailable as exc:
                errors[name] = str(exc)
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    print(json.dumps({
        "markets": results, "errors": errors, "source": cot.URL,
        "notes": [
            "Legacy futures-only report. Speculators = non-commercial traders (mostly funds); commercials = hedgers; small traders = "
            "positions below reporting levels. Net = long minus short, in contracts.",
            "COT index: where the current net position sits between its lowest (0) and highest (100) in the history window.",
            "Positions are as of Tuesday and published on Friday, so they are three days old when released.",
            "Extreme speculator positioning is often read as crowded and prone to reversal, but extremes can persist for months. "
            "Use it as context, not as a timing signal.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
