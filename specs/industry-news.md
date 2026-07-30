# Spec: Industry News (Monday post)

This file controls exactly what the weekly industry report pulls. Edit it freely —
the script reads it at runtime and passes it to Claude as the editorial brief.
No code changes needed. Everything below is instructions to the researcher.

## Sections and what counts

### 📈 BRAND GROWTH — 2–3 items
Growth signals at a fashion, footwear, or apparel brand:
- New store openings, flagships, pop-ups, market entries
- Launches into a new product category (e.g. an activewear brand entering eyewear)
- Reported revenue, sales growth, margin, or comparable-sales milestones
- Store-count expansion plans and rollout targets

Prioritize items with a **hard number** in them (a growth %, a revenue figure, a
store count). A growth story with no figure is weak.

### 💰 INVESTMENT AND M&A ACTIVITY — 2–3 items
- Funding rounds (include round size, lead investor, participating investors)
- Acquisitions and takeover bids (include price, stake %, status)
- IPOs and public listings (include valuation, share price range, exchange)
- Stake sales, buybacks, bankruptcy exits, restructurings

Prioritize deals with disclosed figures over undisclosed ones.

### 🔄 INDUSTRY MOVES — 5–10 items
Executive appointments, departures, and promotions at fashion, footwear, apparel,
or relevant retail companies. Format is strictly:

`[Full Name] → [New Title], [Company] ([Source])`

Include C-suite, president, managing director, creative director, and VP-level
and above. Skip anything below VP unless the company is small and the role is
clearly strategic.

## What to include per item (Growth and Investment sections)

- Company name as the company styles it (adidas, SKIMS, HUGO BOSS)
- The specific figures: percentages, dollar/euro amounts, dates, store counts
- Enough context to make the number meaningful (growth vs. what period; a
  valuation vs. a prior valuation)
- Named executives connected to the news

## Tone

Neutral trade-press. Factual, figure-forward, specific. No hype adjectives, no
second-person address, no emoji inside item bodies. One to two sentences per
item — dense, not padded. Write the way Business of Fashion writes a news brief.

## Preferred sources

Lead with: Business of Fashion, WWD, FashionNetwork, Drapers, SGB Media,
FashionUnited, PR Newswire, Reuters, company investor-relations releases.

## Hard rules

- Never invent a company, person, title, figure, or date. If you cannot verify it
  via search, leave it out.
- Executive moves are especially easy to get wrong — only include a move if you
  found it stated explicitly in a source, with both the name and the new title.
- If a section has fewer items than the target, report fewer — do not pad.
- Every item must trace to a real URL that you list in the SOURCES section.
