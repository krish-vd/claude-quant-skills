#!/usr/bin/env python3
"""SIP and goal planning: project a monthly SIP (with optional yearly step-up and a
starting lumpsum), or work out the SIP needed to reach a target."""
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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--monthly", type=float, help="monthly SIP amount (to project its value)")
    p.add_argument("--target", type=float, help="goal amount (to find the SIP required)")
    p.add_argument("--years", type=int, required=True)
    p.add_argument("--return-pct", type=float, required=True, help="assumed annual return, e.g. 11")
    p.add_argument("--step-up-pct", type=float, default=0.0, help="yearly increase in the instalment, e.g. 10")
    p.add_argument("--lumpsum", type=float, default=0.0, help="amount invested at the start")
    p.add_argument("--inflation-pct", type=float, help="to show results in today's money, e.g. 6")
    p.add_argument("--effective", action="store_true", help="treat the return as a true annual rate instead of a monthly rate of return/12")
    p.add_argument("--scenarios", help="comma-separated alternative annual returns to compare, e.g. 8,10,12")
    a = p.parse_args()
    if (a.monthly is None) == (a.target is None):
        p.error("give exactly one of --monthly or --target")
    try:
        rate = a.return_pct / 100.0
        if a.target is not None:
            need = planning.required_sip(a.target, rate, a.years, a.step_up_pct, a.lumpsum, a.effective)
            monthly = need["required_monthly_sip"]
        else:
            need, monthly = None, a.monthly
        proj = planning.sip_projection(monthly, rate, a.years, a.step_up_pct, a.lumpsum, a.effective)
        scenarios = None
        if a.scenarios:
            scenarios = []
            for text in a.scenarios.split(","):
                r = float(text) / 100.0
                row = {"return_pct": float(text)}
                if a.target is not None:
                    row["required_monthly_sip"] = planning.required_sip(a.target, r, a.years, a.step_up_pct, a.lumpsum, a.effective)["required_monthly_sip"]
                else:
                    row["future_value"] = planning.sip_projection(monthly, r, a.years, a.step_up_pct, a.lumpsum, a.effective)["future_value"]
                scenarios.append(row)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out = {
        "inputs": {"years": a.years, "assumed_return_pct": a.return_pct, "step_up_pct": a.step_up_pct, "lumpsum": a.lumpsum},
        "required": need,
        "monthly_sip": monthly,
        "future_value": proj["future_value"],
        "total_invested": proj["total_invested"],
        "gain": proj["gain"],
        "yearly": proj["yearly"],
        "scenarios": scenarios,
        "convention": ("true annual rate, converted to a monthly rate" if a.effective
                       else "monthly rate = annual return / 12, instalment at the start of each month (the usual fund-site convention)"),
        "notes": [
            "The return is an assumption, not a forecast. Equity returns vary widely from year to year; a constant rate hides that.",
            "Taxes on gains and fund expenses beyond those already in the NAV are not deducted.",
        ],
    }
    if a.inflation_pct is not None:
        out["future_value_in_todays_money"] = round(
            planning.inflation_adjusted(proj["future_value"], a.inflation_pct / 100.0, a.years), 2)
        out["inflation_pct"] = a.inflation_pct
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
