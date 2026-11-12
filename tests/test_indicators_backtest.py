"""Indicator values and backtest fills are checked against figures worked out by hand."""
from datetime import date, timedelta

import pytest

from marketcore import indicators as ind
from marketcore.backtest import Bars, Config, Signals, donchian_breakout, run, sma_cross
from marketcore.costmodel import india_delivery, us_equity


def make_bars(closes, opens=None, highs=None, lows=None, symbol="T", start=date(2025, 1, 1)):
    n = len(closes)
    opens = opens or closes
    highs = highs or [max(o, c) for o, c in zip(opens, closes)]
    lows = lows or [min(o, c) for o, c in zip(opens, closes)]
    return Bars(symbol, [start + timedelta(days=i) for i in range(n)], list(map(float, opens)),
                list(map(float, highs)), list(map(float, lows)), list(map(float, closes)), [1000.0] * n)


def scripted(entry_days, exit_days, stop_distance=None):
    """A strategy that fires on fixed bar numbers, to test the engine alone."""
    def strategy(bars, _params):
        n = len(bars)
        return Signals([i in entry_days for i in range(n)], [i in exit_days for i in range(n)],
                       [stop_distance] * n, [0.0] * n)
    return strategy


NO_COST = dict(slippage_bps=0.0)


# ---------- indicators ----------

def test_sma_and_ema():
    assert ind.sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]
    # EMA(3): seed = mean(1,2,3) = 2; alpha = 0.5 -> 0.5*4 + 0.5*2 = 3; then 0.5*5 + 0.5*3 = 4
    assert ind.ema([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_rsi_by_hand():
    # changes: +1, -1, +2  -> avg gain 1.0, avg loss 1/3 over n=3 -> RS 3 -> RSI 75
    values = [10, 11, 10, 12]
    assert ind.rsi(values, 3)[3] == pytest.approx(75.0)
    # next change +1: avg gain (1*2 + 1)/3 = 1, avg loss (1/3*2)/3 = 2/9 -> RS 4.5 -> RSI 81.8181...
    assert ind.rsi(values + [13], 3)[4] == pytest.approx(100 - 100 / 5.5)
    assert ind.rsi([1, 2, 3, 4], 3)[3] == 100.0          # only gains
    assert ind.rsi([4, 3, 2, 1], 3)[3] == pytest.approx(0.0)  # only losses


def test_atr_by_hand():
    high, low, close = [10, 12, 13], [8, 9, 11], [9, 11, 12]
    # TR: 2 ; max(3, |12-9|, |9-9|) = 3 ; max(2, |13-11|, |11-11|) = 2
    assert ind.true_range(high, low, close) == [2, 3, 2]
    assert ind.atr(high, low, close, 2) == [None, 2.5, pytest.approx(2.25)]   # (2.5*1 + 2)/2


def test_highest_lowest_roc():
    v = [3, 1, 4, 1, 5]
    assert ind.highest(v, 3) == [None, None, 4, 4, 5]
    assert ind.lowest(v, 3) == [None, None, 1, 1, 1]
    assert ind.roc([100, 110, 121], 1) == [None, pytest.approx(0.10), pytest.approx(0.10)]


# ---------- engine ----------

def test_entry_fills_at_next_open_not_signal_close():
    bars = make_bars(closes=[100, 100, 110, 120, 130], opens=[100, 100, 104, 118, 128])
    result = run({"T": bars}, scripted({1}, {3}), config=Config(initial_capital=10_000, alloc_pct=100, max_position_pct=100, **NO_COST))
    trade = result.trades[0]
    assert trade.entry_date == bars.dates[2] and trade.entry_price == 104   # signal on bar 1, fill at bar 2 open
    assert trade.exit_date == bars.dates[4] and trade.exit_price == 128     # exit signal bar 3, fill at bar 4 open
    assert trade.shares == 96                                               # floor(10,000 / 104)
    assert trade.pnl == pytest.approx(96 * 24)
    assert result.metrics["final_equity"] == pytest.approx(10_000 + 96 * 24)


def test_risk_based_sizing_and_stop_fill():
    # Fill at 100, stop distance 5 -> stop 95. Risk 1% of 100,000 = 1,000 -> 200 shares.
    bars = make_bars(closes=[100, 100, 100, 97, 93], opens=[100, 100, 100, 99, 96], lows=[100, 100, 100, 96, 92])
    result = run({"T": bars}, scripted({1}, set(), stop_distance=5.0), config=Config(initial_capital=100_000, **NO_COST))
    trade = result.trades[0]
    assert trade.shares == 200 and trade.stop == 95
    assert trade.exit_reason == "stop" and trade.exit_price == 95 and trade.exit_date == bars.dates[4]
    assert trade.pnl == pytest.approx(-1000) and trade.r_multiple == pytest.approx(-1.0)


def test_gap_through_stop_fills_at_the_open():
    bars = make_bars(closes=[100, 100, 100, 90], opens=[100, 100, 100, 91], lows=[100, 100, 100, 89])
    result = run({"T": bars}, scripted({1}, set(), stop_distance=5.0), config=Config(initial_capital=100_000, **NO_COST))
    trade = result.trades[0]
    assert trade.exit_reason == "stop_gap" and trade.exit_price == 91       # worse than the 95 stop
    assert trade.r_multiple == pytest.approx(-1.8)                          # lost 9 per share against 5 planned


def test_costs_and_slippage_are_charged():
    bars = make_bars(closes=[100, 100, 100, 100], opens=[100, 100, 100, 100])
    cfg = Config(initial_capital=10_000, alloc_pct=50, max_position_pct=100, buy_cost_frac=0.001,
                 sell_cost_frac=0.002, fixed_cost_per_order=10, slippage_bps=10)
    result = run({"T": bars}, scripted({0}, {1}), config=cfg)
    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(100.1) and trade.exit_price == pytest.approx(99.9)
    assert trade.shares == 49                                               # floor(5,000 / 100.1)
    costs = 49 * 100.1 * 0.001 + 10 + 49 * 99.9 * 0.002 + 10
    assert trade.costs == pytest.approx(costs)
    assert trade.pnl == pytest.approx(49 * (99.9 - 100.1) - costs)
    assert result.metrics["final_equity"] == pytest.approx(10_000 + trade.pnl)


def test_equity_identity_and_position_limit():
    a = make_bars([10, 10, 12, 12, 12], symbol="A")
    b = make_bars([20, 20, 18, 18, 18], symbol="B")
    result = run({"A": a, "B": b}, scripted({0}, {2}), config=Config(initial_capital=1_000, alloc_pct=50, max_position_pct=50, max_positions=1, **NO_COST))
    assert len(result.trades) == 1 and result.skipped_entries == 1          # only one slot
    assert result.metrics["final_equity"] == pytest.approx(1_000 + sum(t.pnl for t in result.trades))


def test_open_position_is_marked_to_last_close():
    bars = make_bars([100, 100, 110, 120])
    result = run({"T": bars}, scripted({0}, set()), config=Config(initial_capital=1_000, alloc_pct=100, max_position_pct=100, **NO_COST))
    assert result.trades == [] and len(result.open_positions) == 1
    assert result.metrics["final_equity"] == pytest.approx(1_000 + 10 * 20)  # 10 shares bought at 100, now 120


def test_no_lookahead_future_bars_do_not_change_past_trades():
    closes = [100 + (i % 17) * 3 - (i % 5) * 4 + i * 0.4 for i in range(400)]
    full = make_bars(closes)
    params = {"entry_n": 20, "exit_n": 10, "atr_n": 10}
    cut = 250
    early = run({"T": full.slice(cut)}, donchian_breakout, params)
    late = run({"T": full}, donchian_breakout, params)
    key = lambda t: (t.entry_date, t.entry_price, t.exit_date, t.exit_price, t.shares)
    done_early = [key(t) for t in early.trades]
    assert done_early, "the series should produce trades"
    assert done_early == [key(t) for t in late.trades if t.exit_date <= full.dates[cut - 1]][: len(done_early)]


def test_sma_cross_signals():
    closes = [10] * 5 + [20] * 5 + [5] * 6
    sig = sma_cross(make_bars(closes), {"fast_n": 2, "slow_n": 4})
    assert [i for i, e in enumerate(sig.entry) if e] == [5]    # fast (15) crosses above slow (12.5) on bar 5
    assert [i for i, e in enumerate(sig.exit) if e] == [10]    # fast (12.5) falls below slow (16.25) on bar 10


def test_max_drawdown_metric():
    bars = make_bars([100, 100, 120, 90, 108])
    result = run({"T": bars}, scripted({0}, set()), config=Config(initial_capital=1_000, alloc_pct=100, max_position_pct=100, **NO_COST))
    assert result.metrics["max_drawdown_pct"] == pytest.approx(25.0)        # 1,200 -> 900


# ---------- cost model ----------

def test_cost_models_match_the_rulebook():
    m = india_delivery(date(2026, 11, 12))
    assert m.buy_frac == pytest.approx(118.7406 / 100_000)      # from test_charges: Rs 118.7406 per Rs 1,00,000
    assert m.sell_frac == pytest.approx(103.7406 / 100_000)
    assert india_delivery(date(2026, 11, 12), brokerage_per_order=20, dp_charge=15.34).fixed_per_order == pytest.approx(20 * 1.18 + 7.67)
    assert us_equity(date(2026, 11, 12)).sell_frac == pytest.approx(0.0000206)
