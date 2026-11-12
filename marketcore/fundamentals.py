"""Company fundamentals from the regulators' own filings.

India: quarterly results as filed with NSE (integrated filing, XBRL). Figures are the
company's reported numbers in rupees.
US: the SEC's "company facts" data, built from 10-K and 10-Q filings, in dollars.

Both are primary sources. What is derived here (growth rates, margins, trailing
figures, ratios) is plain arithmetic on those reported numbers and is labelled.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Optional

from .data import DataUnavailable, cache_dir, cached_get
import time

NSE_REFERER = "https://www.nseindia.com/"
NSE_FILINGS = ("https://www.nseindia.com/api/integrated-filing-results?index=equities&symbol={symbol}"
               "&period_ended=all&type=Integrated%20Filing-%20Financials&page=1&size=40")
SEC_UA = "market-skills/0.1 (open-source research tool)"
SEC_LOOKUP = "https://efts.sec.gov/LATEST/search-index?keysTyped={ticker}"
SEC_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
XBRLI = "{http://www.xbrl.org/2003/instance}"

# Element names in the Indian results taxonomy -> our field names. First match wins.
INDIA_FLOW = {
    "revenue": ("RevenueFromOperations", "InterestEarned", "Income"),
    "other_income": ("OtherIncome",),
    "total_income": ("Income",),
    "finance_costs": ("FinanceCosts",),
    "depreciation": ("DepreciationDepletionAndAmortisationExpense",),
    "profit_before_tax": ("ProfitBeforeTax", "ProfitLossFromOrdinaryActivitiesBeforeTax"),
    "tax": ("TaxExpense",),
    "net_profit": ("ProfitLossForPeriod", "ProfitLossForThePeriod"),
    # The second name in each pair is the one banks use in their results format.
    "eps_basic": ("BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations", "BasicEarningsPerShareAfterExtraordinaryItems"),
    "eps_diluted": ("DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations", "DilutedEarningsPerShareAfterExtraordinaryItems"),
    "interest_expended": ("InterestExpended",),
}
INDIA_STOCK = {"equity": ("Equity",), "total_assets": ("Assets",), "paid_up_capital": ("PaidUpValueOfEquityShareCapital",)}
US_TAGS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax"),
    "net_income": ("NetIncomeLoss",),
    "eps_diluted": ("EarningsPerShareDiluted",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
}
US_INSTANT = {"equity": ("StockholdersEquity",), "total_assets": ("Assets",), "total_liabilities": ("Liabilities",),
              "long_term_debt": ("LongTermDebt", "LongTermDebtNoncurrent")}


def _pct(new: Optional[float], old: Optional[float]) -> Optional[float]:
    """Growth in percent. None when the base is missing, zero or negative (growth off a loss is not meaningful)."""
    if new is None or old is None or old <= 0:
        return None
    return round((new / old - 1) * 100, 2)


def _ratio(a: Optional[float], b: Optional[float], scale: float = 100.0) -> Optional[float]:
    return round(a / b * scale, 2) if a is not None and b not in (None, 0) else None


# ---------- India ----------

def parse_india_result(xml_bytes: bytes) -> dict:
    """One filed result: the reporting quarter's figures and the balance sheet date figures, in rupees."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise DataUnavailable("results file is not readable XBRL") from exc
    contexts: dict[str, tuple] = {}
    for ctx in root.iter(f"{XBRLI}context"):
        if ctx.find(f"{XBRLI}scenario") is not None or ctx.find(f"{XBRLI}entity/{XBRLI}segment") is not None:
            continue  # a breakdown (segment, expense line), not the company total
        period = ctx.find(f"{XBRLI}period")
        parts = {child.tag.split("}")[1]: (child.text or "").strip() for child in period}
        if "instant" in parts:
            contexts[ctx.get("id")] = ("instant", None, date.fromisoformat(parts["instant"]))
        elif "startDate" in parts and "endDate" in parts:
            contexts[ctx.get("id")] = ("duration", date.fromisoformat(parts["startDate"]), date.fromisoformat(parts["endDate"]))
    durations = [c for c in contexts.values() if c[0] == "duration"]
    if not durations:
        raise DataUnavailable("results file has no reporting period")
    period_end = max(c[2] for c in durations)
    quarter = min((c for c in durations if c[2] == period_end), key=lambda c: (c[2] - c[1]).days)
    days = (quarter[2] - quarter[1]).days

    facts: dict[str, dict] = {"quarter": {}, "instant": {}, "text": {}}
    for el in root:
        name = el.tag.split("}")[1] if "}" in el.tag else el.tag
        ctx = contexts.get(el.get("contextRef") or "")
        text = (el.text or "").strip()
        if ctx is None or not text:
            continue
        if ctx[0] == "duration" and ctx[1:] == quarter[1:]:
            facts["quarter"].setdefault(name, text)
        elif ctx[0] == "instant" and ctx[2] == period_end:
            facts["instant"].setdefault(name, text)

    def pick(group: str, names: tuple) -> Optional[float]:
        for n in names:
            if n in facts[group]:
                try:
                    return float(facts[group][n])
                except ValueError:
                    continue
        return None

    out = {
        "period_start": quarter[1].isoformat(), "period_end": period_end.isoformat(), "period_days": days,
        "is_single_quarter": 80 <= days <= 100,
        "basis": facts["quarter"].get("NatureOfReportStandaloneConsolidated"),
        "audited": facts["quarter"].get("WhetherResultsAreAuditedOrUnaudited"),
        "company": facts["quarter"].get("NameOfTheCompany") or facts["quarter"].get("NameOfBank"),
        "is_bank_format": "InterestEarned" in facts["quarter"],
        "revenue_is_total_income": "RevenueFromOperations" not in facts["quarter"] and "InterestEarned" not in facts["quarter"],
    }
    out.update({field: pick("quarter", names) for field, names in INDIA_FLOW.items()})
    out.update({field: pick("instant", names) for field, names in INDIA_STOCK.items()})
    out["face_value"] = pick("quarter", ("FaceValueOfEquityShareCapital",))
    return out


def india_filings(symbol: str) -> list[dict]:
    body = cached_get(NSE_FILINGS.format(symbol=urllib.parse.quote(symbol.upper())), f"nse_filings_{symbol.upper()}.json", 6 * 3600.0, NSE_REFERER)
    try:
        rows = json.loads(body).get("data") or []
    except ValueError as exc:
        raise DataUnavailable(f"NSE filings list for {symbol} was not readable") from exc
    if not rows:
        raise DataUnavailable(f"No results filings found on NSE for {symbol.upper()}")
    return rows


def india_quarters(symbol: str, consolidated: bool = True, quarters: int = 8) -> dict:
    """The latest ``quarters`` filed results for an NSE company, newest first, with which basis was used."""
    rows = india_filings(symbol)
    wanted = "Consolidated" if consolidated else "Standalone"
    chosen = [r for r in rows if r.get("consolidated") == wanted]
    basis_note = None
    if not chosen:
        other = "Standalone" if consolidated else "Consolidated"
        chosen = [r for r in rows if r.get("consolidated") == other]
        basis_note = f"No {wanted.lower()} results are filed; {other.lower()} figures are shown."
        wanted = other
    by_period: dict[str, dict] = {}
    for r in chosen:  # keep the latest filing for each period end (a revision replaces the original)
        key = r["qe_Date"]
        stamp = r.get("creation_Date") or ""
        if key not in by_period or stamp > (by_period[key].get("creation_Date") or ""):
            by_period[key] = r
    ordered = sorted(by_period.values(), key=lambda r: datetime.strptime(r["qe_Date"], "%d-%b-%Y"), reverse=True)[:quarters]
    out, problems = [], []
    for r in ordered:
        url = r.get("xbrl") or ""
        if not url.lower().endswith(".xml"):
            problems.append(f"{r['qe_Date']}: no XBRL file")
            continue
        try:
            body = cached_get(url, "nse_xbrl_" + url.rsplit("/", 1)[-1], 10 * 365 * 86400.0, NSE_REFERER)
            parsed = parse_india_result(body)
        except DataUnavailable as exc:
            problems.append(f"{r['qe_Date']}: {exc}")
            continue
        parsed.update(filed=r.get("broadcast_Date"), filing_type=r.get("type_Sub"), source=url)
        out.append(parsed)
    if not out:
        raise DataUnavailable(f"No readable results for {symbol.upper()}: {'; '.join(problems)}")
    return {"symbol": symbol.upper(), "basis": wanted, "basis_note": basis_note, "quarters": out, "problems": problems}


def india_summary(data: dict, price: Optional[float] = None) -> dict:
    """Growth, margins and trailing figures from the quarterly results (newest first)."""
    q = [x for x in data["quarters"] if x["is_single_quarter"]]
    skipped = len(data["quarters"]) - len(q)
    if not q:
        raise DataUnavailable("no single-quarter results to summarise")
    by_end = {x["period_end"]: x for x in q}

    def year_ago(x: dict) -> Optional[dict]:
        end = date.fromisoformat(x["period_end"])
        for delta in (0, -1, 1, -2, 2, -3, 3):
            try:
                key = end.replace(year=end.year - 1).toordinal() + delta
            except ValueError:  # 29 February
                key = end.replace(year=end.year - 1, day=28).toordinal() + delta
            hit = by_end.get(date.fromordinal(key).isoformat())
            if hit:
                return hit
        return None

    table = []
    for x in q:
        prior = year_ago(x)
        table.append({
            "period_end": x["period_end"],
            "revenue": x["revenue"], "net_profit": x["net_profit"], "eps_diluted": x["eps_diluted"],
            "net_margin_pct": _ratio(x["net_profit"], x["revenue"]),
            "pbt_margin_pct": _ratio(x["profit_before_tax"], x["revenue"]),
            "revenue_growth_yoy_pct": _pct(x["revenue"], prior["revenue"]) if prior else None,
            "net_profit_growth_yoy_pct": _pct(x["net_profit"], prior["net_profit"]) if prior else None,
            "eps_growth_yoy_pct": _pct(x["eps_diluted"], prior["eps_diluted"]) if prior else None,
            "audited": x["audited"], "filed": x.get("filed"),
        })
    last4 = q[:4]
    consecutive = len(last4) == 4 and all(
        60 <= (date.fromisoformat(last4[i]["period_end"]) - date.fromisoformat(last4[i + 1]["period_end"])).days <= 100 for i in range(3))
    ttm = None
    if consecutive and all(x["eps_diluted"] is not None for x in last4):
        ttm_eps = sum(x["eps_diluted"] for x in last4)
        ttm = {
            "revenue": sum(x["revenue"] or 0 for x in last4), "net_profit": sum(x["net_profit"] or 0 for x in last4),
            "eps_diluted": round(ttm_eps, 2), "quarters": [x["period_end"] for x in last4],
        }
        if price and ttm_eps > 0:
            ttm["price"] = price
            ttm["price_to_earnings"] = round(price / ttm_eps, 2)
    latest = q[0]
    return {
        "symbol": data["symbol"], "company": latest.get("company"), "basis": data["basis"], "basis_note": data.get("basis_note"),
        "currency": "INR", "latest_quarter": table[0], "quarters": table, "trailing_four_quarters": ttm,
        "balance_sheet": {"as_of": latest["period_end"], "equity": latest["equity"], "total_assets": latest["total_assets"]}
        if latest["equity"] is not None else None,
        "revenue_is_total_income": latest["revenue_is_total_income"],
        "bank_format": latest.get("is_bank_format", False),
        "non_quarter_filings_skipped": skipped,
        "problems": data["problems"],
    }


# ---------- United States ----------

def _sec_get(url: str, cache_name: str, max_age: float) -> bytes:
    path = cache_dir() / cache_name
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age:
        return path.read_bytes()
    request = urllib.request.Request(url, headers={"User-Agent": SEC_UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = response.read()
    except Exception as exc:  # noqa: BLE001 - urllib raises several unrelated types
        raise DataUnavailable(f"{url}: {exc}") from exc
    path.write_bytes(body)
    return body


def sec_cik(ticker: str) -> tuple[int, str]:
    """(CIK, entity name) for a US ticker, from the SEC's own lookup."""
    wanted = ticker.upper()
    body = _sec_get(SEC_LOOKUP.format(ticker=urllib.parse.quote(wanted)), f"sec_lookup_{wanted}.json", 30 * 86400.0)
    try:
        hits = json.loads(body)["hits"]["hits"]
    except (ValueError, KeyError) as exc:
        raise DataUnavailable(f"SEC lookup for {wanted} was not readable") from exc
    for hit in hits:
        tickers = [t.strip().upper() for t in str(hit["_source"].get("tickers", "")).split(",")]
        if wanted in tickers:
            return int(hit["_id"]), hit["_source"].get("entity", "")
    raise DataUnavailable(f"{wanted} was not found in the SEC's company list (foreign and unlisted companies may be absent)")


def us_series(facts: dict) -> dict:
    """Annual and quarterly series from an SEC company-facts document.

    Annual values are periods of about a year; quarterly values are periods of about
    three months. The fourth quarter is not filed separately, so it is derived as the
    year minus the three filed quarters and marked ``derived``.
    """
    gaap = (facts.get("facts") or {}).get("us-gaap") or {}

    def points(tags: tuple, per_share: bool = False) -> tuple[dict, dict, Optional[str]]:
        annual, quarterly, used = {}, {}, None
        for tag in tags:
            units = (gaap.get(tag) or {}).get("units") or {}
            rows = units.get("USD/shares" if per_share else "USD") or []
            if not rows:
                continue
            used = used or tag
            for r in sorted(rows, key=lambda r: r.get("filed", "")):  # later filings overwrite earlier ones
                if "start" not in r or "end" not in r:
                    continue
                days = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
                if 350 <= days <= 380:
                    annual[r["end"]] = (r["start"], float(r["val"]))
                elif 80 <= days <= 100:
                    quarterly[r["end"]] = (r["start"], float(r["val"]), False)
            if annual:
                break
        for end, (start, value) in annual.items():  # derive the fourth quarter
            inside = [(e, v) for e, (s, v, _d) in quarterly.items() if start <= s and e < end]
            if len(inside) == 3 and end not in quarterly:
                third_end = max(e for e, _ in inside)
                quarterly[end] = (third_end, value - sum(v for _, v in inside), True)
        return annual, quarterly, used

    def instants(tags: tuple) -> dict:
        for tag in tags:
            rows = ((gaap.get(tag) or {}).get("units") or {}).get("USD") or []
            if rows:
                return {r["end"]: float(r["val"]) for r in sorted(rows, key=lambda r: r.get("filed", "")) if "end" in r and "start" not in r}
        return {}

    out = {"entity": facts.get("entityName"), "annual": {}, "quarterly": {}, "instant": {}, "tags_used": {}}
    for field, tags in US_TAGS.items():
        annual, quarterly, used = points(tags, per_share=field == "eps_diluted")
        out["annual"][field], out["quarterly"][field], out["tags_used"][field] = annual, quarterly, used
    for field, tags in US_INSTANT.items():
        out["instant"][field] = instants(tags)
    return out


def us_summary(series: dict, price: Optional[float] = None, years: int = 5, quarters: int = 8) -> dict:
    annual, quarterly, instant = series["annual"], series["quarterly"], series["instant"]
    year_ends = sorted(annual["revenue"] or annual["net_income"], reverse=True)[:years + 1]
    if not year_ends:
        raise DataUnavailable("no annual figures in the SEC data for this company")

    def a(field: str, end: str) -> Optional[float]:
        row = annual[field].get(end)
        return row[1] if row else None

    def at(field: str, end: str) -> Optional[float]:
        return instant[field].get(end)

    rows = []
    for i, end in enumerate(year_ends[:years]):
        prev = year_ends[i + 1] if i + 1 < len(year_ends) else None
        ni, eq = a("net_income", end), at("equity", end)
        eq_prev = at("equity", prev) if prev else None
        avg_eq = (eq + eq_prev) / 2 if eq is not None and eq_prev is not None else eq
        ocf, capex = a("operating_cash_flow", end), a("capex", end)
        rows.append({
            "fiscal_year_end": end,
            "revenue": a("revenue", end), "net_income": ni, "eps_diluted": a("eps_diluted", end),
            "revenue_growth_pct": _pct(a("revenue", end), a("revenue", prev)) if prev else None,
            "eps_growth_pct": _pct(a("eps_diluted", end), a("eps_diluted", prev)) if prev else None,
            "net_margin_pct": _ratio(ni, a("revenue", end)),
            "return_on_equity_pct": _ratio(ni, avg_eq) if avg_eq and avg_eq > 0 else None,
            "free_cash_flow": ocf - capex if ocf is not None and capex is not None else None,
            "debt_to_equity": _ratio(at("long_term_debt", end), eq, 1.0) if eq and eq > 0 else None,
        })

    def cagr(field: str, n: int) -> Optional[float]:
        if len(year_ends) <= n:
            return None
        end, start = a(field, year_ends[0]), a(field, year_ends[n])
        if end is None or start is None or start <= 0 or end <= 0:
            return None
        return round(((end / start) ** (1 / n) - 1) * 100, 2)

    q_ends = sorted(quarterly["eps_diluted"] or quarterly["revenue"], reverse=True)
    q_rows = []
    for end in q_ends[:quarters]:
        target = date.fromisoformat(end)
        prior = next((e for e in q_ends if 350 <= (target - date.fromisoformat(e)).days <= 380), None)

        def qv(field: str, e: Optional[str]) -> Optional[float]:
            row = quarterly[field].get(e) if e else None
            return row[1] if row else None

        derived = bool(quarterly["eps_diluted"].get(end, (None, None, False))[2] or quarterly["revenue"].get(end, (None, None, False))[2])
        q_rows.append({
            "quarter_end": end, "revenue": qv("revenue", end), "net_income": qv("net_income", end),
            "eps_diluted": None if qv("eps_diluted", end) is None else round(qv("eps_diluted", end), 4),
            "revenue_growth_yoy_pct": _pct(qv("revenue", end), qv("revenue", prior)),
            "eps_growth_yoy_pct": _pct(qv("eps_diluted", end), qv("eps_diluted", prior)),
            "derived_fourth_quarter": derived,
        })
    ttm = None
    last4 = [quarterly["eps_diluted"].get(e) for e in q_ends[:4]]
    if len(last4) == 4 and all(last4):
        ttm_eps = sum(r[1] for r in last4)
        ttm = {"eps_diluted": round(ttm_eps, 2), "quarters": q_ends[:4]}
        if price and ttm_eps > 0:
            ttm["price"], ttm["price_to_earnings"] = price, round(price / ttm_eps, 2)
    return {
        "company": series["entity"], "currency": "USD",
        "annual": rows, "revenue_cagr_3y_pct": cagr("revenue", 3), "eps_cagr_3y_pct": cagr("eps_diluted", 3),
        "quarters": q_rows, "trailing_four_quarters": ttm, "tags_used": series["tags_used"],
    }


def us_fundamentals(ticker: str, price: Optional[float] = None) -> dict:
    cik, entity = sec_cik(ticker)
    body = _sec_get(SEC_FACTS.format(cik=cik), f"sec_facts_{cik}.json", 12 * 3600.0)
    try:
        facts = json.loads(body)
    except ValueError as exc:
        raise DataUnavailable(f"SEC data for {ticker} was not readable") from exc
    out = us_summary(us_series(facts), price)
    out.update(symbol=ticker.upper(), cik=cik, source=SEC_FACTS.format(cik=cik))
    return out


def india_growth_snapshot(symbol: str, consolidated: bool = True) -> dict:
    """Latest quarter against the same quarter a year earlier, reading only those two
    filings (plus the one before the latest, for acceleration). Cheaper than a full history."""
    rows = india_filings(symbol)
    wanted = "Consolidated" if consolidated else "Standalone"
    chosen = [r for r in rows if r.get("consolidated") == wanted] or [r for r in rows if r.get("consolidated")]
    by_end: dict = {}
    for r in chosen:
        end = datetime.strptime(r["qe_Date"], "%d-%b-%Y").date()
        if end not in by_end or (r.get("creation_Date") or "") > (by_end[end].get("creation_Date") or ""):
            by_end[end] = r
    ends = sorted(by_end, reverse=True)
    if not ends:
        raise DataUnavailable(f"no results filings for {symbol.upper()}")

    def load(end) -> Optional[dict]:
        r = by_end.get(end)
        if not r or not str(r.get("xbrl", "")).lower().endswith(".xml"):
            return None
        body = cached_get(r["xbrl"], "nse_xbrl_" + r["xbrl"].rsplit("/", 1)[-1], 10 * 365 * 86400.0, NSE_REFERER)
        parsed = parse_india_result(body)
        return parsed if parsed["is_single_quarter"] else None

    def year_before(end):
        return next((e for e in ends if 355 <= (end - e).days <= 375), None)

    latest = load(ends[0])
    if latest is None:
        raise DataUnavailable(f"latest filing for {symbol.upper()} is not a readable single quarter")
    prior_end = year_before(ends[0])
    prior = load(prior_end) if prior_end else None
    previous_q = next((e for e in ends[1:] if 80 <= (ends[0] - e).days <= 100), None)
    prev = load(previous_q) if previous_q else None
    prev_year = load(year_before(previous_q)) if previous_q and year_before(previous_q) else None

    def growth(field: str, a: Optional[dict], b: Optional[dict]) -> Optional[float]:
        return _pct(a.get(field), b.get(field)) if a and b else None

    eps_now = growth("eps_diluted", latest, prior) if latest.get("eps_diluted") is not None else growth("net_profit", latest, prior)
    eps_before = growth("eps_diluted", prev, prev_year) if prev and prev.get("eps_diluted") is not None else growth("net_profit", prev, prev_year)
    return {
        "symbol": symbol.upper(), "company": latest.get("company"), "basis": latest.get("basis"),
        "latest_quarter": latest["period_end"], "year_ago_quarter": prior["period_end"] if prior else None,
        "revenue_growth_yoy_pct": growth("revenue", latest, prior),
        "net_profit_growth_yoy_pct": growth("net_profit", latest, prior),
        "eps_growth_yoy_pct": eps_now,
        "previous_quarter_eps_growth_yoy_pct": eps_before,
        "eps_growth_accelerating": None if eps_now is None or eps_before is None else eps_now > eps_before,
        "net_margin_pct": _ratio(latest.get("net_profit"), latest.get("revenue")),
        "bank_format": latest.get("is_bank_format", False),
        "uses_profit_growth_for_eps": latest.get("eps_diluted") is None,
    }
