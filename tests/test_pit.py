from dataclasses import replace
from datetime import date, timedelta

import pytest

from marketcore.backtest import Bars, Config, Signals, momentum_rotation, run
from marketcore.data import DataUnavailable, pit


def test_quarter_starts_and_month_arithmetic():
    assert pit.quarter_starts(date(2025, 2, 10), date(2025, 10, 5)) == [date(2025, 1, 1), date(2025, 4, 1), date(2025, 7, 1), date(2025, 10, 1)]
    assert pit._month_before(date(2025, 1, 1), 1) == date(2024, 12, 1)
    assert pit._month_before(date(2025, 4, 1), 3) == date(2025, 1, 1)


def test_membership_uses_only_data_before_each_quarter():
    seen = []

    def fetch(month_start):
        seen.append(month_start)
        # Before April 2025 A and B are the most traded; from April on, C overtakes A.
        if month_start < date(2025, 4, 1):
            table = {"A": (300.0, "INE0A"), "B": (200.0, "INE0B"), "C": (100.0, "INE0C")}
        else:
            table = {"A": (100.0, "INE0A"), "B": (200.0, "INE0B"), "C": (300.0, "INE0C")}
        return month_start + timedelta(days=1), table

    out = pit.liquidity_membership(date(2025, 4, 1), date(2025, 9, 30), top_n=2, fetch=fetch)
    assert out["membership"] == {date(2025, 4, 1): ["A", "B"], date(2025, 7, 1): ["B", "C"]}
    assert all(month < date(2025, 7, 1) for month in seen)            # nothing dated in or after the last quarter
    assert sorted(m for m in seen if m >= date(2025, 4, 1)) == [date(2025, 4, 1), date(2025, 5, 1), date(2025, 6, 1)]
    assert out["isin"]["C"] == "INE0C" and out["skipped_quarters"] == []


def test_membership_skips_quarters_without_data():
    def fetch(month_start):
        if month_start < date(2025, 4, 1):
            raise DataUnavailable("no file")
        return month_start, {"A": (1.0, "INE0A")}

    out = pit.liquidity_membership(date(2025, 4, 1), date(2025, 9, 30), top_n=5, fetch=fetch)
    assert out["skipped_quarters"] == ["2025-04-01"] and list(out["membership"]) == [date(2025, 7, 1)]
    with pytest.raises(DataUnavailable):
        pit.liquidity_membership(date(2025, 1, 1), date(2025, 3, 31), fetch=lambda m: (_ for _ in ()).throw(DataUnavailable("x")))


def test_membership_lookup_and_renames():
    m = pit.Membership({date(2025, 4, 1): ["A", "OLDNAME"], date(2025, 7, 1): ["B"]}, rename={"OLDNAME": "NEWNAME"})
    assert m(date(2025, 3, 31)) is None
    assert m(date(2025, 4, 1)) == {"A", "NEWNAME"} and m(date(2025, 6, 30)) == {"A", "NEWNAME"}
    assert m(date(2025, 7, 1)) == {"B"} and m.all_symbols() == {"A", "B", "NEWNAME"}
    current = {"NEWNAME": (1.0, "INE111"), "A": (1.0, "INE222")}
    assert pit.rename_to_current({"OLDNAME", "A", "GONE"}, {"OLDNAME": "INE111", "A": "INE222", "GONE": "INE999"}, current) == {"OLDNAME": "NEWNAME"}


def bars(closes, symbol):
    n = len(closes)
    c = [float(x) for x in closes]
    return Bars(symbol, [date(2025, 1, 1) + timedelta(days=i) for i in range(n)], c, c, c, c, [1.0] * n)


def test_engine_only_buys_eligible_symbols():
    def always(b, _p):
        n = len(b)
        return Signals([True] * n, [False] * n, [None] * n, [0.0] * n)

    data = {"IN": bars([10] * 20, "IN"), "OUT": bars([10] * 20, "OUT")}
    switch = data["IN"].dates[10]
    eligible = pit.Membership({data["IN"].dates[0]: ["IN"], switch: ["IN", "OUT"]})
    cfg = Config(initial_capital=1000, alloc_pct=40, max_position_pct=50, slippage_bps=0)
    result = run(data, always, {}, replace(cfg, eligible=eligible))
    entries = {t.symbol: t.entry_date for t in result.open_positions}
    assert entries["IN"] == data["IN"].dates[1]
    assert entries["OUT"] == data["IN"].dates[11]                     # only after it joins the universe
    assert set(run(data, always, {}, cfg).open_positions[i].entry_date for i in range(2)) == {data["IN"].dates[1]}


def test_rotation_ranks_within_the_universe_and_sells_leavers():
    fast = [100 * 1.02 ** i for i in range(80)]
    slow = [100 * 1.005 ** i for i in range(80)]
    data = {"FAST": bars(fast, "FAST"), "SLOW": bars(slow, "SLOW")}
    dates = data["FAST"].dates
    params = {"lookback": 20, "skip": 5, "top_n": 1, "hold_n": 1, "rebalance_days": 10, "trend_n": 0}
    # FAST is the strongest throughout, but it is only in the universe until bar 45.
    universe = pit.Membership({dates[0]: ["FAST", "SLOW"], dates[45]: ["SLOW"]})
    sig = momentum_rotation(data, {**params, "_eligible": universe})
    assert [i for i, e in enumerate(sig["FAST"].entry) if e] == [20, 30, 40]
    assert [i for i, e in enumerate(sig["FAST"].exit) if e] == [50, 60, 70]     # sold once it leaves
    assert [i for i, e in enumerate(sig["SLOW"].entry) if e] == [50, 60, 70]    # the best of what remains
    without = momentum_rotation(data, params)
    assert not any(without["SLOW"].entry)                                       # with hindsight-free ranking off, FAST always wins
