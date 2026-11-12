---
name: corporate-action-adjuster
description: Restate a share trade history for stock splits and bonus issues so that share counts, cost per share and holding periods are correct before computing capital gains. Use when the user's holdings went through a split, face-value split or bonus issue, when a capital-gains run fails because sells exceed buys, when the share count in the trade file does not match the demat statement, or before any tax calculation on a long-held Indian portfolio.
---

# Corporate Action Adjuster

A tradebook only records trades. After a split or bonus the demat account holds more shares than were ever bought, so FIFO matching either fails ("sell exceeds the buys supplied") or uses the wrong cost. Run this between `tradebook-importer` and `india-capital-gains`.

```bash
# 1. Look the actions up on NSE (bonus issues and splits since each symbol's first trade)
python scripts/fetch_actions.py --trades trades.csv --output actions.csv

# 2. Apply them
python scripts/adjust_trades.py --trades trades.csv --actions actions.csv --output trades_adjusted.csv
```

`fetch_actions.py` reads NSE's corporate-actions list. It writes the bonuses and splits it could read into `actions.csv` and reports everything else under `needs_manual_handling` (demergers, rights issues, buybacks, and any bonus or split whose wording it could not parse). **Show the user both lists** and have them confirm the ratios against the company announcements before step 2. You can also write `actions.csv` by hand:

`actions.csv`:

```csv
symbol,date,type,ratio
INFY,2018-09-04,bonus,1
RELIANCE,2024-10-28,bonus,1
TCS,2018-05-31,bonus,1
HDFCBANK,2019-09-19,split,2
```

- `date` is the **ex-date**.
- `split` ratio = new shares for each old share. One share becoming five is `5`; a face-value split from Rs 10 to Rs 2 is also `5`; from Rs 2 to Rs 1 is `2`.
- `bonus` ratio = bonus shares per share held. 1:1 is `1`; 1:2 (one for every two held) is `0.5`; 2:1 (two for each one held) is `2`.

**Get the ratio convention right.** Indian announcements write bonus ratios as "bonus:held", so "1:2" means one bonus share for two held. If the user quotes a ratio, confirm which way round it is, and check the resulting share count against their demat holding. The example rows above show the format only: take dates and ratios from the company's announcement or the exchange's corporate-actions page, not from memory.

## What it does

- **Split:** every trade before the ex-date is restated, quantity multiplied and price divided. Total cost and purchase dates do not change.
- **Bonus:** a new buy row is added on the ex-date at zero cost, for the shares held at that date. For tax, bonus shares cost nothing and their holding period starts on allotment, so they can be short-term while the original shares are long-term.

`actions_applied` lists what was done, including any fractional entitlement that was dropped (companies pay cash for fractions).

## After running it

1. Compare the total shares per symbol with the demat statement. A mismatch means a missed action or missing trades.
2. For shares bought before 1 Feb 2018, the 31-Jan-2018 fair market value used for grandfathering must be on the same post-split, post-bonus basis. Restate it for later actions before passing it to `india-capital-gains`.
3. Then compute gains on the adjusted file.

## Limits

Not handled: demergers (cost must be split between the companies in the ratio the company notifies), mergers and amalgamations (new symbol, carried-over cost and date), rights issues (a purchase the user should enter as a buy row at the rights price), and buybacks. For those, edit the trade file by hand from the company's notice and tell the user that is what is needed. The lookup covers NSE under the company's current symbol: a renamed or merged company may need its earlier history added by hand, and BSE-only stocks are not covered.
