---
name: india-capital-gains
description: Compute capital gains for an Indian resident from a trade history - FIFO lot matching, short-term vs long-term classification, the 31 January 2018 grandfathering rule, the Rs 1.25 lakh equity exemption, and tax at 20% / 12.5% - for listed Indian shares and equity mutual funds, US and other foreign stocks, debt funds and gold ETFs. Use when the user asks how much capital gains tax they owe, whether a holding is long-term yet, what selling now would cost in tax, how US stocks are taxed in India, or wants a realised gains statement for FY 2025-26 onward.
---

# India Capital Gains

Turns a list of buys and sells into realised gains per financial year, classified and taxed under the rules in force from 1 April 2025. Run the script; do not match lots or apply rates by hand.

## Run it

```bash
python scripts/capital_gains.py --trades trades.csv [--fmv fmv.csv] [--lots]
```

`trades.csv`:

```csv
date,symbol,side,quantity,price,asset_class,charges
2024-01-10,INFY,buy,100,1000,listed_equity,0
2025-06-10,INFY,sell,100,3000,listed_equity,0
2023-01-10,AAPL,buy,10,10000,foreign_equity,0
```

- `asset_class` (default `listed_equity`): `listed_equity`, `foreign_equity`, `debt_fund_post_2023`, `listed_other` (gold and silver ETFs), `unlisted_other` (gold and overseas funds-of-funds).
- `charges`: brokerage and transfer expenses for that trade, **excluding STT** (STT is not deductible).
- `--fmv`: `symbol,fmv` with the 31 Jan 2018 highest quoted price, needed for shares bought before 1 Feb 2018.
- `--lots` adds every matched lot to the output.

## Getting the input right

1. **Give the full purchase history for every symbol sold**, even buys from years ago. FIFO needs the earliest lots. If a sell exceeds the buys supplied, the script stops and says how many units are missing.
2. **Foreign stocks must be in rupees.** Convert each trade before building the CSV. The prescribed rate (Rule 115: SBI telegraphic transfer buying rate on the last day of the month before the transfer) is not automated here. If the user only has USD figures, say the INR conversion is their step and which rate applies.
3. **Corporate actions are not applied.** For a split or bonus, adjust the buy rows first (a 1:1 bonus adds a buy row at zero cost on the allotment date; a split multiplies quantity and divides price).
4. A broker's tradebook can be reshaped into this CSV. Check the side and date columns after converting.

## Reading the output

Per financial year there is one bucket per asset class and term, with gains, losses, net, the rate, the exemption and the section. Then:

- `special_rate_tax_with_cess`: tax on the 20% and 12.5% buckets plus 4% cess.
- `gains_taxed_at_slab_rates`: added to the user's other income. Its tax depends on their slab, so it is not computed.
- `warnings` and `notes`: pass these on. In particular, **losses are reported but not set off**. Explain the rule (short-term losses offset any capital gain; long-term losses offset only long-term gains) and that the order is the taxpayer's choice.

## The holding-period boundary

Long-term means held for *more than* 12 months (24 for foreign and unlisted). Bought 1 Jan 2025: a sale on 1 Jan 2026 is short-term, 2 Jan 2026 is long-term. When a user asks "is it long-term yet?", state the first long-term sale date.

## Limits - state them, do not work around them

- Sales before 1 Apr 2025 are not reported (earlier years had a mid-year rate change).
- Not handled: surcharge, loss set-off and carry-forward, the basic-exemption shortfall adjustment, F&O and intraday (business income, not capital gains), buybacks, non-residents. The output lists these under `not_handled`.
- Section numbers of the Income-tax Act, 2025 (196, 197, 198) are shown beside the 1961 numbers. Section 196 was read from the department's site; 197 and 198 come from secondary summaries.
- This is a computation aid. For filing, the user should confirm with a chartered accountant, especially for foreign assets (Schedule FA and foreign tax credit are separate obligations).
