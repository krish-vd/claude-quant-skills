---
name: daily-trading-routine
description: Run a trader's daily routine end to end by chaining the other skills in order - market posture, risk check, results and events due, candidate screen, fundamentals check, position size and costs, pre-trade gate, and journal entry - stopping at each gate that says no. Use when the user asks for their morning routine, a pre-market or daily checklist, to "run my routine", to find and plan today's trades, or how to use these skills together.
---

# Daily Trading Routine

A fixed order of work for a swing trader in Indian or US stocks. Each step uses another skill from this collection; this skill only sets the order and the gates. Run the steps in sequence and **stop when a gate says no**. Most days the correct output of this routine is "no new trade".

Ask once at the start for anything not already known: market (India or US), account size, risk per trade (default 1%), and the universe to screen (default Nifty 200 for India).

## Step 1 - Market conditions (`market-posture-daily`)

Report the label and the cautions.

- `defensive`: say so plainly. The routine continues only to manage existing positions (steps 2 and 3). New entries are for the user to decide knowingly; do not screen for candidates unless they ask.
- `mixed` or `constructive`: continue.

## Step 2 - Am I allowed to take risk? (`risk-circuit-breaker`)

Gate. If `new_risk_allowed` is false, report which limit is breached and end the new-trade part of the routine. Report open positions without a stop.

## Step 3 - What is scheduled? (`results-calendar`)

Run with `--open-trades` and report any holding with results in the next week, and any ex-dates. For India also note the nearest F&O expiry if the user trades derivatives (`fno-expiry-calendar`).

## Step 4 - Candidates (`stock-screener`)

Screen the chosen universe. Use `trend_template` for established uptrends, `contraction` for tight bases, `breakout` for stocks already moving. Apply a liquidity floor suited to the account size. Show at most five to eight rows, with the `as_of` date and the official price check. If nothing passes, say so and stop: an empty screen is information.

For India, `sector-rotation` shows whether a candidate sits in a leading or lagging sector, and `delivery-volume-screener` whether the move came with real delivery.

## Step 5 - Is the business behind the chart? (`company-fundamentals`, `results-calendar`, `market-news-brief`)

For the two or three candidates the user is interested in: recent revenue and profit growth, whether results are due inside the likely holding period, and a brief news check for anything that explains or threatens the move. Drop a candidate with results due in the next few days unless the user chooses to hold through them.

## Step 6 - The plan (`position-sizer`, `trade-cost-calculator`)

The user supplies the entry and the stop. Do not choose them. If they have no stop, ask where the idea is proven wrong; without one the routine stops here. Then compute the size, the planned loss in money, and the round-trip cost.

## Step 7 - Gate (`pre-trade-checklist`)

Run the plan through the gate. If it is blocked, report the failed rule and the adjustment that would pass. Do not weaken a limit to get a pass.

## Step 8 - Record (`trade-journal`)

Only after the user confirms the order was actually filled: record the trade with their own thesis and setup tag.

## Closing summary

End with a short summary: market label, risk status, events to watch, the plan (or "no trade today" with the reason), and what to check tomorrow.

## Boundaries

The routine organises the user's process. Entry, stop, and the decision to trade are theirs. Never present a screened stock as a recommendation, never invent a stop or a target, and never skip a gate because the setup looks good. If a step's data is unavailable, say which step was skipped and why, and carry on with the rest.
