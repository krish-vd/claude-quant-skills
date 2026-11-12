#!/usr/bin/env python3
"""Find growth leaders: stocks with strong recent earnings and sales growth from
their filings, plus price leadership (relative strength, near highs, uptrend)."""
import argparse
import json
import pathlib
import sys
import time

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore import fundamentals, screens  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import load_universe  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], required=True)
    p.add_argument("--index", help="India: nifty50, nifty100, nifty200 ... (each company reads two or three filings: allow time)")
    p.add_argument("--symbols", help="comma-separated symbols")
    p.add_argument("--min-eps-growth", type=float, default=25.0)
    p.add_argument("--min-revenue-growth", type=float, default=15.0)
    p.add_argument("--min-rs", type=int, default=70)
    p.add_argument("--max-below-high", type=float, default=25.0, help="maximum percent below the 52-week high")
    p.add_argument("--top", type=int, default=20)
    a = p.parse_args()
    try:
        symbols = a.symbols.split(",") if a.symbols else None
        data, failed, details = load_universe(a.market, symbols, a.index, "2y")
        price_rows = {r["symbol"]: r for r in screens.screen(data)}
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    # Price filter first: only leaders need their filings read.
    leaders = [r for r in price_rows.values() if (r["rs_rank"] or 0) >= a.min_rs and r["pct_below_52w_high"] <= a.max_below_high
               and r["trend_template_conditions"]["price_above_sma150_and_sma200"]]
    results, no_fundamentals = [], []
    for row in sorted(leaders, key=lambda r: -(r["rs_rank"] or 0)):
        s = row["symbol"]
        try:
            if a.market == "IN":
                g = fundamentals.india_growth_snapshot(s)
                eps, rev = g["eps_growth_yoy_pct"], g["revenue_growth_yoy_pct"]
                extra = {"latest_quarter": g["latest_quarter"], "eps_growth_accelerating": g["eps_growth_accelerating"],
                         "previous_quarter_eps_growth_yoy_pct": g["previous_quarter_eps_growth_yoy_pct"],
                         "net_profit_growth_yoy_pct": g["net_profit_growth_yoy_pct"], "bank_format": g["bank_format"]}
            else:
                f = fundamentals.us_fundamentals(s)
                q = f["quarters"][0] if f["quarters"] else {}
                eps, rev = q.get("eps_growth_yoy_pct"), q.get("revenue_growth_yoy_pct")
                prev = f["quarters"][1] if len(f["quarters"]) > 1 else {}
                extra = {"latest_quarter": q.get("quarter_end"), "previous_quarter_eps_growth_yoy_pct": prev.get("eps_growth_yoy_pct"),
                         "eps_growth_accelerating": None if eps is None or prev.get("eps_growth_yoy_pct") is None else eps > prev["eps_growth_yoy_pct"],
                         "annual_eps_cagr_3y_pct": f["eps_cagr_3y_pct"]}
        except DataUnavailable:
            no_fundamentals.append(s)
            continue
        time.sleep(0.1)
        if eps is None or rev is None or eps < a.min_eps_growth or rev < a.min_revenue_growth:
            continue
        results.append({"symbol": s, "company": details.get(s, {}).get("company"), "industry": details.get(s, {}).get("industry"),
                        "eps_growth_yoy_pct": eps, "revenue_growth_yoy_pct": rev, **extra,
                        "rs_rank": row["rs_rank"], "pct_below_52w_high": row["pct_below_52w_high"], "close": row["close"],
                        "trend_template_passed": row["trend_template_passed"], "as_of": row["date"]})
    results.sort(key=lambda r: (-(r["eps_growth_yoy_pct"] or 0)))
    print(json.dumps({
        "market": a.market, "universe": len(data), "price_leaders_checked": len(leaders), "passed": len(results),
        "criteria": {"min_eps_growth_yoy_pct": a.min_eps_growth, "min_revenue_growth_yoy_pct": a.min_revenue_growth,
                     "min_rs_rank": a.min_rs, "max_pct_below_52w_high": a.max_below_high, "above_150_and_200_day_averages": True},
        "results": results[: a.top],
        "notes": [
            "Growth compares the latest reported quarter with the same quarter a year earlier, from the company's filings "
            "(NSE integrated filings in India, SEC in the US). Where an Indian filing has no EPS, profit growth is used.",
            "eps_growth_accelerating: this quarter's growth is above the previous quarter's. Acceleration is what growth investors look for.",
            "Relative-strength rank is within the universe screened.",
            "Growth off a small or loss-making base can look huge; check the absolute figures with company-fundamentals.",
            "Candidates for research, not recommendations. No valuation or balance-sheet test is applied.",
        ] + ([f"No usable filings for: {', '.join(no_fundamentals)}"] if no_fundamentals else []) + ([f"No price data for: {', '.join(failed)}"] if failed else []),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
