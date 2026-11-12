#!/usr/bin/env python3
"""Crypto market regime: trend, drawdown from peak, realised volatility and
correlation with US tech stocks for major coins, the ETH/BTC ratio, and the CFTC
positioning of large speculators in Bitcoin futures."""
import argparse
import json
import math
import pathlib
import sys

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore import breadth, cot, indicators, sectors  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import daily_bars  # noqa: E402


def realised_vol(closes: list[float], days: int = 30) -> float:
    r = [math.log(closes[i] / closes[i - 1]) for i in range(len(closes) - days, len(closes))]
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(365) * 100


def correlation(a, b, days: int = 90):
    common = sorted(set(a.dates) & set(b.dates))[-days - 1:]
    ca, cb = dict(zip(a.dates, a.close)), dict(zip(b.dates, b.close))
    ra = [math.log(ca[common[i]] / ca[common[i - 1]]) for i in range(1, len(common))]
    rb = [math.log(cb[common[i]] / cb[common[i - 1]]) for i in range(1, len(common))]
    if len(ra) < 20:
        return None
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return round(cov / math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)), 2)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--coins", default="BTC,ETH,SOL", help="comma-separated coin tickers (default BTC,ETH,SOL)")
    a = p.parse_args()
    coins, failed = {}, []
    for coin in [c.strip().upper() for c in a.coins.split(",") if c.strip()]:
        try:
            coins[coin] = daily_bars(f"{coin}-USD", "5y", "CRYPTO")
        except DataUnavailable:
            failed.append(coin)
    if not coins:
        print(json.dumps({"error": "no coin prices could be loaded"}, indent=2))
        return 2
    try:
        nasdaq = daily_bars("^IXIC", "2y", "US")
    except DataUnavailable:
        nasdaq = None
    rows = {}
    for coin, b in coins.items():
        t = breadth.index_trend(b)
        peak = max(b.close)
        s50, s200 = indicators.sma(b.close, 50)[-1], indicators.sma(b.close, 200)[-1]
        rows[coin] = {
            "as_of": t["as_of"], "close_usd": t["close"], "above_sma50": t["above_sma50"], "above_sma200": t["above_sma200"],
            "sma50_above_sma200": t["sma50_above_sma200"], "return_1m_pct": t["return_1m_pct"], "return_3m_pct": t["return_3m_pct"],
            "drawdown_from_5y_peak_pct": round((b.close[-1] / peak - 1) * 100, 2),
            "realised_vol_30d_pct": round(realised_vol(b.close), 1),
            "correlation_with_nasdaq_90d": correlation(b, nasdaq) if nasdaq else None,
        }
    eth_btc = sectors.ratio_summary("eth_btc", coins["ETH"], coins["BTC"]) if "ETH" in coins and "BTC" in coins else None
    try:
        positioning = cot.analyse(cot.fetch(cot.MARKETS["bitcoin"], 156))
        positioning.pop("history", None)
    except DataUnavailable as exc:
        positioning = {"error": str(exc)}
    btc = rows.get("BTC")
    label = None
    if btc:
        label = ("uptrend" if btc["above_sma200"] and btc["sma50_above_sma200"] else
                 "downtrend" if not btc["above_sma200"] and not btc["sma50_above_sma200"] else "transition")
    print(json.dumps({
        "bitcoin_trend": label, "coins": rows, "eth_btc_ratio": eth_btc, "cme_bitcoin_futures_positioning": positioning,
        "notes": [
            "Prices in US dollars from an unofficial source (Yahoo); daily bars close at 00:00 UTC and the current day is excluded.",
            "Realised volatility is annualised over 365 days because crypto trades every day.",
            "CFTC positioning covers CME Bitcoin futures only, not offshore exchanges where most crypto derivatives trade.",
            "Crypto is extremely volatile; drawdowns of 70% or more have happened repeatedly. This describes conditions only.",
            "In India, gains on crypto are taxed under a separate flat-rate regime with TDS on transfers and no set-off of losses; "
            "confirm the current rules with a tax professional.",
        ] + ([f"No data for: {', '.join(failed)}"] if failed else []),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
