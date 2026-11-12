#!/usr/bin/env python3
"""Mutual fund return analysis from NAV history: trailing returns, rolling returns,
drawdown, volatility and what a monthly SIP actually earned. Compare several funds."""
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

from marketcore import planning  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.mfhistory import nav_history  # noqa: E402


def analyse(code: str, sip_amount: float) -> dict:
    h = nav_history(code)
    dates, navs = h["dates"], h["navs"]
    return {
        "scheme_code": h["scheme_code"],
        "scheme_name": h["scheme_name"],
        "category": h["category"],
        "history_from": dates[0].isoformat(),
        "latest_nav_date": dates[-1].isoformat(),
        "latest_nav": navs[-1],
        "trailing_returns_pct": planning.trailing_returns(dates, navs),
        "rolling_returns": {f"{y}y": planning.rolling_returns(dates, navs, y) for y in (1, 3, 5)},
        "risk": planning.drawdown_and_volatility(dates, navs),
        "sip_actual": {
            "monthly_amount": sip_amount,
            **{f"{y}y": planning.sip_backtest(dates, navs, sip_amount, y) for y in (3, 5, 10)},
            "since_start": planning.sip_backtest(dates, navs, sip_amount),
        },
        "official_check": h["official_check"],
        "source": h["source"],
        "source_kind": h["source_kind"],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scheme-code", action="append", required=True, help="AMFI scheme code; repeat to compare funds")
    p.add_argument("--sip-amount", type=float, default=10_000.0, help="monthly amount for the SIP illustration")
    a = p.parse_args()
    funds, errors = [], []
    for code in a.scheme_code:
        try:
            funds.append(analyse(code, a.sip_amount))
        except (DataUnavailable, ValueError) as exc:
            errors.append({"scheme_code": code, "error": str(exc)})
    if not funds:
        print(json.dumps({"errors": errors}, indent=2))
        return 2
    print(json.dumps({
        "funds": funds,
        "errors": errors,
        "notes": [
            "Returns up to 1 year are absolute; 3y, 5y and 10y are annualised (CAGR). Rolling returns are annualised.",
            "Growth-option NAVs include reinvested income. IDCW NAVs fall on each payout, so their returns here are understated.",
            "Past returns do not predict future returns. Compare funds only within the same category and over the same period.",
            "NAV history is from a community mirror; official_check compares its latest NAV with AMFI's own file.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
