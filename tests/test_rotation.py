from datetime import date, timedelta

import pytest

from marketcore.backtest import STRATEGIES, Bars, Config, momentum_rotation, run


def bars(closes, symbol):
    n = len(closes)
    c = [float(x) for x in closes]
    return Bars(symbol, [date(2025, 1, 1) + timedelta(days=i) for i in range(n)], c, c, c, c, [1.0] * n)


def universe(days=80):
    a = [100 * 1.01 ** i for i in range(days)]                          # steady 1% a day
    b = [100.0] * 40 + [100 * 1.03 ** (i - 39) for i in range(40, days)]  # flat, then 3% a day from day 40
    c = [100.0] * days                                                  # never moves
    return {"A": bars(a, "A"), "B": bars(b, "B"), "C": bars(c, "C")}


PARAMS = {"lookback": 20, "skip": 5, "top_n": 1, "hold_n": 1, "rebalance_days": 10, "trend_n": 0}
CFG = Config(initial_capital=100_000, alloc_pct=100, max_position_pct=100, max_positions=1, slippage_bps=0)


def test_rotation_signals_follow_the_leader():
    data = universe()
    sig = momentum_rotation(data, PARAMS)
    # Rebalance days are bars 20, 30, 40, 50, 60, 70. A's score is always 1.01^15 - 1 = 16.1%.
    # B is flat until bar 39, so it scores 0 at bars 20-40. At bar 50 its score is
    # B(45) / B(30) - 1 = 1.03^6 - 1 = 19.4%, which overtakes A.
    entries_a = [i for i, e in enumerate(sig["A"].entry) if e]
    entries_b = [i for i, e in enumerate(sig["B"].entry) if e]
    exits_a = [i for i, e in enumerate(sig["A"].exit) if e]
    assert entries_a == [20, 30, 40]
    assert entries_b == [50, 60, 70]
    assert exits_a == [50, 60, 70]
    assert not any(sig["C"].entry)
    assert all(sig["C"].exit[i] for i in (20, 30, 40, 50, 60, 70))       # ranked below hold_n every time


def test_rotation_backtest_switches_at_the_next_open():
    data = universe()
    result = run(data, momentum_rotation, PARAMS, CFG)
    dates = data["A"].dates
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert (trade.symbol, trade.entry_date, trade.exit_date) == ("A", dates[21], dates[51])
    assert trade.entry_price == pytest.approx(100 * 1.01 ** 21) and trade.exit_price == pytest.approx(100 * 1.01 ** 51)
    assert [(t.symbol, t.entry_date) for t in result.open_positions] == [("B", dates[51])]


def test_rotation_has_no_lookahead():
    full = run(universe(80), momentum_rotation, PARAMS, CFG)
    early = run(universe(45), momentum_rotation, PARAMS, CFG)
    assert early.trades == [] and [(t.symbol, t.entry_date) for t in early.open_positions] == [("A", universe()["A"].dates[21])]
    assert full.trades[0].entry_date == early.open_positions[0].entry_date


def test_trend_filter_blocks_buying_below_the_average():
    falling = [200 * 0.99 ** i for i in range(80)]
    less_bad = [200 * 0.995 ** i for i in range(80)]
    data = {"X": bars(falling, "X"), "Y": bars(less_bad, "Y")}
    with_filter = momentum_rotation(data, {**PARAMS, "trend_n": 20})
    assert not any(with_filter["Y"].entry)                               # top-ranked but below its own average
    without = momentum_rotation(data, PARAMS)
    assert any(without["Y"].entry)


def test_registration_and_validation():
    assert STRATEGIES["momentum_rotation"] is momentum_rotation and momentum_rotation.cross_sectional
    with pytest.raises(ValueError):
        momentum_rotation(universe(), {"lookback": 10, "skip": 10})
