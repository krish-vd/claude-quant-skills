"""SIP and goal arithmetic, and return statistics for a NAV or price series.

SIP convention (matches the calculators most Indian fund sites use): the
instalment is invested at the START of each month and grows at a monthly rate
of annual_rate / 12. Pass ``effective=True`` to use (1 + annual_rate)^(1/12) - 1
instead, where the annual rate is the true yearly growth.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from datetime import date
from typing import Optional

from .tax_india import add_months
from .xirr import XirrError, xirr


def monthly_rate(annual_rate: float, effective: bool = False) -> float:
    return (1.0 + annual_rate) ** (1.0 / 12.0) - 1.0 if effective else annual_rate / 12.0


def sip_projection(
    monthly_amount: float, annual_rate: float, years: int, step_up_pct: float = 0.0,
    initial_lumpsum: float = 0.0, effective: bool = False,
) -> dict:
    """Value of a monthly SIP after ``years``. ``step_up_pct`` raises the instalment once a year."""
    if monthly_amount < 0 or initial_lumpsum < 0 or years < 1:
        raise ValueError("amounts cannot be negative and years must be at least 1")
    if annual_rate <= -1:
        raise ValueError("annual_rate must be above -100%")
    i = monthly_rate(annual_rate, effective)
    balance, invested, instalment = initial_lumpsum, initial_lumpsum, monthly_amount
    table = []
    for year in range(1, years + 1):
        for _ in range(12):
            balance = (balance + instalment) * (1.0 + i)
            invested += instalment
        table.append({"year": year, "monthly_instalment": round(instalment, 2),
                      "invested_to_date": round(invested, 2), "value": round(balance, 2)})
        instalment *= 1.0 + step_up_pct / 100.0
    return {
        "future_value": round(balance, 2),
        "total_invested": round(invested, 2),
        "gain": round(balance - invested, 2),
        "monthly_rate_used": i,
        "yearly": table,
    }


def required_sip(
    target: float, annual_rate: float, years: int, step_up_pct: float = 0.0,
    initial_lumpsum: float = 0.0, effective: bool = False,
) -> dict:
    """Starting monthly SIP needed to reach ``target``. Exact, because value is linear in the instalment."""
    if target <= 0:
        raise ValueError("target must be positive")
    # Work at a large scale so the 2-decimal rounding inside sip_projection cannot distort the ratio.
    scale = 1e9
    from_lumpsum = sip_projection(0.0, annual_rate, years, 0.0, initial_lumpsum, effective)["future_value"]
    per_rupee = sip_projection(scale, annual_rate, years, step_up_pct, 0.0, effective)["future_value"] / scale
    shortfall = target - from_lumpsum
    amount = max(shortfall, 0.0) / per_rupee if per_rupee > 0 else math.inf
    return {
        "required_monthly_sip": round(amount, 2),
        "lumpsum_alone_grows_to": from_lumpsum,
        "target": target,
        "already_met_by_lumpsum": shortfall <= 0,
    }


def inflation_adjusted(amount: float, inflation_rate: float, years: float) -> float:
    """What ``amount`` received ``years`` from now is worth in today's money."""
    return amount / (1.0 + inflation_rate) ** years


# ---------- return statistics for a dated value series ----------

def _value_on_or_before(dates: list[date], values: list[float], target: date) -> Optional[tuple[date, float]]:
    i = bisect_right(dates, target) - 1
    return (dates[i], values[i]) if i >= 0 else None


def trailing_returns(dates: list[date], values: list[float]) -> dict:
    """Point-to-point returns ending at the last value. Periods up to a year are
    absolute; longer periods are annualised (CAGR). The start value is the last
    one on or before the anniversary date."""
    end_date, end_value = dates[-1], values[-1]
    out = {}
    for label, months in (("1m", 1), ("3m", 3), ("6m", 6), ("1y", 12), ("3y", 36), ("5y", 60), ("10y", 120)):
        start = _value_on_or_before(dates, values, add_months(end_date, -months))
        if start is None or (end_date - start[0]).days > months * 31 + 10:
            out[label] = None
            continue
        growth = end_value / start[1]
        years = months / 12.0
        out[label] = round(((growth ** (1.0 / years) - 1.0) if months > 12 else (growth - 1.0)) * 100, 2)
    return out


def rolling_returns(dates: list[date], values: list[float], years: int) -> Optional[dict]:
    """Distribution of annualised returns over every ``years``-long window in the series."""
    results = []
    for i, start_date in enumerate(dates):
        end = _value_on_or_before(dates, values, add_months(start_date, 12 * years))
        target = add_months(start_date, 12 * years)
        if target > dates[-1]:
            break
        results.append((end[1] / values[i]) ** (1.0 / years) - 1.0)
    if not results:
        return None
    results.sort()
    n = len(results)
    return {
        "window_years": years,
        "windows": n,
        "min_pct": round(results[0] * 100, 2),
        "p25_pct": round(results[n // 4] * 100, 2),
        "median_pct": round(results[n // 2] * 100, 2),
        "p75_pct": round(results[(3 * n) // 4] * 100, 2),
        "max_pct": round(results[-1] * 100, 2),
        "negative_windows_pct": round(sum(1 for r in results if r < 0) / n * 100, 1),
    }


def drawdown_and_volatility(dates: list[date], values: list[float]) -> dict:
    peak, peak_date, worst, worst_from, worst_to = values[0], dates[0], 0.0, dates[0], dates[0]
    for d, v in zip(dates, values):
        if v > peak:
            peak, peak_date = v, d
        dd = 1.0 - v / peak
        if dd > worst:
            worst, worst_from, worst_to = dd, peak_date, d
    logs = [math.log(values[i] / values[i - 1]) for i in range(1, len(values)) if values[i - 1] > 0 and values[i] > 0]
    vol = None
    if len(logs) > 1:
        mean = sum(logs) / len(logs)
        per_year = len(logs) / max((dates[-1] - dates[0]).days / 365.25, 1e-9)
        vol = math.sqrt(sum((x - mean) ** 2 for x in logs) / (len(logs) - 1)) * math.sqrt(per_year)
    return {
        "max_drawdown_pct": round(worst * 100, 2),
        "drawdown_peak_date": worst_from.isoformat(),
        "drawdown_trough_date": worst_to.isoformat(),
        "annualised_volatility_pct": None if vol is None else round(vol * 100, 2),
    }


def sip_backtest(dates: list[date], values: list[float], monthly_amount: float = 10_000.0, years: Optional[int] = None) -> Optional[dict]:
    """What a monthly SIP into this series actually returned: invest on the first
    available date of each month, value at the last price, annualise with XIRR."""
    start_from = add_months(dates[-1], -12 * years) if years else dates[0]
    flows, units, seen = [], 0.0, set()
    for d, v in zip(dates, values):
        if d < start_from or (d.year, d.month) in seen or d == dates[-1]:
            continue
        seen.add((d.year, d.month))
        units += monthly_amount / v
        flows.append((d, -monthly_amount))
    if len(flows) < 2:
        return None
    final_value = units * values[-1]
    flows.append((dates[-1], final_value))
    try:
        rate = xirr(flows)
    except XirrError:
        return None
    invested = monthly_amount * (len(flows) - 1)
    return {
        "instalments": len(flows) - 1,
        "first_instalment": flows[0][0].isoformat(),
        "invested": round(invested, 2),
        "value": round(final_value, 2),
        "xirr_pct": round(rate * 100, 2),
    }
