"""Expected values are computed by hand from the cited circulars, not by the code under test."""
from datetime import date
from decimal import Decimal as D

import pytest

from marketcore import rules
from marketcore.charges import (
    Brokerage,
    india_leg,
    india_option_exercise_stt,
    india_round_trip,
    us_equity_leg,
)

NOV = date(2026, 11, 12)


def test_nse_delivery_buy_and_sell_after_march_2026():
    # 100 shares at Rs 1,000 = Rs 1,00,000 turnover, zero brokerage
    buy = india_leg("equity_delivery", "buy", 1000, 100, NOV)
    assert buy.amount("stt") == D("100")                 # 0.1%
    assert buy.amount("exchange_txn") == D("3.0699")     # Rs 306.99 per crore
    assert buy.amount("ipft") == D("0.0001")             # Rs 0.01 per crore
    assert buy.amount("sebi_fee") == D("0.1")            # Rs 10 per crore
    assert buy.amount("stamp_duty") == D("15")           # 0.015%, buy only
    assert buy.amount("gst") == D("0.5706")              # 18% of 3.0699 + 0.0001 + 0.1
    assert buy.total == D("118.7406")

    sell = india_leg("equity_delivery", "sell", 1000, 100, NOV)
    assert sell.amount("stamp_duty") == 0
    assert sell.total == D("103.7406")


def test_futures_stt_changes_on_1_april_2026():
    before = india_leg("futures", "sell", 1000, 1000, date(2026, 3, 31))
    after = india_leg("futures", "sell", 1000, 1000, date(2026, 4, 1))
    assert before.amount("stt") == D("200")   # 0.02% of Rs 10,00,000
    assert after.amount("stt") == D("500")    # 0.05%
    assert india_leg("futures", "buy", 1000, 1000, date(2026, 4, 1)).amount("stt") == 0


def test_nse_transaction_charge_changes_on_1_march_2026():
    before = india_leg("futures", "buy", 1000, 1000, date(2026, 2, 28))
    after = india_leg("futures", "buy", 1000, 1000, date(2026, 3, 1))
    assert (before.amount("exchange_txn"), before.amount("ipft")) == (D("17.3"), D("1"))
    assert (after.amount("exchange_txn"), after.amount("ipft")) == (D("18.299"), D("0.001"))
    # The circular says the member's total outflow is unchanged: Rs 183 per crore
    assert before.amount("exchange_txn") + before.amount("ipft") == after.amount("exchange_txn") + after.amount("ipft")


def test_option_sell_with_flat_brokerage():
    # premium 100 x 650 units = Rs 65,000 premium turnover
    leg = india_leg("options", "sell", 100, 650, NOV, brokerage=Brokerage(flat=20))
    assert leg.amount("stt") == D("97.5")                  # 0.15% of premium
    assert leg.amount("exchange_txn") == D("23.094435")    # Rs 3,552.99 per crore
    assert leg.amount("gst") == D("7.76871")               # 18% of 20 + 23.094435 + 0.000065 + 0.065
    buy = india_leg("options", "buy", 100, 650, NOV)
    assert buy.amount("stt") == 0
    assert buy.amount("stamp_duty") == D("1.95")           # 0.003% of premium


def test_option_stt_before_april_2026():
    assert india_leg("options", "sell", 100, 650, date(2026, 3, 31)).amount("stt") == D("65")  # 0.10%


def test_exercise_stt():
    assert india_option_exercise_stt(10000, NOV).amount == D("15")                 # 0.15%
    assert india_option_exercise_stt(10000, date(2026, 3, 31)).amount == D("12.5")  # 0.125%


def test_intraday_and_etf_stt():
    assert india_leg("equity_intraday", "sell", 1000, 100, NOV).amount("stt") == D("25")
    assert india_leg("equity_intraday", "buy", 1000, 100, NOV).amount("stt") == 0
    assert india_leg("equity_intraday", "buy", 1000, 100, NOV).amount("stamp_duty") == D("3")
    assert india_leg("etf_delivery", "sell", 1000, 100, NOV).amount("stt") == D("1")
    assert india_leg("etf_delivery", "buy", 1000, 100, NOV).amount("stt") == 0


def test_brokerage_pct_with_cap_and_gst():
    low = india_leg("equity_intraday", "buy", 100, 100, NOV, brokerage=Brokerage(pct="0.0003", cap=20))
    assert low.amount("brokerage") == D("3")       # 0.03% of 10,000
    high = india_leg("equity_intraday", "buy", 1000, 1000, NOV, brokerage=Brokerage(pct="0.0003", cap=20))
    assert high.amount("brokerage") == D("20")     # capped


def test_mcx_gold_future_and_agri():
    # 1 lot GOLD = multiplier 100 at Rs 1,25,000 per 10 g -> Rs 1,25,00,000
    sell = india_leg("commodity_futures", "sell", 125000, 100, NOV)
    assert sell.amount("ctt") == D("1250")
    assert sell.amount("exchange_txn") == D("262.5")
    assert sell.amount("sebi_fee") == D("12.5")
    buy = india_leg("commodity_futures", "buy", 125000, 100, NOV)
    assert buy.amount("ctt") == 0
    assert buy.amount("stamp_duty") == D("250")
    agri = india_leg("commodity_futures", "sell", 125000, 100, NOV, agri=True)
    assert agri.amount("ctt") == 0
    assert agri.amount("sebi_fee") == D("1.25")
    assert any("secondary" in w for w in sell.warnings)


def test_dates_and_exchanges_outside_coverage_are_refused():
    with pytest.raises(rules.RuleNotCovered):
        india_leg("equity_delivery", "buy", 1000, 100, date(2024, 9, 30))
    with pytest.raises(rules.RuleNotCovered):
        india_leg("futures", "buy", 1000, 100, NOV, exchange="BSE")
    with pytest.raises(rules.RuleNotCovered):
        india_leg("equity_delivery", "buy", 1000, 100, date(2026, 1, 5), exchange="BSE")


def test_round_trip_breakeven():
    trip = india_round_trip("equity_delivery", 1000, 1010, 100, NOV, dp_charge="15.34")
    assert trip.gross_pnl == D("1000")
    # buy 118.7406; sell: stt 101, txn 3.100599, ipft 0.000101, sebi 0.101, gst 0.5763060, dp 15.34
    assert trip.sell.total == D("101") + D("3.100599") + D("0.000101") + D("0.101") + D("0.576306") + D("15.34")
    assert trip.total_cost == trip.buy.total + trip.sell.total
    assert trip.breakeven_move_per_unit == trip.total_cost / 100


def test_dp_charge_only_on_delivery_sell():
    with pytest.raises(ValueError):
        india_leg("equity_delivery", "buy", 1000, 100, NOV, dp_charge=15)


def test_us_sell_fees():
    leg = us_equity_leg("sell", 200, 100, date(2026, 6, 1))
    assert leg.amount("sec_fee") == D("0.42")     # 20,000 x 20.60 / 1e6 = 0.412, rounded up
    assert leg.amount("finra_taf") == D("0.02")   # 100 x 0.000195 = 0.0195, rounded up
    assert us_equity_leg("buy", 200, 100, date(2026, 6, 1)).total == 0


def test_us_taf_cap_and_sec_zero_period():
    big = us_equity_leg("sell", 10, 100000, date(2026, 6, 1))
    assert big.amount("finra_taf") == D("9.79")
    early = us_equity_leg("sell", 200, 100, date(2026, 4, 3))
    assert early.amount("sec_fee") == 0
    assert us_equity_leg("sell", 200, 100, date(2026, 4, 4)).amount("sec_fee") == D("0.42")


def test_us_taf_pause_is_flagged_unconfirmed():
    leg = us_equity_leg("sell", 200, 100, NOV)
    assert leg.amount("finra_taf") == 0
    assert any("unconfirmed" in w for w in leg.warnings)


def test_every_rule_has_a_source_and_valid_dates():
    for book in ("in_charges", "us_charges"):
        data = rules.load(book)
        for rule in data["rules"]:
            assert rule["source"] in data["sources"], rule["id"]
            previous_end = None
            for v in rule["versions"]:
                start = date.fromisoformat(v["from"])
                if previous_end is not None:
                    assert (start - previous_end).days == 1, f"{rule['id']}: gap or overlap in versions"
                previous_end = date.fromisoformat(v["to"]) if v["to"] else None
            assert rule["versions"][-1]["to"] is None, rule["id"]
