from datetime import date

from marketcore.backtest import Bars
from marketcore.data import DataUnavailable, history, nse

D1, D2, D3 = date(2026, 11, 6), date(2026, 11, 9), date(2026, 11, 11)


def bars(symbol, dates, closes):
    c = [float(x) for x in closes]
    return Bars(symbol, list(dates), list(c), list(c), list(c), list(c), [100.0] * len(c))


def official(symbol, o, h, l, c, volume=500, series="EQ"):
    return {"TckrSymb": symbol, "SctySrs": series, "OpnPric": str(o), "HghPric": str(h), "LwPric": str(l),
            "ClsPric": str(c), "TtlTradgVol": str(volume)}


def test_missing_latest_session_is_filled_from_the_official_file(monkeypatch):
    universe = {
        "FULL": bars("FULL", [D1, D2, D3], [10, 11, 12]),
        "GAP": bars("GAP", [D1, D2], [100, 102]),
    }
    monkeypatch.setattr(nse, "cm_bhavcopy", lambda day: [official("GAP", 103, 106, 101, 105)])
    report = history.repair_recent_gaps_from_nse(universe)
    assert report == {"repaired": ["GAP 2026-11-11"], "unrepaired": []}
    gap = universe["GAP"]
    assert gap.dates == [D1, D2, D3]
    assert (gap.open[-1], gap.high[-1], gap.low[-1], gap.close[-1], gap.volume[-1]) == (103, 106, 101, 105, 500)


def test_interior_gap_is_inserted_in_order(monkeypatch):
    universe = {
        "FULL": bars("FULL", [D1, D2, D3], [10, 11, 12]),
        "GAP": bars("GAP", [D1, D3], [100, 104]),
    }
    monkeypatch.setattr(nse, "cm_bhavcopy", lambda day: [official("GAP", 101, 103, 100, 102)])
    history.repair_recent_gaps_from_nse(universe)
    assert universe["GAP"].dates == [D1, D2, D3] and universe["GAP"].close == [100, 102, 104]


def test_price_jump_is_not_repaired(monkeypatch):
    universe = {
        "FULL": bars("FULL", [D1, D2, D3], [10, 11, 12]),
        "SPLIT": bars("SPLIT", [D1, D2], [100, 102]),
    }
    monkeypatch.setattr(nse, "cm_bhavcopy", lambda day: [official("SPLIT", 51, 52, 50, 51)])   # halved: likely a split
    report = history.repair_recent_gaps_from_nse(universe)
    assert report["repaired"] == [] and "possible corporate action" in report["unrepaired"][0]
    assert universe["SPLIT"].dates == [D1, D2]


def test_symbol_absent_from_official_file_and_unavailable_file(monkeypatch):
    def make():
        return {"FULL": bars("FULL", [D1, D2, D3], [10, 11, 12]), "GONE": bars("GONE", [D1, D2], [100, 102])}

    monkeypatch.setattr(nse, "cm_bhavcopy", lambda day: [])
    assert "not in the NSE file" in history.repair_recent_gaps_from_nse(make())["unrepaired"][0]

    def unavailable(day):
        raise DataUnavailable("holiday")

    monkeypatch.setattr(nse, "cm_bhavcopy", unavailable)
    universe = make()
    assert history.repair_recent_gaps_from_nse(universe)["repaired"] == []
    assert universe["GONE"].dates == [D1, D2]


def test_nothing_to_repair_makes_no_download(monkeypatch):
    def fail(day):
        raise AssertionError("should not be called")

    monkeypatch.setattr(nse, "cm_bhavcopy", fail)
    universe = {"A": bars("A", [D1, D2, D3], [1, 2, 3]), "B": bars("B", [D1, D2, D3], [4, 5, 6])}
    assert history.repair_recent_gaps_from_nse(universe) == {"repaired": [], "unrepaired": []}
