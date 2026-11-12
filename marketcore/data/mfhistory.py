"""Mutual fund NAV history.

AMFI publishes the latest NAV as one file but has no simple per-scheme history
endpoint, so history comes from mfapi.in, a free community mirror of AMFI data.
It is a SECONDARY source: ``nav_history`` therefore checks the mirror's latest
NAV against AMFI's official file and reports whether they agree.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from . import DataUnavailable, amfi, cached_get

HISTORY_URL = "https://api.mfapi.in/mf/{code}"


def parse_history(payload: dict) -> tuple[dict, list[date], list[float]]:
    try:
        meta, rows = payload["meta"], payload["data"]
    except (KeyError, TypeError) as exc:
        raise DataUnavailable("NAV history response has an unexpected shape") from exc
    points = {}
    for row in rows:
        try:
            day = datetime.strptime(row["date"], "%d-%m-%Y").date()
            value = float(row["nav"])
        except (KeyError, ValueError):
            continue
        if value > 0:
            points[day] = value
    if not points:
        raise DataUnavailable("NAV history is empty")
    dates = sorted(points)
    return meta, dates, [points[d] for d in dates]


def nav_history(scheme_code: str) -> dict:
    """Full NAV history for an AMFI scheme code, oldest first, with an official cross-check."""
    body = cached_get(HISTORY_URL.format(code=scheme_code), f"mfapi_{scheme_code}.json", 6 * 3600.0)
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise DataUnavailable(f"Unreadable NAV history for scheme {scheme_code}") from exc
    meta, dates, values = parse_history(payload)

    check = {"status": "not checked", "official_nav": None, "official_date": None}
    try:
        official = amfi.nav(scheme_code=str(scheme_code))
        official_date = date.fromisoformat(official["nav_date"])
        check.update(official_nav=official["nav"], official_date=official["nav_date"])
        if official_date in dates:
            mirrored = values[dates.index(official_date)]
            agrees = abs(mirrored / official["nav"] - 1.0) <= 0.0001
            check["status"] = "matches AMFI" if agrees else f"MISMATCH: mirror has {mirrored} for that date"
        else:
            check["status"] = "mirror does not have AMFI's latest date yet"
    except DataUnavailable:
        check["status"] = "AMFI official file unavailable"
    return {
        "scheme_code": str(scheme_code),
        "scheme_name": meta.get("scheme_name"),
        "fund_house": meta.get("fund_house"),
        "category": meta.get("scheme_category"),
        "dates": dates,
        "navs": values,
        "source": HISTORY_URL.format(code=scheme_code),
        "source_kind": "secondary (community mirror of AMFI)",
        "official_check": check,
    }
