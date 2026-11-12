from datetime import date
from decimal import Decimal as D

import pytest

from marketcore.harvest import open_lots, plan
from marketcore.tax_india import Trade

TODAY = date(2026, 2, 15)   # FY 2025-26


def test_open_lots_after_fifo_sells():
    trades = [
        Trade(date(2023, 1, 1), "A", "buy", 10, 100),
        Trade(date(2024, 1, 1), "A", "buy", 10, 200),
        Trade(date(2025, 6, 1), "A", "sell", 15, 300),
        Trade(date(2024, 5, 1), "B", "buy", 5, 50),
        Trade(date(2025, 7, 1), "B", "sell", 5, 60),
    ]
    lots = open_lots(trades)
    assert list(lots) == ["A"]
    assert lots["A"][0]["qty"] == D("5") and lots["A"][0]["date"] == date(2024, 1, 1)
    with pytest.raises(ValueError):
        open_lots([Trade(date(2025, 1, 1), "X", "sell", 1, 10)])


def test_gain_harvest_fills_the_exemption_exactly():
    # Long-term lot: 1,000 shares bought at 100, now 300 -> 200 gain per share. Nothing realised yet.
    trades = [Trade(date(2023, 1, 10), "INFY", "buy", 1000, 100)]
    out = plan(trades, {"INFY": 300}, TODAY)
    assert out["financial_year"] == "2025-26" and out["ltcg_exemption_left"] == "125000"
    sale = out["gain_harvest"]["sales"][0]
    assert sale["units_to_sell"] == "625"                      # 625 x 200 = 1,25,000
    assert out["gain_harvest"]["long_term_gain_realised"] == "125000.00"
    assert out["gain_harvest"]["exemption_left_after"] == "0.00"
    assert out["gain_harvest"]["future_tax_avoided"] == "16250.00"   # 1,25,000 x 12.5% x 1.04


def test_realised_gains_reduce_the_room_and_whole_units_only():
    trades = [
        Trade(date(2023, 1, 10), "INFY", "buy", 1000, 100),
        Trade(date(2025, 6, 10), "INFY", "sell", 300, 400),     # realised long-term gain 90,000
    ]
    out = plan(trades, {"INFY": 330}, TODAY)                    # 230 gain per share left on 700 shares
    assert out["realised_long_term_gain_so_far"] == "90000"
    assert out["ltcg_exemption_left"] == "35000"
    assert out["gain_harvest"]["sales"][0]["units_to_sell"] == "152"   # floor(35,000 / 230)
    assert out["gain_harvest"]["long_term_gain_realised"] == "34960.00"


def test_short_term_lot_at_the_front_blocks_harvesting():
    # FIFO: the oldest lot is what gets sold. Here the only long-term shares were already sold,
    # so the front lot is short-term and nothing can be harvested as long-term.
    trades = [
        Trade(date(2025, 11, 1), "TCS", "buy", 100, 3000),      # short-term on 15 Feb 2026
    ]
    out = plan(trades, {"TCS": 3600}, TODAY)
    assert out["gain_harvest"]["sales"] == []
    lot = out["positions"][0]["lots"][0]
    assert lot["term_if_sold_today"] == "short" and lot["sellable_now_as_long_term"] is False
    assert lot["first_long_term_date"] == "2026-11-02"


def test_later_long_term_lot_behind_a_short_term_one_is_not_reachable():
    trades = [
        Trade(date(2023, 1, 1), "X", "buy", 10, 100),
        Trade(date(2025, 12, 1), "X", "buy", 10, 100),
        Trade(date(2025, 12, 15), "X", "sell", 10, 100),        # consumed the 2023 lot
        Trade(date(2023, 6, 1), "Y", "buy", 10, 100),
    ]
    out = plan(trades, {"X": 200, "Y": 200}, TODAY)
    by_symbol = {p["symbol"]: p for p in out["positions"]}
    assert by_symbol["X"]["lots"][0]["term_if_sold_today"] == "short"
    assert [s["symbol"] for s in out["gain_harvest"]["sales"]] == ["Y"]


def test_loss_candidates_and_wait_list():
    trades = [
        Trade(date(2025, 3, 1), "LOSS", "buy", 100, 500),       # now 400: loss 10,000; long-term from 2 Mar 2026
        Trade(date(2025, 3, 10), "SOON", "buy", 100, 100),      # now 200: short-term gain 10,000; long-term in 24 days
    ]
    out = plan(trades, {"LOSS": 400, "SOON": 200}, TODAY)
    assert out["loss_harvest_candidates"] == [
        {"symbol": "LOSS", "buy_date": "2025-03-01", "quantity": "100", "term": "short", "loss": "-10000.00"}]
    wait = out["wait_for_long_term"][0]
    assert wait["symbol"] == "SOON" and wait["first_long_term_date"] == "2026-03-11" and wait["days_until_long_term"] == 24
    assert wait["tax_rate_difference_on_this_gain"] == "780.00"  # 10,000 x (20% - 12.5%) x 1.04


def test_missing_prices_and_other_asset_classes_are_listed():
    trades = [
        Trade(date(2023, 1, 1), "NOPRICE", "buy", 10, 100),
        Trade(date(2023, 1, 1), "AAPL", "buy", 10, 10000, "foreign_equity"),
    ]
    out = plan(trades, {}, TODAY)
    assert out["symbols_without_a_price"] == ["NOPRICE"] and out["symbols_not_covered"] == ["AAPL"]


def test_grandfathered_cost_is_used():
    trades = [Trade(date(2017, 6, 1), "OLD", "buy", 100, 100)]
    out = plan(trades, {"OLD": 500}, TODAY, {"OLD": 300})
    assert out["positions"][0]["lots"][0]["unit_cost"] == "300.0000"
    assert out["gain_harvest"]["sales"][0]["units_to_sell"] == "100"   # 100 x 200 = 20,000, within the exemption
