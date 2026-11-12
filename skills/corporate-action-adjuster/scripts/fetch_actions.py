#!/usr/bin/env python3
"""Look up bonus issues and splits on NSE for the symbols in a trade file and write
the actions CSV that adjust_trades.py needs. Demergers, rights and anything it cannot
read are listed for manual handling, never guessed."""
import argparse
import csv
import json
import pathlib
import sys
import time
from datetime import date

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore import corporate  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trades", required=True, help="standard trade CSV; actions are looked up from each symbol's first trade")
    p.add_argument("--output", required=True, help="where to write the actions CSV")
    a = p.parse_args()
    try:
        first: dict[str, date] = {}
        with open(a.trades, newline="", encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
                symbol, day = row["symbol"].upper(), date.fromisoformat(row["date"])
                first[symbol] = min(first.get(symbol, day), day)
    except (KeyError, ValueError, OSError) as exc:
        print(json.dumps({"error": f"could not read {a.trades}: {exc}"}, indent=2))
        return 2
    usable, manual, failed = [], [], []
    for symbol, start in sorted(first.items()):
        try:
            for row in corporate.actions(symbol, start, date.today()):
                if row["ex_date"] <= start:
                    continue
                item = {"symbol": symbol, "date": row["ex_date"].isoformat(), "subject": row["subject"]}
                if row["type"] in ("bonus", "split"):
                    usable.append({**item, "type": row["type"], "ratio": row["ratio"]})
                elif row["type"] in ("demerger", "rights", "buyback", "unparsed_bonus_or_split"):
                    manual.append({**item, "type": row["type"]})
        except DataUnavailable as exc:
            failed.append(f"{symbol}: {exc}")
        time.sleep(0.2)
    with open(a.output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["symbol", "date", "type", "ratio"])
        for r in usable:
            writer.writerow([r["symbol"], r["date"], r["type"], f"{r['ratio']:g}"])
    print(json.dumps({
        "output": a.output,
        "symbols_checked": len(first),
        "actions_written": usable,
        "needs_manual_handling": manual,
        "lookup_failed": failed,
        "source": corporate.ACTIONS_URL,
        "notes": [
            "Only actions with an ex-date after the symbol's first trade in the file are included.",
            "Bonus ratio is bonus shares per share held; split ratio is new shares per old share. Check each against the company's announcement.",
            "Demergers, rights issues and buybacks change cost or holdings in ways this tool does not apply: edit the trade file for those.",
            "NSE lists actions under the current symbol. A company that was renamed or merged may need its old symbol's history added by hand.",
            "Next: python adjust_trades.py --trades <trades> --actions <this file> --output <adjusted trades>, then compare share counts with the demat statement.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
