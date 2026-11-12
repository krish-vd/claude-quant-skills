import math
import random
from datetime import date, timedelta

import pytest

from marketcore import pairs, rulestrategy, timing
from marketcore.backtest import Bars, Config, run


def bars(closes, volumes=None, symbol="IDX"):
    n = len(closes)
    c = [float(x) for x in closes]
    return Bars(symbol, [date(2025, 1, 1) + timedelta(days=i) for i in range(n)], c, c, c, c, list(volumes or [100.0] * n))


def test_distribution_days_count_and_expiry():
    closes = [100.0] * 30
    vols = [100.0] * 30
    closes[20], vols[20] = 99.7, 150.0           # -0.3% on higher volume: counts
    closes[22], vols[22] = closes[21] * 0.999, 200.0   # -0.1%: too small
    closes[24], vols[24] = 99.0, 90.0            # -0.7% but on lower volume: does not count
    d = timing.distribution_days(bars(closes, vols))
    assert d["count"] == 1 and d["days"][0]["change_pct"] == -0.3
    closes2 = closes[:] + [105.0]                # index later 5.3% above day 20's close: expired
    d2 = timing.distribution_days(bars(closes2, vols + [100.0]))
    assert d2["count"] == 0 and len(d2["expired_by_rally"]) == 1


def test_follow_through_day_found_on_day_four_or_later():
    closes = [100.0] * 10 + [100 - 2 * i for i in range(1, 6)] + [90.5, 90.8, 91.0, 92.5, 93.0]
    vols = [100.0] * 18 + [150.0, 100.0]
    # Low 90 at index 14; day 1 = index 15 (90.5); index 18 is day 4, +1.65% on higher volume
    s = timing.rally_status(bars(closes, vols), lookback=30)
    assert s["state"] == "follow_through" and s["follow_through_day_number"] == 4
    assert s["follow_through_gain_pct"] == pytest.approx(1.65, abs=0.01)


def test_rally_attempt_fails_below_the_low_and_no_correction():
    closes = [100.0] * 10 + [100 - 2 * i for i in range(1, 6)] + [91.0, 92.0, 89.5]
    assert timing.rally_status(bars(closes), lookback=30)["state"] in ("attempt_failed", "no_rally_attempt")
    assert timing.rally_status(bars([100 + i * 0.1 for i in range(60)]))["state"] == "no_correction"
    attempt = timing.rally_status(bars([100.0] * 10 + [100 - 2 * i for i in range(1, 6)] + [90.5, 90.6]), lookback=30)
    assert attempt["state"] == "rally_attempt" and attempt["day_number"] == 2


def test_top_checklist_levels():
    up = bars([100 * 1.002 ** i for i in range(300)])
    assert timing.top_checklist(up, 1, 70.0)["level"] == "low"
    down = bars([100 * 1.002 ** i for i in range(250)] + [165 * 0.99 ** i for i in range(50)])
    out = timing.top_checklist(down, 6, 25.0)
    assert out["level"] == "high" and out["warning_count"] >= 4


def test_ols_and_adf_on_known_cases():
    x = [float(i) for i in range(50)]
    beta, se, resid = pairs.ols([2 + 3 * v for v in x], [x])
    assert beta[0] == pytest.approx(2) and beta[1] == pytest.approx(3) and max(abs(r) for r in resid) < 1e-9
    rng = random.Random(7)
    walk, noise = [0.0], [rng.gauss(0, 1) for _ in range(600)]
    for e in noise[1:]:
        walk.append(walk[-1] + e)
    stationary = [rng.gauss(0, 1) for _ in range(600)]
    assert pairs.adf_statistic(stationary) < -10            # strongly rejects a unit root
    assert pairs.adf_statistic(walk) > -3.0                  # random walk: does not reject


def test_cointegrated_pair_is_detected_and_unrelated_is_not():
    rng = random.Random(11)
    common = [0.0]
    for _ in range(799):
        common.append(common[-1] + rng.gauss(0, 0.01))
    spread = [0.0]
    for _ in range(799):
        spread.append(0.8 * spread[-1] + rng.gauss(0, 0.005))   # half-life ln2 / -ln(0.8) = 3.1
    b = [100 * math.exp(v) for v in common]
    a = [50 * math.exp(1.5 * v + s) for v, s in zip(common, spread)]
    out = pairs.analyse_pair(a, b)
    assert out["cointegrated_at"] == "1%" and out["hedge_ratio"] == pytest.approx(1.5, abs=0.05)
    assert out["half_life_sessions"] == pytest.approx(3.1, abs=1.0)
    other = [0.0]
    for _ in range(799):
        other.append(other[-1] + rng.gauss(0, 0.01))
    assert pairs.analyse_pair(a, [100 * math.exp(v) for v in other])["cointegrated_at"] is None


def test_screen_pairs_orders_by_statistic():
    rng = random.Random(3)
    base = [0.0]
    for _ in range(399):
        base.append(base[-1] + rng.gauss(0, 0.01))
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(400)]
    series = {
        "A": (dates, [100 * math.exp(v + rng.gauss(0, 0.003)) for v in base]),
        "B": (dates, [80 * math.exp(v + rng.gauss(0, 0.003)) for v in base]),
        "C": (dates, [60 * math.exp(rng.gauss(0, 0.2) + 0.002 * i) for i in range(400)]),
    }
    rows = pairs.screen_pairs(series)
    assert (rows[0]["a"], rows[0]["b"]) == ("A", "B") and rows[0]["cointegrated_at"] is not None
    with pytest.raises(ValueError):
        pairs.screen_pairs({str(i): (dates, [1.0] * 400) for i in range(40)})


def test_rule_strategy_matches_built_in_sma_cross():
    from marketcore.backtest import sma_cross

    closes = [100 + 10 * math.sin(i / 15) + i * 0.05 for i in range(400)]
    b = bars(closes)
    spec = {"entry": [["sma:20", "crosses_above", "sma:50"]], "exit": [["sma:20", "crosses_below", "sma:50"]]}
    cfg = Config(initial_capital=10_000, alloc_pct=100, max_position_pct=100, slippage_bps=0)
    rule = run({"T": b}, rulestrategy.build(spec), {}, cfg)
    builtin = run({"T": b}, sma_cross, {"fast_n": 20, "slow_n": 50}, cfg)
    key = lambda t: (t.entry_date, t.exit_date, t.shares)
    assert rule.trades and [key(t) for t in rule.trades] == [key(t) for t in builtin.trades]


def test_rule_terms_do_not_look_ahead():
    b = bars([10, 11, 12, 13, 14, 15, 9, 20])
    hi = rulestrategy.term_series(b, "highest:3", {})
    assert hi[:3] == [None, None, None] and hi[3] == 12 and hi[7] == 15    # excludes today's bar
    assert rulestrategy.term_series(b, "close_pct_of_highest:3", {})[7] == pytest.approx(20 / 15)


def test_rule_validation():
    with pytest.raises(ValueError, match="entry"):
        rulestrategy.build({"exit": [["close", ">", 1]]})
    with pytest.raises(ValueError, match="never close"):
        rulestrategy.build({"entry": [["close", ">", 1]]})
    with pytest.raises(ValueError, match="unknown"):
        rulestrategy.build({"entry": [["magic:5", ">", 1]], "exit": [["close", "<", 1]]})(bars([1, 2, 3]), {})
    with pytest.raises(ValueError, match="operator"):
        rulestrategy.build({"entry": [["close", "==", 1]], "exit": [["close", "<", 1]]})(bars([1, 2, 3]), {})
