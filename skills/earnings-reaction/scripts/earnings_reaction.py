#!/usr/bin/env python3
"""How stocks react to their results: for one stock, every past results announcement
with the gap, the day's move and the drift over the next 5 and 20 sessions against
the index; or, for an index, the companies that reported in the last few days and
how the market took it."""
import argparse
import json
import pathlib
import sys
import time
from datetime import date, datetime, timedelta, timezone

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore import earnings, fundamentals  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.data.history import daily_bars, load_universe, nse_index_members  # noqa: E402

INDEX = {"IN": "^NSEI", "US": "^GSPC"}


def history(symbol: str, market: str) -> dict:
    bars = daily_bars(symbol, "10y", market)
    index = daily_bars(INDEX[market], "10y", "US")
    events = earnings.india_events(symbol) if market == "IN" else earnings.us_events(symbol)
    rows = earnings.reactions(bars, events, market, index)
    return {"symbol": symbol.upper(), "summary": earnings.summarise(rows), "events": rows[::-1]}


def recent(index_name: str, days: int, with_growth: bool) -> dict:
    members = nse_index_members(index_name)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out, failed = [], []
    index_bars = daily_bars(INDEX["IN"], "1y", "US")
    for m in members:
        try:
            events = [e for e in earnings.india_events(m["symbol"]) if e["announced"] >= cutoff]
            if not events:
                continue
            bars = daily_bars(m["symbol"], "1y", "IN")
            rows = earnings.reactions(bars, events[-1:], "IN", index_bars)
            if not rows:
                continue
            row = {"symbol": m["symbol"], "company": m["company"], "industry": m["industry"], **rows[0]}
            if with_growth:
                try:
                    g = fundamentals.india_growth_snapshot(m["symbol"])
                    row.update({k: g[k] for k in ("revenue_growth_yoy_pct", "net_profit_growth_yoy_pct", "eps_growth_yoy_pct")})
                except DataUnavailable:
                    pass
            out.append(row)
        except DataUnavailable:
            failed.append(m["symbol"])
        time.sleep(0.1)
    out.sort(key=lambda r: -(r.get("day_move_vs_index_pct") or r["day_move_pct"]))
    return {"index": index_name, "window_days": days, "reported": len(out), "results": out, "failed": failed}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--market", choices=["IN", "US"], default="IN")
    p.add_argument("--symbol", help="one stock: its full reaction history")
    p.add_argument("--recent-index", help="India: scan an index for companies that reported recently, e.g. nifty100")
    p.add_argument("--days", type=int, default=7, help="with --recent-index: look back this many days")
    p.add_argument("--with-growth", action="store_true", help="with --recent-index: add revenue and profit growth (slower)")
    a = p.parse_args()
    if bool(a.symbol) == bool(a.recent_index):
        p.error("give exactly one of --symbol or --recent-index")
    try:
        out = history(a.symbol, a.market) if a.symbol else recent(a.recent_index, a.days, a.with_growth)
    except (ValueError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    out["notes"] = [
        "Reaction day = the first session that could react: the same day if the result was published during market hours, "
        "otherwise the next session. India times are NSE broadcast times; US times are SEC 8-K (item 2.02) acceptance times.",
        "Drift is measured from the reaction day's close, so it is what a buyer at that close would have seen. '_vs_index' subtracts "
        "the index move over the same days.",
        "A history of a dozen or so events is a small sample: averages describe this stock's past, they do not predict the next result.",
        "Prices from an unofficial source, split-adjusted; announcement times from the regulators' filings.",
    ]
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
