---
name: delivery-volume-screener
description: Find NSE stocks where the quantity of shares actually delivered (settled into demat, not squared off intraday) has jumped against its recent average, using the exchange's official security-wise delivery data. Use when the user asks about delivery percentage, delivery volume spikes, high-delivery stocks, where real buying or accumulation is showing up, or wants to tell genuine volume from intraday churn.
---

# Delivery Volume Screener

```bash
python scripts/delivery_screen.py                              # latest day vs the 10 sessions before it
python scripts/delivery_screen.py --direction up --min-ratio 3 --min-turnover-lakh 2000
python scripts/delivery_screen.py --date 2026-11-11 --sessions 20 --top 40
```

Options: `--min-ratio` (delivered quantity over its average, default 2), `--min-turnover-lakh` (that day's turnover in Rs lakh, default 500 = Rs 5 crore), `--direction up|down|any` (the day's price change), `--sessions` (days averaged, default 10).

## Reading a row

| Field | Meaning |
|---|---|
| `delivery_ratio` | Today's delivered quantity divided by its average over the earlier sessions |
| `delivered_qty`, `avg_delivered_qty` | The two figures behind the ratio |
| `delivery_pct`, `avg_delivery_pct` | Share of traded quantity that was delivered, today and on average |
| `price_change_pct` | Close against the previous close |
| `turnover_lakh` | Value traded that day, Rs lakh |

The most informative rows combine a high ratio with a delivery percentage well above the stock's own average. A high ratio with a low delivery percentage just means a very heavy trading day.

## What it does and does not tell you

Data is NSE's own end-of-day file (EQ series). It shows that more shares than usual changed hands for keeps. It does not show who bought, who sold, or why. Every delivered share has a buyer and a seller, so "accumulation" is an interpretation, not a fact in the data. Spikes are commonly caused by block and bulk deals, index inclusions and rebalancing, results days, promoter or fund transactions, and stocks moving in or out of F&O.

So present the list as stocks where something happened, then check the cause: look for a bulk or block deal, results, or news that day. A spike on a down day is as much a spike as one on an up day; do not describe either as bullish or bearish on the delivery figure alone.

Follow-ups: `stock-screener` for the trend context of a name, `market-data nse-quote` for its official price.

## Limits

- NSE keeps this file for recent sessions only, so the average window cannot reach far back; a stock needs a figure on every day of the window to be screened.
- India only. One exchange: BSE deliveries are not included.
- End-of-day. Stocks in trade-for-trade series (100% delivery by rule) are excluded.
- Candidates for research, not recommendations.
