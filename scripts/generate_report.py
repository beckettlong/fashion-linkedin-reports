#!/usr/bin/env python3
"""
Two-stage LinkedIn post pipeline.

  Stage 1 (collect) : search the web, score and rank candidate stories,
                      post them as a checkbox list for human review.
  Stage 2 (draft)   : read back which boxes were checked, then draft the
                      post using ONLY the approved stories.

Nothing here touches LinkedIn — posting stays manual.

Editorial criteria live in specs/*.md. Already-covered stories live in
history/covered.json and are excluded from candidate collection.
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
CANDIDATES_MARKER = "=== CANDIDATES_JSON ==="
# Candidate data rides along inside the issue body in an HTML comment, so the
# draft stage needs nothing but the issue number to reconstruct everything.
EMBED_OPEN = "<!-- CANDIDATES_DATA"
EMBED_CLOSE = "-->"

WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 30}
WEB_FETCH = {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 25}

REPORTS = {
    "industry": {
        "spec": "specs/industry-news.md",
        "label": "Industry News",
        "window_days": 7,
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
        "lookback_days": 42,
        "format": """🛍 [Start Date] – [End Date] Collections & Collaborations
[1-2 sentence intro summarizing the themes of the week's drops]

[Brand] × [Brand] "[Collection Name]" ([Release date])
[one short paragraph with the details]

[repeat per item]""",
    },
}

# ---------------------------------------------------------------- stage 1

COLLECT_PROMPT = """You are researching candidate stories for a fashion,
footwear, and apparel industry newsletter. You are NOT writing the post yet —
your job is to find and rank candidates for a human editor to choose from.

Today is {today}. The window is {start} through {today} — find stories
announced or published in that window.

Use the web_search tool aggressively: search repeatedly, from many angles, with
different phrasings and brand names, until you have a broad pool. Only report
things you actually found — never invent a story, brand, date, or URL.

=== WHAT COUNTS AS A CANDIDATE ===
{spec}
=== END ===

=== HOW TO SCORE AND RANK ===
{ranking}
=== END ===

{dedup_section}

Output a short plain-text summary of what you searched and how many candidates
you found. Then output this marker on its own line:

{marker}

followed by a single JSON array, sorted by combined score descending. One
object per candidate with exactly these fields:
  "id"           - "c01", "c02", ... in final sorted order
  "title"        - the article headline, exactly as published
  "url"          - direct link to the article
  "source"       - publishing outlet, e.g. "WWD"
  "brands"       - array of brands/companies involved
  "published_at" - when the ARTICLE was published: "YYYY-MM-DD", optionally
                   with a time if stated, e.g. "2026-08-12 09:30 ET".
                   Use "unknown" if the article carries no date.
  "released_at"  - when the DROP itself releases or released. Same format.
                   Many drops have a specific launch time — include it when
                   reported, e.g. "2026-08-15 10:00 ET". Use "unknown" if no
                   release date is given, or "TBC" if explicitly unannounced.
  "relevance"    - integer 1-10
  "hype"         - integer 1-10
  "why"          - one sentence: what the drop is and why it scored this way
  "key"          - short lowercase slug for dedup, e.g. "burberry-hunza-g-swim"

These two dates are DIFFERENT and must not be conflated. The article date is
when coverage ran; the release date is when the product becomes available. A
preview published well ahead of launch is common — report both accurately and
never copy one into the other as a guess.
Output only the raw JSON array after the marker — no prose, no code fence.
"""

# ---------------------------------------------------------------- stage 2

DRAFT_PROMPT = """You are drafting a LinkedIn post for a fashion, footwear, and
apparel industry newsletter.

A human editor has already reviewed a candidate list and approved exactly the
stories below. Write the post from these and ONLY these — do not add stories,
do not search for additional items, and do not drop an approved item.

=== APPROVED STORIES ===
{approved}
=== END ===

Use the web_fetch tool to read each article at its URL so your summaries carry
accurate specifics — prices, dates, silhouettes, named people, figures. If a
fetch fails, fall back to web_search for that story. Never invent a detail to
fill a gap; if something cannot be verified, leave it out of the summary.

=== EDITORIAL BRIEF (tone, structure, house style) ===
{spec}
=== END ===

Output the post in exactly this format:

{format}

After the post text, add two more sections.

First, "SUGGESTED LINKEDIN TAGS" — every named individual and brand mentioned.
Do NOT guess a LinkedIn profile URL. Give a people-search link instead:
- [Full Name] ([Company]): https://www.linkedin.com/search/results/people/?keywords=<urlencoded "Full Name Company">

Second, "SOURCES" — every URL you used, one per line, labeled with its item.

Finally, output this marker on its own line:

{marker}

followed by a single JSON array recording what you covered, one object per item
with fields "key", "brands", "headline", "note" (a short phrase on what
specifically happened). Reuse the "key" given for each approved story above.
Output only the raw JSON array after the marker — no prose, no code fence.
"""


def load_text(rel_path: str) -> str:
    path = REPO_ROOT / rel_path
    if not path.exists():
        sys.exit(f"File not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {"entries": []}
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(f"history/covered.json is not valid JSON: {exc}")


def build_dedup_section(report_type: str) -> str:
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
    lines = [
        f'- ({e.get("key", "?")}) {", ".join(e.get("brands", []))} — '
        f'{e.get("headline", "")}. {e.get("note", "")}'.strip()
        for e in sorted(recent, key=lambda e: e["date"], reverse=True)
    ]
    return (
        "=== ALREADY COVERED — EXCLUDE FROM CANDIDATES ===\n"
        "These stories already ran in this newsletter. Do not surface them again\n"
        "unless there is a genuine material development since (a deal closed or\n"
        "was rejected, a valuation changed, an announced collection actually\n"
        "launched). If you do surface a development, reuse the same key and say\n"
        "in \"why\" what is new. Never re-surface an executive appointment.\n\n"
        + "\n".join(lines)
        + "\n=== END ===\n"
    )


def call_claude(prompt: str, tools: list) -> str:
    client = anthropic.Anthropic()
    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "high"},
        tools=tools,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request (safety refusal).")
    parts = [b.text for b in response.content if b.type == "text"]
    if not parts:
        raise RuntimeError(f"No text returned. stop_reason={response.stop_reason}")
    return "\n\n".join(parts)


def split_marker(raw: str, marker: str) -> tuple[str, list]:
    """Separate human-facing prose from a trailing JSON block."""
    if marker not in raw:
        print(f"WARNING: marker {marker} not found in response.")
        return raw.strip(), []
    prose, _, tail = raw.partition(marker)
    tail = re.sub(r"^\s*```(?:json)?|```\s*$", "", tail.strip(), flags=re.MULTILINE)
    try:
        items = json.loads(tail.strip())
        if not isinstance(items, list):
            raise ValueError("expected a JSON array")
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"WARNING: could not parse JSON after {marker}: {exc}")
        return prose.strip(), []
    return prose.strip(), items


# ------------------------------------------------------------ github i/o

def gh_request(method: str, path: str, **kwargs) -> dict:
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    resp = requests.request(
        method,
        f"https://api.github.com/repos/{repo}/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
        **kwargs,
    )
    resp.raise_for_status()
    return resp.json()


def release_status(released_at: str) -> str:
    """Label a drop as upcoming / live based on its release date."""
    if not released_at or released_at.lower() in {"unknown", "tbc", "n/a"}:
        return "❔ undated"
    try:
        when = datetime.strptime(released_at[:10], "%Y-%m-%d").date()
    except ValueError:
        return "❔ undated"
    delta = (when - date.today()).days
    if delta > 0:
        return f"🔜 in {delta}d"
    if delta == 0:
        return "🔴 today"
    return f"✅ {abs(delta)}d ago"


def render_review_issue(report_type: str, candidates: list, notes: str) -> str:
    """Build the checkbox list a human ticks to approve stories."""
    label = REPORTS[report_type]["label"]
    lines = [
        f"### Candidate stories — {label}",
        "",
        "**Tick every story you want in the post, then add the `approved` "
        "label to this issue.** That triggers the drafting run, which reads "
        "each approved article in full and writes the post from those only.",
        "",
        "Unticked stories are ignored. If nothing is ticked, no draft is made.",
        "",
        "`drops` = when the product releases · `article` = when coverage ran",
        "",
        "| | score | timing | story |",
        "|---|---|---|---|",
    ]
    for c in candidates:
        combined = c.get("relevance", 0) + c.get("hype", 0)
        released = c.get("released_at", "unknown")
        published = c.get("published_at", "unknown")
        lines.append(
            f'| `{c["id"]}` | **{combined}** '
            f'<br><sub>rel {c.get("relevance","?")} · hype {c.get("hype","?")}</sub> '
            f'| <sub>**drops** {released}<br>{release_status(released)}'
            f'<br><br>**article** {published}</sub> '
            f'| [{c.get("title","(untitled)")}]({c.get("url","")})'
            f'<br><sub>{c.get("source","?")} · '
            f'{", ".join(c.get("brands", []))}</sub>'
            f'<br>{c.get("why","")} |'
        )
    lines += ["", "---", ""]
    for c in candidates:
        combined = c.get("relevance", 0) + c.get("hype", 0)
        lines.append(
            f'- [ ] `{c["id"]}` **{combined}** — {c.get("title","(untitled)")} '
            f'({c.get("source","?")})'
        )
    lines += [
        "",
        "<details><summary>Search notes from this run</summary>",
        "",
        notes,
        "",
        "</details>",
        "",
        f"{EMBED_OPEN}",
        json.dumps({"report_type": report_type, "candidates": candidates}, indent=1),
        f"{EMBED_CLOSE}",
    ]
    return "\n".join(lines)


def parse_approved(issue_body: str) -> tuple[str, list]:
    """Pull the embedded candidate data back out and filter to ticked boxes."""
    start = issue_body.find(EMBED_OPEN)
    if start == -1:
        sys.exit("No embedded candidate data in that issue — is it a review issue?")
    end = issue_body.find(EMBED_CLOSE, start)
    payload = issue_body[start + len(EMBED_OPEN):end].strip()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        sys.exit(f"Embedded candidate data is corrupt: {exc}")

    ticked = set(re.findall(r"^\s*-\s*\[[xX]\]\s*`([^`]+)`", issue_body, re.MULTILINE))
    approved = [c for c in data["candidates"] if c.get("id") in ticked]
    return data["report_type"], approved


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
                "followup": key in existing,
            }
        )
        added += 1
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    return added


# ---------------------------------------------------------------- stages

def stage_collect(report_type: str, local: bool) -> None:
    config = REPORTS[report_type]
    today = date.today()
    prompt = COLLECT_PROMPT.format(
        today=today.isoformat(),
        start=(today - timedelta(days=config["window_days"])).isoformat(),
        spec=load_text(config["spec"]),
        ranking=load_text("specs/ranking.md"),
        dedup_section=build_dedup_section(report_type),
        marker=CANDIDATES_MARKER,
    )
    notes, candidates = split_marker(call_claude(prompt, [WEB_SEARCH]), CANDIDATES_MARKER)
    if not candidates:
        sys.exit("No candidates returned — nothing to review.")

    body = render_review_issue(report_type, candidates, notes)
    if local:
        print(body)
        print(f"\n--- {len(candidates)} candidate(s); no issue created (--local) ---")
        return

    issue = gh_request(
        "POST",
        "issues",
        json={
            "title": f"[REVIEW] {config['label']} candidates — {today.isoformat()}",
            "body": body,
        },
    )
    print(f"{len(candidates)} candidates posted for review: {issue['html_url']}")


def stage_draft(issue_number: int, local: bool) -> None:
    issue = gh_request("GET", f"issues/{issue_number}")
    report_type, approved = parse_approved(issue.get("body") or "")
    if not approved:
        sys.exit(
            f"No stories ticked in issue #{issue_number}. "
            "Tick at least one checkbox, then re-run."
        )
    print(f"Drafting from {len(approved)} approved story/stories...")

    config = REPORTS[report_type]
    approved_block = "\n".join(
        f'{i}. [{c["key"]}] {c.get("title","")}\n'
        f'   URL: {c.get("url","")}\n'
        f'   Brands: {", ".join(c.get("brands", []))}\n'
        f'   Source: {c.get("source","")}\n'
        f'   Article published: {c.get("published_at","unknown")}\n'
        f'   Drop releases: {c.get("released_at","unknown")}\n'
        f'   Editor note: {c.get("why","")}'
        for i, c in enumerate(approved, 1)
    )
    prompt = DRAFT_PROMPT.format(
        approved=approved_block,
        spec=load_text(config["spec"]),
        format=config["format"],
        marker=LEDGER_MARKER,
    )
    draft, ledger = split_marker(call_claude(prompt, [WEB_FETCH, WEB_SEARCH]), LEDGER_MARKER)

    if local:
        print(draft)
        print(f"\n--- {len(ledger)} ledger item(s); history NOT updated (--local) ---")
        return

    body = f"{draft}\n\n---\n*Drafted from approved candidates in #{issue_number}.*"
    new_issue = gh_request(
        "POST",
        "issues",
        json={
            "title": f"[{config['label']}] Draft for {date.today().isoformat()}",
            "body": body,
        },
    )
    print(f"Draft posted: {new_issue['html_url']}")
    print(f"Recorded {append_history(report_type, ledger)} item(s) in history.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["collect", "draft"], required=True)
    parser.add_argument("--type", choices=sorted(REPORTS), help="required for --stage collect")
    parser.add_argument("--issue", type=int, help="review issue number; required for --stage draft")
    parser.add_argument("--local", action="store_true", help="print instead of writing to GitHub")
    args = parser.parse_args()

    if args.stage == "collect":
        if not args.type:
            parser.error("--type is required with --stage collect")
        stage_collect(args.type, args.local)
    else:
        if not args.issue:
            parser.error("--issue is required with --stage draft")
        stage_draft(args.issue, args.local)


if __name__ == "__main__":
    main()
