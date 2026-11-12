---
name: commodity-regime
description: Read the commodity and currency backdrop - trend and one-year range position of gold, silver, copper, WTI and Brent crude, natural gas, platinum, the dollar index and USD/INR; the gold/silver, gold/copper, gold/crude and Brent/WTI ratios with percentiles; and international prices converted to MCX quoting units in rupees. Use when the user asks about gold, silver, crude or commodity trends, the gold-silver ratio, whether MCX gold is at a premium to international prices, how the rupee affects commodity prices, or wants a commodities overview before trading MCX or US futures.
---

# Commodity Regime

```bash
python scripts/commodities.py
python scripts/commodities.py --mcx gold=125000 --mcx silver=152000 --mcx crude=8150
```

## Reading the output

**`instruments`** - for each of gold, silver, copper, crude (WTI), brent, natural gas, platinum, dollar index and USD/INR: last close, whether it is above its 50 and 200-day averages, 1 and 3-month returns, distance from the 52-week high, and `percentile_in_1y_range` (0 = at the one-year low, 100 = at the high).

**`ratios`** - value, its percentile within the last year and within the full five-year history, and the one-month change:

| Ratio | Commonly read as |
|---|---|
| `gold_to_silver` | High when silver lags gold (risk aversion or weak industrial demand); low when silver outruns it |
| `gold_to_copper` | High when safety is preferred to growth; low when industrial demand leads |
| `gold_to_crude` | Barrels of oil one ounce of gold buys |
| `brent_to_wti` | The spread between seaborne and US crude |

These readings are conventions among traders. Present them as such, not as rules.

**`rupee_conversion`** - the international price converted at the current USD/INR into the unit MCX quotes in: gold per 10 g, silver per kg, copper per kg, crude per barrel, natural gas per mmBtu. With `--mcx COMMODITY=PRICE` it adds `local_premium_pct`.

## About the MCX premium

The conversion is currency and units only (1 troy ounce = 31.1034768 g; 1 lb = 0.45359237 kg). An MCX price normally sits above it because of import duty, taxes, freight, the local premium or discount, and a different contract month. So:

- A positive `local_premium_pct` on gold or silver is normal. Do not call it mispricing or an arbitrage.
- What is informative is a **change** in the premium over time, or a premium far from its usual size. The script does not know the usual size; if the user tracks it, compare with their figure. Do not quote a duty rate from memory to explain the gap - rates change with budgets.
- The MCX price must come from the user (or their broker screen). There is no free MCX price feed here.

## Using it

For an Indian commodity trader the rupee leg matters as much as the dollar price: a flat gold price with a weaker rupee still lifts MCX gold. Point this out when USD/INR has moved. To size a trade, use `position-sizer` with the MCX or US contract symbol; for charges, `trade-cost-calculator` with `commodity_futures`.

Describe the regime; do not forecast. A ratio at a one-year extreme can stay there.

## Limits

- Front-month futures from an unofficial source (Yahoo): continuous series jump at contract rolls, which distorts returns and ratios around roll dates, most of all for natural gas and crude.
- No MCX prices, no inventories, positioning or seasonality. End-of-day only.
- Five years of history, so `percentile_all` is "within five years", not all time.
