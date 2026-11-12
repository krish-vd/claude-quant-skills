---
name: tax-year-routine
description: Take an Indian investor from raw broker files to a complete picture of their capital gains tax for a financial year by chaining the tax skills in the right order - import the tradebook, apply corporate actions, compute gains, plan year-end harvesting, work out advance-tax instalments, and handle F&O income and foreign shares separately. Use when the user asks to do their capital gains for the year, prepare for tax filing, sort out their trading taxes, what they owe on their investments, or what to do before 31 March.
---

# Tax Year Routine

The tax skills depend on each other, and running them out of order gives wrong answers (gains computed before corporate actions are applied are the usual mistake). This skill fixes the order.

Establish first: the financial year, which brokers and accounts are involved, and whether the user has F&O or intraday trades, mutual funds, or foreign shares. Each needs its own handling.

## 1. Build the trade history (`tradebook-importer`)

Import every broker's tradebook for **all years**, not only the year being filed: gains need the original purchase of every share sold. Report what the importer set aside (intraday round trips, F&O rows) and resolve any unreadable rows. Ask about shares that arrived without a trade (IPO allotments, transfers, ESOPs, gifts) and add them as buy rows.

## 2. Apply corporate actions (`corporate-action-adjuster`)

Fetch bonuses and splits from NSE, show the user what was found and what needs manual handling (demergers, rights, buybacks), and apply. **Then check the share count per stock against the demat holding statement.** Do not go on until they match: a mismatch means missing trades or a missed action, and every later number would be wrong.

## 3. Compute the gains (`india-capital-gains`)

Run on the adjusted file, with 31 Jan 2018 values for shares bought before 1 Feb 2018 (restated for later splits and bonuses). Report by bucket: short-term and long-term equity, and anything taxed at slab rates. Pass on every warning. Compare the totals with the broker's own tax statement if there is one; a difference points back to step 1 or 2.

## 4. Before the year ends (`tax-harvest-planner`)

If the financial year is still open: unused long-term exemption, the shares that could be sold to use it, loss candidates, and lots about to turn long-term. Include the cost of the round trip (`trade-cost-calculator`).

## 5. Instalments (`advance-tax-on-gains`)

What was due by each instalment date for the gains realised so far, and the next amount due. Remind the user this covers capital gains only and that other income and TDS change the full picture.

## 6. The separate streams

- **F&O and intraday** (`fno-business-income`): business income, not capital gains. Report profit and both turnover figures, and take the audit question to a chartered accountant.
- **Foreign shares** (`foreign-assets-schedule-fa`, and `india-capital-gains` with `foreign_equity`): Schedule FA is for the calendar year and needs SBI rates the user supplies; gains must be in rupees.
- **Mutual funds:** the fund registrar's capital-gains statement is the practical source. `india-capital-gains` handles fund units if the user enters them, with the right asset class for equity or debt funds.

## Summary to give the user

A table for the year: each stream, the gain or loss, the tax computed where the skills compute it, and what remains open. Then a list of what they still need to do or confirm, in order.

## Boundaries

Say clearly at the start and the end: this prepares the numbers and catches mistakes; it is not a tax filing and not tax advice. The skills do not cover surcharge, loss set-off between buckets, carried-forward losses, slab tax, or non-residents. Recommend that a chartered accountant reviews the result before filing, and say so with more force when there are foreign assets, F&O turnover near an audit threshold, or large amounts. Never invent a cost, a date, a rate or an exchange rate to complete a calculation: ask for it.
