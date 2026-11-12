---
name: institutional-holdings-13f
description: Show what a US institutional investor owns and what it changed last quarter, from its 13F filings with the SEC - top holdings by value and weight, new positions, the largest increases and decreases, and exits. Use when the user asks what a hedge fund or well-known investor bought or sold, about 13F filings, Berkshire Hathaway's or another fund's portfolio, or institutional buying in a US stock.
---

# Institutional Holdings (13F)

**One-time setup.** The SEC requires automated requests to identify the requester by name and email. Ask the user which name and email to use and set:

```bash
export MARKET_SKILLS_SEC_USER_AGENT="Their Name their.email@example.com"
# Windows PowerShell: $env:MARKET_SKILLS_SEC_USER_AGENT="Their Name their.email@example.com"
```

Never invent an email or use a placeholder: the SEC uses it to contact requesters. Without it the script stops and explains.

```bash
python scripts/holdings_13f.py --ticker BRK-B       # a listed manager
python scripts/holdings_13f.py --cik 1067983        # any manager, by SEC CIK
```

Find a manager's CIK through the SEC's EDGAR company search.

## Output

Latest and previous filing (period, filing date), number of positions and total value, top holdings with weight and share change, new positions, largest increases and decreases, and exits. Lines for the same security are combined.

## Reading it correctly

- **It is old:** filed up to 45 days after the quarter end. Always state the period.
- **It is partial:** US-listed long positions and listed options only; no shorts, cash, bonds or foreign shares. It is not the whole portfolio, and a large position can be one side of a hedge.
- **Reasons are unknown:** a sale may be a redemption or a risk limit.
- Following a manager means buying weeks later at other prices. Present the data; do not suggest copying it.

## Limits

US managers filing 13F-HR (over $100 million in US equities). Amendments are not merged. Values as reported by the filer.
