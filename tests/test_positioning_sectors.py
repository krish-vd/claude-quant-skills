from datetime import date, timedelta

import pytest

from marketcore import positioning as pos
from marketcore import sectors as sec
from marketcore.backtest import Bars

# The real NSE participant OI file for 11 Nov 2026.
OI_FILE = '''""Participant wise Open Interest (no. of contracts) in Equity Derivatives as on Nov 11, 2026"",,,,,,,,,,,,,,
Client Type,Future Index Long,Future Index Short,Future Stock Long,Future Stock Short       ,Option Index Call Long,Option Index Put Long,Option Index Call Short,Option Index Put Short,Option Stock Call Long,Option Stock Put Long,Option Stock Call Short,Option Stock Put Short,Total Long Contracts      ,Total Short Contracts
Client,172162,105154,3139266,347050,3045743,2722311,2706602,3140961,1965989,1233953,1123164,1147025,12279424,8569956
DII,54376,27224,340835,4329625,2610,107042,1550,1200,2775,41308,434434,34359,548946,4828392
FII,57226,127639,3575532,2540154,722656,1094827,958257,647495,330474,415049,426899,322256,6195764,5022700
Pro,26450,50197,704626,543430,1052450,954754,1157051,1089278,1328053,1037804,1642794,1224474,5104137,5707224
TOTAL,310214,310214,7760259,7760259,4823459,4878935,4823459,4878935,3627291,2728114,3627291,2728114,24128272,24128272
'''


def test_participant_file_parses_and_balances():
    table = pos.parse_participant_oi(OI_FILE)
    assert table["FII"]["Future Index Long"] == 57226 and table["FII"]["Future Index Short"] == 127639
    assert table["DII"]["Future Stock Short"] == 4329625          # header has trailing spaces in the file
    net = pos.net_positions(table)
    assert net["FII"]["index_futures"] == {"long": 57226, "short": 127639, "net": -70413, "long_pct": 30.96}
    # Every contract has two sides, so the four groups net to zero - up to rounding in NSE's file:
    # on this day the index call shorts add up to one contract more than the stated total.
    for group in pos.PAIRS:
        assert abs(sum(net[who][group]["net"] for who in pos.PARTICIPANTS)) <= 2
    assert sum(net[who]["index_futures"]["net"] for who in pos.PARTICIPANTS) == 0


def test_compare_two_days():
    today = pos.parse_participant_oi(OI_FILE)
    yesterday = pos.parse_participant_oi(OI_FILE.replace("FII,57226,127639", "FII,60000,120000"))
    change = pos.compare(today, yesterday)
    assert change["FII"]["index_futures"] == -70413 - (-60000)   # FIIs got 10,413 contracts more net short
    assert change["Client"]["index_futures"] == 0


def test_bad_participant_file():
    with pytest.raises(pos.DataUnavailable):
        pos.parse_participant_oi("<html>blocked</html>")


def test_cash_flow_parsing_and_log(tmp_path):
    payload = [
        {"buyValue": "19704.39", "category": "DII", "date": "11-Nov-2026", "netValue": "-8434.53", "sellValue": "28138.92"},
        {"buyValue": "30087.21", "category": "FII/FPI", "date": "11-Nov-2026", "netValue": "12563.33", "sellValue": "17523.88"},
    ]
    flow = pos.parse_cash_flows(payload)
    assert flow["date"] == "2026-11-11" and flow["FII"]["net"] == 12563.33 and flow["DII"]["net"] == -8434.53
    assert flow["FII"]["buy"] - flow["FII"]["sell"] == pytest.approx(flow["FII"]["net"])
    path = tmp_path / "log.json"
    assert len(pos.log_cash_flows(flow, path)) == 1
    assert len(pos.log_cash_flows(flow, path)) == 1               # same date is not duplicated
    later = {**flow, "date": "2026-11-12"}
    assert [r["date"] for r in pos.log_cash_flows(later, path)] == ["2026-11-11", "2026-11-12"]
    with pytest.raises(pos.DataUnavailable):
        pos.parse_cash_flows([payload[0]])


def bars(closes, symbol):
    n = len(closes)
    c = [float(x) for x in closes]
    return Bars(symbol, [date(2025, 1, 1) + timedelta(days=i) for i in range(n)], c, c, c, c, [1.0] * n)


def test_sector_ranking_and_rank_change():
    bench = bars([100.0] * 300, "BENCH")
    steady = bars([100 * 1.002 ** i for i in range(300)], "STEADY")                 # always strong
    late = bars([100.0] * 279 + [100 * 1.02 ** i for i in range(1, 22)], "LATE")     # flat, then surges in the last 21
    weak = bars([100 * 0.999 ** i for i in range(300)], "WEAK")
    rows = {r["group"]: r for r in sec.rank_groups({"Steady": steady, "Late": late, "Weak": weak}, bench)}
    assert rows["Weak"]["rank"] == 3 and rows["Weak"]["above_sma200"] is False
    assert rows["Steady"]["rank_before"] == 1 and rows["Late"]["rank_before"] == 2   # before the surge, Late was flat
    # After 21 sessions at 2% a day Late shows +51.6% over every period (composite 51.6),
    # ahead of Steady's 0.2 x 4.3 + 0.4 x 13.4 + 0.2 x 28.6 + 0.2 x 65.5 = 25.0.
    assert rows["Late"]["rank"] == 1 and rows["Late"]["rank_change"] == 1
    assert rows["Steady"]["rank"] == 2 and rows["Steady"]["rank_change"] == -1
    assert rows["Late"]["relative_strength_score"] == pytest.approx((1.02 ** 21 - 1) * 100, abs=0.01)
    assert rows["Steady"]["returns_pct"]["1m"] == pytest.approx((1.002 ** 21 - 1) * 100, abs=0.01)
    assert rows["Steady"]["excess_vs_benchmark_pct"]["3m"] == rows["Steady"]["returns_pct"]["3m"]   # benchmark is flat


def test_composite_by_hand():
    bench = bars([100.0] * 300, "B")
    closes = [100.0] * 300
    closes[-1] = 120.0                         # every period shows +20%
    row = sec.rank_groups({"X": bars(closes, "X")}, bench)[0]
    assert row["relative_strength_score"] == pytest.approx(20.0)   # weights sum to 1
    short = sec.rank_groups({"S": bars([100.0] * 100, "S")}, bench)[0]
    assert short["relative_strength_score"] is None and short["rank"] is None   # no 12-month history


def test_industry_breadth():
    up = [100 * 1.002 ** i for i in range(100)]
    down = [100 * 0.998 ** i for i in range(100)]
    universe = {f"U{i}": bars(up, f"U{i}") for i in range(3)} | {f"D{i}": bars(down, f"D{i}") for i in range(3)} | {"SOLO": bars(up, "SOLO")}
    details = {**{f"U{i}": {"industry": "Tech"} for i in range(3)}, **{f"D{i}": {"industry": "Metals"} for i in range(3)},
               "SOLO": {"industry": "Lonely"}}
    rows = sec.industry_breadth(universe, details)
    assert [r["industry"] for r in rows] == ["Tech", "Metals"]      # the single-member industry is left out
    assert rows[0]["pct_above_sma50"] == 100.0 and rows[1]["pct_above_sma50"] == 0.0


def test_ratio_and_parity_by_hand():
    gold = bars([2000.0] * 9 + [4000.0], "GOLD")
    silver = bars([25.0] * 9 + [50.0], "SILVER")
    summary = sec.ratio_summary("gold/silver", gold, silver)
    assert summary["value"] == 80.0 and summary["sessions_in_history"] == 10

    # 4,000 USD/oz x 88 INR/USD = 3,52,000 INR/oz; / 31.1034768 g x 10 g = 1,13,170.63 per 10 g
    parity = sec.import_parity("gold", 4000, 88, local_price=121000)
    assert parity["converted_price"] == pytest.approx(113170.63, abs=0.01)
    assert parity["local_premium_pct"] == pytest.approx((121000 / 113170.63 - 1) * 100, abs=0.01)
    assert sec.import_parity("silver", 50, 88)["converted_price"] == pytest.approx(50 * 88 * 1000 / 31.1034768, abs=0.01)
    assert sec.import_parity("copper", 5, 88)["converted_price"] == pytest.approx(5 * 88 / 0.45359237, abs=0.01)
    assert sec.import_parity("crude", 80, 88)["converted_price"] == 7040.0
    with pytest.raises(ValueError):
        sec.import_parity("uranium", 1, 1)
