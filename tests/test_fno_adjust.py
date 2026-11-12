from datetime import date
from decimal import Decimal as D

import pytest

from marketcore import fnotools
from marketcore.adjust import apply_actions, rebalance
from marketcore.tax_india import Trade, realised_gains

AS_OF = date(2026, 11, 11)


def fut(expiry, price, oi, symbol="NIFTY", kind="IDF", spot="25255.05"):
    return {"TckrSymb": symbol, "FinInstrmTp": kind, "XpryDt": expiry, "ClsPric": str(price), "SttlmPric": str(price),
            "UndrlygPric": spot, "OpnIntrst": str(oi), "ChngInOpnIntrst": "0", "TtlTradgVol": "10", "NewBrdLotQty": "65"}


def opt(expiry, symbol="NIFTY", kind="IDO"):
    return {"TckrSymb": symbol, "FinInstrmTp": kind, "XpryDt": expiry, "ClsPric": "10", "SttlmPric": "10",
            "UndrlygPric": "25255.05", "OpnIntrst": "650", "ChngInOpnIntrst": "0", "TtlTradgVol": "10", "NewBrdLotQty": "65"}


# The three NIFTY futures as they appeared in the NSE file for 11 Nov 2026.
ROWS = [
    fut("2026-11-23", 25214.20, 11455275), fut("2026-12-29", 25360.10, 1546740), fut("2027-01-25", 25519.50, 485810),
    opt("2026-11-17"), opt("2026-11-23"),
    fut("2026-11-23", 500.0, 1000, symbol="ABC", kind="STF", spot="498.00"),
    fut("2026-12-29", 503.0, 3000, symbol="ABC", kind="STF", spot="498.00"),
]


def test_futures_curve_by_hand():
    curve = fnotools.futures_curve(ROWS, "nifty", AS_OF)
    near, nxt = curve["contracts"][0], curve["contracts"][1]
    assert curve["spot"] == 25255.05 and curve["total_open_interest_units"] == 13487825
    assert near["days_to_expiry"] == 12 and near["basis"] == -40.85
    assert near["basis_pct"] == pytest.approx(-0.162, abs=0.001)
    assert near["annualised_basis_pct"] == pytest.approx(-40.85 / 25255.05 * 365 / 12 * 100, abs=0.01)   # about -4.92%
    assert curve["rollover_pct"] == pytest.approx(2032550 / 13487825 * 100, abs=0.01)                      # 15.07%
    assert curve["near_to_next_spread"] == pytest.approx(145.90, abs=0.01)
    assert nxt["share_of_open_interest_pct"] == pytest.approx(11.47, abs=0.01)
    with pytest.raises(ValueError):
        fnotools.futures_curve(ROWS, "NOPE", AS_OF)


def test_rollover_table_ranks_by_rollover():
    table = fnotools.rollover_table(ROWS, AS_OF)
    assert [r["symbol"] for r in table] == ["ABC", "NIFTY"]
    assert table[0]["rollover_pct"] == 75.0 and table[0]["near_basis_pct"] == pytest.approx(0.402, abs=0.001)
    assert fnotools.rollover_table(ROWS, AS_OF, min_oi_units=1_000_000) == [table[1]]


def test_expiry_calendar():
    index = fnotools.expiry_calendar(ROWS, AS_OF)
    assert [(e["symbol"], e["expiry"]) for e in index] == [
        ("NIFTY", "2026-11-17"), ("NIFTY", "2026-11-23"), ("NIFTY", "2026-12-29"), ("NIFTY", "2027-01-25")]
    weekly, monthly = index[0], index[1]
    assert (weekly["options"], weekly["futures"], weekly["weekday"], weekly["days_to_expiry"]) == (True, False, "Tuesday", 6)
    assert monthly["options"] and monthly["futures"] and monthly["lot_size"] == 65
    assert [e["expiry"] for e in fnotools.expiry_calendar(ROWS, AS_OF, "abc")] == ["2026-11-23", "2026-12-29"]


def test_ban_list():
    assert fnotools.parse_ban_list("Securities in Ban For Trade Date 12-NOV-2026:\n1,KAYNES\n2,SAIL\n") == {
        "trade_date": "12-NOV-2026", "symbols": ["KAYNES", "SAIL"]}
    assert fnotools.parse_ban_list("Securities in Ban For Trade Date 12-NOV-2026:\n")["symbols"] == []


def test_split_restates_earlier_trades_only():
    trades = [Trade(date(2024, 1, 1), "X", "buy", 10, 1000), Trade(date(2024, 7, 1), "X", "buy", 5, 210),
              Trade(date(2024, 1, 1), "Y", "buy", 10, 1000)]
    out, notes = apply_actions(trades, [{"symbol": "x", "date": date(2024, 6, 1), "type": "split", "ratio": 5}])
    x = [t for t in out if t.symbol == "X"]
    assert (x[0].quantity, x[0].price) == (D("50"), D("200"))       # cost of 10,000 is unchanged
    assert (x[1].quantity, x[1].price) == (5, 210)                  # bought after the split
    assert [t for t in out if t.symbol == "Y"][0].quantity == 10
    assert "restated 1 earlier trade" in notes[0]


def test_bonus_adds_a_zero_cost_lot():
    trades = [Trade(date(2023, 1, 1), "X", "buy", 10, 1000), Trade(date(2025, 6, 10), "X", "sell", 20, 600)]
    out, notes = apply_actions(trades, [{"symbol": "X", "date": date(2024, 6, 1), "type": "bonus", "ratio": 1}])
    bonus = [t for t in out if t.trade_date == date(2024, 6, 1)][0]
    assert (bonus.side, bonus.quantity, bonus.price) == ("buy", D("10"), 0)
    lots, _ = realised_gains(out)
    # Original lot: 6,000 - 10,000 = -4,000. Bonus lot: 6,000 - 0 = 6,000. Both long-term by June 2025.
    assert [(l.buy_date, l.gain, l.term) for l in lots] == [
        (date(2023, 1, 1), D("-4000"), "long"), (date(2024, 6, 1), D("6000"), "long")]
    # Without the adjustment the same sale cannot even be matched.
    with pytest.raises(ValueError):
        realised_gains(trades)


def test_bonus_fraction_and_bad_input():
    out, notes = apply_actions([Trade(date(2024, 1, 1), "X", "buy", 5, 100)],
                               [{"symbol": "X", "date": date(2024, 6, 1), "type": "bonus", "ratio": "0.5"}])
    assert [t.quantity for t in out if t.price == 0] == [D("2")] and "Fractional entitlement of 0.5" in notes[0]
    with pytest.raises(ValueError, match="not supported"):
        apply_actions([], [{"symbol": "X", "date": date(2024, 6, 1), "type": "demerger", "ratio": 1}])
    with pytest.raises(ValueError, match="incomplete"):
        apply_actions([Trade(date(2024, 1, 1), "X", "sell", 5, 100)], [{"symbol": "X", "date": date(2024, 6, 1), "type": "bonus", "ratio": 1}])


def test_split_then_bonus_in_date_order():
    trades = [Trade(date(2023, 1, 1), "X", "buy", 10, 1000)]
    out, _ = apply_actions(trades, [
        {"symbol": "X", "date": date(2024, 9, 1), "type": "bonus", "ratio": 1},
        {"symbol": "X", "date": date(2024, 3, 1), "type": "split", "ratio": 2},
    ])
    assert [(t.trade_date, t.quantity, t.price) for t in out] == [
        (date(2023, 1, 1), D("20"), D("500")), (date(2024, 9, 1), D("20"), 0)]


def trade_of(result, asset):
    return next(r for r in result["assets"] if r["asset"] == asset)


def test_rebalance_with_sales():
    out = rebalance({"equity": 700, "debt": 300}, {"equity": 60, "debt": 40})
    assert trade_of(out, "equity")["trade"] == "-100.00" and trade_of(out, "debt")["trade"] == "100.00"
    assert trade_of(out, "equity")["drift_pct_points"] == "10.00" and trade_of(out, "equity")["pct_after"] == "60.00"
    assert out["total_sold"] == "100.00" and out["largest_drift_pct_points"] == "10.00"


def test_rebalance_with_new_money_only():
    # 100 added: targets become 660 / 440. Only debt is short (by 140), so all 100 goes there.
    out = rebalance({"equity": 700, "debt": 300}, {"equity": 60, "debt": 40}, new_money=100, sell_allowed=False)
    assert trade_of(out, "debt")["trade"] == "100.00" and trade_of(out, "equity")["trade"] == "0.00"
    assert out["total_sold"] == "0.00" and trade_of(out, "debt")["pct_after"] == "36.36"
    # 200 added: targets 720 / 480, gaps 20 and 180, exactly the cash available.
    exact = rebalance({"equity": 700, "debt": 300}, {"equity": 60, "debt": 40}, new_money=200, sell_allowed=False)
    assert trade_of(exact, "equity")["trade"] == "20.00" and trade_of(exact, "debt")["trade"] == "180.00"
    assert trade_of(exact, "equity")["pct_after"] == "60.00"


def test_rebalance_band_new_asset_and_validation():
    assert rebalance({"equity": 610, "debt": 390}, {"equity": 60, "debt": 40}, band_pct=2)["total_bought"] == "0.00"
    out = rebalance({"equity": 1000}, {"equity": 80, "gold": 20})
    assert trade_of(out, "gold")["trade"] == "200.00" and trade_of(out, "equity")["trade"] == "-200.00"
    with pytest.raises(ValueError, match="add to 100"):
        rebalance({"a": 1}, {"a": 60, "b": 30})
    with pytest.raises(ValueError, match="withdrawal"):
        rebalance({"a": 100}, {"a": 100}, new_money=-10, sell_allowed=False)
