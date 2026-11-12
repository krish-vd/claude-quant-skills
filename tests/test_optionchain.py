from datetime import date

import pytest

from marketcore.optionchain import StrikeRow, analyse, build_chain, expiries, max_pain, parity_forward
from marketcore.options import black_76


def opt(strike, kind, price, oi, change=0, volume=10, expiry="2026-11-26", symbol="NIFTY"):
    return {"TckrSymb": symbol, "FinInstrmTp": "IDO", "XpryDt": expiry, "StrkPric": f"{strike:.2f}", "OptnTp": kind,
            "ClsPric": str(price), "SttlmPric": str(price), "OpnIntrst": str(oi), "ChngInOpnIntrst": str(change),
            "TtlTradgVol": str(volume), "UndrlygPric": "100.00", "NewBrdLotQty": "10"}


def fut(price, expiry="2026-11-26", symbol="NIFTY"):
    return {"TckrSymb": symbol, "FinInstrmTp": "IDF", "XpryDt": expiry, "StrkPric": "", "OptnTp": "",
            "ClsPric": str(price), "SttlmPric": str(price), "OpnIntrst": "1000", "ChngInOpnIntrst": "0",
            "TtlTradgVol": "5", "UndrlygPric": "100.00", "NewBrdLotQty": "10"}


ROWS = [
    opt(90, "CE", 11.0, 100), opt(90, "PE", 0.5, 300, change=50),
    opt(100, "CE", 3.0, 200, change=80), opt(100, "PE", 2.5, 200),
    opt(110, "CE", 0.4, 400), opt(110, "PE", 10.2, 100),
    opt(100, "CE", 9.0, 999, expiry="2026-12-31"),
    opt(100, "CE", 1.0, 999, symbol="OTHER"),
]


def test_expiries_and_chain_building():
    assert expiries(ROWS, "nifty") == ["2026-11-26", "2026-12-31"]
    chain, info = build_chain(ROWS, "NIFTY", "2026-11-26")
    assert [r.strike for r in chain] == [90.0, 100.0, 110.0]
    assert (chain[1].call_oi, chain[1].put_oi, chain[1].call_oi_change) == (200, 200, 80)
    assert info["lot_size"] == 10 and info["spot"] == 100.0


def test_max_pain_by_hand():
    chain, _ = build_chain(ROWS, "NIFTY", "2026-11-26")
    # At 90:  puts 200x10 + 100x20 = 4,000
    # At 100: calls 100x10 = 1,000 ; puts 100x10 = 1,000 -> 2,000
    # At 110: calls 100x20 + 200x10 = 4,000
    assert max_pain(chain) == 100.0
    assert max_pain([]) is None


def test_parity_forward():
    chain, _ = build_chain(ROWS, "NIFTY", "2026-11-26")
    forward, strike = parity_forward(chain, 0.0, 0.0)
    assert strike == 100.0 and forward == pytest.approx(100.5)       # 100 + (3.0 - 2.5)
    untraded = [StrikeRow(100.0, call_price=3.0, put_price=2.5)]     # no volume: stale prices are ignored
    assert parity_forward(untraded, 0.0, 0.0) is None


def test_analyse_ratios_and_forward_source():
    out = analyse(ROWS, "NIFTY", "2026-11-26", date(2026, 11, 12))
    assert out["pcr_open_interest"] == pytest.approx(600 / 700, abs=1e-3)
    assert out["days_to_expiry"] == 14 and out["lot_size"] == 10
    assert out["forward"] == 100.5 and "parity" in out["forward_source"]
    assert out["atm_strike"] == 100.0 and out["atm_straddle_price"] == 5.5
    assert out["straddle_implied_move_pct"] == pytest.approx(5.5 / 100.5 * 100, abs=0.01)
    assert out["highest_call_oi"][0] == {"strike": 110.0, "oi_units": 400, "oi_lots": 40, "oi_change_units": 0}
    assert out["highest_put_oi"][0]["strike"] == 90.0
    assert out["largest_call_oi_additions"] == [{"strike": 100.0, "oi_change_units": 80}]

    with_future = analyse(ROWS + [fut(101.0)], "NIFTY", "2026-11-26", date(2026, 11, 12))
    assert with_future["forward"] == 101.0 and "futures" in with_future["forward_source"]


def test_atm_implied_volatility_recovers_the_input():
    t, vol, f = 14 / 365.0, 0.15, 100.0
    rows = [
        opt(100, "CE", black_76("call", f, 100, t, 0.0, vol).price, 100),
        opt(100, "PE", black_76("put", f, 100, t, 0.0, vol).price, 100),
        fut(f),
    ]
    out = analyse(rows, "NIFTY", "2026-11-26", date(2026, 11, 12))
    assert out["atm_iv_call_pct"] == pytest.approx(15.0, abs=0.01)
    assert out["atm_iv_put_pct"] == pytest.approx(15.0, abs=0.01)


def test_unknown_expiry_is_an_error():
    with pytest.raises(ValueError):
        analyse(ROWS, "NIFTY", "2030-01-01", date(2026, 11, 12))
