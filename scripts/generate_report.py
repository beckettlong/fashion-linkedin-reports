#!/usr/bin/env python3
"""
Research current fashion/apparel news via Claude's web search tool, draft a
LinkedIn post in the account's historic format, and open the draft as a
GitHub Issue for human review (manual posting — this script never touches
LinkedIn).

Editorial criteria live in specs/*.md, not in this file. Edit those to change
what gets pulled.
"""
import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import anthropic
import requests

MODEL = "claude-opus-5"
REPO_ROOT = Path(__file__).resolve().parent.parent

REPORTS = {
    "industry": {
        "spec": "specs/industry-news.md",
        "label": "Industry News",
        "window_days": 7,
        "format": """🚨LATEST FASHION, FOOTWEAR, AND APPAREL NEWS
[one sentence teaser naming the week's 1-2 biggest stories]

📈BRAND GROWTH
• [Brand] [Headline in title case] ([Source outlet])
[1-2 sentence summary with the key figures]

💰INVESTMENT AND M&A ACTIVITY
• [Company] [Headline in title case] ([Source outlet])
[1-2 sentence summary with the key figures]

🔄INDUSTRY MOVES
• [Full Name] → [New Title], [Company] ([Source outlet])
[one line per move, no summary paragraph]""",
    },
    "drops": {
        "spec": "specs/collaborations.md",
        "label": "Collections & Collaborations",
        "window_days": 7,
        "format": """🛍 [Start Date] – [End Date] Collections & Collaborations
[1-2 sentence intro summarizing the themes of the week's drops]

[Brand] × [Brand] "[Collection Name]" ([Release date])
[one short paragraph with the details]

[repeat per item]""",
    },
}

PROMPT = """You are researching and drafting a LinkedIn post for a fashion,
footwear, and apparel industry newsletter.

Today is {today}. The report window is {start} through {today} — find news
announced or published in that window.

Use the web_search tool to gather the stories. Search repeatedly and from
different angles until you have enough material to satisfy the brief below;
do not stop after one search. Only report things you actually found via
search — never invent a name, figure, date, or detail.

=== EDITORIAL BRIEF ===
{spec}
=== END EDITORIAL BRIEF ===

Output the post in exactly this format:

{format}

After the post text, add two more sections.

First, "SUGGESTED LINKEDIN TAGS" — list every named individual and every
brand/company mentioned in the post above. Do NOT guess a LinkedIn profile
URL. Instead give a LinkedIn people-search link built from their name and
company, formatted as:
- [Full Name] ([Company]): https://www.linkedin.com/search/results/people/?keywords=<urlencoded "Full Name Company">
The person composing the post will click through and pick the correct match
themselves, so accurate search terms matter more than a guessed profile.

Second, "SOURCES" — every URL you used, one per line, labeled with the item
it supports.
"""


def load_spec(spec_path: str) -> str:
    path = REPO_ROOT / spec_path
    if not path.exists():
        sys.exit(f"Spec file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def generate(report_type: str) -> str:
    config = REPORTS[report_type]
    today = date.today()
    start = today - timedelta(days=config["window_days"])

    prompt = PROMPT.format(
        today=today.isoformat(),
        start=start.isoformat(),
        spec=load_spec(config["spec"]),
        format=config["format"],
    )

    client = anthropic.Anthropic()
    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "high"},
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 25}],
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
    parser.add_argument("--type", choices=sorted(REPORTS), required=True)
    parser.add_argument(
        "--local",
        action="store_true",
        help="Print the draft to stdout instead of opening a GitHub Issue.",
    )
    args = parser.parse_args()

    report_text = generate(args.type)

    if args.local:
        print(report_text)
        return

    title = f"[{REPORTS[args.type]['label']}] Draft for {date.today().isoformat()}"
    print(f"Draft posted: {create_github_issue(title, report_text)}")


if __name__ == "__main__":
    main()
