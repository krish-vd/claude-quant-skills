---
name: market-news-brief
description: Research and summarise the market-moving news behind a stock, sector, index or commodity move - what happened, when, which sources reported it, how prices reacted, and what is scheduled next - for Indian and US markets, with every claim tied to a dated source. Use when the user asks why a stock or the market moved, what the news is on a company, what happened in the markets today or this week, what events are coming up (RBI, Fed, budget, results, data releases), or wants a news check before taking a trade.
---

# Market News Brief

This skill has no script. It is a method for using web search carefully, because news is where an assistant most easily states something stale or invented as fact.

## Ground rules

1. **Search; never answer from memory.** Anything you remember about a company or the market may be months out of date. If web search is not available in this session, say so and stop: do not write a news summary from recall.
2. **Every factual claim needs a source and a date.** Give the publication and the date of the article. If you cannot find a source for a claim, leave it out.
3. **Check the date of each result.** Search engines return old articles for new queries. Discard anything outside the period the user asked about, and state the period you covered.
4. **Prefer primary sources:** exchange announcements (NSE and BSE corporate filings, SEC filings), regulator and central-bank releases (SEBI, RBI, the Federal Reserve), company press releases, then established financial news. Treat social media, forums and unsourced "market buzz" as rumour and label it so, or omit it.
5. **Separate what happened from why the price moved.** "The stock fell 6% after the company cut guidance" reports a sequence. Whether the cut caused the fall is an inference; phrase it as "the fall followed" or "reports attribute it to". Often no clear cause exists: say that instead of inventing one.
6. **Numbers come from the tools, not from articles.** For a price, a move, results figures or an event date, use the other skills: `market-data` for official closes, `company-fundamentals` for reported results, `results-calendar` for results and ex-dates, `institutional-positioning` for FII and DII flows, `market-breadth` and `sector-rotation` for the market's state. Quote an article's number only when no tool has it, and say it is the article's figure.

## Method

1. Fix the scope: which instrument, and which period (today, this week, since a date). If the user asked "why did X fall", first confirm the move and its size from `market-data`.
2. Search with specific, dated queries: the company name plus "results", "announcement", "order", "SEBI", "downgrade", the month and year. For a market-wide move add the index name and the date. Run several queries rather than one broad one.
3. For a company, also check the exchange's announcements page for filings in the period.
4. Read the best two to four sources. Do not rely on headlines or search snippets: they are often misleading or truncated.
5. Note what is scheduled next: results date, ex-date, a regulatory decision, a central-bank meeting, a data release.

## Output

Keep it short and in this order:

- **What happened:** two to five dated bullet points, each with its source.
- **Price reaction:** the move, from the tools, with the date.
- **What is not known or disputed:** conflicting reports, unconfirmed claims, or "no specific news found for this move".
- **What is next:** dated upcoming events.
- **Sources:** the links used.

## What not to do

- Do not say whether the news makes the stock a buy or a sell, and do not predict the reaction to an upcoming event.
- Do not present analyst price targets or broker calls as facts about value; if reported, attribute them ("X brokerage cut its target, according to Y").
- Do not fill a gap with a plausible story. "I found no news explaining this move" is a complete and useful answer.
- Do not paste long passages from articles; summarise in your own words and link.
