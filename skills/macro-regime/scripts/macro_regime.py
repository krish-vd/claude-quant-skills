#!/usr/bin/env python3
"""Cross-asset macro regime: US yield curve, credit risk appetite, growth versus
safety (copper/gold), stocks versus bonds, the dollar, the rupee, oil and volatility,
each with its trend and position in its own history, and a rule-based summary."""
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

from marketcore import breadth, indicators, sectors  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import daily_bars  # noqa: E402

SERIES = {"us_10y_yield": "^TNX", "us_3m_yield": "^IRX", "high_yield_bonds": "HYG", "investment_grade_bonds": "LQD",
          "copper": "HG=F", "gold": "GC=F", "us_stocks": "SPY", "long_treasuries": "TLT", "dollar_index": "DX-Y.NYB",
          "usd_inr": "INR=X", "crude_brent": "BZ=F", "vix": "^VIX", "nifty": "^NSEI"}
RATIOS = [("credit_appetite_hyg_lqd", "high_yield_bonds", "investment_grade_bonds", "rising = investors favour riskier credit"),
          ("growth_vs_safety_copper_gold", "copper", "gold", "rising = industrial demand favoured over safety"),
          ("stocks_vs_bonds_spy_tlt", "us_stocks", "long_treasuries", "rising = equities favoured over long bonds")]


def trend_flag(values: list[float]) -> str:
    s50 = indicators.sma(values, 50)[-1]
    if s50 is None:
        return "unknown"
    return "rising" if values[-1] > s50 * 1.01 else "falling" if values[-1] < s50 * 0.99 else "flat"


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    data, failed = {}, []
    for name, symbol in SERIES.items():
        try:
            b = daily_bars(symbol, "5y", "US")
            b.symbol = symbol
            data[name] = b
        except DataUnavailable:
            failed.append(name)
    if len(data) < 5:
        print(json.dumps({"error": f"too few series loaded; missing {failed}"}, indent=2))
        return 2
    snapshot = {}
    for name, b in data.items():
        t = breadth.index_trend(b)
        level = breadth.level_percentile(b, 252 * 5)
        snapshot[name] = {"symbol": b.symbol, "as_of": t["as_of"], "level": t["close"], "trend_vs_50_day": trend_flag(b.close),
                          "above_sma200": t["above_sma200"], "return_3m_pct": t["return_3m_pct"],
                          "percentile_5y": level["percentile_in_window"]}
    ratios = {}
    for label, x, y, meaning in RATIOS:
        if x in data and y in data:
            dates, values = sectors.ratio_series(data[x], data[y])
            ratios[label] = {**sectors.ratio_summary(label, data[x], data[y]), "trend_vs_50_day": trend_flag(values), "meaning": meaning}
    curve = None
    if "us_10y_yield" in data and "us_3m_yield" in data:
        long_y, short_y = data["us_10y_yield"].close[-1], data["us_3m_yield"].close[-1]
        curve = {"us_10y_minus_3m_pct_points": round(long_y - short_y, 2), "inverted": long_y < short_y,
                 "meaning": "an inverted curve (short rates above long) has often preceded US recessions, with long and variable lags"}

    checks = []

    def add(name, status, detail):
        checks.append({"item": name, "status": status, "detail": detail})

    if curve:
        add("yield_curve", "caution" if curve["inverted"] else "supportive", f"10y minus 3m = {curve['us_10y_minus_3m_pct_points']} points")
    for label, good in (("credit_appetite_hyg_lqd", "rising"), ("growth_vs_safety_copper_gold", "rising"), ("stocks_vs_bonds_spy_tlt", "rising")):
        if label in ratios:
            t = ratios[label]["trend_vs_50_day"]
            add(label, "supportive" if t == good else "caution" if t in ("rising", "falling") else "neutral", f"trend {t}")
    if "vix" in snapshot:
        pct = breadth.level_percentile(data["vix"], 252)["percentile_in_window"]
        add("volatility", "caution" if pct >= 80 else "supportive" if pct <= 50 else "neutral", f"VIX at {snapshot['vix']['level']}, {pct} percentile of the past year")
    if "dollar_index" in snapshot:
        t = snapshot["dollar_index"]["trend_vs_50_day"]
        add("dollar", "caution" if t == "rising" else "supportive" if t == "falling" else "neutral",
            f"dollar trend {t} (a rising dollar usually tightens conditions for emerging markets)")
    supportive = sum(c["status"] == "supportive" for c in checks)
    cautions = sum(c["status"] == "caution" for c in checks)
    label = "risk_on" if supportive >= 4 and cautions <= 1 else "risk_off" if cautions >= 4 else "mixed"
    print(json.dumps({
        "regime": {"label": label, "supportive": supportive, "cautions": cautions, "checklist": checks},
        "yield_curve": curve, "ratios": ratios, "series": snapshot,
        "notes": [
            "Prices and yields from an unofficial source (Yahoo); yields are in percent. Five years of history.",
            "Regime label: risk_on with four or more supportive items and at most one caution; risk_off with four or more cautions.",
            "Macro conditions change slowly and act on markets with long, variable lags. This describes the backdrop; it does not time trades.",
            "No Indian bond yields or macro data releases are included: there is no reliable free source.",
        ] + ([f"No data for: {', '.join(failed)}"] if failed else []),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
