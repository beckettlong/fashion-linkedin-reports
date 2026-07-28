#!/usr/bin/env python3
"""
Research current fashion/apparel news via Claude's web search tool, draft a
LinkedIn post in the account's historic format, and open the draft as a
GitHub Issue for human review (manual posting — this script never touches
LinkedIn).
"""
import argparse
import os
from datetime import date, timedelta

import anthropic
import requests

MODEL = "claude-opus-5"

INDUSTRY_INSTRUCTIONS = """
You are drafting a LinkedIn post for a fashion/apparel/footwear industry newsletter.
Use the web_search tool to find REAL, VERIFIABLE news from the past 7 days (as of {today}).
Only include stories you found via search — never invent names, figures, or quotes.

Cover these categories, in this order, using ONLY items with a real, cited source:

1. BRAND GROWTH — store openings, product launches, sales/revenue milestones
2. INVESTMENT AND M&A ACTIVITY — funding rounds, acquisitions, IPOs, stake sales
3. INDUSTRY MOVES — executive hires/departures/promotions at fashion, footwear, or
   apparel companies

Match this EXACT historic format:

🚨LATEST FASHION, FOOTWEAR, AND APPAREL NEWS
[one sentence teaser naming the week's 1-2 biggest stories]

📈BRAND GROWTH
• [Brand] [Headline in title case] ([Source outlet])
[1-2 sentence summary of the news, written in a neutral trade-press tone,
including the key figures/facts]

💰INVESTMENT AND M&A ACTIVITY
• [Company] [Headline] ([Source outlet])
[1-2 sentence summary]

🔄INDUSTRY MOVES
• [Full Name] → [New Title], [Company] ([Source outlet])
(repeat for each move found, 5-10 items if available)

Pick 2-3 items per BRAND GROWTH and INVESTMENT sections (the strongest, most
verifiable stories), and as many INDUSTRY MOVES items as you can confidently
source.

After the full post text, add a section titled "SUGGESTED LINKEDIN TAGS" listing
every named individual and brand/company mentioned above. For each one, do NOT
guess a LinkedIn profile URL — instead give a LinkedIn people-search link built
from their name and company, formatted as:
- [Full Name] ([Company]): https://www.linkedin.com/search/results/people/?keywords=<urlencoded "Full Name Company">
The person composing the post will click through and pick the correct match
themselves, so accuracy of the search terms matters more than a guessed profile.

Then add a "SOURCES" section listing every URL you used, one per line.
"""

DROPS_INSTRUCTIONS = """
You are drafting a LinkedIn post for a fashion/apparel newsletter covering the
week's collaborations and product drops. Use the web_search tool to find REAL,
VERIFIABLE collaborations, capsule collections, or special releases announced
or launched between {start} and {today}. Only include drops you found via
search — never invent brands, dates, or details.

Match this EXACT historic format:

🛍 [Start Date] – [Today's Date] Collections & Collaborations
[1-2 sentence intro summarizing the theme/highlights of the week's drops]

[Brand] × [Brand] "[Capsule/Collection Name]" ([Release date])
[1 short paragraph: what the collaboration is, key details — price, availability,
design inspiration, notable people involved]

(repeat for each drop found, aim for 4-8 items)

After the full post text, add a section titled "SUGGESTED LINKEDIN TAGS" listing
every named individual, brand, and company mentioned above. For each one, do NOT
guess a LinkedIn profile URL — instead give a LinkedIn people-search link built
from their name and company, formatted as:
- [Full Name] ([Company]): https://www.linkedin.com/search/results/people/?keywords=<urlencoded "Full Name Company">
The person composing the post will click through and pick the correct match
themselves, so accuracy of the search terms matters more than a guessed profile.

Then add a "SOURCES" section listing every URL you used, one per line.
"""


def build_prompt(report_type: str) -> str:
    today = date.today()
    if report_type == "industry":
        return INDUSTRY_INSTRUCTIONS.format(today=today.isoformat())
    start = today - timedelta(days=7)
    return DROPS_INSTRUCTIONS.format(start=start.isoformat(), today=today.isoformat())


def generate(report_type: str) -> str:
    client = anthropic.Anthropic()
    prompt = build_prompt(report_type)

    with client.messages.stream(
        model=MODEL,
        max_tokens=8000,
        output_config={"effort": "medium"},
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 15}],
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request (safety refusal).")

    text_parts = [block.text for block in response.content if block.type == "text"]
    if not text_parts:
        raise RuntimeError(f"No text content returned. stop_reason={response.stop_reason}")
    return "\n\n".join(text_parts)


def create_github_issue(title: str, body: str) -> str:
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"title": title, "body": body},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["html_url"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["industry", "drops"], required=True)
    args = parser.parse_args()

    report_text = generate(args.type)
    label = "Industry News" if args.type == "industry" else "Collections & Collaborations"
    title = f"[{label}] Draft for {date.today().isoformat()}"

    url = create_github_issue(title, report_text)
    print(f"Draft posted: {url}")


if __name__ == "__main__":
    main()
