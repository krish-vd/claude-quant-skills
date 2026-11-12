from datetime import date, timedelta

import pytest

from marketcore import delivery, dividends
from marketcore.backtest import Bars
from marketcore.screens import analyse


def make(closes, highs=None, lows=None, volumes=None):
    n = len(closes)
    return Bars("T", [date(2024, 1, 1) + timedelta(days=i) for i in range(n)], list(closes),
                list(highs or closes), list(lows or closes), list(closes), list(volumes or [1000.0] * n))


def test_contraction_passes_on_a_tight_quiet_base_near_highs():
    # 260 sessions rising 0.3% a day, then a 30-session wide swing, then 10 tight quiet sessions.
    rise = [100 * 1.003 ** i for i in range(260)]
    top = rise[-1]
    swing = [top * (1 + 0.06 * ((-1) ** i)) for i in range(30)]          # +/-6%: a 12% range
    tight = [top * (1 + 0.01 * ((-1) ** (i + 1))) for i in range(10)]    # +/-1%: a 2% range, ending on an up day
    closes = rise + swing + tight
    volumes = [1000.0] * 290 + [500.0] * 10                              # volume halves in the tight range
    row = analyse(make(closes, volumes=volumes))
    assert row["contraction_checks"] == {"uptrend": True, "near_52w_high": True, "tight_range": True, "volume_dry_up": True}
    assert row["contraction"] is True
    assert row["range_10d_pct"] == pytest.approx(2.0, abs=0.1) and row["range_40d_pct"] > 10
    assert row["pivot"] == pytest.approx(top * 1.01, abs=0.01)
    assert row["volume_10d_vs_50d"] == pytest.approx((500 * 10) / ((1000 * 40 + 500 * 10)) * 5, abs=0.01)   # 0.56

    loud = analyse(make(closes))                                         # same prices, no volume dry-up
    assert loud["contraction"] is False and loud["contraction_checks"]["volume_dry_up"] is False
    wide = analyse(make(rise + swing + swing[:10]))
    assert wide["contraction_checks"]["tight_range"] is False


DELIVERY_FILE = """SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
20MICRONS, EQ, 11-Nov-2026, 187.33, 187.50, 189.78, 186.20, 187.15, 188.12, 188.40, 52116, 98.19, 2089, 29010, 55.66
21STCENMGM, BE, 11-Nov-2026, 54.53, 57.20, 57.25, 56.10, 57.00, 56.58, 57.06, 25557, 14.58, 151, -, -
"""


def test_delivery_file_parsing():
    table = delivery.parse(DELIVERY_FILE)
    assert list(table) == ["20MICRONS"]                                  # BE series and '-' rows are left out
    assert table["20MICRONS"] == {"close": 188.12, "prev_close": 187.33, "volume": 52116.0, "turnover_lakh": 98.19,
                                  "delivered": 29010.0, "delivery_pct": 55.66}
    with pytest.raises(delivery.DataUnavailable):
        delivery.parse("<html>blocked</html>")


def test_delivery_screen_by_hand():
    def day(d, **stocks):
        return (d, {s: {"close": c, "prev_close": pc, "volume": 0.0, "turnover_lakh": t, "delivered": q, "delivery_pct": pct}
                    for s, (c, pc, t, q, pct) in stocks.items()})

    tables = [
        day(date(2026, 11, 5), SPIKE=(100, 100, 900, 1000, 40), FLAT=(50, 50, 900, 1000, 40), TINY=(10, 10, 5, 100, 40)),
        day(date(2026, 11, 6), SPIKE=(100, 100, 900, 3000, 50), FLAT=(50, 50, 900, 1000, 40), TINY=(10, 10, 5, 100, 40)),
        day(date(2026, 11, 9), SPIKE=(104, 100, 2000, 8000, 70), FLAT=(50, 50, 900, 1100, 40), TINY=(10, 10, 5, 900, 40),
            NEW=(20, 20, 900, 5000, 60)),
    ]
    rows = delivery.screen(tables, min_turnover_lakh=500, min_ratio=2.0)
    assert [r["symbol"] for r in rows] == ["SPIKE"]                      # FLAT: ratio 1.1; TINY: illiquid; NEW: no history
    spike = rows[0]
    assert spike["avg_delivered_qty"] == 2000 and spike["delivery_ratio"] == 4.0
    assert spike["price_change_pct"] == 4.0 and spike["avg_delivery_pct"] == 45.0 and spike["sessions_in_average"] == 2


def test_dividend_summary_by_hand():
    as_of = date(2026, 11, 12)
    divs = [(date(2021, 7, 1), 4.0), (date(2022, 7, 1), 5.0), (date(2023, 7, 1), 6.0), (date(2024, 7, 1), 6.0),
            (date(2025, 2, 1), 3.0), (date(2025, 7, 1), 5.0), (date(2026, 2, 1), 4.0), (date(2026, 7, 1), 6.0)]
    out = dividends.summarise("itc", divs, 400.0, as_of)
    assert out["dividends_ttm"] == 10.0 and out["payments_ttm"] == 2 and out["yield_ttm_pct"] == 2.5
    assert out["annual_totals"] == {"2021": 4.0, "2022": 5.0, "2023": 6.0, "2024": 6.0, "2025": 8.0}   # 2026 is not complete
    assert out["years_of_history"] == 5 and out["years_paid"] == 5 and out["consecutive_years_paid"] == 5
    assert out["consecutive_years_of_increase"] == 1                     # 2025 > 2024, but 2024 = 2023
    assert out["dividend_cagr_3y_pct"] == pytest.approx(((8 / 5) ** (1 / 3) - 1) * 100, abs=0.01)
    assert out["dividend_cagr_5y_pct"] is None                           # needs six complete years
    assert out["last_dividend"] == {"date": "2026-07-01", "amount": 6.0}


def test_dividend_gaps_and_none():
    as_of = date(2026, 11, 12)
    gappy = dividends.summarise("X", [(date(2022, 5, 1), 2.0), (date(2025, 5, 1), 3.0)], 100.0, as_of)
    assert gappy["years_of_history"] == 4 and gappy["years_paid"] == 2 and gappy["consecutive_years_paid"] == 1
    assert gappy["dividends_ttm"] == 0 and gappy["yield_ttm_pct"] == 0.0
    none = dividends.summarise("Y", [], 100.0, as_of)
    assert none["years_of_history"] == 0 and none["last_dividend"] is None and none["yield_ttm_pct"] == 0.0


def test_dividend_payload_parsing():
    payload = {"chart": {"result": [{
        "meta": {"gmtoffset": 19800},
        "timestamp": [1794000000, 1794086400],
        "indicators": {"quote": [{"close": [400.0, None]}]},
        "events": {"dividends": {"a": {"amount": 6.5, "date": 1770176700}, "b": {"amount": 8.0, "date": 1779853500}}},
    }]}}
    rows, close, last_date = dividends.parse_dividends(payload)
    assert [a for _, a in rows] == [6.5, 8.0] and rows[0][0] < rows[1][0]
    assert close == 400.0 and last_date is not None
    with pytest.raises(dividends.DataUnavailable):
        dividends.parse_dividends({"chart": {"result": None}})
