from marketcore.breadth import posture_checklist
from marketcore.robustness import review_report


def report(**overrides):
    base = {
        "strategy": "donchian_breakout",
        "parameters": "defaults",
        "metrics": {"closed_trades": 250, "years": 10, "cagr_pct": 15.0, "max_drawdown_pct": 25.0, "profit_factor": 1.6, "win_rate_pct": 42.0},
        "benchmark_buy_and_hold": {"cagr_pct": 12.0, "max_drawdown_pct": 38.0},
        "out_of_sample": {"in_sample": {"cagr_pct": 16.0}, "out_of_sample": {"cagr_pct": 13.0}},
        "point_in_time_universe": {"missing_price_history": ["DHFL"]},
        "parameter_sweep": {"profitable_share_pct": 90.0, "cagr_best_pct": 17.0, "cagr_median_pct": 13.0},
        "cautions": [],
    }
    base.update(overrides)
    return base


def checks(result, severity):
    return [f["check"] for f in result["findings"] if f["severity"] == severity]


def test_clean_report_has_no_red_flags():
    out = review_report(report())
    assert out["verdict"] == "no red flags on these checks" and out["high"] == 0 and out["medium"] == 0
    assert set(checks(out, "info")) == {"out_of_sample", "survivorship_bias"}


def test_survivorship_on_index_is_high_for_momentum_and_medium_otherwise():
    biased = dict(point_in_time_universe=None, cautions=["Survivorship bias: nifty100 is today's member list."])
    assert "survivorship_bias" in checks(review_report(report(strategy="momentum_rotation", **biased)), "high")
    out = review_report(report(**biased))
    assert "survivorship_bias" in checks(out, "medium") and out["verdict"] == "no red flags on these checks"   # one medium only
    hand_picked = review_report(report(point_in_time_universe=None))
    assert "survivorship_bias" in checks(hand_picked, "medium")


def test_out_of_sample_collapse_and_missing():
    halved = review_report(report(out_of_sample={"in_sample": {"cagr_pct": 40.5}, "out_of_sample": {"cagr_pct": 12.4}}))
    assert halved["verdict"] == "do not rely on this result" and "out_of_sample" in checks(halved, "high")
    lost = review_report(report(out_of_sample={"in_sample": {"cagr_pct": 20.0}, "out_of_sample": {"cagr_pct": -3.0}}))
    assert "did not survive" in lost["findings"][0]["detail"]
    assert "out_of_sample" in checks(review_report(report(out_of_sample=None)), "medium")


def test_benchmark_comparisons():
    both = review_report(report(metrics={"closed_trades": 250, "years": 10, "cagr_pct": 8.9, "max_drawdown_pct": 39.0}))
    assert "benchmark" in checks(both, "high")
    lower_return = review_report(report(metrics={"closed_trades": 250, "years": 10, "cagr_pct": 8.9, "max_drawdown_pct": 20.0}))
    assert "benchmark" in checks(lower_return, "medium")
    assert "benchmark" in checks(review_report(report(benchmark_buy_and_hold=None)), "medium")


def test_sample_size_drawdown_and_too_good():
    assert "sample_size" in checks(review_report(report(metrics={"closed_trades": 12, "years": 10, "cagr_pct": 30.0, "max_drawdown_pct": 10.0})), "high")
    deep = review_report(report(metrics={"closed_trades": 250, "years": 10, "cagr_pct": 15.0, "max_drawdown_pct": 65.0}))
    assert "drawdown" in checks(deep, "high")
    lucky = review_report(report(metrics={"closed_trades": 250, "years": 10, "cagr_pct": 15.0, "max_drawdown_pct": 10.0,
                                          "profit_factor": 6.0, "win_rate_pct": 85.0}))
    assert "too_good" in checks(lucky, "medium")


def test_parameter_sensitivity_and_weak_evidence_verdict():
    fragile = review_report(report(parameter_sweep={"profitable_share_pct": 40.0, "cagr_best_pct": 30.0, "cagr_median_pct": 5.0}))
    assert checks(fragile, "medium").count("parameter_sensitivity") == 2 and fragile["verdict"] == "weak evidence"
    untested = review_report(report(parameter_sweep=None, parameters={"entry_n": 37.0}))
    assert "parameter_sensitivity" in checks(untested, "medium")


def test_posture_checklist_labels():
    index_up = {"symbol": "^NSEI", "close": 25000, "above_sma200": True, "sma50_above_sma200": True}
    strong = {"pct_above_sma200": 65.0, "pct_above_sma50": 70.0, "pct_above_sma50_20_sessions_ago": 55.0,
              "net_new_highs": 20, "new_52w_highs": 25, "new_52w_lows": 5}
    out = posture_checklist(strong, index_up, {"symbol": "^INDIAVIX", "level": 12, "percentile_in_window": 30.0}, 40.0, 30.0)
    assert out["label"] == "constructive" and out["supportive"] == 7 and out["cautions"] == 0 and out["items_checked"] == 7

    index_down = {"symbol": "^NSEI", "close": 20000, "above_sma200": False, "sma50_above_sma200": False}
    weak = {"pct_above_sma200": 30.0, "pct_above_sma50": 25.0, "pct_above_sma50_20_sessions_ago": 45.0,
            "net_new_highs": -40, "new_52w_highs": 2, "new_52w_lows": 42}
    out = posture_checklist(weak, index_down, {"symbol": "^INDIAVIX", "level": 28, "percentile_in_window": 95.0})
    assert out["label"] == "defensive" and out["cautions"] == 6 and out["items_checked"] == 6     # FII item skipped

    middling = {"pct_above_sma200": 45.0, "pct_above_sma50": 50.0, "pct_above_sma50_20_sessions_ago": 50.0, "net_new_highs": 0,
                "new_52w_highs": 3, "new_52w_lows": 3}
    out = posture_checklist(middling, index_up, {"symbol": "^VIX", "level": 18, "percentile_in_window": 65.0})
    assert out["label"] == "mixed" and out["neutral"] == 4 and out["supportive"] == 2
