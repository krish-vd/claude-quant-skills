import pytest

from marketcore import fundamentals as f

XBRL = """<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in="http://example/in">
  <xbrli:context id="OneD"><xbrli:entity><xbrli:identifier scheme="x">INFY</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2026-07-01</xbrli:startDate><xbrli:endDate>2026-09-30</xbrli:endDate></xbrli:period></xbrli:context>
  <xbrli:context id="FourD"><xbrli:entity><xbrli:identifier scheme="x">INFY</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-09-30</xbrli:endDate></xbrli:period></xbrli:context>
  <xbrli:context id="OneI"><xbrli:entity><xbrli:identifier scheme="x">INFY</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2026-09-30</xbrli:instant></xbrli:period></xbrli:context>
  <xbrli:context id="Seg"><xbrli:entity><xbrli:identifier scheme="x">INFY</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2026-07-01</xbrli:startDate><xbrli:endDate>2026-09-30</xbrli:endDate></xbrli:period>
    <xbrli:scenario><seg>one segment</seg></xbrli:scenario></xbrli:context>
  <in:NameOfTheCompany contextRef="OneD">INFOSYS LIMITED</in:NameOfTheCompany>
  <in:NatureOfReportStandaloneConsolidated contextRef="OneD">Consolidated</in:NatureOfReportStandaloneConsolidated>
  <in:WhetherResultsAreAuditedOrUnaudited contextRef="OneD">Audited</in:WhetherResultsAreAuditedOrUnaudited>
  <in:RevenueFromOperations contextRef="Seg" unitRef="INR">111</in:RevenueFromOperations>
  <in:RevenueFromOperations contextRef="OneD" unitRef="INR">492440000000</in:RevenueFromOperations>
  <in:RevenueFromOperations contextRef="FourD" unitRef="INR">974540000000</in:RevenueFromOperations>
  <in:ProfitBeforeTax contextRef="OneD" unitRef="INR">110630000000</in:ProfitBeforeTax>
  <in:ProfitLossForPeriod contextRef="OneD" unitRef="INR">78380000000</in:ProfitLossForPeriod>
  <in:DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef="OneD">19.3</in:DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations>
  <in:DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef="FourD">38.46</in:DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations>
  <in:Equity contextRef="OneI" unitRef="INR">995430000000</in:Equity>
  <in:Assets contextRef="OneI" unitRef="INR">1634800000000</in:Assets>
</xbrli:xbrl>""".encode()


def test_india_result_takes_the_quarter_not_the_half_year_or_a_segment():
    r = f.parse_india_result(XBRL)
    assert (r["period_start"], r["period_end"], r["is_single_quarter"]) == ("2026-07-01", "2026-09-30", True)
    assert r["revenue"] == 492440000000 and r["net_profit"] == 78380000000 and r["eps_diluted"] == 19.3
    assert r["equity"] == 995430000000 and r["total_assets"] == 1634800000000
    assert r["basis"] == "Consolidated" and r["audited"] == "Audited" and r["revenue_is_total_income"] is False
    with pytest.raises(f.DataUnavailable):
        f.parse_india_result(b"<html>not xbrl")


def quarter(end, revenue, profit, eps, pbt=None):
    start = {"03-31": "01-01", "06-30": "04-01", "09-30": "07-01", "12-31": "10-01"}[end[5:]]
    return {"period_start": end[:5] + start, "period_end": end, "period_days": 91, "is_single_quarter": True, "revenue": revenue,
            "net_profit": profit, "eps_diluted": eps, "profit_before_tax": pbt or profit * 1.3, "equity": 5000.0, "total_assets": 9000.0,
            "audited": "Audited", "company": "TEST LTD", "revenue_is_total_income": False}


def test_india_summary_growth_margins_and_trailing_pe():
    data = {"symbol": "TEST", "basis": "Consolidated", "problems": [], "quarters": [
        quarter("2026-09-30", 1200.0, 240.0, 12.0), quarter("2026-06-30", 1100.0, 198.0, 9.9),
        quarter("2026-03-31", 1050.0, 189.0, 9.45), quarter("2025-12-31", 1000.0, 180.0, 9.0),
        quarter("2025-09-30", 1000.0, 200.0, 10.0),
    ]}
    out = f.india_summary(data, price=807.0)
    latest = out["latest_quarter"]
    assert latest["revenue_growth_yoy_pct"] == 20.0 and latest["net_profit_growth_yoy_pct"] == 20.0 and latest["eps_growth_yoy_pct"] == 20.0
    assert latest["net_margin_pct"] == 20.0
    assert out["quarters"][1]["revenue_growth_yoy_pct"] is None            # no year-ago quarter supplied
    ttm = out["trailing_four_quarters"]
    assert ttm["eps_diluted"] == 40.35 and ttm["price_to_earnings"] == 20.0   # 12 + 9.9 + 9.45 + 9 ; 807 / 40.35
    assert out["balance_sheet"]["equity"] == 5000.0


def test_india_summary_no_trailing_figure_when_a_quarter_is_missing_or_loss_base():
    data = {"symbol": "T", "basis": "Standalone", "problems": [], "quarters": [
        quarter("2026-09-30", 1200.0, 240.0, 12.0), quarter("2026-03-31", 1050.0, 189.0, 9.45),
        quarter("2025-12-31", 1000.0, 180.0, 9.0), quarter("2025-09-30", 1000.0, -50.0, -2.5),
    ]}
    out = f.india_summary(data, price=100.0)
    assert out["trailing_four_quarters"] is None                           # June 2026 is missing
    assert out["latest_quarter"]["net_profit_growth_yoy_pct"] is None      # growth off a loss is not reported


def sec_facts():
    def dur(start, end, val, form="10-Q"):
        return {"start": start, "end": end, "val": val, "form": form, "filed": end}

    return {"entityName": "Test Corp", "facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [
            dur("2023-10-01", "2024-09-30", 1000, "10-K"), dur("2024-10-01", "2025-09-30", 1200, "10-K"),
            dur("2023-10-01", "2023-12-31", 240), dur("2024-01-01", "2024-03-31", 250), dur("2024-04-01", "2024-06-30", 250),
            dur("2024-10-01", "2024-12-31", 300), dur("2025-01-01", "2025-03-31", 290), dur("2025-04-01", "2025-06-30", 300),
            dur("2024-10-01", "2025-03-31", 590),                      # a six-month figure: must be ignored
        ]}},
        "NetIncomeLoss": {"units": {"USD": [dur("2023-10-01", "2024-09-30", 100, "10-K"), dur("2024-10-01", "2025-09-30", 150, "10-K")]}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": [
            dur("2023-10-01", "2024-09-30", 4.0, "10-K"), dur("2024-10-01", "2025-09-30", 6.0, "10-K"),
            dur("2023-10-01", "2023-12-31", 0.9), dur("2024-01-01", "2024-03-31", 1.0), dur("2024-04-01", "2024-06-30", 1.0),
            dur("2024-10-01", "2024-12-31", 1.5), dur("2025-01-01", "2025-03-31", 1.4), dur("2025-04-01", "2025-06-30", 1.5),
        ]}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [dur("2024-10-01", "2025-09-30", 200, "10-K")]}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [dur("2024-10-01", "2025-09-30", 50, "10-K")]}},
        "StockholdersEquity": {"units": {"USD": [{"end": "2024-09-30", "val": 400, "filed": "2024-11-01"}, {"end": "2025-09-30", "val": 600, "filed": "2025-11-01"}]}},
        "LongTermDebt": {"units": {"USD": [{"end": "2025-09-30", "val": 300, "filed": "2025-11-01"}]}},
    }}}


def test_us_series_derives_the_fourth_quarter():
    s = f.us_series(sec_facts())
    assert s["annual"]["revenue"]["2025-09-30"][1] == 1200
    assert s["quarterly"]["revenue"]["2025-09-30"] == ("2025-06-30", 310.0, True)      # 1,200 - 300 - 290 - 300
    assert s["quarterly"]["eps_diluted"]["2025-09-30"][1] == pytest.approx(1.6)        # 6.0 - 1.5 - 1.4 - 1.5
    assert "2025-03-31" in s["quarterly"]["revenue"] and s["quarterly"]["revenue"]["2025-03-31"][1] == 290   # not the 590
    assert s["tags_used"]["revenue"] == "Revenues"


def test_us_summary_by_hand():
    out = f.us_summary(f.us_series(sec_facts()), price=120.0)
    latest = out["annual"][0]
    assert latest["fiscal_year_end"] == "2025-09-30" and latest["revenue_growth_pct"] == 20.0 and latest["eps_growth_pct"] == 50.0
    assert latest["net_margin_pct"] == 12.5 and latest["free_cash_flow"] == 150 and latest["debt_to_equity"] == 0.5
    assert latest["return_on_equity_pct"] == 30.0                           # 150 / average equity of 500
    q = out["quarters"][0]
    assert q["quarter_end"] == "2025-09-30" and q["derived_fourth_quarter"] is True
    assert q["eps_growth_yoy_pct"] == pytest.approx((1.6 / 1.1 - 1) * 100, abs=0.01)   # FY24 Q4 = 4.0 - 2.9 = 1.1
    ttm = out["trailing_four_quarters"]
    assert ttm["eps_diluted"] == 6.0 and ttm["price_to_earnings"] == 20.0
    assert out["revenue_cagr_3y_pct"] is None                               # only two years supplied
    with pytest.raises(f.DataUnavailable):
        f.us_summary(f.us_series({"entityName": "Empty", "facts": {"us-gaap": {}}}))
