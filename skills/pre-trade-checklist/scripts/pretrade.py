#!/usr/bin/env python3
"""Pre-trade gate: check a planned trade against the trader's own rules before the
order goes in - stop defined, risk per trade, position size, reward to risk, the
loss circuit breaker, room under the open-risk cap, and duplicate positions."""
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
    p.add_argument("--account", type=float, required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--direction", choices=["long", "short"], required=True)
    p.add_argument("--entry", type=float, required=True)
    p.add_argument("--stop", type=float)
    p.add_argument("--target", type=float)
    p.add_argument("--quantity", type=float, required=True, help="shares, or number of lots/contracts")
    p.add_argument("--multiplier", type=float, default=1.0, help="lot size or contract multiplier when quantity is in lots")
    p.add_argument("--leveraged", action="store_true", help="futures or other margined instrument: skip the position-size cap")
    p.add_argument("--max-risk-pct", type=float, default=1.0)
    p.add_argument("--min-reward-to-risk", type=float, default=2.0)
    p.add_argument("--max-position-pct", type=float, default=20.0)
    p.add_argument("--daily-loss-pct", type=float, default=2.0)
    p.add_argument("--weekly-loss-pct", type=float, default=4.0)
    p.add_argument("--monthly-loss-pct", type=float, default=8.0)
    p.add_argument("--max-consecutive-losses", type=int, default=3)
    p.add_argument("--max-open-risk-pct", type=float, default=6.0)
    p.add_argument("--journal", help="path to the journal file (default ~/.market-skills/journal.json)")
    p.add_argument("--date", default=date.today().isoformat())
    a = p.parse_args()
    path = pathlib.Path(a.journal) if a.journal else journal.default_path()
    try:
        out = journal.pretrade_check(
            journal.load(path), a.account, date.fromisoformat(a.date), a.symbol, a.direction, a.entry, a.stop,
            a.quantity, a.target, a.multiplier, a.max_risk_pct, a.min_reward_to_risk, a.max_position_pct, a.leveraged,
            daily_loss_pct=a.daily_loss_pct, weekly_loss_pct=a.weekly_loss_pct, monthly_loss_pct=a.monthly_loss_pct,
            max_consecutive_losses=a.max_consecutive_losses, max_open_risk_pct=a.max_open_risk_pct,
        )
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["journal"] = str(path)
    out["notes"] = [
        "The rules and limits are the trader's own; the defaults are common conventions.",
        "The check covers process and risk, not whether the trade idea is good.",
    ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
