#!/usr/bin/env python3
"""
Research current fashion/apparel news via Claude's web search tool, draft a
LinkedIn post in the account's historic format, and open the draft as a
GitHub Issue for human review (manual posting — this script never touches
LinkedIn).

Editorial criteria live in specs/*.md, not in this file.
Already-covered items live in history/covered.json and are fed back into the
prompt so successive reports don't repeat themselves.
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import anthropic
import requests

MODEL = "claude-opus-5"
REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = REPO_ROOT / "history" / "covered.json"
LEDGER_MARKER = "=== COVERED_ITEMS_JSON ==="

REPORTS = {
    "industry": {
        "spec": "specs/industry-news.md",
        "label": "Industry News",
        "window_days": 7,
        # How far back to look when suppressing repeats. Executive moves and
        # deals stay "old news" for a while, so this is deliberately long.
        "lookback_days": 60,
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
        # A drop happens once; 6 weeks is more than enough to catch repeats
        # from the announce-then-launch cycle.
        "lookback_days": 42,
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

{dedup_section}

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

Finally, on its own line, output exactly this marker:

{marker}

and after it a single JSON array recording every item you included, so future
reports can avoid repeating them. One object per item, with these fields:
  "key"      - short lowercase slug identifying the story, e.g.
               "target-rosie-assoulin" or "frasers-hugo-boss-stake"
               Use the same slug you would use for any future development of
               the SAME underlying story.
  "brands"   - array of the companies/brands involved
  "headline" - the headline as it appears in your post
  "note"     - one short phrase on what specifically happened, so a future
               report can tell a genuine development apart from a repeat
Output only the raw JSON array after the marker — no prose, no code fence.
"""

DEDUP_TEMPLATE = """=== ALREADY COVERED — DO NOT REPEAT ===
The following stories appeared in recent editions of this newsletter. Treat
them as already published.

{items}

Rules for handling these:
- Do NOT include an item that is substantially the same story as one above,
  even if you find it covered by a different outlet or with different wording.
- DO include a story whose slug matches one above ONLY IF there is a genuine
  material development since it was covered — a deal closed or was rejected, a
  price or valuation changed, a bid was raised, a collection that was merely
  announced has now actually launched with new detail. When you do, lead the
  summary with what is NEW, and do not re-narrate what was already reported.
- NEVER repeat an executive appointment that already appears above. A person
  starting a role you already announced is not a development.
- If avoiding repeats leaves you short of the target item count, report fewer
  items. Do not pad with weak stories to hit a number.
=== END ALREADY COVERED ===
"""


def load_spec(spec_path: str) -> str:
    path = REPO_ROOT / spec_path
    if not path.exists():
        sys.exit(f"Spec file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {"entries": []}
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"history/covered.json is not valid JSON: {exc}")


def build_dedup_section(report_type: str) -> str:
    """Render recent ledger entries into a 'do not repeat' block."""
    cutoff = date.today() - timedelta(days=REPORTS[report_type]["lookback_days"])
    recent = []
    for entry in load_history().get("entries", []):
        try:
            covered = datetime.strptime(entry["date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        if covered >= cutoff:
            recent.append(entry)

    if not recent:
        return ""

    lines = []
    for entry in sorted(recent, key=lambda e: e["date"], reverse=True):
        brands = ", ".join(entry.get("brands", []))
        lines.append(
            f'- [{entry["date"]}] ({entry.get("key", "?")}) {brands} — '
            f'{entry.get("headline", "")}. {entry.get("note", "")}'.strip()
        )
    return DEDUP_TEMPLATE.format(items="\n".join(lines))


def split_ledger(raw: str) -> tuple[str, list]:
    """Separate the human-facing draft from the machine-readable ledger."""
    if LEDGER_MARKER not in raw:
        print("WARNING: no ledger block found; history will not be updated.")
        return raw.strip(), []

    draft, _, tail = raw.partition(LEDGER_MARKER)
    tail = re.sub(r"^\s*```(?:json)?|```\s*$", "", tail.strip(), flags=re.MULTILINE)
    try:
        items = json.loads(tail.strip())
        if not isinstance(items, list):
            raise ValueError("ledger is not a JSON array")
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"WARNING: could not parse ledger ({exc}); history will not be updated.")
        return draft.strip(), []
    return draft.strip(), items


def append_history(report_type: str, items: list) -> int:
    if not items:
        return 0
    history = load_history()
    today = date.today().isoformat()
    existing = {e.get("key") for e in history.get("entries", [])}
    added = 0
    for item in items:
        key = item.get("key")
        if not key:
            continue
        history.setdefault("entries", []).append(
            {
                "date": today,
                "report_type": report_type,
                "key": key,
                "brands": item.get("brands", []),
                "headline": item.get("headline", ""),
                "note": item.get("note", ""),
                # Flag re-coverage so you can spot stories being followed
                # across weeks when reviewing the ledger.
                "followup": key in existing,
            }
        )
        added += 1
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    return added


def generate(report_type: str) -> str:
    config = REPORTS[report_type]
    today = date.today()
    start = today - timedelta(days=config["window_days"])

    prompt = PROMPT.format(
        today=today.isoformat(),
        start=start.isoformat(),
        spec=load_spec(config["spec"]),
        dedup_section=build_dedup_section(report_type),
        format=config["format"],
        marker=LEDGER_MARKER,
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
        help="Print the draft to stdout and do NOT record it in history.",
    )
    args = parser.parse_args()

    draft, ledger_items = split_ledger(generate(args.type))

    if args.local:
        print(draft)
        print(f"\n--- {len(ledger_items)} item(s) found; history NOT updated (--local) ---")
        return

    title = f"[{REPORTS[args.type]['label']}] Draft for {date.today().isoformat()}"
    print(f"Draft posted: {create_github_issue(title, draft)}")
    print(f"Recorded {append_history(args.type, ledger_items)} item(s) in history.")


if __name__ == "__main__":
    main()
