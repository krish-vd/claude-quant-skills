---
name: option-chain-analyzer
description: Analyse an NSE option chain (NIFTY, BANKNIFTY, FINNIFTY or any F&O stock) from the official end-of-day bhavcopy - put/call ratio by open interest and volume, max pain, the forward price implied by put-call parity, at-the-money implied volatility, the straddle-implied move, the strikes with the most open interest and the largest additions. Use when the user asks about option chain data, PCR, max pain, open interest build-up, where support and resistance sit by OI, what move the market is pricing in before expiry or an event, or the current implied volatility of an index or stock.
---

# Option Chain Analyzer

Reads the exchange's own end-of-day F&O file. Run the script; never quote option-chain figures from memory.

## Run it

```bash
python scripts/option_chain.py NIFTY --rate 0.065                 # nearest expiry, latest published day
python scripts/option_chain.py BANKNIFTY --expiry 2026-11-24
python scripts/option_chain.py RELIANCE --date 2026-11-11 --top 8
python scripts/option_chain.py NIFTY --list-expiries
```

`--rate` is the risk-free rate as a decimal, used only for implied volatility; pass the current 91-day T-bill yield (it matters little for near expiries).

## What each figure means

| Field | Meaning | How to read it |
|---|---|---|
| `forward`, `forward_source` | The futures settlement price for that expiry, or, when no future lists for it (weekly expiries), the forward implied by put-call parity | This, not spot, is the centre of the chain |
| `pcr_open_interest`, `pcr_volume` | Put OI / call OI, and put volume / call volume | A level, not a signal. Compare with the same expiry on earlier days |
| `max_pain` | The strike where option buyers in total would be paid least at expiry | Descriptive; index expiries often settle elsewhere |
| `atm_iv_pct` | Black-76 implied volatility at the strike nearest the forward | The market's annualised volatility estimate for that expiry |
| `atm_straddle_price`, `straddle_implied_move_pct` | Cost of the at-the-money call plus put, and that cost as a percent of the forward | Roughly the move, up or down, priced in until expiry |
| `highest_call_oi`, `highest_put_oi` | Strikes with the most open interest | Where positions are concentrated |
| `largest_*_oi_additions` | Strikes where open interest rose most that day | Where new positions were opened |

Open interest is in units of the underlying; `oi_lots` divides by the lot size.

## Stating results honestly

- **Always give `as_of`.** This is end-of-day data, published in the evening. It is not a live chain and will differ from what a trading screen shows intraday.
- **Open interest has no direction.** Every contract has a buyer and a seller. "Heavy call OI at 26000" means many contracts exist there; it does not show who wrote them. The common reading that call writers defend a strike is an interpretation - present it as one.
- Do not present max pain, a PCR level or an OI wall as a forecast or a price target.
- The straddle-implied move is what option prices imply, not a probability of the move happening.
- Implied volatility within a day or two of expiry is unstable; the script flags this.

## Useful follow-ups

- Run it for two dates (`--date`) to show how OI and implied volatility changed.
- Feed the forward and `atm_iv_pct` into `option-pricer` for greeks, or build the user's position in `option-payoff-builder`.

## Limits

NSE only. No intraday data, no historical implied-volatility percentile, no volatility skew table (only the at-the-money point). Illiquid stock options can have stale settlement prices: the parity forward uses only strikes that traded that day.
