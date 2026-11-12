#!/usr/bin/env python3
"""Loss circuit breaker: reads the trade journal and says whether new risk is allowed
today, based on daily, weekly and monthly loss limits, a losing streak, and open risk."""
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
    p.add_argument("--account", type=float, required=True, help="account equity")
    p.add_argument("--journal", help="path to the journal file (default ~/.market-skills/journal.json)")
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--daily-loss-pct", type=float, default=2.0)
    p.add_argument("--weekly-loss-pct", type=float, default=4.0)
    p.add_argument("--monthly-loss-pct", type=float, default=8.0)
    p.add_argument("--max-consecutive-losses", type=int, default=3)
    p.add_argument("--max-open-risk-pct", type=float, default=6.0)
    a = p.parse_args()
    path = pathlib.Path(a.journal) if a.journal else journal.default_path()
    try:
        out = journal.circuit_breaker(
            journal.load(path), a.account, date.fromisoformat(a.date), a.daily_loss_pct, a.weekly_loss_pct,
            a.monthly_loss_pct, a.max_consecutive_losses, a.max_open_risk_pct,
        )
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["limits"] = {
        "daily_loss_pct": a.daily_loss_pct, "weekly_loss_pct": a.weekly_loss_pct, "monthly_loss_pct": a.monthly_loss_pct,
        "max_consecutive_losses": a.max_consecutive_losses, "max_open_risk_pct": a.max_open_risk_pct,
    }
    out["notes"] = [
        "Only trades recorded in the journal are counted. Unrecorded trades and open-position mark-to-market losses are not.",
        "The default limits are common conventions; set limits you have decided on in advance.",
    ]
    out["journal"] = str(path)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
