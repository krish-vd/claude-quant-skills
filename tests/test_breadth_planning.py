from datetime import date, timedelta

import pytest

from marketcore.backtest import Bars
from marketcore.breadth import index_trend, level_percentile, measure
from marketcore.planning import (
    drawdown_and_volatility,
    inflation_adjusted,
    required_sip,
    rolling_returns,
    sip_backtest,
    sip_projection,
    trailing_returns,
)
from marketcore.tax_india import add_months


def bars(closes, symbol):
    n = len(closes)
    c = [float(x) for x in closes]
    return Bars(symbol, [date(2025, 1, 1) + timedelta(days=i) for i in range(n)], c, c, c, c, [1.0] * n)


def test_breadth_counts_by_hand():
    up = bars([100 * 1.002 ** i for i in range(300)], "UP")          # above all averages, new high, advancing
    down = bars([300 * 0.998 ** i for i in range(300)], "DOWN")      # below all averages, new low, declining
    flat = bars([50.0] * 300, "FLAT")                                # equal to its averages: not above
    out = measure({"UP": up, "DOWN": down, "FLAT": flat}, history_days=5)
    assert out["stocks_measured"] == 3
    assert out["pct_above_sma50"] == pytest.approx(33.3) and out["pct_above_sma200"] == pytest.approx(33.3)
    assert (out["advances"], out["declines"], out["unchanged"]) == (1, 1, 1)
    assert (out["new_52w_highs"], out["new_52w_lows"], out["net_new_highs"]) == (1, 1, 0)
    assert out["posture"] == "broad_downtrend"                        # 33% above the 200-day
    assert len(out["history"]) == 5 and out["history"][-1]["pct_above_sma50"] == pytest.approx(33.3)


def test_breadth_posture_and_stale_symbols():
    ups = {f"U{k}": bars([100 * 1.002 ** i for i in range(300)], f"U{k}") for k in range(9)}
    one_down = bars([300 * 0.998 ** i for i in range(300)], "D")
    out = measure({**ups, "D": one_down})
    assert out["posture"] == "broad_uptrend" and out["flags"] == ["stretched"]   # 90% above the 50-day
    stale = bars([10.0] * 200, "OLD")                                 # stopped trading 100 days earlier
    out = measure({**ups, "OLD": stale})
    assert out["excluded_stale_symbols"] == ["OLD"] and out["stocks_measured"] == 9
    with pytest.raises(ValueError):
        measure({})


def test_index_trend_and_percentile():
    b = bars([100 * 1.001 ** i for i in range(300)], "IDX")
    t = index_trend(b)
    assert t["above_sma50"] and t["above_sma200"] and t["sma50_above_sma200"] and t["pct_from_52w_high"] == 0.0
    v = level_percentile(bars(list(range(1, 253)), "VIX"))
    assert v["level"] == 252 and v["percentile_in_window"] == pytest.approx(251 / 252 * 100, abs=0.1)


def test_sip_future_value_by_hand():
    # 10,000 a month at 12% (1% a month), invested at the start of each month, 1 year:
    # 10,000 x ((1.01^12 - 1) / 0.01) x 1.01 = 10,000 x 12.682503 x 1.01 = 1,28,093.28
    out = sip_projection(10_000, 0.12, 1)
    assert out["future_value"] == pytest.approx(128_093.28, abs=0.01)
    assert out["total_invested"] == 120_000 and out["gain"] == pytest.approx(8_093.28, abs=0.01)


def test_sip_step_up_and_lumpsum():
    # Year 1 at 1,000 -> 12,809.328, which grows x 1.12682503 -> 14,433.871.
    # Year 2 at 1,100 -> 14,090.261. Total 28,524.13.
    out = sip_projection(1_000, 0.12, 2, step_up_pct=10)
    assert out["future_value"] == pytest.approx(28_524.13, abs=0.01)
    assert out["yearly"][1]["monthly_instalment"] == 1100
    assert sip_projection(0, 0.12, 1, initial_lumpsum=100_000)["future_value"] == pytest.approx(112_682.50, abs=0.01)
    assert sip_projection(0, 0.12, 1, initial_lumpsum=100_000, effective=True)["future_value"] == pytest.approx(112_000, abs=0.01)


def test_required_sip_inverts_the_projection():
    need = required_sip(128_093.28, 0.12, 1)
    assert need["required_monthly_sip"] == pytest.approx(10_000, abs=0.01)
    stepped = required_sip(5_000_000, 0.11, 15, step_up_pct=8, initial_lumpsum=200_000)
    check = sip_projection(stepped["required_monthly_sip"], 0.11, 15, step_up_pct=8, initial_lumpsum=200_000)
    assert check["future_value"] == pytest.approx(5_000_000, abs=5)
    assert required_sip(100, 0.12, 1, initial_lumpsum=1_000)["already_met_by_lumpsum"] is True
    assert inflation_adjusted(200.0, 0.06, 12) == pytest.approx(200 / 1.06 ** 12)


def monthly_series(months, growth=1.01):
    dates = [add_months(date(2015, 1, 1), m) for m in range(months + 1)]
    return dates, [100.0 * growth ** m for m in range(months + 1)]


def test_trailing_and_rolling_returns_on_steady_growth():
    dates, values = monthly_series(84)                    # 7 years at 1% a month = 12.6825% a year
    t = trailing_returns(dates, values)
    assert t["1m"] == pytest.approx(1.0, abs=0.01) and t["1y"] == pytest.approx(12.68, abs=0.01)
    assert t["3y"] == pytest.approx(12.68, abs=0.01) and t["5y"] == pytest.approx(12.68, abs=0.01)
    assert t["10y"] is None                               # not enough history
    r = rolling_returns(dates, values, 3)
    assert r["windows"] == 49 and r["min_pct"] == pytest.approx(12.68, abs=0.01) == pytest.approx(r["max_pct"], abs=0.01)
    assert r["negative_windows_pct"] == 0.0
    assert rolling_returns(dates, values, 10) is None


def test_drawdown_and_sip_backtest():
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(5)]
    dd = drawdown_and_volatility(dates, [100, 120, 90, 108, 130])
    assert dd["max_drawdown_pct"] == 25.0
    assert dd["drawdown_peak_date"] == "2025-01-02" and dd["drawdown_trough_date"] == "2025-01-03"

    dates, values = monthly_series(36)
    sip = sip_backtest(dates, values, 1_000)
    assert sip["instalments"] == 36 and sip["invested"] == 36_000
    assert sip["xirr_pct"] == pytest.approx(12.68, abs=0.05)   # a SIP into steady 1%-a-month growth earns that rate
