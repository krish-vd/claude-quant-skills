from datetime import date
from decimal import Decimal as D

import pytest

from marketcore.tax_india import Trade, add_months, financial_year, is_long_term, realised_gains, summarise


def _run(trades, fmv=None):
    lots, warnings = realised_gains(trades, fmv)
    return lots, warnings, summarise(lots)


def test_financial_year_and_month_arithmetic():
    assert financial_year(date(2026, 3, 31)) == "2025-26"
    assert financial_year(date(2026, 4, 1)) == "2026-27"
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)
    assert add_months(date(2025, 8, 31), 6) == date(2026, 2, 28)


def test_twelve_month_boundary():
    bought = date(2025, 1, 1)
    assert not is_long_term(bought, date(2026, 1, 1), 12)   # exactly 12 months: short-term
    assert is_long_term(bought, date(2026, 1, 2), 12)       # more than 12 months
    assert not is_long_term(bought, date(2030, 1, 1), None)  # debt funds bought after Apr 2023


def test_listed_equity_ltcg_with_exemption():
    lots, _, years = _run([
        Trade(date(2024, 1, 10), "INFY", "buy", 100, 1000),
        Trade(date(2025, 6, 10), "INFY", "sell", 100, 3000),
    ])
    assert lots[0].term == "long" and lots[0].gain == D("200000")
    y = years[0]
    assert y.fy == "2025-26"
    assert y.tax_before_cess == D("9375")      # (2,00,000 - 1,25,000) x 12.5%
    assert y.cess == D("375")
    assert y.tax_with_cess == D("9750")


def test_ltcg_below_exemption_is_tax_free():
    _, _, years = _run([
        Trade(date(2024, 1, 10), "INFY", "buy", 100, 1000),
        Trade(date(2025, 6, 10), "INFY", "sell", 100, 2000),   # gain 1,00,000
    ])
    assert years[0].tax_before_cess == 0


def test_listed_equity_stcg_at_20_percent():
    lots, _, years = _run([
        Trade(date(2025, 5, 1), "TCS", "buy", 1000, 100),
        Trade(date(2025, 8, 1), "TCS", "sell", 1000, 150),
    ])
    assert lots[0].term == "short"
    assert years[0].tax_before_cess == D("10000")   # 50,000 x 20%


def test_charges_reduce_gain():
    lots, _, _ = _run([
        Trade(date(2025, 5, 1), "TCS", "buy", 100, 100, charges=50),
        Trade(date(2025, 8, 1), "TCS", "sell", 100, 150, charges=30),
    ])
    assert lots[0].gain == D("5000") - D("50") - D("30")


def test_fifo_across_lots_and_partial_sells():
    lots, _, _ = _run([
        Trade(date(2024, 1, 1), "X", "buy", 10, 100),
        Trade(date(2025, 3, 1), "X", "buy", 10, 200),
        Trade(date(2025, 6, 1), "X", "sell", 15, 300),
    ])
    assert [(l.quantity, l.term, l.gain) for l in lots] == [
        (D("10"), "long", D("2000")),
        (D("5"), "short", D("500")),
    ]


def test_grandfathering_three_cases():
    def gain(fmv, sale):
        lots, _, _ = _run(
            [Trade(date(2017, 6, 1), "OLD", "buy", 1, 100), Trade(date(2025, 7, 1), "OLD", "sell", 1, sale)],
            {"OLD": fmv},
        )
        return lots[0].cost_used, lots[0].gain

    assert gain(300, 500) == (D("300"), D("200"))   # FMV between cost and sale: cost stepped up to FMV
    assert gain(600, 500) == (D("500"), D("0"))     # FMV above sale: cost capped at sale value, no loss created
    assert gain(50, 500) == (D("100"), D("400"))    # FMV below actual cost: actual cost stands


def test_missing_fmv_warns():
    _, warnings, _ = _run([
        Trade(date(2017, 6, 1), "OLD", "buy", 1, 100),
        Trade(date(2025, 7, 1), "OLD", "sell", 1, 500),
    ])
    assert any("31-Jan-2018" in w for w in warnings)


def test_foreign_equity_needs_24_months_and_gets_no_exemption():
    lots, _, years = _run([
        Trade(date(2023, 1, 10), "AAPL", "buy", 10, 10000, "foreign_equity"),
        Trade(date(2025, 6, 10), "AAPL", "sell", 10, 20000, "foreign_equity"),   # 29 months
        Trade(date(2024, 6, 10), "MSFT", "buy", 10, 10000, "foreign_equity"),
        Trade(date(2025, 12, 10), "MSFT", "sell", 10, 15000, "foreign_equity"),  # 18 months
    ])
    terms = {l.symbol: l.term for l in lots}
    assert terms == {"AAPL": "long", "MSFT": "short"}
    y = years[0]
    assert y.tax_before_cess == D("12500")     # 1,00,000 x 12.5%, no exemption
    assert y.slab_income == D("50000")         # short-term foreign gain goes to slab


def test_debt_fund_after_2023_is_always_slab():
    lots, _, years = _run([
        Trade(date(2023, 5, 1), "DEBTFUND", "buy", 1000, 10, "debt_fund_post_2023"),
        Trade(date(2026, 6, 1), "DEBTFUND", "sell", 1000, 13, "debt_fund_post_2023"),
    ])
    assert lots[0].term == "short"
    assert years[0].slab_income == D("3000") and years[0].tax_before_cess == 0


def test_losses_are_reported_not_set_off():
    _, _, years = _run([
        Trade(date(2025, 5, 1), "A", "buy", 100, 100),
        Trade(date(2025, 6, 1), "A", "sell", 100, 80),      # short-term loss 2,000
        Trade(date(2024, 1, 1), "B", "buy", 100, 1000),
        Trade(date(2025, 6, 1), "B", "sell", 100, 3000),    # long-term gain 2,00,000
    ])
    y = years[0]
    assert y.tax_before_cess == D("9375")
    assert any("NOT set off" in n for n in y.notes)


def test_sell_without_buys_is_an_error():
    with pytest.raises(ValueError, match="exceeds the buys"):
        realised_gains([Trade(date(2025, 6, 1), "X", "sell", 10, 100)])


def test_old_sells_consume_lots_but_are_not_reported():
    lots, warnings, _ = _run([
        Trade(date(2023, 1, 1), "X", "buy", 10, 100),
        Trade(date(2024, 1, 1), "X", "buy", 10, 200),
        Trade(date(2024, 6, 1), "X", "sell", 10, 150),      # before coverage: uses the first lot
        Trade(date(2025, 6, 1), "X", "sell", 10, 300),      # must match the SECOND lot
    ])
    assert len(lots) == 1
    assert lots[0].actual_cost == D("2000") and lots[0].buy_date == date(2024, 1, 1)
    assert any("not reported" in w for w in warnings)
