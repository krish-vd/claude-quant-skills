"""Parser tests use small samples copied from the real files. Live fetches run only
when MARKET_SKILLS_LIVE=1 is set."""
import os
from datetime import date

import pytest

from marketcore.data import amfi, nse

LOTS_SAMPLE = """UNDERLYING                          ,SYMBOL    ,NOV-26     ,DEC-26     ,JAN-27     ,MAR-27
NIFTY 50                            ,NIFTY     ,65         ,65         ,65         ,65
NIFTY BANK                          ,BANKNIFTY ,30         ,30         ,30         ,
Derivatives on Individual Securities,Symbol    ,NOV-26     ,DEC-26     ,JAN-27     ,
ADANI ENTERPRISES LIMITED           ,ADANIENT  ,309        ,309        ,309        ,
"""

NAV_SAMPLE = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date

Open Ended Schemes(Children's Fund - Childrens' Fund)

Axis Mutual Fund

135762;INF846K01WO1;-;Axis Children's Fund;Direct Plan;Growth Option;31.0915;11-Nov-2026
135765;INF846K01WP8;-;Axis Children's Fund;Direct Plan;IDCW Option;N.A.;11-Nov-2026
"""


def test_parse_lots():
    lots = nse.parse_lots(LOTS_SAMPLE)
    assert lots["NIFTY"] == {"NOV-26": 65, "DEC-26": 65, "JAN-27": 65, "MAR-27": 65}
    assert lots["BANKNIFTY"] == {"NOV-26": 30, "DEC-26": 30, "JAN-27": 30}
    assert lots["ADANIENT"]["NOV-26"] == 309
    assert "SYMBOL" not in lots


def test_parse_nav_all():
    schemes = amfi.parse_nav_all(NAV_SAMPLE)
    assert len(schemes) == 1                      # the N.A. row is dropped
    s = schemes[0]
    assert s["scheme_code"] == "135762" and s["nav"] == 31.0915
    assert s["nav_date"] == "2026-11-11"
    assert s["fund_house"] == "Axis Mutual Fund"
    assert s["category"].startswith("Open Ended Schemes")
    assert s["isin"] == "INF846K01WO1"
    assert (s["plan"], s["option"]) == ("Direct Plan", "Growth Option")


live = pytest.mark.skipif(os.environ.get("MARKET_SKILLS_LIVE") != "1", reason="set MARKET_SKILLS_LIVE=1 to hit the network")


@live
def test_live_nse_lot_size():
    assert nse.lot_size("NIFTY")["lot_size"] > 0


@live
def test_live_bhavcopy_known_day():
    quote = nse.equity_quote("RELIANCE", date(2026, 11, 11))
    assert float(quote["close"]) > 0 and quote["isin"].startswith("INE")


@live
def test_live_amfi():
    assert len(amfi.all_navs()) > 1000
