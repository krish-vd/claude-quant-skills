"""Reference values: the standard textbook case S=K=100, r=5%, sigma=20%, T=1
(call 10.4506, put 5.5735, call delta 0.6368, gamma 0.018762, vega 37.524,
call theta -6.414, call rho 53.232), plus put-call parity and numerical derivatives."""
import math

import pytest

from marketcore.options import Leg, black_76, black_scholes, implied_volatility, payoff_at, payoff_profile

S, K, R, V, T = 100.0, 100.0, 0.05, 0.20, 1.0


def test_black_scholes_reference_values():
    call, put = black_scholes("call", S, K, T, R, V), black_scholes("put", S, K, T, R, V)
    assert call.price == pytest.approx(10.4506, abs=1e-4)
    assert put.price == pytest.approx(5.5735, abs=1e-4)
    assert call.delta == pytest.approx(0.6368, abs=1e-4)
    assert put.delta == pytest.approx(0.6368 - 1.0, abs=1e-4)
    assert call.gamma == pytest.approx(0.018762, abs=1e-6)
    assert call.vega == pytest.approx(37.524, abs=1e-3)
    assert call.theta == pytest.approx(-6.414, abs=1e-3)
    assert call.rho == pytest.approx(53.232, abs=1e-3)
    assert put.gamma == pytest.approx(call.gamma) and put.vega == pytest.approx(call.vega)


def test_put_call_parity_spot_and_futures():
    for strike in (80.0, 100.0, 125.0):
        c, p = black_scholes("call", S, strike, 0.5, R, V, q=0.02), black_scholes("put", S, strike, 0.5, R, V, q=0.02)
        assert c.price - p.price == pytest.approx(S * math.exp(-0.02 * 0.5) - strike * math.exp(-R * 0.5), abs=1e-9)
        c, p = black_76("call", S, strike, 0.5, R, V), black_76("put", S, strike, 0.5, R, V)
        assert c.price - p.price == pytest.approx((S - strike) * math.exp(-R * 0.5), abs=1e-9)


@pytest.mark.parametrize("kind", ["call", "put"])
@pytest.mark.parametrize("model", ["bs", "b76"])
def test_greeks_match_numerical_derivatives(kind, model):
    def f(s=105.0, t=0.4, r=0.06, v=0.25):
        return (black_scholes(kind, s, 100.0, t, r, v, q=0.01) if model == "bs" else black_76(kind, s, 100.0, t, r, v))

    g, h = f(), 1e-4
    assert g.delta == pytest.approx((f(s=105 + h).price - f(s=105 - h).price) / (2 * h), abs=1e-6)
    assert g.gamma == pytest.approx((f(s=105 + h).price - 2 * g.price + f(s=105 - h).price) / h**2, abs=1e-4)
    assert g.vega == pytest.approx((f(v=0.25 + h).price - f(v=0.25 - h).price) / (2 * h), abs=1e-5)
    assert g.theta == pytest.approx(-(f(t=0.4 + h).price - f(t=0.4 - h).price) / (2 * h), abs=1e-5)
    assert g.rho == pytest.approx((f(r=0.06 + h).price - f(r=0.06 - h).price) / (2 * h), abs=1e-5)


def test_expiry_and_zero_vol_edges():
    assert black_scholes("call", 110, 100, 0, R, V).price == 10.0
    assert black_scholes("put", 110, 100, 0, R, V).price == 0.0
    assert black_76("call", 100, 100, 1, 0.0, 0.0).price == 0.0
    with pytest.raises(ValueError):
        black_scholes("straddle", 100, 100, 1, R, V)


def test_implied_volatility_round_trip():
    for kind, strike, vol in (("call", 100.0, 0.20), ("put", 90.0, 0.35), ("call", 130.0, 0.12)):
        price = black_76(kind, S, strike, 0.25, R, vol).price
        assert implied_volatility(kind, price, S, strike, 0.25, R) == pytest.approx(vol, abs=1e-7)
        price = black_scholes(kind, S, strike, 0.25, R, vol, q=0.01).price
        assert implied_volatility(kind, price, S, strike, 0.25, R, "black_scholes", q=0.01) == pytest.approx(vol, abs=1e-7)


def test_implied_volatility_refuses_impossible_prices():
    assert implied_volatility("call", 5.0, 120.0, 100.0, 0.25, 0.0) is None     # below intrinsic value of 20
    assert implied_volatility("call", 500.0, 100.0, 100.0, 0.25, 0.0) is None   # above the underlying
    assert implied_volatility("call", 5.0, 100.0, 100.0, 0.0, 0.0) is None      # expired


def test_long_call_payoff():
    legs = [Leg("call", "buy", 65, 120.0, strike=25000)]
    prof = payoff_profile(legs)
    assert prof["breakevens"] == [25120.0]
    assert prof["max_loss"] == -7800.0 and prof["unlimited_profit"] and prof["max_profit"] is None
    assert payoff_at(legs, 25500) == pytest.approx(65 * 380)


def test_bull_call_spread():
    legs = [Leg("call", "buy", 65, 200.0, strike=25000), Leg("call", "sell", 65, 80.0, strike=25300)]
    prof = payoff_profile(legs)
    assert prof["breakevens"] == [25120.0]                 # lower strike + net debit 120
    assert prof["max_loss"] == -65 * 120 and prof["max_profit"] == 65 * 180
    assert not prof["unlimited_profit"] and not prof["unlimited_loss"]
    assert prof["net_premium"] == -65 * 120


def test_short_straddle_and_iron_condor():
    straddle = [Leg("call", "sell", 65, 150.0, strike=25000), Leg("put", "sell", 65, 140.0, strike=25000)]
    prof = payoff_profile(straddle)
    assert prof["breakevens"] == [24710.0, 25290.0]
    assert prof["max_profit"] == 65 * 290 and prof["unlimited_loss"] and prof["max_loss"] is None

    condor = [
        Leg("put", "buy", 65, 20.0, strike=24500), Leg("put", "sell", 65, 60.0, strike=24700),
        Leg("call", "sell", 65, 55.0, strike=25300), Leg("call", "buy", 65, 15.0, strike=25500),
    ]
    prof = payoff_profile(condor)
    assert prof["max_profit"] == 65 * 80                   # net credit 80
    assert prof["max_loss"] == -65 * 120                   # wing width 200 minus credit 80
    assert prof["breakevens"] == [24620.0, 25380.0]


def test_covered_call_and_costs():
    legs = [Leg("underlying", "buy", 100, 500.0), Leg("call", "sell", 100, 10.0, strike=520)]
    prof = payoff_profile(legs)
    assert prof["breakevens"] == [490.0]
    assert prof["max_profit"] == 100 * 30 and prof["max_loss"] == -100 * 490   # stock to zero, premium kept
    assert not prof["unlimited_profit"]
    with_costs = payoff_profile(legs, costs=200.0)
    assert with_costs["max_profit"] == 2800 and with_costs["breakevens"] == [492.0]
