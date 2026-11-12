from datetime import date

import pytest

from marketcore import corporate as c


@pytest.mark.parametrize("subject, kind, ratio", [
    (" Bonus 1:1", "bonus", 1.0),
    ("Bonus 1:2", "bonus", 0.5),
    ("Bonus issue 3:1", "bonus", 3.0),
    ("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share", "split", 5.0),
    ("Face Value Split (Sub-Division) - From Rs 2/- Per Share To Re 1/- Per Share", "split", 2.0),
    ("Demerger", "demerger", None),
    ("Rights 1:15 @ Premium Rs 1247", "rights", None),
    ("Buy Back", "buyback", None),
    ("Bonus", "unparsed_bonus_or_split", None),
    ("Annual General Meeting", "other", None),
])
def test_action_descriptions(subject, kind, ratio):
    out = c.parse_action(subject)
    assert out["type"] == kind and out["ratio"] == ratio


def test_dividend_amounts():
    assert c.parse_action("Interim Dividend - Rs 19 Per Share")["amount"] == 19.0
    assert c.parse_action(" Dividend -  Rs 11/- Per Share")["amount"] == 11.0
    assert c.parse_action("Annual General Meeting/Dividend - Rs 6.50 Per Share")["amount"] == 6.5
    two = c.parse_action("Dividend - Rs 5 Per Share & Special Dividend - Rs 10 Per Share")
    assert two["type"] == "dividend" and two["amount"] is None          # two figures: not guessed


def test_actions_payload():
    payload = [
        {"symbol": "RELIANCE", "exDate": "28-Oct-2024", "recDate": "28-Oct-2024", "faceVal": "10", "series": "EQ", "subject": "Bonus 1:1"},
        {"symbol": "RELIANCE", "exDate": "07-Sep-2017", "recDate": "09-Sep-2017", "faceVal": "10", "series": "EQ", "subject": " Bonus 1:1"},
        {"symbol": "RELIANCE", "exDate": "-", "recDate": "-", "faceVal": "10", "series": "EQ", "subject": "Dividend"},
        {"symbol": "BOND", "exDate": "01-Jan-2025", "recDate": "-", "faceVal": "1000", "series": "N1", "subject": "Interest Payment"},
    ]
    rows = c.parse_actions(payload)
    assert [(r["ex_date"], r["type"], r["ratio"]) for r in rows] == [(date(2017, 9, 7), "bonus", 1.0), (date(2024, 10, 28), "bonus", 1.0)]
    assert rows[0]["record_date"] == date(2017, 9, 9)


def test_calendar_payload():
    payload = [
        {"symbol": "B", "company": "B Ltd", "purpose": "Dividend", "bm_desc": "To consider  dividend", "date": "14-Nov-2026"},
        {"symbol": "A", "company": "A Ltd", "purpose": "Financial Results/Dividend", "bm_desc": "Results for the period ended September 30, 2026", "date": "13-Nov-2026"},
        {"symbol": "X", "company": "X Ltd", "purpose": "Financial Results", "bm_desc": "", "date": "bad"},
    ]
    rows = c.parse_calendar(payload)
    assert [(r["symbol"], r["date"], r["is_results"]) for r in rows] == [("A", date(2026, 11, 13), True), ("B", date(2026, 11, 14), False)]
    assert rows[1]["detail"] == "To consider dividend"
