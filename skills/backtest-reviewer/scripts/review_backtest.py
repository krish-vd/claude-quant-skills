#!/usr/bin/env python3
"""Audit a backtest report for the usual ways a backtest misleads: too few trades,
no out-of-sample test, survivorship bias, failing to beat buy and hold, parameter
sensitivity, results that are too good, and drawdowns nobody would sit through.

Input: the JSON printed by the backtest-runner skill (a file, or '-' for stdin).
"""
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

from marketcore.robustness import review_report  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("report", help="backtest JSON file, or - to read from standard input")
    a = p.parse_args()
    try:
        text = sys.stdin.read() if a.report == "-" else pathlib.Path(a.report).read_text(encoding="utf-8")
        report = json.loads(text)
        if "metrics" not in report:
            raise ValueError("this is not a backtest-runner report (no 'metrics' section)" + (f": {report['error']}" if "error" in report else ""))
        out = review_report(report)
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    m = report["metrics"]
    out["summary"] = {
        "strategy": report.get("strategy"), "parameters": report.get("parameters"),
        "period": f"{m.get('start')} to {m.get('end')}", "cagr_pct": m.get("cagr_pct"),
        "max_drawdown_pct": m.get("max_drawdown_pct"), "closed_trades": m.get("closed_trades"),
    }
    out["notes"] = [
        "The review checks how the test was run, not whether the idea is sound. A clean review is not proof that a strategy will make money.",
        "Thresholds are rules of thumb: under 30 trades is noise; out-of-sample return under half of in-sample is a failure; "
        "drawdown above 40% is hard to hold, above 60% is disqualifying.",
    ]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
