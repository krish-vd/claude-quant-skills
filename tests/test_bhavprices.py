"""Bars rebuilt from NSE bhavcopies, and the engine's handling of stocks that stop trading."""
from datetime import date, timedelta

import pytest

from marketcore.backtest import Bars, Config, Signals, run
from marketcore.data import DataUnavailable, bhavprices


def raw_rows(closes, volume=10.0, start=date(2025, 1, 6)):
    """(date, open, high, low, close, volume) on consecutive days, open = high = low = close."""
    return [(start + timedelta(days=i), c, c, c, c, volume) for i, c in enumerate(closes)]


# ---------- adjustment ----------

def test_split_divides_earlier_prices_and_multiplies_earlier_volume():
    # 100, 100, 100, then a 2-for-1 split on day 4 where the price becomes 50.
    raw = raw_rows([100, 100, 100, 50, 50])
    action = {"ex_date": raw[3][0], "type": "split", "ratio": 2.0}
    bars, applied, jumps = bhavprices.adjust("X", raw, [action])
    assert bars.close == [50.0, 50.0, 50.0, 50.0, 50.0]
    assert bars.volume == [20.0, 20.0, 20.0, 10.0, 10.0]   # 10 / 0.5 on the three earlier days
    assert applied == ["2025-01-09 split x2"] and jumps == []


def test_bonus_one_for_four_scales_earlier_prices_by_point_eight():
    # 1 bonus share per 4 held (ratio 0.25): 1 / (1 + 0.25) = 0.8. A price of 100 becomes 80 after.
    raw = raw_rows([100, 100, 80, 80])
    bars, _, jumps = bhavprices.adjust("X", raw, [{"ex_date": raw[2][0], "type": "bonus", "ratio": 0.25}])
    assert bars.close == pytest.approx([80.0, 80.0, 80.0, 80.0])
    assert jumps == []


def test_reverse_split_multiplies_earlier_prices():
    # Consolidation 5 old shares into 1 is ratio 0.2: earlier prices are divided by 0.2, i.e. x5.
    raw = raw_rows([10, 10, 50, 50])
    bars, _, _ = bhavprices.adjust("X", raw, [{"ex_date": raw[2][0], "type": "split", "ratio": 0.2}])
    assert bars.close == pytest.approx([50.0, 50.0, 50.0, 50.0])


def test_an_unadjusted_big_move_is_flagged_not_hidden():
    bars, applied, jumps = bhavprices.adjust("X", raw_rows([100, 100, 50, 50]), [])
    assert applied == [] and jumps == ["2025-01-08 -50%"]


def test_action_outside_the_data_changes_nothing():
    raw = raw_rows([100, 101, 102])
    bars, applied, _ = bhavprices.adjust("X", raw, [{"ex_date": date(2030, 1, 1), "type": "split", "ratio": 2.0},
                                                    {"ex_date": date(2020, 1, 1), "type": "split", "ratio": 2.0}])
    assert bars.close == [100.0, 101.0, 102.0] and applied == []


def test_usable_actions_dedupes_and_reports_what_it_cannot_apply():
    day = date(2025, 3, 3)
    rows = [{"ex_date": day, "type": "split", "ratio": 2.0, "subject": "a"},
            {"ex_date": day, "type": "split", "ratio": 2.0, "subject": "a"},
            {"ex_date": date(2025, 4, 1), "type": "demerger", "ratio": None, "subject": "Demerger of the pharma business"},
            {"ex_date": date(2025, 5, 1), "type": "dividend", "ratio": None, "amount": 5.0, "subject": "Dividend"}]
    apply, notes = bhavprices.usable_actions(rows)
    assert len(apply) == 1 and apply[0]["type"] == "split"
    assert notes == ["2025-04-01 demerger: Demerger of the pharma business"]


# ---------- reading the files ----------

def test_session_rows_reads_the_old_format_and_prefers_eq_over_be(monkeypatch):
    rows = [{"SYMBOL": "AAA ", "SERIES": "BE", "OPEN": "9", "HIGH": "9", "LOW": "9", "CLOSE": "9", "TOTTRDQTY": "5", "": ""},
            {"SYMBOL": "AAA", "SERIES": "EQ", "OPEN": "10", "HIGH": "12", "LOW": "9.5", "CLOSE": "11", "TOTTRDQTY": "100", "ISIN": "INE1"},
            {"SYMBOL": "ETF", "SERIES": "N1", "OPEN": "1", "HIGH": "1", "LOW": "1", "CLOSE": "1", "TOTTRDQTY": "1"},
            {"SYMBOL": "BZZ", "SERIES": "BZ", "OPEN": "3", "HIGH": "3", "LOW": "3", "CLOSE": "3", "TOTTRDQTY": "7", "ISIN": "INE2"}]
    monkeypatch.setattr(bhavprices, "_rows", lambda url, name: rows if "old" in name else (_ for _ in ()).throw(DataUnavailable("x")))
    out = bhavprices.session_rows(date(2019, 9, 19))
    assert out == {"AAA": (10.0, 12.0, 9.5, 11.0, 100.0, "INE1"), "BZZ": (3.0, 3.0, 3.0, 3.0, 7.0, "INE2")}


def test_session_rows_reads_the_new_format_and_orders_by_date(monkeypatch):
    seen = []
    new = [{"TckrSymb": "AAA", "SctySrs": "EQ", "OpnPric": "10", "HghPric": "12", "LwPric": "9", "ClsPric": "11", "TtlTradgVol": "50", "ISIN": "INE1"}]

    def fake(url, name):
        seen.append(name)
        if "old" in name:
            raise DataUnavailable("old file should not be needed")
        return new
    monkeypatch.setattr(bhavprices, "_rows", fake)
    assert bhavprices.session_rows(date(2025, 6, 2)) == {"AAA": (10.0, 12.0, 9.0, 11.0, 50.0, "INE1")}
    assert seen == ["nse_cm_20250602.zip"]    # on a new-format date the first request is the new format


def test_session_rows_raises_when_no_file_exists(monkeypatch):
    monkeypatch.setattr(bhavprices, "_rows", lambda url, name: (_ for _ in ()).throw(DataUnavailable("404")))
    with pytest.raises(DataUnavailable):
        bhavprices.session_rows(date(2025, 1, 26))


def test_collect_retries_once_and_counts_holidays():
    calls = {}

    def fetch(day):
        calls[day] = calls.get(day, 0) + 1
        if day == date(2025, 1, 7):
            raise DataUnavailable("holiday")
        if day == date(2025, 1, 8) and calls[day] == 1:
            raise DataUnavailable("dropped connection")
        return {"AAA": (1.0, 2.0, 0.5, 1.5, 9.0)}

    rows, info = bhavprices.collect({"AAA", "ZZZ"}, date(2025, 1, 6), date(2025, 1, 10), fetch=fetch, workers=1)
    assert [r[0].day for r in rows["AAA"]] == [6, 8, 9, 10]      # the 7th was a holiday; the 8th succeeded on retry
    assert rows["ZZZ"] == []
    assert info == {"sessions_read": 4, "days_without_file": 1}


def test_adjusted_bars_end_to_end_and_reports_missing_symbols():
    days = {date(2025, 1, 6) + timedelta(days=i): c for i, c in enumerate([100, 100, 50, 50, 50])}
    out, info = bhavprices.adjusted_bars(
        {"AAA", "GONE"}, date(2025, 1, 6), date(2025, 1, 10),
        get_actions=lambda s: [{"ex_date": date(2025, 1, 8), "type": "split", "ratio": 2.0, "subject": "s"}],
        fetch=lambda d: {"AAA": (days[d], days[d], days[d], days[d], 1.0)}, workers=1)
    assert out["AAA"].close == [50.0] * 5
    assert info["not_in_bhavcopies"] == ["GONE"]
    assert info["symbols"]["AAA"]["adjusted_for"] == ["2025-01-08 split x2"]


def test_a_failed_corporate_actions_lookup_is_reported_not_fatal():
    def broken(_symbol):
        raise DataUnavailable("blocked")
    out, info = bhavprices.adjusted_bars({"AAA"}, date(2025, 1, 6), date(2025, 1, 7), get_actions=broken,
                                         fetch=lambda d: {"AAA": (1.0, 1.0, 1.0, 1.0, 1.0)}, workers=1)
    assert "AAA" in out and info["symbols"]["AAA"]["corporate_actions_unavailable"] == "blocked"


def test_demerger_drop_is_treated_as_a_transfer_of_value_but_a_real_crash_is_kept():
    # 100, 100, then a 50% fall on the demerger date: holders received shares worth the drop.
    raw = raw_rows([100, 100, 50, 50])
    bars, applied, jumps = bhavprices.adjust("X", raw, [], schemes=[raw[2][0]])
    assert bars.close == pytest.approx([50.0] * 4) and jumps == []
    assert "demerger/scheme" in applied[0]
    # The same fall with no scheme on that date is a real loss and stays, flagged.
    bars, applied, jumps = bhavprices.adjust("X", raw, [])
    assert bars.close == [100.0, 100.0, 50.0, 50.0] and jumps == ["2025-01-08 -50%"]


def test_a_small_move_on_a_scheme_date_is_left_alone():
    raw = raw_rows([100, 100, 95, 95])
    bars, applied, _ = bhavprices.adjust("X", raw, [], schemes=[raw[2][0]])
    assert bars.close == [100.0, 100.0, 95.0, 95.0] and applied == []


def test_scheme_dates_picks_demergers_and_arrangements_only():
    rows = [{"ex_date": date(2025, 1, 1), "type": "demerger", "subject": "Demerger"},
            {"ex_date": date(2025, 2, 1), "type": "other", "subject": "Scheme Of Arrangement"},
            {"ex_date": date(2025, 3, 1), "type": "other", "subject": "Annual General Meeting"},
            {"ex_date": date(2025, 4, 1), "type": "dividend", "subject": "Dividend - Rs 5"}]
    assert bhavprices.scheme_dates(rows) == [date(2025, 1, 1), date(2025, 2, 1)]


def test_successor_follows_a_rename_by_isin():
    tables = {date(2025, 1, 6): {"OLD": (1, 1, 1, 1, 1, "INE9")},
              date(2025, 1, 7): {"NEW": (1, 1, 1, 1, 1, "INE9"), "OTHER": (1, 1, 1, 1, 1, "INE5")}}

    def fetch(day):
        if day in tables:
            return tables[day]
        raise DataUnavailable("none")
    assert bhavprices.successor("OLD", date(2025, 1, 6), fetch) == "NEW"
    # Still listed under the same name the next session: a gap, not a rename.
    tables[date(2025, 1, 7)]["OLD"] = (1, 1, 1, 1, 1, "INE9")
    assert bhavprices.successor("OLD", date(2025, 1, 6), fetch) is None
    # Different ISIN next session (for example after a face-value split): not followed.
    tables[date(2025, 1, 7)] = {"NEW": (1, 1, 1, 1, 1, "INE7")}
    assert bhavprices.successor("OLD", date(2025, 1, 6), fetch) is None


def test_a_renamed_stock_is_continued_and_its_actions_come_from_both_names():
    days = [date(2025, 1, 6) + timedelta(days=i) for i in range(5)]       # Mon..Fri
    price = {days[0]: 100, days[1]: 100, days[2]: 100, days[3]: 50, days[4]: 50}

    def fetch(day):
        if day not in price:
            raise DataUnavailable("none")
        name = "OLD" if day <= days[1] else "NEW"            # renamed after Tuesday, same ISIN
        return {name: (price[day],) * 4 + (1.0, "INE9")}

    def actions(symbol):    # the 2-for-1 split is filed under the NEW name
        return [{"ex_date": days[3], "type": "split", "ratio": 2.0, "subject": "s"}] if symbol == "NEW" else []

    out, info = bhavprices.adjusted_bars({"OLD"}, days[0], days[0] + timedelta(days=40), get_actions=actions, fetch=fetch, workers=1)
    assert out["OLD"].close == [50.0] * 5 and len(out["OLD"]) == 5
    assert info["symbols"]["OLD"]["continued_as"] == ["NEW"]


# ---------- the engine when a stock stops trading ----------

def flat_bars(symbol, n, price=100.0, start=date(2025, 1, 1)):
    return Bars(symbol, [start + timedelta(days=i) for i in range(n)], [price] * n, [price] * n,
                [price] * n, [price] * n, [1000.0] * n)


def entry_on(bar_number):
    def strategy(bars, _params):
        n = len(bars)
        return Signals([i == bar_number for i in range(n)], [False] * n, [None] * n, [0.0] * n)
    return strategy


def two_stock_run(dead_bars, haircut=0.0, max_positions=1):
    """DEAD enters at bar 0 (fills at bar 1). LIVE would enter at bar 15 (fills at bar 16)."""
    data = {"DEAD": flat_bars("DEAD", dead_bars), "LIVE": flat_bars("LIVE", 30)}

    def strategy(bars, params):
        return entry_on(0 if bars.symbol == "DEAD" else 15)(bars, params)
    cfg = Config(slippage_bps=0.0, max_positions=max_positions, delisting_haircut_pct=haircut)
    return run(data, strategy, {}, cfg)


def test_a_held_stock_that_stops_trading_is_closed_on_its_last_session():
    result = two_stock_run(dead_bars=10)
    dead = next(t for t in result.trades if t.symbol == "DEAD")
    assert dead.exit_reason == "delisted" and dead.exit_date == date(2025, 1, 10)   # bar 9 is the last
    assert dead.shares == 1000 and dead.pnl == 0                                    # 10% of 1,000,000 at 100; flat price, no haircut


def test_the_freed_slot_can_be_used_afterwards():
    # With one slot, LIVE can only be bought on bar 16 if DEAD was really closed on bar 9.
    result = two_stock_run(dead_bars=10, max_positions=1)
    assert [t.symbol for t in result.open_positions] == ["LIVE"]


def test_delisting_haircut_is_a_loss_on_the_last_close():
    # 1,000 shares at 100; a 100% haircut sells at 0, losing 100,000.
    assert next(t for t in two_stock_run(10, haircut=100.0).trades if t.symbol == "DEAD").pnl == pytest.approx(-100_000.0)
    # A 25% haircut sells at 75, losing 25,000.
    assert next(t for t in two_stock_run(10, haircut=25.0).trades if t.symbol == "DEAD").pnl == pytest.approx(-25_000.0)


def test_a_short_gap_at_the_end_is_a_lagging_feed_not_a_delisting():
    # DEAD stops 3 sessions before the data ends (inside the 5-session grace): still held, valued at its last close.
    result = two_stock_run(dead_bars=27)
    assert not any(t.exit_reason == "delisted" for t in result.trades)
    assert "DEAD" in {t.symbol for t in result.open_positions}
