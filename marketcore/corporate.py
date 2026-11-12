"""Corporate events from NSE: actions (bonus, split, dividend, rights, demerger) and
the calendar of upcoming board meetings for results.

NSE describes each action in free text ("Bonus 1:1", "Face Value Split (Sub-Division)
- From Rs 10/- Per Share To Rs 2/- Per Share"). ``parse_action`` turns the common
forms into numbers and marks everything else for manual handling instead of guessing.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Optional

from .data import DataUnavailable, cached_get

REFERER = "https://www.nseindia.com/"
ACTIONS_URL = "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
CALENDAR_URL = "https://www.nseindia.com/api/event-calendar"

_BONUS = re.compile(r"bonus\D{0,12}(\d+)\s*:\s*(\d+)", re.I)
_SPLIT = re.compile(r"(?:split|sub-?division).*?(?:from\s+)?r[se]\.?\s*([\d.]+).*?to\s+r[se]\.?\s*([\d.]+)", re.I)
_RUPEES = re.compile(r"r[se]\.?\s*([\d.]+)", re.I)


def parse_action(subject: str) -> dict:
    """Classify one NSE action description.

    bonus: ``ratio`` = bonus shares per share held ("Bonus 1:2" = one for every two = 0.5).
    split: ``ratio`` = new shares per old share (face value Rs 10 to Rs 2 = 5).
    dividend: ``amount`` per share when a single rupee figure is stated.
    Rights, demergers, buybacks and anything unrecognised are returned as such with no ratio.
    """
    text = " ".join(subject.split())
    lower = text.lower()
    out: dict = {"subject": text, "type": "other", "ratio": None, "amount": None}
    bonus, split = _BONUS.search(text), _SPLIT.search(text)
    if "bonus" in lower and bonus and int(bonus.group(2)) > 0:
        out.update(type="bonus", ratio=int(bonus.group(1)) / int(bonus.group(2)))
    elif ("split" in lower or "sub-division" in lower or "subdivision" in lower) and split and float(split.group(2)) > 0:
        out.update(type="split", ratio=float(split.group(1)) / float(split.group(2)))
    elif "demerger" in lower:
        out["type"] = "demerger"
    elif "rights" in lower:
        out["type"] = "rights"
    elif "buy" in lower and "back" in lower:
        out["type"] = "buyback"
    elif "dividend" in lower:
        amounts = _RUPEES.findall(text)
        out["type"] = "dividend"
        if len(amounts) == 1:
            out["amount"] = float(amounts[0].rstrip("."))
    elif "bonus" in lower or "split" in lower:
        out["type"] = "unparsed_bonus_or_split"
    return out


def _nse_date(text: Optional[str]) -> Optional[date]:
    try:
        return datetime.strptime(text.strip(), "%d-%b-%Y").date() if text and text.strip() not in ("-", "") else None
    except ValueError:
        return None


def parse_actions(payload: list) -> list[dict]:
    rows = []
    for r in payload:
        ex = _nse_date(r.get("exDate"))
        if ex is None or r.get("series") not in (None, "EQ", "BE"):
            continue
        rows.append({"symbol": r.get("symbol"), "ex_date": ex, "record_date": _nse_date(r.get("recDate")),
                     "face_value": r.get("faceVal"), **parse_action(r.get("subject") or "")})
    rows.sort(key=lambda r: (r["ex_date"], r["symbol"] or ""))
    return rows


def actions(symbol: Optional[str] = None, start: Optional[date] = None, end: Optional[date] = None) -> list[dict]:
    """Corporate actions for one symbol over a period, or (no symbol) NSE's current and upcoming list."""
    url = ACTIONS_URL
    name = "nse_ca_upcoming.json"
    if symbol:
        start, end = start or date(2000, 1, 1), end or date.today() + timedelta(days=90)
        url += f"&symbol={urllib.parse.quote(symbol.upper())}&from_date={start:%d-%m-%Y}&to_date={end:%d-%m-%Y}"
        name = f"nse_ca_{symbol.upper()}_{start:%Y%m%d}_{end:%Y%m%d}.json"
    body = cached_get(url, re.sub(r"[^A-Za-z0-9_.]", "_", name), 6 * 3600.0, REFERER)
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise DataUnavailable("NSE corporate-actions response was not readable (the site may be blocking automated requests)") from exc
    if not isinstance(payload, list):
        raise DataUnavailable("NSE corporate-actions response had an unexpected shape")
    return parse_actions(payload)


def parse_calendar(payload: list) -> list[dict]:
    rows = []
    for r in payload:
        day = _nse_date(r.get("date"))
        if day is None:
            continue
        purpose = r.get("purpose") or ""
        rows.append({"symbol": r.get("symbol"), "company": r.get("company"), "date": day, "purpose": purpose,
                     "is_results": "result" in purpose.lower(), "detail": " ".join((r.get("bm_desc") or "").split())})
    rows.sort(key=lambda r: (r["date"], r["symbol"] or ""))
    return rows


def calendar() -> list[dict]:
    """Upcoming board meetings notified to NSE (results, dividends, fund raising)."""
    body = cached_get(CALENDAR_URL, "nse_event_calendar.json", 3 * 3600.0, REFERER)
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise DataUnavailable("NSE event calendar was not readable (the site may be blocking automated requests)") from exc
    return parse_calendar(payload if isinstance(payload, list) else [])
