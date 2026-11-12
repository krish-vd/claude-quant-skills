"""AMFI daily NAV file: the official NAV for every Indian mutual fund scheme.

Source: https://portal.amfiindia.com/spages/NAVAll.txt (semicolon separated).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from . import DataUnavailable, cached_get

NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"


def parse_nav_all(text: str) -> list[dict]:
    """Parse NAVAll.txt. Section headings (fund house, category) are carried onto each scheme."""
    lines = text.splitlines()
    if not lines:
        return []
    header = [h.strip() for h in lines[0].split(";")]
    try:
        i_code, i_name = header.index("Scheme Code"), header.index("Scheme Name")
        i_nav, i_date = header.index("Net Asset Value"), header.index("Date")
    except ValueError as exc:
        raise DataUnavailable(f"AMFI NAV file layout changed: header is {header}") from exc
    i_isin = 1
    i_plan = header.index("Plan") if "Plan" in header else None
    i_option = header.index("Option") if "Option" in header else None
    schemes: list[dict] = []
    category, fund_house = "", ""
    for line in lines[1:]:
        text_line = line.strip()
        if not text_line:
            continue
        cells = [c.strip() for c in text_line.split(";")]
        if len(cells) < len(header):
            if "(" in text_line and text_line.endswith(")"):
                category = text_line
            else:
                fund_house = text_line
            continue
        if not cells[i_code].isdigit():
            continue
        try:
            nav = float(cells[i_nav])
            nav_date = datetime.strptime(cells[i_date], "%d-%b-%Y").date().isoformat()
        except ValueError:
            continue  # NAV shown as N.A. or date missing
        schemes.append(
            {
                "scheme_code": cells[i_code],
                "isin": cells[i_isin] if cells[i_isin] not in ("", "-") else None,
                "scheme_name": cells[i_name],
                "plan": cells[i_plan] if i_plan is not None else "",
                "option": cells[i_option] if i_option is not None else "",
                "nav": nav,
                "nav_date": nav_date,
                "fund_house": fund_house,
                "category": category,
            }
        )
    return schemes


def all_navs() -> list[dict]:
    """Latest NAV of every scheme (cached for 3 hours)."""
    body = cached_get(NAV_URL, "amfi_navall.txt", 3 * 3600.0)
    schemes = parse_nav_all(body.decode("utf-8", errors="replace"))
    if not schemes:
        raise DataUnavailable("AMFI NAV file returned no schemes")
    return schemes


def find_schemes(query: str, limit: int = 20) -> list[dict]:
    """Schemes whose name, plan and option together contain every word of ``query``."""
    words = query.lower().split()
    hits = [
        s for s in all_navs()
        if all(w in f"{s['scheme_name']} {s['plan']} {s['option']}".lower() for w in words)
    ]
    return hits[:limit]


def nav(scheme_code: Optional[str] = None, isin: Optional[str] = None) -> dict:
    """Latest NAV for one scheme, by AMFI scheme code or ISIN."""
    if not scheme_code and not isin:
        raise ValueError("pass scheme_code or isin")
    for scheme in all_navs():
        if scheme_code and scheme["scheme_code"] == str(scheme_code):
            return {**scheme, "source": NAV_URL}
        if isin and scheme["isin"] == isin:
            return {**scheme, "source": NAV_URL}
    raise DataUnavailable(f"No scheme found for code={scheme_code} isin={isin}")
