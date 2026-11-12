"""Rulebook loader.

Every rate the calculators use lives in ``marketcore/rulebook/*.json`` with an
effective-date range and a source. Nothing is hard-coded in the calculators.
A lookup for a date the rulebook does not cover raises ``RuleNotCovered``
instead of guessing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

RULEBOOK_DIR = Path(__file__).parent / "rulebook"


class RuleNotCovered(LookupError):
    """The rulebook has no rate for this rule on this date."""


@dataclass(frozen=True)
class Rate:
    rule_id: str
    levy: str
    rate: Decimal
    side: str  # "buy", "sell" or "both"
    basis: str
    source_title: str
    source_url: str
    source_kind: str  # "primary", "secondary", "unverified" or "unconfirmed"
    max_per_trade: Optional[Decimal] = None
    note: str = ""


@lru_cache(maxsize=None)
def load(name: str) -> dict[str, Any]:
    with open(RULEBOOK_DIR / f"{name}.json", encoding="utf-8") as fh:
        return json.load(fh)


def _as_date(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _segments(rule: dict[str, Any]) -> list[str]:
    seg = rule.get("segment", "*")
    return seg if isinstance(seg, list) else [seg]


def rates_for(
    book: str,
    on: date,
    segment: str = "*",
    exchange: Optional[str] = None,
) -> list[Rate]:
    """All rates in ``book`` that apply to ``segment`` (and ``exchange``) on ``on``.

    Raises RuleNotCovered if a matching rule exists but none of its versions
    covers the date.
    """
    data = load(book)
    sources = data["sources"]
    out: list[Rate] = []
    for rule in data["rules"]:
        segs = _segments(rule)
        if "*" not in segs and segment not in segs:
            continue
        if rule.get("exchange") and exchange and rule["exchange"] != exchange:
            continue
        version = None
        for v in rule["versions"]:
            start = _as_date(v["from"])
            end = _as_date(v["to"]) if v.get("to") else date.max
            if start <= on <= end:
                version = v
                break
        if version is None:
            raise RuleNotCovered(
                f"{rule['id']}: no rate recorded for {on.isoformat()} "
                f"(covered from {rule['versions'][0]['from']})"
            )
        src = sources[version.get("source", rule["source"])]
        kind = "unconfirmed" if version.get("unconfirmed") else src["kind"]
        cap = version.get("max_per_trade")
        out.append(
            Rate(
                rule_id=rule["id"],
                levy=rule["levy"],
                rate=Decimal(version["rate"]),
                side=rule["side"],
                basis=rule["basis"],
                source_title=src["title"],
                source_url=src["url"],
                source_kind=kind,
                max_per_trade=Decimal(cap) if cap is not None else None,
                note=rule.get("note", ""),
            )
        )
    return out


def contract(symbol: str) -> dict[str, Any]:
    """Contract spec for a futures symbol in contracts.json (case-insensitive)."""
    data = load("contracts")
    wanted = symbol.upper()
    for row in data["contracts"]:
        if row["symbol"] == wanted:
            src = data["sources"][row["source"]]
            return {**row, "source_title": src["title"], "source_url": src["url"], "source_kind": src["kind"]}
    known = ", ".join(r["symbol"] for r in data["contracts"])
    raise RuleNotCovered(f"No contract spec for {symbol!r}. Known: {known}")
