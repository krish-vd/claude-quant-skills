"""Sector and commodity comparisons: ranked relative strength, ratios and unit conversions."""
from __future__ import annotations

from datetime import date
from typing import Optional

from . import indicators as ind
from .backtest import Bars

# Yahoo symbols, each checked to resolve on 2026-11-12. Unofficial prices.
IN_SECTORS = {
    "Bank": "^NSEBANK", "Financial Services": "NIFTY_FIN_SERVICE.NS", "IT": "^CNXIT", "Auto": "^CNXAUTO",
    "Pharma": "^CNXPHARMA", "FMCG": "^CNXFMCG", "Metal": "^CNXMETAL", "Realty": "^CNXREALTY",
    "Energy": "^CNXENERGY", "PSU Bank": "^CNXPSUBANK", "Infrastructure": "^CNXINFRA", "Media": "^CNXMEDIA",
    "Consumption": "^CNXCONSUM", "PSE": "^CNXPSE",
}
US_SECTORS = {
    "Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Health Care": "XLV",
    "Consumer Discretionary": "XLY", "Consumer Staples": "XLP", "Industrials": "XLI", "Materials": "XLB",
    "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC",
}
BENCHMARKS = {"IN": "^NSEI", "US": "SPY"}
PERIODS = {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "12m": 252}
WEIGHTS = {"1m": 0.2, "3m": 0.4, "6m": 0.2, "12m": 0.2}

TROY_OUNCE_GRAMS = 31.1034768  # exact by definition
POUND_KG = 0.45359237  # exact by definition


def _returns(closes: list[float], end: int) -> dict[str, Optional[float]]:
    """Returns over each period ending at index ``end`` (negative indices count from the end)."""
    n = len(closes)
    last_index = n + end if end < 0 else end
    out = {}
    for label, bars in PERIODS.items():
        start = last_index - bars
        out[label] = closes[last_index] / closes[start] - 1.0 if start >= 0 and closes[start] > 0 else None
    return out


def _composite(rets: dict, bench: dict) -> Optional[float]:
    """Weighted excess return over the benchmark; None unless every weighted period is available."""
    total = 0.0
    for label, weight in WEIGHTS.items():
        if rets[label] is None or bench[label] is None:
            return None
        total += weight * (rets[label] - bench[label])
    return total


def rank_groups(series: dict[str, Bars], benchmark: Bars, shift: int = 21) -> list[dict]:
    """Rank groups by weighted return in excess of the benchmark, now and ``shift`` sessions ago.

    Composite = 0.2 x 1-month + 0.4 x 3-month + 0.2 x 6-month + 0.2 x 12-month excess return.
    """
    bench_now, bench_then = _returns(benchmark.close, -1), _returns(benchmark.close, -1 - shift)
    rows = []
    for name, bars in series.items():
        if len(bars) < 2:
            continue
        now = _returns(bars.close, -1)
        then = _returns(bars.close, -1 - shift) if len(bars) > shift + 1 else {k: None for k in PERIODS}
        s50, s200 = ind.sma(bars.close, 50)[-1], ind.sma(bars.close, 200)[-1]
        rows.append({
            "group": name,
            "symbol": bars.symbol,
            "as_of": bars.dates[-1].isoformat(),
            "returns_pct": {k: None if v is None else round(v * 100, 2) for k, v in now.items()},
            "excess_vs_benchmark_pct": {k: None if now[k] is None or bench_now[k] is None else round((now[k] - bench_now[k]) * 100, 2)
                                        for k in PERIODS},
            "above_sma50": None if s50 is None else bars.close[-1] > s50,
            "above_sma200": None if s200 is None else bars.close[-1] > s200,
            "_score": _composite(now, bench_now),
            "_score_then": _composite(then, bench_then),
        })

    def assign(key: str, field: str) -> None:
        scored = sorted((r for r in rows if r[key] is not None), key=lambda r: -r[key])
        for position, row in enumerate(scored, start=1):
            row[field] = position

    assign("_score", "rank")
    assign("_score_then", "rank_before")
    for row in rows:
        score = row.pop("_score")
        row.pop("_score_then")
        row["relative_strength_score"] = None if score is None else round(score * 100, 2)
        row.setdefault("rank", None)
        row.setdefault("rank_before", None)
        both = row["rank"] is not None and row["rank_before"] is not None
        row["rank_change"] = row["rank_before"] - row["rank"] if both else None  # positive = moved up
    rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0))
    return rows


def industry_breadth(universe: dict[str, Bars], details: dict[str, dict], min_members: int = 3) -> list[dict]:
    """Equal-weight view of each industry among index members: median 3-month return and share above the 50-day."""
    groups: dict[str, list[Bars]] = {}
    for symbol, bars in universe.items():
        industry = details.get(symbol, {}).get("industry")
        if industry and len(bars) > 64:
            groups.setdefault(industry, []).append(bars)
    rows = []
    for industry, members in groups.items():
        if len(members) < min_members:
            continue
        three_month = sorted(b.close[-1] / b.close[-64] - 1.0 for b in members)
        above = sum(1 for b in members if (ind.sma(b.close, 50)[-1] or float("inf")) < b.close[-1])
        rows.append({
            "industry": industry,
            "members": len(members),
            "median_3m_return_pct": round(three_month[len(three_month) // 2] * 100, 2),
            "pct_above_sma50": round(above / len(members) * 100, 1),
        })
    rows.sort(key=lambda r: -r["median_3m_return_pct"])
    return rows


def ratio_series(a: Bars, b: Bars) -> tuple[list[date], list[float]]:
    """a / b on the dates both series have."""
    other = dict(zip(b.dates, b.close))
    dates, values = [], []
    for d, v in zip(a.dates, a.close):
        if d in other and other[d] > 0:
            dates.append(d)
            values.append(v / other[d])
    return dates, values


def ratio_summary(name: str, a: Bars, b: Bars) -> dict:
    dates, values = ratio_series(a, b)
    if len(values) < 2:
        return {"ratio": name, "error": "no overlapping dates"}
    last = values[-1]
    year = values[-252:]
    return {
        "ratio": name,
        "as_of": dates[-1].isoformat(),
        "value": round(last, 4),
        "percentile_1y": round(sum(1 for v in year if v < last) / len(year) * 100, 1),
        "percentile_all": round(sum(1 for v in values if v < last) / len(values) * 100, 1),
        "sessions_in_history": len(values),
        "low_1y": round(min(year), 4),
        "high_1y": round(max(year), 4),
        "change_1m_pct": round((last / values[-22] - 1) * 100, 2) if len(values) > 22 else None,
    }


CONVERSIONS = {
    # international quote -> Indian quoting unit, before duties and local costs
    "gold": {"from": "USD per troy ounce", "to": "INR per 10 g", "factor": 10.0 / TROY_OUNCE_GRAMS},
    "silver": {"from": "USD per troy ounce", "to": "INR per kg", "factor": 1000.0 / TROY_OUNCE_GRAMS},
    "copper": {"from": "USD per pound", "to": "INR per kg", "factor": 1.0 / POUND_KG},
    "crude": {"from": "USD per barrel", "to": "INR per barrel", "factor": 1.0},
    "natural_gas": {"from": "USD per mmBtu", "to": "INR per mmBtu", "factor": 1.0},
}


def import_parity(commodity: str, international_price: float, usd_inr: float, local_price: Optional[float] = None) -> dict:
    """International price converted to the Indian quoting unit at the given exchange rate.

    This is the raw currency-and-unit conversion only. Indian prices also carry import
    duty, taxes, freight and local premiums, so a gap to the local price is expected;
    ``local_premium_pct`` measures that gap and nothing more.
    """
    if commodity not in CONVERSIONS:
        raise ValueError(f"commodity must be one of {sorted(CONVERSIONS)}")
    if international_price <= 0 or usd_inr <= 0:
        raise ValueError("price and exchange rate must be positive")
    spec = CONVERSIONS[commodity]
    converted = international_price * usd_inr * spec["factor"]
    out = {
        "commodity": commodity,
        "international_price": international_price,
        "international_unit": spec["from"],
        "usd_inr": usd_inr,
        "converted_price": round(converted, 2),
        "converted_unit": spec["to"],
    }
    if local_price is not None:
        out["local_price"] = local_price
        out["local_premium_pct"] = round((local_price / converted - 1) * 100, 2)
    return out
