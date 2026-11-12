#!/usr/bin/env python3
"""Performance review of closed trades in the journal: expectancy, R-multiples,
streaks, drawdown, and breakdowns by setup, month and plan adherence."""
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

from marketcore import journal  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal", help="path to the journal file (default ~/.market-skills/journal.json)")
    p.add_argument("--from", dest="start", help="first exit date YYYY-MM-DD")
    p.add_argument("--to", dest="end", help="last exit date YYYY-MM-DD")
    a = p.parse_args()
    path = pathlib.Path(a.journal) if a.journal else journal.default_path()
    try:
        trades = journal.load(path)
        out = journal.review(
            trades,
            date.fromisoformat(a.start) if a.start else None,
            date.fromisoformat(a.end) if a.end else None,
        )
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    cautions = []
    n = out.get("trades", 0)
    if n == 0:
        cautions.append("No closed trades in this window.")
    elif n < 30:
        cautions.append(f"Only {n} closed trades: win rate and expectancy are not yet reliable. Treat patterns as hints.")
    if out.get("trades_without_a_stop"):
        cautions.append(f"{out['trades_without_a_stop']} trade(s) had no stop, so they are missing from the R statistics.")
    out["cautions"] = cautions
    out["journal"] = str(path)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
