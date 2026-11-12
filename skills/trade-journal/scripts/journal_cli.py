#!/usr/bin/env python3
"""Trade journal: record a trade when it is opened, close it with the outcome, list trades.

The journal is a JSON file on this machine (default ~/.market-skills/journal.json).
"""
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
    sub = p.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("open", help="record a trade you have entered")
    o.add_argument("--symbol", required=True)
    o.add_argument("--direction", choices=["long", "short"], required=True)
    o.add_argument("--entry", type=float, required=True)
    o.add_argument("--quantity", type=float, required=True, help="shares, or number of lots/contracts")
    o.add_argument("--multiplier", type=float, default=1.0, help="value of a 1.0 move per unit of quantity: 1 for shares, lot size or contract multiplier for lots")
    o.add_argument("--stop", type=float)
    o.add_argument("--target", type=float)
    o.add_argument("--setup", default="", help="short tag, e.g. breakout, pullback, earnings")
    o.add_argument("--thesis", default="", help="why you took the trade, in your words")
    o.add_argument("--market", default="IN", choices=["IN", "US"])
    o.add_argument("--date", default=date.today().isoformat())

    c = sub.add_parser("close", help="close an open trade")
    c.add_argument("--id", type=int, required=True)
    c.add_argument("--exit", type=float, required=True)
    c.add_argument("--fees", type=float, default=0.0, help="total charges for the round trip")
    c.add_argument("--date", default=date.today().isoformat())
    plan = c.add_mutually_exclusive_group()
    plan.add_argument("--followed-plan", dest="followed", action="store_true", default=None)
    plan.add_argument("--broke-plan", dest="followed", action="store_false")
    c.add_argument("--notes", default="", help="what happened, what you would do differently")

    ls = sub.add_parser("list", help="list trades")
    ls.add_argument("--status", choices=["open", "closed", "all"], default="open")
    ls.add_argument("--symbol")

    a = p.parse_args()
    path = pathlib.Path(a.journal) if a.journal else journal.default_path()
    try:
        trades = journal.load(path)
        if a.cmd == "open":
            result = journal.add_trade(trades, a.symbol, a.direction, date.fromisoformat(a.date), a.entry, a.quantity,
                                       a.stop, a.target, a.setup, a.thesis, a.market, a.multiplier)
            journal.save(trades, path)
            out = {"recorded": result}
            if a.stop is None:
                out["warning"] = "No stop recorded: this trade has no planned risk, so it cannot be measured in R and the circuit breaker cannot count its risk."
        elif a.cmd == "close":
            result = journal.close_trade(trades, a.id, date.fromisoformat(a.date), a.exit, a.fees, a.followed, a.notes)
            journal.save(trades, path)
            out = {"closed": result}
        else:
            rows = [t for t in trades if a.status == "all" or t["status"] == a.status]
            if a.symbol:
                rows = [t for t in rows if t["symbol"] == a.symbol.upper()]
            out = {"count": len(rows), "trades": rows}
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["journal"] = str(path)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
