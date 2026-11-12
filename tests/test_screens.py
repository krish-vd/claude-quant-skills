from datetime import date, timedelta

import pytest

from marketcore.backtest import Bars
from marketcore.screens import analyse, percentile_ranks, rs_raw, screen


def bars_from(closes, volumes=None, symbol="T"):
    n = len(closes)
    volumes = volumes or [1000.0] * n
    return Bars(symbol, [date(2024, 1, 1) + timedelta(days=i) for i in range(n)],
                list(closes), list(closes), list(closes), list(closes), list(volumes))


def test_rs_raw_by_hand():
    closes = [100.0] * 253
    closes[-1] = 150.0          # every lookback sees +50%
    assert rs_raw(bars_from(closes)) == pytest.approx(0.5)
    closes[-64] = 120.0         # 3-month return becomes 25%; the others stay 50%
    assert rs_raw(bars_from(closes)) == pytest.approx(0.4 * 0.25 + 0.6 * 0.5)
    assert rs_raw(bars_from([100.0] * 252)) is None


def test_percentile_ranks():
    ranks = percentile_ranks({"A": 0.5, "B": 0.1, "C": 0.3, "D": None})
    assert ranks == {"A": 99, "B": 1, "C": 50, "D": None}
    assert percentile_ranks({"A": 0.2}) == {"A": 50}


def test_steady_uptrend_passes_trend_template():
    closes = [100.0 * 1.003 ** i for i in range(300)]
    row = analyse(bars_from(closes), rs_rank=90)
    assert row["trend_template"] is True and row["trend_template_passed"] == 8
    assert row["pct_below_52w_high"] == 0.0
    assert analyse(bars_from(closes), rs_rank=60)["trend_template"] is False   # fails only on RS rank


def test_downtrend_fails_and_short_history_is_skipped():
    closes = [300.0 * 0.997 ** i for i in range(300)]
    row = analyse(bars_from(closes), rs_rank=10)
    assert row["trend_template"] is False and row["trend_template_passed"] == 0
    assert analyse(bars_from([100.0] * 100)) is None


def test_breakout_needs_new_high_and_volume():
    closes = [100.0] * 299 + [101.0]
    quiet = analyse(bars_from(closes))
    assert quiet["new_52w_closing_high"] is True and quiet["breakout"] is False   # volume ratio 1.0
    loud = analyse(bars_from(closes, volumes=[1000.0] * 299 + [1500.0]))
    assert loud["breakout"] is True and loud["volume_ratio_vs_50d"] == 1.5


def test_screen_ranks_within_universe():
    up = bars_from([100.0 * 1.003 ** i for i in range(300)], symbol="UP")
    flat = bars_from([100.0] * 300, symbol="FLAT")
    down = bars_from([300.0 * 0.997 ** i for i in range(300)], symbol="DOWN")
    rows = {r["symbol"]: r for r in screen({"UP": up, "FLAT": flat, "DOWN": down})}
    assert (rows["UP"]["rs_rank"], rows["FLAT"]["rs_rank"], rows["DOWN"]["rs_rank"]) == (99, 50, 1)
    assert rows["UP"]["trend_template"] is True
