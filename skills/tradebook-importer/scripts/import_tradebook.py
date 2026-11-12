#!/usr/bin/env python3
"""Convert a broker tradebook CSV into the standard trade CSV for india-capital-gains,
separating intraday round trips and setting derivatives aside."""
import argparse
import json
import pathlib
import sys

_here = pathlib.Path(__file__).resolve()
for _candidate in (_here.parent / "_vendor", *_here.parents):
    if (_candidate / "marketcore" / "__init__.py").exists():
        sys.path.insert(0, str(_candidate))
        break
else:
    sys.exit("marketcore not found: run from the repo, or use a packaged skill")

from marketcore import tradebook  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, action="append", help="tradebook CSV; repeat to combine several files (e.g. one per year)")
    p.add_argument("--output", required=True, help="where to write the standard trade CSV")
    p.add_argument("--map", action="append", default=[], metavar="FIELD=COLUMN",
                   help="name a column explicitly: FIELD is date, symbol, side, quantity, price or segment")
    p.add_argument("--date-format", help="strptime format if dates are not recognised, e.g. %%m/%%d/%%Y for US-style dates")
    p.add_argument("--asset-class", default="listed_equity",
                   choices=["listed_equity", "foreign_equity", "debt_fund_post_2023", "listed_other", "unlisted_other"])
    a = p.parse_args()
    try:
        overrides = {}
        for item in a.map:
            field, sep, column = item.partition("=")
            if not sep:
                p.error(f"--map must be FIELD=COLUMN, got {item!r}")
            overrides[field.strip().lower()] = column
        fills, reports = [], []
        for path in a.input:
            text = pathlib.Path(path).read_text(encoding="utf-8-sig", errors="replace")
            file_fills, report = tradebook.read_fills(text, overrides, a.date_format)
            for f in file_fills:
                f.line += len(fills) * 1_000_000  # keep file order stable across files
            fills.extend(file_fills)
            reports.append({"file": path, "equity_rows": len(file_fills), **report})
        fills.sort(key=lambda f: (f.trade_date, f.line))
        delivery, intraday = tradebook.split_intraday(fills)
        pathlib.Path(a.output).write_text(tradebook.to_standard_csv(delivery, a.asset_class), encoding="utf-8")
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    dates = [f.trade_date for f in fills]
    symbols = sorted({f.symbol for f in delivery})
    notes = [
        "Check the first and last dates and the symbol list against the broker statement before using the output.",
        "Same-day buys and sells of a symbol were treated as intraday (speculative business income) and left out of the delivery file.",
        "Charges are set to 0 in the output: brokerage and other costs (not STT) can be added per row to reduce the gain.",
        "Corporate actions are not applied. Adjust the rows for splits, bonuses and demergers before computing gains.",
    ]
    if any(r["derivative_rows_skipped"] for r in reports):
        notes.append("Derivative rows were skipped: F&O is business income, not capital gains.")
    if any(r["unreadable_rows"] for r in reports):
        notes.append("Some rows could not be read (see unreadable_rows). Fix or account for them: missing trades give wrong gains.")
    print(json.dumps({
        "output": a.output,
        "files": reports,
        "delivery_trades_written": len(delivery),
        "first_trade_date": min(dates).isoformat() if dates else None,
        "last_trade_date": max(dates).isoformat() if dates else None,
        "symbols": symbols,
        "intraday_round_trips": len(intraday),
        "intraday_pnl_before_charges": round(sum(r["pnl_before_charges"] for r in intraday), 2),
        "intraday": intraday,
        "notes": notes,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
