"""XIRR: annualised money-weighted return for dated cash flows.

Uses the same convention as spreadsheet XIRR: actual days / 365, discounting
every flow back to the earliest date. Investments are negative, redemptions and
the current value are positive.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Sequence


class XirrError(ValueError):
    pass


def _npv(rate: float, flows: Sequence[tuple[date, float]], t0: date) -> float:
    return sum(amount / (1.0 + rate) ** ((when - t0).days / 365.0) for when, amount in flows)


def xirr(cashflows: Iterable[tuple[date, float]], tolerance: float = 1e-10) -> float:
    """Return the annual rate (0.12 = 12%) that makes the net present value zero.

    Solved by bisection on a bracket that is widened until the sign changes, so
    it does not depend on a starting guess and cannot diverge.
    """
    flows = sorted((d, float(a)) for d, a in cashflows if float(a) != 0.0)
    if len(flows) < 2:
        raise XirrError("need at least two non-zero cash flows")
    if not (any(a < 0 for _, a in flows) and any(a > 0 for _, a in flows)):
        raise XirrError("need at least one negative and one positive cash flow")
    t0 = flows[0][0]
    if flows[-1][0] == t0:
        raise XirrError("all cash flows are on the same date")

    low, high = -0.999999, 1.0
    f_low, f_high = _npv(low, flows, t0), _npv(high, flows, t0)
    while f_low * f_high > 0:
        high *= 2
        if high > 1e7:
            raise XirrError("no rate found: cash flows do not bracket a solution")
        f_high = _npv(high, flows, t0)
    for _ in range(400):
        mid = (low + high) / 2
        f_mid = _npv(mid, flows, t0)
        if abs(f_mid) < tolerance or (high - low) < 1e-13:
            return mid
        if f_low * f_mid <= 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2
