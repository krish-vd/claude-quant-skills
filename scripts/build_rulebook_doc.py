#!/usr/bin/env python3
"""Generate docs/RULEBOOK.md from marketcore/rulebook/*.json.

The JSON files are the source of truth. Re-run this after editing them.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "marketcore" / "rulebook"


def pct(rate: str) -> str:
    value = Decimal(rate) * 100
    return f"{value.normalize():f}%"


def charges_section(name: str, title: str) -> list[str]:
    data = json.loads((BOOK / f"{name}.json").read_text(encoding="utf-8"))
    out = [f"## {title}", "", data["description"], "",
           "| Rule | Applies to | Side | Basis | From | To | Rate | Source |", "|---|---|---|---|---|---|---|---|"]
    for rule in data["rules"]:
        seg = rule.get("segment", "all")
        seg = ", ".join(seg) if isinstance(seg, list) else seg
        if rule.get("exchange"):
            seg = f"{seg} ({rule['exchange']})"
        for v in rule["versions"]:
            src = data["sources"][v.get("source", rule["source"])]
            kind = "unconfirmed" if v.get("unconfirmed") else src["kind"]
            rate = v["rate"] if rule["basis"] == "shares" else pct(v["rate"])
            if v.get("max_per_trade"):
                rate += f" (max {v['max_per_trade']})"
            out.append(
                f"| `{rule['id']}` | {seg} | {rule['side']} | {rule['basis']} | {v['from']} | {v['to'] or 'current'} "
                f"| {rate} | [{kind}]({src['url']}) |"
            )
    out += ["", "Sources:", ""]
    for src in data["sources"].values():
        out.append(f"- **{src['kind']}** - [{src['title']}]({src['url']}) (checked {src['checked_on']})")
    return out + [""]


def tax_section() -> list[str]:
    data = json.loads((BOOK / "in_tax.json").read_text(encoding="utf-8"))
    out = ["## India: capital gains (resident individual)", "", data["description"], "",
           "| Asset class | Long-term after | Short-term gains | Long-term gains | Exemption per FY |", "|---|---|---|---|---|"]
    for key, rule in data["asset_classes"].items():
        months = f"{rule['long_term_after_months']} months" if rule["long_term_after_months"] else "never"
        st = pct(rule["stcg"]["rate"]) if rule["stcg"]["mode"] == "special_rate" else "slab rate"
        lt, ex = "-", "-"
        if rule["ltcg"]:
            lt = pct(rule["ltcg"]["rate"])
            ex = f"Rs {int(rule['ltcg']['exemption_per_fy']):,}" if rule["ltcg"]["exemption_per_fy"] != "0" else "none"
        out.append(f"| `{key}`: {rule['label']} | {months} | {st} | {lt} | {ex} |")
    out += ["", "Not handled:", ""] + [f"- {item}" for item in data["not_handled"]]
    out += ["", "Sources:", ""]
    for src in data["sources"].values():
        out.append(f"- **{src['kind']}** - [{src['title']}]({src['url']}) (checked {src['checked_on']})")
    return out + [""]


def contracts_section() -> list[str]:
    data = json.loads((BOOK / "contracts.json").read_text(encoding="utf-8"))
    out = ["## Futures contract specifications", "", data["description"], "",
           "| Symbol | Exchange | Contract | Multiplier | Tick | Currency | Source |", "|---|---|---|---|---|---|---|"]
    for c in data["contracts"]:
        src = data["sources"][c["source"]]
        out.append(f"| {c['symbol']} | {c['exchange']} | {c['name']} | {c['multiplier']} | {c['tick_size']} | {c['currency']} | [{src['kind']}]({src['url']}) |")
    return out + [""]


def main() -> int:
    lines = [
        "# Rulebook",
        "",
        "Generated from `marketcore/rulebook/*.json` by `scripts/build_rulebook_doc.py`. Do not edit by hand.",
        "",
        "Source standing: **primary** = read from the exchange or regulator's own document; "
        "**secondary** = cross-checked against a broker or summary only; **unverified** = general knowledge, "
        "not checked against a document; **unconfirmed** = a filed change whose effect was not confirmed.",
        "",
    ]
    lines += charges_section("in_charges", "India: trade charges")
    lines += charges_section("us_charges", "US: equity regulatory fees")
    lines += tax_section()
    lines += contracts_section()
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "RULEBOOK.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote docs/RULEBOOK.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
