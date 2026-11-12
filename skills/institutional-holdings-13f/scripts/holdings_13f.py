#!/usr/bin/env python3
"""What a US fund manager owns and what it changed last quarter, from its 13F filings
with the SEC: top holdings, new positions, increases, decreases and exits.

Requires MARKET_SKILLS_SEC_USER_AGENT set to your name and email (the SEC's rule for
automated access), for example: MARKET_SKILLS_SEC_USER_AGENT="Jane Doe jane@example.com"
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

from marketcore import holdings13f  # noqa: E402
from marketcore.data import DataUnavailable  # noqa: E402
from marketcore.fundamentals import sec_cik  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--cik", type=int, help="the manager's SEC CIK number")
    g.add_argument("--ticker", help="for a manager that is itself listed, e.g. BRK-B")
    p.add_argument("--top", type=int, default=25)
    a = p.parse_args()
    try:
        cik = a.cik or sec_cik(a.ticker)[0]
        filings = holdings13f.latest_filings(cik, 2)
        current = holdings13f.infotable(cik, filings[0]["accession"])
        previous = holdings13f.infotable(cik, filings[1]["accession"]) if len(filings) > 1 else []
        out = holdings13f.compare(current, previous, a.top)
    except (ValueError, KeyError, DataUnavailable) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2
    print(json.dumps({
        "cik": cik, "latest_filing": filings[0], "previous_filing": filings[1] if len(filings) > 1 else None, **out,
        "notes": [
            "13F filings list US-listed long positions and listed options only, as of the quarter end, filed up to 45 days later. "
            "Shorts, cash, bonds and foreign shares are not shown, so this is not the whole portfolio and it is weeks out of date.",
            "Values are in US dollars as reported. Lines for the same security are combined.",
            "A position change shows what the manager did, not why: it may be a client flow, a hedge or a risk limit.",
            "Copying a manager's holdings means buying weeks later at different prices; past selection skill does not carry forward.",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
