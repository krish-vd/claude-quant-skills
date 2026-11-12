"""US institutional holdings from 13F filings with the SEC.

Managers with over $100 million in US equities file a 13F within 45 days of each
quarter end. The filing lists long positions in US-listed shares and options only:
no shorts, no cash, no foreign shares. This module compares the last two filings of
one manager.

The SEC requires automated requests to identify the requester with a contact email.
Set the environment variable MARKET_SKILLS_SEC_USER_AGENT to something like
"Your Name your.email@example.com" before use.
"""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from typing import Optional

from .data import DataUnavailable
from .fundamentals import _sec_get

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"


def _require_agent() -> str:
    agent = os.environ.get("MARKET_SKILLS_SEC_USER_AGENT", "").strip()
    if "@" not in agent:
        raise DataUnavailable("The SEC requires a contact email for downloading filings. Set MARKET_SKILLS_SEC_USER_AGENT "
                              "to your name and email, for example: MARKET_SKILLS_SEC_USER_AGENT=\"Jane Doe jane@example.com\"")
    return agent


def _get(url: str, cache_name: str, max_age: float) -> bytes:
    import urllib.request

    from .data import cache_dir
    path = cache_dir() / cache_name
    if path.exists():
        import time
        if time.time() - path.stat().st_mtime < max_age:
            return path.read_bytes()
    request = urllib.request.Request(url, headers={"User-Agent": _require_agent()})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = response.read()
    except Exception as exc:  # noqa: BLE001
        raise DataUnavailable(f"{url}: {exc}") from exc
    path.write_bytes(body)
    return body


def parse_infotable(xml_bytes: bytes) -> list[dict]:
    """Holdings from a 13F information table: issuer, CUSIP, value (dollars), shares, put/call."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise DataUnavailable("13F information table is not readable XML") from exc

    def text(node, name: str) -> Optional[str]:
        for child in node.iter():
            if child.tag.split("}")[-1] == name:
                return (child.text or "").strip()
        return None

    rows = []
    for node in root.iter():
        if node.tag.split("}")[-1] != "infoTable":
            continue
        value = float(text(node, "value") or 0)
        shares = float(text(node, "sshPrnamt") or 0)
        rows.append({"issuer": text(node, "nameOfIssuer"), "cusip": text(node, "cusip"), "class": text(node, "titleOfClass"),
                     "value": value, "shares": shares, "share_type": text(node, "sshPrnamtType"),
                     "put_call": text(node, "putCall") or None})
    return rows


def aggregate(rows: list[dict]) -> dict[tuple, dict]:
    """Combine lines for the same security (managers often split a position across sub-advisers)."""
    out: dict[tuple, dict] = {}
    for r in rows:
        key = (r["cusip"], r["put_call"])
        if key not in out:
            out[key] = {**r}
        else:
            out[key]["value"] += r["value"]
            out[key]["shares"] += r["shares"]
    return out


def compare(current: list[dict], previous: list[dict], top: int = 25) -> dict:
    now, before = aggregate(current), aggregate(previous)
    total = sum(r["value"] for r in now.values())
    rows = []
    for key, r in now.items():
        prior = before.get(key)
        change = None if prior is None or prior["shares"] == 0 else round((r["shares"] / prior["shares"] - 1) * 100, 1)
        rows.append({"issuer": r["issuer"], "cusip": r["cusip"], "put_call": r["put_call"], "value": r["value"], "shares": r["shares"],
                     "weight_pct": round(r["value"] / total * 100, 2) if total else None,
                     "status": "new" if prior is None else "unchanged" if change == 0 else "changed",
                     "share_change_pct": change})
    exited = [{"issuer": r["issuer"], "cusip": r["cusip"], "put_call": r["put_call"], "previous_shares": r["shares"]}
              for key, r in before.items() if key not in now]
    rows.sort(key=lambda r: -r["value"])
    return {
        "positions": len(now), "total_value": total,
        "top_holdings": rows[:top],
        "new_positions": [r for r in rows if r["status"] == "new"][:top],
        "largest_increases": sorted((r for r in rows if r["share_change_pct"] and r["share_change_pct"] > 0), key=lambda r: -r["share_change_pct"])[:10],
        "largest_decreases": sorted((r for r in rows if r["share_change_pct"] and r["share_change_pct"] < 0), key=lambda r: r["share_change_pct"])[:10],
        "exited_positions": exited[:top],
    }


def latest_filings(cik: int, count: int = 2) -> list[dict]:
    body = _sec_get(SUBMISSIONS.format(cik=cik), f"sec_sub_{cik}.json", 12 * 3600.0)
    recent = json.loads(body)["filings"]["recent"]
    out = []
    for form, acc, filed, period in zip(recent["form"], recent["accessionNumber"], recent["filingDate"], recent["reportDate"]):
        if form == "13F-HR":
            out.append({"accession": acc, "filed": filed, "period": period})
        if len(out) == count:
            break
    if not out:
        raise DataUnavailable(f"no 13F-HR filings for CIK {cik}")
    return out


def infotable(cik: int, accession: str) -> list[dict]:
    acc = accession.replace("-", "")
    index = json.loads(_get(ARCHIVE.format(cik=cik, acc=acc) + "index.json", f"sec13f_idx_{acc}.json", 365 * 86400.0))
    names = [item["name"] for item in index["directory"]["item"] if item["name"].lower().endswith(".xml")]
    table = next((n for n in names if re.search(r"info|table", n, re.I)), None) or next((n for n in names if "primary" not in n.lower()), None)
    if not table:
        raise DataUnavailable(f"no information table in filing {accession}")
    return parse_infotable(_get(ARCHIVE.format(cik=cik, acc=acc) + table, f"sec13f_{acc}_{table}", 365 * 86400.0))
