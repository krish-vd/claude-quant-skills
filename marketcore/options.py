"""European option pricing, greeks, implied volatility and expiry payoffs.

Two models:

* Black-Scholes-Merton on the spot price, with a continuous dividend yield ``q``.
* Black-76 on the futures price. Use this for index options that are hedged and
  quoted against the future (NIFTY, BANKNIFTY) and for options on futures (MCX,
  CME): it needs no dividend or carry assumption.

Conventions: ``t`` is time to expiry in YEARS (calendar days / 365), rates and
volatility are decimals (0.065 = 6.5%, 0.14 = 14%). Greeks are per unit of the
underlying: vega and rho are per 1.00 change (divide by 100 for per-point),
theta is per YEAR (divide by 365 for per-day).

Limits: European exercise only (correct for NSE index and stock options and
most MCX options; US single-stock options are American, where this understates
puts and dividend-paying calls). Constant volatility and rates; no skew.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

SQRT_2PI = math.sqrt(2.0 * math.pi)


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


@dataclass(frozen=True)
class Greeks:
    price: float
    delta: float
    gamma: float
    vega: float  # per 1.00 (100 vol points)
    theta: float  # per year
    rho: float  # per 1.00 (100 percentage points)

    def per_day_and_point(self) -> dict:
        """The same greeks in trader units: theta per calendar day, vega and rho per 1 point."""
        return {
            "price": self.price, "delta": self.delta, "gamma": self.gamma,
            "vega_per_vol_point": self.vega / 100.0,
            "theta_per_day": self.theta / 365.0,
            "rho_per_rate_point": self.rho / 100.0,
        }


def _check(kind: str, price: float, strike: float, t: float, sigma: float) -> None:
    if kind not in ("call", "put"):
        raise ValueError("kind must be 'call' or 'put'")
    if price <= 0 or strike <= 0:
        raise ValueError("underlying price and strike must be positive")
    if t < 0 or sigma < 0:
        raise ValueError("time to expiry and volatility cannot be negative")


def _generalised(kind: str, s: float, k: float, t: float, r: float, b: float, sigma: float) -> Greeks:
    """Generalised Black-Scholes with cost of carry ``b`` (b = r - q for spot, b = 0 for futures)."""
    _check(kind, s, k, t, sigma)
    sign = 1.0 if kind == "call" else -1.0
    carry, disc = math.exp((b - r) * t), math.exp(-r * t)
    if t == 0 or sigma == 0:
        forward = s * math.exp(b * t)
        intrinsic = max(sign * (forward - k), 0.0) * disc
        in_money = sign * (forward - k) > 0
        return Greeks(intrinsic, sign * carry if in_money else 0.0, 0.0, 0.0, 0.0, 0.0)
    vol_t = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (b + 0.5 * sigma * sigma) * t) / vol_t
    d2 = d1 - vol_t
    price = sign * (s * carry * norm_cdf(sign * d1) - k * disc * norm_cdf(sign * d2))
    delta = sign * carry * norm_cdf(sign * d1)
    gamma = carry * norm_pdf(d1) / (s * vol_t)
    vega = s * carry * norm_pdf(d1) * math.sqrt(t)
    theta = (
        -s * carry * norm_pdf(d1) * sigma / (2.0 * math.sqrt(t))
        - sign * (b - r) * s * carry * norm_cdf(sign * d1)
        - sign * r * k * disc * norm_cdf(sign * d2)
    )
    if b == 0.0:  # option on a future: the whole premium is discounted
        rho = -t * price
    else:
        rho = sign * t * k * disc * norm_cdf(sign * d2)
    return Greeks(price, delta, gamma, vega, theta, rho)


def black_scholes(kind: str, spot: float, strike: float, t: float, r: float, sigma: float, q: float = 0.0) -> Greeks:
    """Option on a spot price with continuous dividend yield ``q``."""
    return _generalised(kind, spot, strike, t, r, r - q, sigma)


def black_76(kind: str, future: float, strike: float, t: float, r: float, sigma: float) -> Greeks:
    """Option on a futures price. Delta is with respect to the future."""
    return _generalised(kind, future, strike, t, r, 0.0, sigma)


def implied_volatility(
    kind: str, market_price: float, underlying: float, strike: float, t: float, r: float,
    model: str = "black_76", q: float = 0.0,
) -> Optional[float]:
    """Volatility that reproduces ``market_price``, or None when no volatility can
    (price below intrinsic value, above the no-arbitrage ceiling, or expired)."""
    if t <= 0 or market_price <= 0:
        return None

    def price_at(sigma: float) -> float:
        if model == "black_76":
            return black_76(kind, underlying, strike, t, r, sigma).price
        if model == "black_scholes":
            return black_scholes(kind, underlying, strike, t, r, sigma, q).price
        raise ValueError("model must be 'black_76' or 'black_scholes'")

    low, high = 1e-6, 5.0
    if market_price < price_at(low) - 1e-12 or market_price > price_at(high):
        return None
    for _ in range(200):
        mid = 0.5 * (low + high)
        if price_at(mid) < market_price:
            low = mid
        else:
            high = mid
        if high - low < 1e-10:
            break
    return 0.5 * (low + high)


# ---------- expiry payoff of a multi-leg position ----------

@dataclass(frozen=True)
class Leg:
    """One leg. ``kind``: call, put, or underlying (a future or shares).
    ``price`` is the premium paid or received per unit, or the entry price of the underlying."""

    kind: str
    side: str  # buy or sell
    quantity: float  # units: lots x lot size
    price: float
    strike: float = 0.0

    def payoff(self, at: float) -> float:
        if self.kind == "call":
            value = max(at - self.strike, 0.0) - self.price
        elif self.kind == "put":
            value = max(self.strike - at, 0.0) - self.price
        elif self.kind == "underlying":
            value = at - self.price
        else:
            raise ValueError("leg kind must be call, put or underlying")
        if self.side not in ("buy", "sell"):
            raise ValueError("leg side must be buy or sell")
        return value * self.quantity * (1.0 if self.side == "buy" else -1.0)


def payoff_at(legs: list[Leg], at: float) -> float:
    return sum(leg.payoff(at) for leg in legs)


def payoff_profile(legs: list[Leg], costs: float = 0.0) -> dict:
    """Expiry profit and loss of the whole position, exact at every kink.

    The payoff is piecewise linear with kinks only at the strikes, so breakevens,
    maximum profit and maximum loss are found exactly, not by scanning a grid.
    ``costs`` (total charges for the position) are subtracted everywhere.
    """
    if not legs:
        raise ValueError("at least one leg is required")
    strikes = sorted({leg.strike for leg in legs if leg.kind in ("call", "put")})
    top = (strikes[-1] if strikes else max(leg.price for leg in legs)) * 2.0 + 1.0
    knots = [0.0] + strikes + [top]
    values = [payoff_at(legs, x) - costs for x in knots]

    slope_up = sum(
        (1.0 if leg.side == "buy" else -1.0) * leg.quantity
        for leg in legs if leg.kind in ("call", "underlying")
    )
    breakevens = []
    for i in range(len(knots) - 1):
        x0, x1, y0, y1 = knots[i], knots[i + 1], values[i], values[i + 1]
        if y0 == 0.0:
            breakevens.append(x0)
        elif y0 * y1 < 0:
            breakevens.append(x0 + (x1 - x0) * (-y0) / (y1 - y0))
    if slope_up != 0 and values[-1] != 0 and (values[-1] > 0) != (slope_up > 0):
        breakevens.append(knots[-1] - values[-1] / slope_up)  # crossing beyond the last knot

    finite_values = values[:-1]  # the last knot is only a probe for the upper tail
    max_profit: Optional[float] = max(finite_values)
    max_loss: Optional[float] = min(finite_values)
    if slope_up > 0:
        max_profit = None  # unlimited upside
    elif slope_up < 0:
        max_loss = None  # unlimited loss as the price rises
    return {
        "breakevens": sorted(round(b, 4) for b in set(breakevens)),
        "max_profit": None if max_profit is None else round(max_profit, 2),
        "max_loss": None if max_loss is None else round(max_loss, 2),
        "unlimited_profit": slope_up > 0,
        "unlimited_loss": slope_up < 0,
        "payoff_at_strikes": [{"price": k, "pnl": round(payoff_at(legs, k) - costs, 2)} for k in strikes],
        "payoff_at_zero": round(values[0], 2),
        "net_premium": round(
            sum((-1.0 if leg.side == "buy" else 1.0) * leg.price * leg.quantity
                for leg in legs if leg.kind in ("call", "put")), 2),
    }
