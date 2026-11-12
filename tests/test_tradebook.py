from datetime import date

import pytest

from marketcore import tradebook as tb

ZERODHA = """symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id,order_id,order_execution_time
INFY,INE009A01021,2025-06-02,NSE,EQ,EQ,buy,false,100,1500.00,1,11,2025-06-02T09:20:00
INFY,INE009A01021,2025-06-02,NSE,EQ,EQ,sell,false,40,1510.00,2,12,2025-06-02T11:00:00
TCS,INE467B01029,2025-06-03,NSE,EQ,EQ,buy,false,10,3500.50,3,13,2025-06-03T10:00:00
NIFTY25JUNFUT,,2025-06-03,NFO,FO,,buy,false,75,24800,4,14,2025-06-03T10:05:00
"""


def test_zerodha_format_is_read_and_derivatives_set_aside():
    fills, report = tb.read_fills(ZERODHA)
    assert len(fills) == 3 and report["derivative_rows_skipped"] == 1 and report["unreadable_rows"] == []
    assert report["columns_used"]["date"] == "trade_date" and report["columns_used"]["side"] == "trade_type"
    assert fills[0] == tb.Fill(date(2025, 6, 2), "INFY", "buy", 100.0, 1500.0, 2)
    assert tb.PRESETS["zerodha"]["quantity"] == "quantity"


def test_intraday_part_is_separated_from_delivery():
    fills, _ = tb.read_fills(ZERODHA)
    delivery, intraday = tb.split_intraday(fills)
    # INFY: bought 100, sold 40 the same day -> 40 intraday, 60 delivered.
    assert intraday == [{"date": "2025-06-02", "symbol": "INFY", "quantity": 40.0, "buy_value": 60000.0,
                         "sell_value": 60400.0, "pnl_before_charges": 400.0}]
    assert [(f.symbol, f.side, f.quantity) for f in delivery] == [("INFY", "buy", 60.0), ("TCS", "buy", 10.0)]


def test_intraday_matching_is_first_in_first_out():
    text = """Date,Scrip,Buy/Sell,Qty,Rate
03-06-2025,ABC,B,10,100
03-06-2025,ABC,B,10,110
03-06-2025,ABC,S,15,120
04-06-2025,ABC,S,5,130
"""
    fills, report = tb.read_fills(text)
    assert report["columns_used"] == {"date": "Date", "symbol": "Scrip", "side": "Buy/Sell", "quantity": "Qty", "price": "Rate"}
    delivery, intraday = tb.split_intraday(fills)
    # 15 sold on the day: matched to the first 10 @ 100 and 5 of the 10 @ 110 -> buy value 1,550, sell value 1,800.
    assert intraday[0]["quantity"] == 15 and intraday[0]["buy_value"] == 1550.0 and intraday[0]["pnl_before_charges"] == 250.0
    # 5 @ 110 are delivered, then sold the next day (a delivery sale, not intraday).
    assert [(f.trade_date, f.side, f.quantity, f.price) for f in delivery] == [
        (date(2025, 6, 3), "buy", 5.0, 110.0), (date(2025, 6, 4), "sell", 5.0, 130.0)]


def test_full_same_day_round_trip_leaves_no_delivery():
    text = "date,symbol,side,quantity,price\n2025-06-02,X,buy,50,10\n2025-06-02,X,sell,50,9\n"
    delivery, intraday = tb.split_intraday(tb.read_fills(text)[0])
    assert delivery == [] and intraday[0]["pnl_before_charges"] == -50.0


def test_dates_and_overrides():
    assert tb.parse_date("2025-06-02T09:20:00") == date(2025, 6, 2)
    assert tb.parse_date("02/06/2025") == date(2025, 6, 2)          # day first, the Indian convention
    assert tb.parse_date("02-Jun-2025 14:01:05") == date(2025, 6, 2)
    assert tb.parse_date("06/02/2025", "%m/%d/%Y") == date(2025, 6, 2)
    with pytest.raises(ValueError):
        tb.parse_date("June 2nd")
    text = "When,Name,Dir,N,Px\n2025-06-02,ABC,BUY,5,10\n"
    with pytest.raises(ValueError, match="could not find column"):
        tb.read_fills(text)
    fills, _ = tb.read_fills(text, {"date": "When", "symbol": "Name", "side": "Dir", "quantity": "N", "price": "Px"})
    assert fills[0].symbol == "ABC" and fills[0].quantity == 5
    with pytest.raises(ValueError, match="is not in the file"):
        tb.read_fills(text, {"date": "Nope"})


def test_bad_rows_are_reported_not_dropped_silently():
    text = "date,symbol,side,quantity,price\n2025-06-02,X,buy,abc,10\n2025-06-02,Y,hold,5,10\n2025-06-02,Z,buy,5,10\n"
    fills, report = tb.read_fills(text)
    assert [f.symbol for f in fills] == ["Z"] and len(report["unreadable_rows"]) == 2
    assert report["unreadable_rows"][0].startswith("line 2")


def test_standard_csv_feeds_the_tax_engine():
    from marketcore.tax_india import Trade, realised_gains

    delivery, _ = tb.split_intraday(tb.read_fills(ZERODHA)[0])
    text = tb.to_standard_csv(delivery)
    assert text.splitlines()[0] == "date,symbol,side,quantity,price,asset_class,charges"
    assert text.splitlines()[1] == "2025-06-02,INFY,buy,60,1500.0,listed_equity,0"
    trades = [Trade(f.trade_date, f.symbol, f.side, f.quantity, f.price) for f in delivery]
    trades.append(Trade(date(2025, 9, 1), "INFY", "sell", 60, 1600))
    lots, _ = realised_gains(trades)
    assert lots[0].gain == 6000                                      # only the 60 delivered shares, not all 100
