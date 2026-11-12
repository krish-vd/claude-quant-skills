import math
from datetime import date, datetime, timedelta, timezone

import pytest

from marketcore import cot, earnings, holdings13f, levels, optstrategy
from marketcore.backtest import Bars
from marketcore.options import Leg, black_76


# ---------- option strategy comparison ----------

def test_candidate_strikes_are_on_the_grid_and_ordered():
    legs = optstrategy.candidate_legs("neutral", 25000, 0.15, 14 / 365, 50)
    condor = [s for _, _, s in legs["iron_condor"]]
    assert condor == sorted(condor) and all(s % 50 == 0 for s in condor)
    assert len(set(condor)) == 4
    with pytest.raises(ValueError):
        optstrategy.candidate_legs("sideways", 100, 0.2, 0.1, 1)


def test_probability_of_profit_matches_closed_form():
    f, k, sigma, t = 100.0, 100.0, 0.2, 0.25
    premium = black_76("call", f, k, t, 0.0, sigma).price
    legs = [Leg("call", "buy", 1, premium, k)]
    # Profit when S > K + premium: P = N(d2) evaluated at that breakeven.
    be = k + premium
    d2 = (math.log(f / be) - 0.5 * sigma * sigma * t) / (sigma * math.sqrt(t))
    expected = 0.5 * (1 + math.erf(d2 / math.sqrt(2))) * 100
    assert optstrategy.probability_of_profit(legs, f, sigma, t) == pytest.approx(expected, abs=0.1)
    short_put = [Leg("put", "sell", 1, black_76("put", f, 90, t, 0, sigma).price, 90)]
    assert optstrategy.probability_of_profit(short_put, f, sigma, t) > 80


def test_compare_uses_market_prices_when_given():
    rows = optstrategy.compare("bullish", 25000, 0.15, 14, 65, 50)
    names = {r["structure"] for r in rows}
    assert names == {"long_call", "bull_call_spread", "bull_put_spread", "short_put"}
    spread = next(r for r in rows if r["structure"] == "bull_call_spread")
    assert spread["max_loss"] < 0 < spread["max_profit"] and spread["pricing"] == "model" and spread["position_delta"] > 0
    short_put = next(r for r in rows if r["structure"] == "short_put")
    assert short_put["max_loss"] < 0 and not short_put["unlimited_loss"]       # bounded at a price of zero
    market = optstrategy.compare("bullish", 25000, 0.15, 14, 65, 50, price_lookup=lambda kind, k: 123.0)
    assert all(l["premium"] == 123.0 for r in market for l in r["legs"]) and market[0]["pricing"] == "market"


# ---------- results reactions ----------

def bars(closes, opens=None, start=date(2026, 1, 5)):
    n = len(closes)
    dates = []
    d = start
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)
    c = [float(x) for x in closes]
    return Bars("T", dates, list(opens or c), c, c, c, [100.0] * n)


IST = timezone(timedelta(hours=5, minutes=30))


def test_reaction_day_depends_on_announcement_time():
    b = bars([100.0] * 10)
    during = datetime(2026, 1, 7, 13, 0, tzinfo=IST)     # Wednesday, market open
    after = datetime(2026, 1, 7, 17, 0, tzinfo=IST)      # after the close: Thursday reacts
    friday_evening = datetime(2026, 1, 9, 19, 0, tzinfo=IST)
    assert b.dates[earnings.reaction_index(b.dates, during, "IN")] == date(2026, 1, 7)
    assert b.dates[earnings.reaction_index(b.dates, after, "IN")] == date(2026, 1, 8)
    assert b.dates[earnings.reaction_index(b.dates, friday_evening, "IN")] == date(2026, 1, 12)
    us_after = datetime(2026, 1, 7, 21, 30, tzinfo=timezone.utc)   # 16:30 New York
    assert b.dates[earnings.reaction_index(b.dates, us_after, "US")] == date(2026, 1, 8)


def test_reaction_measures_by_hand():
    closes = [100.0] * 5 + [110.0] + [110.0 + i for i in range(1, 25)]
    opens = [100.0] * 5 + [104.0] + closes[6:]
    b = bars(closes, opens)
    idx = bars([1000.0] * 5 + [1010.0] + [1010.0] * 24)
    ev = [{"period_end": "2025-12-31", "announced": datetime(2026, 1, 9, 18, 0, tzinfo=IST)}]   # reacts Monday 12 Jan (index 5)
    row = earnings.reactions(b, ev, "IN", idx)[0]
    assert row["reaction_date"] == "2026-01-12" and row["gap_pct"] == 4.0 and row["day_move_pct"] == 10.0
    assert row["day_move_vs_index_pct"] == 9.0
    assert row["drift_5d_pct"] == pytest.approx(5 / 110 * 100, abs=0.01) and row["drift_20d_pct"] == pytest.approx(20 / 110 * 100, abs=0.01)
    s = earnings.summarise([row])
    assert s["up_reactions"] == 1 and s["average_absolute_day_move_pct"] == 10.0


# ---------- levels ----------

def test_swings_zones_and_structure():
    # Up-down waves with rising highs and rising lows.
    closes = []
    for wave in range(6):
        base = 100 + wave * 5
        closes += [base + i for i in range(8)] + [base + 7 - i for i in range(1, 6)]
    b = Bars("T", [date(2025, 1, 1) + timedelta(days=i) for i in range(len(closes))], closes, closes, closes, closes, [1.0] * len(closes))
    highs, lows = levels.swings(b, k=3)
    assert len(highs) >= 4 and len(lows) >= 4
    out = levels.analyse(b, k=3)
    assert out["structure"] == "higher highs and higher lows"
    assert all(z["high"] < out["close"] for z in out["support_zones"])
    assert levels.zones([(0, 100.0), (5, 101.0), (9, 110.0)], 1.5) == [
        {"low": 100.0, "high": 101.0, "touches": 2, "last_index": 5}, {"low": 110.0, "high": 110.0, "touches": 1, "last_index": 9}]


# ---------- commitments of traders ----------

def test_cot_net_positions_and_index():
    def row(d, oi, nl, ns, cl, cs):
        return {"report_date_as_yyyy_mm_dd": d + "T00:00:00.000", "open_interest_all": oi, "noncomm_positions_long_all": nl,
                "noncomm_positions_short_all": ns, "comm_positions_long_all": cl, "comm_positions_short_all": cs,
                "nonrept_positions_long_all": 0, "nonrept_positions_short_all": 0, "market_and_exchange_names": "GOLD"}
    rows = [row("2026-11-03", 1000, 600, 100, 100, 600), row("2026-10-27", 1000, 400, 200, 200, 400),
            row("2026-10-20", 1000, 300, 300, 300, 300)]
    out = cot.analyse(rows)
    assert out["speculator_net"] == 500 and out["speculator_net_pct_of_oi"] == 50.0
    assert out["speculator_cot_index"] == 100.0 and out["commercial_cot_index"] == 0.0
    assert out["speculator_net_change_1w"] == 300 and out["history"][0]["date"] == "2026-10-20"
    assert set(cot.MARKETS) >= {"gold", "crude_wti", "sp500_emini"}


# ---------- 13F ----------

INFO = b"""<?xml version="1.0"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
 <infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip>
  <value>1000</value><shrsOrPrnAmt><sshPrnamt>10</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
 <infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>037833100</cusip>
  <value>500</value><shrsOrPrnAmt><sshPrnamt>5</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
 <infoTable><nameOfIssuer>COCA COLA</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>191216100</cusip>
  <value>500</value><shrsOrPrnAmt><sshPrnamt>50</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>
</informationTable>"""


def test_13f_parse_aggregate_compare():
    rows = holdings13f.parse_infotable(INFO)
    assert len(rows) == 3 and rows[0]["issuer"] == "APPLE INC"
    prev = [{"issuer": "APPLE INC", "cusip": "037833100", "put_call": None, "value": 1000, "shares": 10, "class": "COM", "share_type": "SH"},
            {"issuer": "OLDCO", "cusip": "000000000", "put_call": None, "value": 9, "shares": 9, "class": "COM", "share_type": "SH"}]
    out = holdings13f.compare(rows, prev)
    apple = out["top_holdings"][0]
    assert apple["shares"] == 15 and apple["share_change_pct"] == 50.0 and apple["weight_pct"] == 75.0
    assert [r["issuer"] for r in out["new_positions"]] == ["COCA COLA"] and out["exited_positions"][0]["issuer"] == "OLDCO"


def test_13f_needs_a_contact(monkeypatch):
    monkeypatch.delenv("MARKET_SKILLS_SEC_USER_AGENT", raising=False)
    with pytest.raises(holdings13f.DataUnavailable, match="contact email"):
        holdings13f._require_agent()
