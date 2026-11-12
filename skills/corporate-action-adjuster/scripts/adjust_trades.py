#!/usr/bin/env python3
"""Restate a trade history for stock splits and bonus issues so that FIFO lots,
holding periods and costs are right before computing capital gains.

Actions CSV columns: symbol,date,type,ratio
  type split : ratio = new shares per old share (1 share becoming 5 -> 5)
  type bonus : ratio = bonus shares per share held (1:1 -> 1 ; 1 for every 2 held -> 0.5)
  date       : the ex-date, YYYY-MM-DD
"""
import argparse
import csv
import io
import json
import pathlib
import sys
from datetime import date
from decimal import Decimal

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore.adjust import apply_actions  # noqa: E402
from marketcore.tax_india import Trade  # noqa: E402


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [{k.strip().lower(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(fh)]


def fmt(value) -> str:
    number = Decimal(str(value))
    text = format(number.normalize(), "f")
    return text if text else "0"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--trades", required=True, help="standard trade CSV")
    p.add_argument("--actions", required=True, help="CSV of corporate actions")
    p.add_argument("--output", required=True, help="where to write the adjusted trade CSV")
    a = p.parse_args()
    try:
        trades = [Trade(date.fromisoformat(r["date"]), r["symbol"], r["side"].lower(), r["quantity"], r["price"],
                        r.get("asset_class") or "listed_equity", r.get("charges") or 0) for r in read_csv(a.trades)]
        actions = [{"symbol": r["symbol"], "date": date.fromisoformat(r["date"]), "type": r["type"], "ratio": r["ratio"]}
                   for r in read_csv(a.actions)]
        adjusted, notes = apply_actions(trades, actions)
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(["date", "symbol", "side", "quantity", "price", "asset_class", "charges"])
        for t in adjusted:
            writer.writerow([t.trade_date.isoformat(), t.symbol.upper(), t.side, fmt(t.quantity), fmt(t.price), t.asset_class, fmt(t.charges)])
        pathlib.Path(a.output).write_text(out.getvalue(), encoding="utf-8")
    except (ValueError, KeyError, OSError, ArithmeticError) as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 2
    print(json.dumps({
        "output": a.output,
        "trades_in": len(trades),
        "trades_out": len(adjusted),
        "actions_applied": notes,
        "notes": [
            "Splits restate earlier trades (quantity up, price down); cost and purchase dates do not change.",
            "Bonus shares are a new lot at zero cost acquired on the action date, so their holding period starts then.",
            "For shares bought before 1 Feb 2018, restate the 31-Jan-2018 fair market value for later splits and bonuses too.",
            "Demergers, mergers, rights issues and buybacks are not handled: adjust those rows by hand from the company's cost-apportionment notice.",
            "Check the resulting share count against the demat statement before computing gains.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
