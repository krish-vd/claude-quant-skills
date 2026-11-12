---
name: fno-expiry-calendar
description: List NSE futures and options expiry dates - weekly and monthly expiries for NIFTY, BANKNIFTY, FINNIFTY and other indices, or all expiries of one stock - with weekday, days remaining, lot size and open interest, plus the stocks currently in the F&O ban. Use when the user asks when the next expiry is, which day NIFTY or BANKNIFTY expires, how many days are left to expiry, what the lot size is for an expiry, or which stocks are in the F&O ban list.
---

# F&O Expiry Calendar

```bash
python scripts/expiry_calendar.py                      # all index expiries
python scripts/expiry_calendar.py --within-days 14     # only the next two weeks
python scripts/expiry_calendar.py --symbol RELIANCE
```

Expiry dates are read from the contracts NSE actually lists in its latest F&O file, so this is never a remembered schedule. **Do not answer expiry-day questions from memory:** the exchange has changed weekly expiry days and which indices have weekly contracts more than once. Run the script.

## Reading the output

- `nearest_expiry` and `expiries`: each with `symbol`, `expiry`, `weekday`, `days_to_expiry`, whether `futures` and/or `options` exist for that date, `lot_size`, and total `open_interest_units`.
- An expiry with options but no futures is a weekly expiry. Monthly expiries have both.
- `fo_ban_list`: stocks in the ban period for the stated trade date.
- `contracts_as_listed_on`: the date of the file used.

## Things to tell the user when relevant

- **Holidays:** if the scheduled expiry day is a trading holiday, the exchange moves it (normally to the previous trading day). The file reflects this once NSE has listed the contract with the revised date; for an expiry several weeks out, mention that a holiday could still shift it.
- **Lot sizes change.** NSE revises them periodically, and the far-month contract can carry a different lot from the near month. Quote the lot for the specific expiry.
- **Ban list:** in a banned stock only position-reducing trades are allowed; opening new positions draws a penalty. Check it before planning a stock F&O trade.
- **Physical settlement:** stock futures and options are settled by delivery. An in-the-money stock option or any stock future left open at expiry means buying or delivering the shares, with extra margin required in the last days before expiry. Index contracts are cash-settled.
- **Expiry-day behaviour:** option prices move very fast on the last day and exercise of bought options attracts STT on intrinsic value.

## Limits

NSE only (no BSE Sensex or MCX expiries). End-of-day file: a contract listed today appears after the evening publication. It does not give trading holidays or settlement calendars.
