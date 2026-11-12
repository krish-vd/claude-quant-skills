from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from marketcore.backtest import Bars, Config, Signals, bars_before, run
from marketcore.data.history import drop_unfinished_bar
from marketcore.robustness import monte_carlo, out_of_sample, parameter_sweep


def make_bars(closes, symbol="T", start=date(2025, 1, 1)):
    n = len(closes)
    c = [float(x) for x in closes]
    return Bars(symbol, [start + timedelta(days=i) for i in range(n)], c, c, c, c, [1000.0] * n)


def every_other_day(bars, params):
    """Buy on bars divisible by ``gap``, sell on the bar after."""
    n = len(bars)
    gap = int(params.get("gap", 2))
    return Signals([i % gap == 0 for i in range(n)], [i % gap == 1 for i in range(n)], [None] * n, [0.0] * n)


CFG = Config(initial_capital=10_000, alloc_pct=100, max_position_pct=100, slippage_bps=0)


def test_bars_before():
    bars = make_bars([1, 2, 3, 4, 5])
    assert bars_before(bars, date(2025, 1, 3)).close == [1.0, 2.0]
    assert len(bars_before(bars, date(2030, 1, 1))) == 5


def test_entries_from_blocks_earlier_entries():
    bars = make_bars([100 + i for i in range(20)])
    split = bars.dates[10]
    result = run({"T": bars}, every_other_day, {}, replace(CFG, entries_from=split))
    assert result.trades and all(t.entry_date > split for t in result.trades)
    assert all(v == 10_000 for d, v in result.equity_curve if d <= split)


def test_regime_filter_blocks_entries_on_false_days():
    bars = make_bars([100 + i for i in range(20)])
    regime = {d: i >= 10 for i, d in enumerate(bars.dates)}
    result = run({"T": bars}, every_other_day, {}, replace(CFG, regime=regime))
    assert result.trades and all(t.entry_date > bars.dates[10] for t in result.trades)


def test_out_of_sample_windows_do_not_overlap():
    bars = make_bars([100 + i for i in range(40)])
    split = bars.dates[20]
    res = out_of_sample({"T": bars}, every_other_day, {}, CFG, split)
    assert res["in_sample"]["end"] < split.isoformat() <= res["out_of_sample"]["start"]
    assert res["in_sample"]["closed_trades"] > 0 and res["out_of_sample"]["closed_trades"] > 0


def test_parameter_sweep_ranks_and_reports_out_of_sample():
    bars = make_bars([100 + i for i in range(60)])
    res = parameter_sweep({"T": bars}, every_other_day, {"gap": [2, 3, 4]}, CFG, split=bars.dates[40])
    assert res["combinations"] == 3 and len(res["results"]) == 3
    cagrs = [r["cagr_pct"] for r in res["results"]]
    assert cagrs == sorted(cagrs, reverse=True)
    assert res["best_in_sample_params"] == res["results"][0]["params"]
    assert "best_out_of_sample" in res
    with pytest.raises(ValueError):
        parameter_sweep({"T": bars}, every_other_day, {"gap": list(range(2, 300))}, CFG)


def test_monte_carlo_is_deterministic_and_bounded():
    returns = [0.02, -0.01, 0.03, -0.015, 0.01] * 6
    a, b = monte_carlo(returns, runs=500, seed=7), monte_carlo(returns, runs=500, seed=7)
    assert a == b
    assert a["total_return_pct"]["p5"] <= a["total_return_pct"]["p50"] <= a["total_return_pct"]["p95"]
    assert 0 <= a["max_drawdown_pct"]["p50"] <= a["max_drawdown_pct"]["p99"] <= 100
    assert monte_carlo([0.01] * 10, runs=100)["probability_of_loss_pct"] == 0.0
    assert monte_carlo([0.01]) == {}


def test_unfinished_session_is_dropped():
    bars = make_bars([1, 2, 3], start=date(2026, 11, 10))            # last bar is 12 Nov 2026
    during = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)       # 11:30 IST, market open
    after = datetime(2026, 11, 12, 10, 30, tzinfo=timezone.utc)      # 16:00 IST, closed
    assert len(drop_unfinished_bar(bars, "IN", during)) == 2
    assert len(drop_unfinished_bar(bars, "IN", after)) == 3
    assert len(drop_unfinished_bar(bars, "US", after)) == 2          # the US session has not closed yet
    assert len(drop_unfinished_bar(bars, "US", datetime(2026, 11, 12, 21, 30, tzinfo=timezone.utc))) == 3
