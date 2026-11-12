#!/usr/bin/env python3
"""Work out the trades that bring a portfolio back to its target allocation,
optionally using only new money so that nothing is sold.

  --holding NAME=VALUE   current value of each asset or fund (repeat)
  --target  NAME=PERCENT target weight (repeat; must add to 100)
"""
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

from marketcore.adjust import rebalance  # noqa: E402


def pairs(items, label):
    out = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep:
            raise ValueError(f"{label} must be NAME=VALUE, got {item!r}")
        out[name.strip()] = value.strip().replace(",", "")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--holding", action="append", default=[], required=True)
    p.add_argument("--target", action="append", default=[], required=True)
    p.add_argument("--new-money", default="0", help="cash being added (negative to withdraw)")
    p.add_argument("--band", default="0", help="leave assets alone if within this many percentage points of target")
    p.add_argument("--no-sell", action="store_true", help="use only the new money; sell nothing")
    a = p.parse_args()
    try:
        out = rebalance(pairs(a.holding, "--holding"), pairs(a.target, "--target"), a.new_money, a.band, not a.no_sell)
    except (ValueError, ArithmeticError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["notes"] = [
        "Selling to rebalance can trigger capital gains tax and exit loads; buying with new money does not.",
        "Trades are in currency value. Convert to units at the current price or NAV, and round to what can actually be bought.",
        "The target allocation is the investor's own decision; this only does the arithmetic.",
    ]
    if a.no_sell:
        out["notes"].insert(0, "No-sell mode: new money goes to the assets furthest below target. The portfolio may still be off target afterwards.")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
