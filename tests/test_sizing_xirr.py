from datetime import date
from decimal import Decimal as D

import pytest

from marketcore import rules
from marketcore.sizing import size_cash, size_futures, size_long_option
from marketcore.xirr import XirrError, xirr


def test_cash_long_basic():
    r = size_cash(1_000_000, 1, 500, 480)
    assert r.direction == "long"
    assert r.units == D("500")               # 10,000 risk / 20 per share
    assert r.planned_loss == D("10000")
    assert r.position_value == D("250000")
    assert r.binding_constraint == "risk"


def test_cash_rounds_down_never_over_budget():
    r = size_cash(100_000, 1, 155, 148.5)    # 1,000 / 6.5 = 153.8
    assert r.units == D("153")
    assert r.planned_loss <= r.risk_budget


def test_cash_position_cap_and_short():
    capped = size_cash(1_000_000, 1, 500, 480, max_position_pct=20)
    assert capped.units == D("400")
    assert capped.binding_constraint == "max_position_pct"
    short = size_cash(1_000_000, 1, 500, 520)
    assert short.direction == "short" and short.units == D("500")


def test_cash_costs_and_fractional():
    with_cost = size_cash(1_000_000, 1, 500, 480, cost_per_share=5)
    assert with_cost.units == D("400")       # 10,000 / 25
    frac = size_cash(1000, 1, 155, 148.5, fractional_step="0.0001")
    assert frac.units == D("1.5384")


def test_cash_cannot_exceed_account_when_long():
    r = size_cash(10_000, 2, 100, 99.9)      # risk allows 2,000 shares; cash buys 100
    assert r.units == D("100") and r.binding_constraint == "account_cash"


def test_cash_validation():
    with pytest.raises(ValueError):
        size_cash(100_000, 1, 100, 100)
    with pytest.raises(ValueError):
        size_cash(100_000, 0, 100, 90)


def test_futures_nifty_lot():
    r = size_futures(1_000_000, 1, 25000, 24900, multiplier=65)   # 6,500 per lot
    assert r.units == D("1") and r.quantity == D("65")
    assert r.planned_loss == D("6500")
    none = size_futures(500_000, 1, 25000, 24900, multiplier=65)  # budget 5,000 < 6,500
    assert none.units == 0 and any("no position" in n for n in none.notes)


def test_futures_margin_binds():
    r = size_futures(1_000_000, 5, 25000, 24900, multiplier=65, margin_per_contract=250_000)
    assert r.units == D("4") and r.binding_constraint == "margin"   # risk allows 7


def test_long_option():
    r = size_long_option(1_000_000, 1, 120, 65)                    # 7,800 per lot
    assert r.units == D("1")
    r2 = size_long_option(1_000_000, 1, 120, 65, stop_premium=60)  # 3,900 per lot
    assert r2.units == D("2")
    with pytest.raises(ValueError):
        size_long_option(1_000_000, 1, 120, 65, stop_premium=120)


def test_contract_table_lookup():
    gold = rules.contract("gold")
    assert gold["multiplier"] == "100" and gold["currency"] == "INR"
    assert rules.contract("GC")["multiplier"] == "100"
    assert rules.contract("CL")["multiplier"] == "1000"
    with pytest.raises(rules.RuleNotCovered):
        rules.contract("NOPE")


def test_xirr_matches_spreadsheet_reference():
    # The worked example in Microsoft's XIRR documentation: result 0.373362535
    flows = [
        (date(2008, 1, 1), -10000),
        (date(2008, 3, 1), 2750),
        (date(2008, 10, 30), 4250),
        (date(2009, 2, 15), 3250),
        (date(2009, 4, 1), 2750),
    ]
    assert xirr(flows) == pytest.approx(0.373362535, abs=1e-8)


def test_xirr_simple_cases():
    assert xirr([(date(2025, 1, 1), -100), (date(2026, 1, 1), 110)]) == pytest.approx(0.10, abs=1e-9)
    assert xirr([(date(2025, 1, 1), -100), (date(2026, 1, 1), 90)]) == pytest.approx(-0.10, abs=1e-9)


def test_xirr_rejects_bad_input():
    with pytest.raises(XirrError):
        xirr([(date(2025, 1, 1), -100), (date(2026, 1, 1), -10)])
    with pytest.raises(XirrError):
        xirr([(date(2025, 1, 1), -100)])
