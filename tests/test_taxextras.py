from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from marketcore.tax_india import Trade, realised_gains
from marketcore.taxextras import advance_tax_schedule, fno_income, schedule_fa_rows


def test_fno_income_two_turnover_readings():
    trades = [
        {"kind": "future", "pnl": 50000, "charges": 1200},
        {"kind": "future", "pnl": -30000, "charges": 900},
        {"kind": "option", "pnl": 20000, "charges": 400, "sale_value": 150000},   # written or sold option
        {"kind": "option", "pnl": -45000, "charges": 500, "sale_value": 60000},
    ]
    out = fno_income(trades)
    assert out["net_profit_before_charges"] == "-5000" and out["charges"] == "3000" and out["net_profit_after_charges"] == "-8000"
    assert out["futures_turnover"] == "80000" and out["options_absolute_pnl"] == "65000"
    assert out["turnover_absolute_method"]["turnover"] == "145000"                 # 50,000 + 30,000 + 20,000 + 45,000
    assert out["turnover_absolute_plus_option_premium"]["turnover"] == "355000"    # + 1,50,000 + 60,000
    assert out["methods_agree"] is False
    assert fno_income([{"kind": "future", "pnl": 10}])["methods_agree"] is True
    with pytest.raises(ValueError):
        fno_income([{"kind": "swap", "pnl": 1}])


def test_fno_audit_flags():
    big = fno_income([{"kind": "future", "pnl": 12_000_000}])
    assert big["turnover_absolute_method"]["above_1_crore"] is True and big["turnover_absolute_method"]["above_10_crore"] is False


def lots_for(trades):
    return realised_gains(trades)[0]


def test_advance_tax_follows_when_gains_arise():
    # FY 2026-27. A short-term gain of 1,00,000 on 10 May (tax 20,000 + 4% cess = 20,800)
    # and another of 2,00,000 on 10 Oct (tax 40,000 + cess = 41,600). Total 62,400.
    trades = [
        Trade(date(2026, 4, 10), "A", "buy", 1000, 100), Trade(date(2026, 5, 10), "A", "sell", 1000, 200),
        Trade(date(2026, 9, 20), "B", "buy", 1000, 100), Trade(date(2026, 10, 10), "B", "sell", 1000, 300),
    ]
    out = advance_tax_schedule(lots_for(trades), "2026-27")
    assert out["special_rate_tax_for_the_year"] == "62400.00" and out["advance_tax_applies"] is True
    due = {r["due_date"]: r for r in out["instalments"]}
    assert due["2026-06-15"]["cumulative_amount_due"] == "3120"      # 15% of 20,800
    assert due["2026-09-15"]["cumulative_amount_due"] == "9360"      # 45% of 20,800: the October gain has not arisen
    assert due["2026-12-15"]["cumulative_amount_due"] == "46800"     # 75% of 62,400
    assert due["2027-03-15"]["cumulative_amount_due"] == "62400"
    assert out["tax_on_gains_after_15_march_due_by_31_march"] == "0.00"


def test_advance_tax_gain_after_15_march_and_payments():
    trades = [
        Trade(date(2026, 4, 10), "A", "buy", 1000, 100), Trade(date(2026, 5, 10), "A", "sell", 1000, 200),
        Trade(date(2027, 3, 1), "C", "buy", 1000, 100), Trade(date(2027, 3, 20), "C", "sell", 1000, 150),   # 50,000 gain after 15 Mar
    ]
    out = advance_tax_schedule(lots_for(trades), "2026-27", paid={date(2026, 6, 15): 3120, date(2026, 9, 15): 5000})
    due = {r["due_date"]: r for r in out["instalments"]}
    assert due["2027-03-15"]["cumulative_amount_due"] == "20800"     # only the May gain
    assert out["tax_on_gains_after_15_march_due_by_31_march"] == "10400.00"
    assert due["2026-09-15"]["cumulative_paid"] == "8120" and due["2026-09-15"]["shortfall"] == "1240"
    assert due["2026-06-15"]["shortfall"] == "0"


def test_advance_tax_below_threshold_and_other_years():
    trades = [Trade(date(2026, 4, 10), "A", "buy", 100, 100), Trade(date(2026, 5, 10), "A", "sell", 100, 200)]   # tax 2,080
    out = advance_tax_schedule(lots_for(trades), "2026-27")
    assert out["advance_tax_applies"] is False
    assert advance_tax_schedule(lots_for(trades), "2027-28")["special_rate_tax_for_the_year"] == "0.00"


def test_schedule_fa_by_hand():
    # Bought 10 AAPL at 150 on 15 Mar 2024; bought 5 more at 200 on 10 Feb 2025; sold 4 at 250 on 1 Sep 2025.
    trades = [
        {"symbol": "aapl", "date": date(2024, 3, 15), "side": "buy", "quantity": 10, "price": 150},
        {"symbol": "AAPL", "date": date(2025, 2, 10), "side": "buy", "quantity": 5, "price": 200},
        {"symbol": "AAPL", "date": date(2025, 9, 1), "side": "sell", "quantity": 4, "price": 250},
        {"symbol": "OLD", "date": date(2023, 1, 5), "side": "buy", "quantity": 3, "price": 10},
        {"symbol": "OLD", "date": date(2024, 6, 5), "side": "sell", "quantity": 3, "price": 12},   # gone before 2025
    ]
    days = [date(2025, 1, 2), date(2025, 7, 15), date(2025, 12, 31)]
    prices = {"AAPL": (days, [180.0, 260.0, 240.0])}
    out = schedule_fa_rows(trades, prices, 2025, rates={date(2025, 7, 15): 86.0, date(2025, 12, 31): 88.0})
    assert [r["symbol"] for r in out["rows"]] == ["AAPL"]                     # OLD was not held in 2025
    row = out["rows"][0]
    assert row["date_of_first_acquisition"] == "2024-03-15" and row["shares_at_year_end"] == 11
    assert row["initial_value_foreign"] == 2500.0                             # 10 x 150 + 5 x 200
    assert (row["peak_value_foreign"], row["peak_date"]) == (3900.0, "2025-07-15")   # 15 shares x 260
    assert row["peak_value_inr"] == 335400.0                                  # x 86
    assert row["closing_value_foreign"] == 2640.0 and row["closing_value_inr"] == 232320.0   # 11 x 240 x 88
    assert row["sale_proceeds_foreign"] == 1000.0
    assert out["rates_needed"] == ["2024-03-15", "2025-02-10"]                # purchase dates without a supplied rate
    assert row["purchase_lots"][0]["cost_inr"] is None


def test_schedule_fa_fully_sold_holding_has_zero_closing_value():
    trades = [{"symbol": "X", "date": date(2024, 5, 1), "side": "buy", "quantity": 2, "price": 100},
              {"symbol": "X", "date": date(2025, 3, 3), "side": "sell", "quantity": 2, "price": 130}]
    prices = {"X": ([date(2025, 1, 2), date(2025, 12, 31)], [120.0, 150.0])}
    row = schedule_fa_rows(trades, prices, 2025)["rows"][0]
    assert row["shares_at_year_end"] == 0 and row["closing_value_foreign"] == 0.0 and row["closing_value_inr"] == 0.0
    assert row["peak_value_foreign"] == 240.0 and row["sale_proceeds_foreign"] == 260.0
