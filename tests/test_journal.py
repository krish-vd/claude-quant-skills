from datetime import date

import pytest

from marketcore import journal as j


def sample():
    trades = []
    # id 1: long 100 @ 500, stop 480 (risk 2,000), exit 540, fees 50 -> +3,950 (+1.975R)
    j.add_trade(trades, "infy", "long", date(2026, 11, 2), 500, 100, stop=480, setup="breakout")
    j.close_trade(trades, 1, date(2026, 11, 5), 540, fees=50, followed_plan=True)
    # id 2: long 50 @ 1000, stop 980 (risk 1,000), exit 980 -> -1,000 (-1R)
    j.add_trade(trades, "TCS", "long", date(2026, 11, 3), 1000, 50, stop=980, setup="breakout")
    j.close_trade(trades, 2, date(2026, 11, 6), 980, followed_plan=True)
    # id 3: short 2 lots NIFTY fut (multiplier 65) @ 25000, stop 25100 (risk 13,000), exit 25150 -> -19,500 (-1.5R)
    j.add_trade(trades, "NIFTY", "short", date(2026, 11, 9), 25000, 2, stop=25100, setup="reversal", multiplier=65)
    j.close_trade(trades, 3, date(2026, 11, 10), 25150, followed_plan=False)
    # id 4: open, risk 100 x 10 = 1,000
    j.add_trade(trades, "SBIN", "long", date(2026, 11, 11), 800, 100, stop=790)
    return trades


def test_pnl_and_r_multiples():
    t = sample()
    assert t[0]["pnl"] == 3950 and t[0]["r_multiple"] == pytest.approx(1.975)
    assert t[1]["pnl"] == -1000 and t[1]["r_multiple"] == pytest.approx(-1.0)
    assert t[2]["planned_risk"] == 13000 and t[2]["pnl"] == -19500 and t[2]["r_multiple"] == pytest.approx(-1.5)
    assert t[3]["status"] == "open" and t[0]["symbol"] == "INFY"


def test_validation():
    trades = []
    with pytest.raises(ValueError):
        j.add_trade(trades, "X", "long", date(2026, 1, 1), 100, 10, stop=105)     # stop on the wrong side
    with pytest.raises(ValueError):
        j.add_trade(trades, "X", "sideways", date(2026, 1, 1), 100, 10)
    j.add_trade(trades, "X", "long", date(2026, 1, 5), 100, 10)
    with pytest.raises(ValueError):
        j.close_trade(trades, 1, date(2026, 1, 1), 110)                           # exit before entry
    j.close_trade(trades, 1, date(2026, 1, 6), 110)
    with pytest.raises(ValueError):
        j.close_trade(trades, 1, date(2026, 1, 7), 120)                           # already closed
    assert trades[0]["r_multiple"] is None                                         # no stop, so no R


def test_review_by_hand():
    r = j.review(sample())
    assert r["trades"] == 3 and r["net_pnl"] == -16550
    assert r["win_rate_pct"] == pytest.approx(33.3)
    assert r["avg_win"] == 3950 and r["avg_loss"] == -10250
    assert r["profit_factor"] == pytest.approx(0.19)                 # 3,950 / 20,500
    assert r["avg_r"] == pytest.approx((1.975 - 1.0 - 1.5) / 3, abs=1e-3)
    assert r["longest_losing_streak"] == 2 and r["current_streak"] == -2
    assert r["max_drawdown_of_realised_pnl"] == 20500                # peak 3,950 -> -16,550
    assert r["by_setup"]["breakout"]["trades"] == 2 and r["by_setup"]["reversal"]["net_pnl"] == -19500
    assert r["by_plan_adherence"]["broke"]["net_pnl"] == -19500
    assert r["by_plan_adherence"]["followed"]["net_pnl"] == 2950
    assert r["worst_trade"]["symbol"] == "NIFTY"
    assert j.review(sample(), start=date(2026, 12, 1)) == {"trades": 0}
    assert j.review(sample(), end=date(2026, 11, 6))["trades"] == 2


def test_circuit_breaker():
    trades = sample()
    # Tuesday 10 Nov 2026, account 10,00,000: day -19,500 (limit -20,000), week (from Mon 9 Nov) -19,500
    cb = j.circuit_breaker(trades, 1_000_000, date(2026, 11, 10))
    checks = {c["check"]: c for c in cb["checks"]}
    assert checks["daily_loss"]["realised_pnl"] == -19500 and not checks["daily_loss"]["breached"]
    assert checks["daily_loss"]["used_pct_of_limit"] == 97.5
    assert checks["monthly_loss"]["realised_pnl"] == -16550
    assert checks["consecutive_losses"]["count"] == 2 and not checks["consecutive_losses"]["breached"]
    assert checks["open_risk"]["open_risk"] == 1000 and checks["open_risk"]["room_for_new_risk"] == 59000
    assert cb["new_risk_allowed"] is True

    small = j.circuit_breaker(trades, 500_000, date(2026, 11, 10))   # daily limit is now -10,000
    assert small["new_risk_allowed"] is False and "daily_loss" in small["breached"]
    strict = j.circuit_breaker(trades, 1_000_000, date(2026, 11, 12), max_consecutive_losses=2)
    assert strict["breached"] == ["consecutive_losses"]
    next_week = j.circuit_breaker(trades, 500_000, date(2026, 11, 16))
    assert {c["check"]: c for c in next_week["checks"]}["weekly_loss"]["realised_pnl"] == 0


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "journal.json"
    assert j.load(path) == []
    trades = sample()
    j.save(trades, path)
    assert j.load(path) == trades


def rule(result, name):
    return next(c for c in result["checks"] if c["rule"] == name)


def test_pretrade_check_approves_a_sound_plan():
    # Account 10,00,000. Buy 200 @ 500, stop 480 -> risk 4,000 (0.4%), value 1,00,000 (10%), target 550 -> 2.5R.
    out = j.pretrade_check([], 1_000_000, date(2026, 11, 12), "wipro", "long", 500, 480, 200, target=550)
    assert out["approved"] is True and out["failed_rules"] == [] and out["warnings"] == []
    assert out["planned_risk"] == 4000 and out["planned_risk_pct"] == 0.4 and out["position_value"] == 100000
    assert "2.50" in rule(out, "reward_to_risk")["detail"]


def test_pretrade_check_blocks_each_broken_rule():
    day = date(2026, 11, 12)
    no_stop = j.pretrade_check([], 1_000_000, day, "X", "long", 500, None, 100)
    assert no_stop["failed_rules"] == ["stop_defined"] and no_stop["planned_risk"] is None

    wrong_side = j.pretrade_check([], 1_000_000, day, "X", "short", 500, 480, 100)
    assert "stop_defined" in wrong_side["failed_rules"]

    too_much_risk = j.pretrade_check([], 1_000_000, day, "X", "long", 500, 400, 200, target=800)   # risk 20,000 = 2%
    assert too_much_risk["failed_rules"] == ["risk_per_trade"]

    too_big = j.pretrade_check([], 1_000_000, day, "X", "long", 500, 495, 600, target=520)         # value 3,00,000 = 30%
    assert too_big["failed_rules"] == ["position_size"]

    poor_reward = j.pretrade_check([], 1_000_000, day, "X", "long", 500, 480, 100, target=520)     # 1R
    assert poor_reward["failed_rules"] == ["reward_to_risk"]


def test_pretrade_check_uses_the_journal():
    trades = sample()                                  # one open SBIN trade (risk 1,000), last two closed trades lost
    day = date(2026, 11, 12)
    out = j.pretrade_check(trades, 1_000_000, day, "SBIN", "long", 800, 790, 100, target=830)
    assert out["approved"] is True and out["warnings"] == ["not_already_open"]

    blocked = j.pretrade_check(trades, 1_000_000, day, "ITC", "long", 400, 396, 100, target=412, max_consecutive_losses=2)
    assert blocked["approved"] is False and blocked["failed_rules"] == ["circuit_breaker"]

    # Open-risk cap 0.5% of 10,00,000 = 5,000; 1,000 is used, so a 4,500 trade does not fit.
    no_room = j.pretrade_check(trades, 1_000_000, day, "ITC", "long", 400, 391, 500, target=430, max_open_risk_pct=0.5)
    assert no_room["failed_rules"] == ["open_risk_room"]


def test_pretrade_check_futures_use_multiplier_and_skip_the_size_cap():
    # 1 lot NIFTY (65) long at 25,000, stop 24,900 -> risk 6,500; notional 16,25,000 is above the account.
    out = j.pretrade_check([], 1_000_000, date(2026, 11, 12), "NIFTY", "long", 25000, 24900, 1, target=25300,
                           multiplier=65, leveraged=True)
    assert out["planned_risk"] == 6500 and out["approved"] is True
    assert rule(out, "position_size")["status"] == "warn"
