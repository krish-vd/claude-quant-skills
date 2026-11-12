"""Compare option structures for a stated view, on one expiry.

For each candidate the legs are priced (Black-76 at a given implied volatility, or
from actual settlement prices when supplied), then the expiry payoff, breakevens,
maximum profit and loss, and the probability of finishing above zero are computed.

Probability of profit is risk-neutral: it assumes the forward is the expected price
and the implied volatility is right. It is a property of the prices, not a forecast.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from .options import Leg, black_76, norm_cdf, payoff_at, payoff_profile

VIEWS = ("bullish", "bearish", "neutral", "volatile")


def _round_strike(x: float, step: float) -> float:
    return round(round(x / step) * step, 10)


def candidate_legs(view: str, forward: float, sigma: float, t: float, step: float) -> dict[str, list[tuple]]:
    """Standard structures for a view, as (side, kind, strike) tuples per unit. Distances
    scale with the expected move: one standard deviation = forward x sigma x sqrt(t)."""
    if view not in VIEWS:
        raise ValueError(f"view must be one of {VIEWS}")
    sd = forward * sigma * math.sqrt(t)
    atm = _round_strike(forward, step)
    near_up, near_dn = _round_strike(forward + 0.5 * sd, step), _round_strike(forward - 0.5 * sd, step)
    far_up, far_dn = _round_strike(forward + sd, step), _round_strike(forward - sd, step)
    wing_up, wing_dn = _round_strike(forward + 1.5 * sd, step), _round_strike(forward - 1.5 * sd, step)
    if near_up == atm:
        near_up += step
    if near_dn == atm:
        near_dn -= step
    if far_up <= near_up:
        far_up = near_up + step
    if far_dn >= near_dn:
        far_dn = near_dn - step
    if wing_up <= far_up:
        wing_up = far_up + step
    if wing_dn >= far_dn:
        wing_dn = far_dn - step
    table = {
        "bullish": {
            "long_call": [("buy", "call", atm)],
            "bull_call_spread": [("buy", "call", atm), ("sell", "call", far_up)],
            "bull_put_spread": [("sell", "put", atm), ("buy", "put", far_dn)],
            "short_put": [("sell", "put", near_dn)],
        },
        "bearish": {
            "long_put": [("buy", "put", atm)],
            "bear_put_spread": [("buy", "put", atm), ("sell", "put", far_dn)],
            "bear_call_spread": [("sell", "call", atm), ("buy", "call", far_up)],
            "short_call": [("sell", "call", near_up)],
        },
        "neutral": {
            "iron_condor": [("buy", "put", wing_dn), ("sell", "put", far_dn), ("sell", "call", far_up), ("buy", "call", wing_up)],
            "iron_butterfly": [("buy", "put", far_dn), ("sell", "put", atm), ("sell", "call", atm), ("buy", "call", far_up)],
            "short_strangle": [("sell", "put", far_dn), ("sell", "call", far_up)],
        },
        "volatile": {
            "long_straddle": [("buy", "call", atm), ("buy", "put", atm)],
            "long_strangle": [("buy", "call", near_up), ("buy", "put", near_dn)],
        },
    }
    return table[view]


def probability_of_profit(legs: list[Leg], forward: float, sigma: float, t: float, costs: float = 0.0) -> Optional[float]:
    """Risk-neutral probability that the expiry P&L is above zero, under a lognormal
    distribution with the given forward and volatility. Exact for piecewise-linear payoffs."""
    if t <= 0 or sigma <= 0:
        return None
    vol_t = sigma * math.sqrt(t)

    def cdf(x: float) -> float:
        if x <= 0:
            return 0.0
        return norm_cdf((math.log(x / forward) + 0.5 * vol_t * vol_t) / vol_t)

    profile = payoff_profile(legs, costs)
    points = sorted({0.0, *profile["breakevens"], *(leg.strike for leg in legs if leg.kind != "underlying")})
    points.append(points[-1] * 3 + forward * 3)
    prob = 0.0
    for lo, hi in zip(points, points[1:]):
        if hi <= lo:
            continue
        if payoff_at(legs, (lo + hi) / 2) - costs > 0:
            prob += cdf(hi) - cdf(lo)
    last = points[-1]
    if payoff_at(legs, last * 2) - costs > 0:
        prob += 1 - cdf(last)
    return round(min(max(prob, 0.0), 1.0) * 100, 1)


def compare(
    view: str, forward: float, sigma: float, days: float, quantity: float, step: float, rate: float = 0.0,
    price_lookup: Optional[Callable[[str, float], Optional[float]]] = None,
) -> list[dict]:
    """Price and evaluate each candidate structure. ``price_lookup(kind, strike)`` returns a
    market premium; when it returns None the leg is priced with Black-76 at ``sigma``."""
    t = days / 365.0
    out = []
    for name, spec in candidate_legs(view, forward, sigma, t, step).items():
        legs, sources = [], set()
        for side, kind, strike in spec:
            premium = price_lookup(kind, strike) if price_lookup else None
            if premium is None:
                premium = black_76(kind, forward, strike, t, rate, sigma).price
                sources.add("model")
            else:
                sources.add("market")
            legs.append(Leg(kind, side, quantity, round(premium, 2), strike))
        profile = payoff_profile(legs)
        net_delta = sum((1 if l.side == "buy" else -1) * black_76(l.kind, forward, l.strike, t, rate, sigma).delta * quantity for l in legs)
        net_theta = sum((1 if l.side == "buy" else -1) * black_76(l.kind, forward, l.strike, t, rate, sigma).theta / 365 * quantity for l in legs)
        net_vega = sum((1 if l.side == "buy" else -1) * black_76(l.kind, forward, l.strike, t, rate, sigma).vega / 100 * quantity for l in legs)
        reward_risk = None
        if profile["max_profit"] is not None and profile["max_loss"] not in (None, 0):
            reward_risk = round(profile["max_profit"] / abs(profile["max_loss"]), 2)
        out.append({
            "structure": name,
            "legs": [{"side": l.side, "kind": l.kind, "strike": l.strike, "premium": l.price} for l in legs],
            "pricing": "/".join(sorted(sources)),
            "net_premium": profile["net_premium"],
            "max_profit": profile["max_profit"], "max_loss": profile["max_loss"],
            "unlimited_profit": profile["unlimited_profit"], "unlimited_loss": profile["unlimited_loss"],
            "breakevens": profile["breakevens"],
            "reward_to_risk": reward_risk,
            "probability_of_profit_pct": probability_of_profit(legs, forward, sigma, t),
            "position_delta": round(net_delta, 2), "theta_per_day": round(net_theta, 2), "vega_per_vol_point": round(net_vega, 2),
        })
    return out
