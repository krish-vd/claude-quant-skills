---
name: crypto-regime
description: Read the crypto market regime - Bitcoin, Ethereum, Solana and other coins' trend, drawdown from the five-year peak, 30-day realised volatility and correlation with the Nasdaq, the ETH/BTC ratio, and large-speculator positioning in CME Bitcoin futures from the CFTC. Use when the user asks about crypto market conditions, whether Bitcoin is in an uptrend or bear market, crypto volatility, altcoin strength against Bitcoin, or before trading or sizing a crypto position.
---

# Crypto Regime

```bash
python scripts/crypto_regime.py
python scripts/crypto_regime.py --coins BTC,ETH,SOL,XRP,DOGE
```

## Output

- `bitcoin_trend`: `uptrend` (above the 200-day average and 50-day above 200-day), `downtrend` (both below) or `transition`.
- Per coin: close in USD, trend flags, 1- and 3-month returns, drawdown from the five-year peak, 30-day realised volatility (annualised over 365 days), and 90-day correlation of daily returns with the Nasdaq Composite.
- `eth_btc_ratio`: value, one-year and five-year percentile, one-month change. Rising means Ethereum is outperforming Bitcoin, often read as wider risk appetite within crypto.
- `cme_bitcoin_futures_positioning`: large speculators' net position in CME Bitcoin futures and its three-year COT index (see `cot-positioning`).

## Presenting it

State trend, drawdown and volatility first: volatility is what should set position size. `position-sizer` with a stop sized to crypto's volatility usually gives far smaller positions than for stocks; say so. A high correlation with the Nasdaq means crypto is behaving as a risk asset, not a hedge.

Do not predict prices, halving effects or cycles. Mention that falls of 70% or more have happened more than once.

For Indian users: crypto gains are taxed under a separate flat-rate regime with TDS on transfers and no set-off of losses against other income. These skills do not compute it; tell them to confirm the current rules with a tax professional.

## Limits

Prices from Yahoo, daily bars ending 00:00 UTC; the current day is excluded. No on-chain data, funding rates, or open interest outside CME.
