# Fashion/Apparel LinkedIn Weekly Report

Automates the *research + drafting* half of your two weekly LinkedIn posts:

- **Monday** — Brand Growth / Investment & M&A / Industry Moves roundup
- **Wednesday** — Collections & Collaborations (weekly drops)

Each run searches the web for real news from the past week, drafts the post
in your historic format, and opens it as a **GitHub Issue** for you to review.
**Posting to LinkedIn is still manual** — this deliberately does not touch
LinkedIn. See "Future: automated posting" below for the next step when you're
ready.

## How it works

1. A GitHub Actions workflow fires twice a week (Monday & Wednesday mornings).
2. It reads the editorial brief from `specs/`, then calls Claude with the web
   search tool to gather this week's fashion/apparel news and draft the post in
   your exact format.
3. For every person/brand mentioned, it generates a LinkedIn *people-search*
   link (not a guessed profile URL) — click it while composing your post to
   pick the correct match before typing `@Name`.
4. The draft + sources + tag-search links are posted as a new GitHub Issue.
   You review/edit, then copy the text into LinkedIn and post it yourself.

## Tuning what it pulls — `specs/`

The editorial criteria live in plain markdown, not in the code:

- `specs/industry-news.md` — the Monday roundup
- `specs/collaborations.md` — the Wednesday drops post

Each spec covers what counts as an item, what to exclude, how many to pull, how
to prioritize when there are more candidates than slots, which details each item
must carry, tone, and preferred sources. The script loads the file at runtime and
passes it to Claude as the brief, so **editing the markdown is the whole workflow**
— no Python changes, no redeploy. Commit the edit and the next run uses it.

I pre-filled both specs by reverse-engineering the criteria from your example
posts, so they should already be close. Treat them as a starting point and tighten
them as you see what the drafts get wrong: if a week comes back with five sneaker
collabs and nothing else, that's a line to add to the prioritization section; if
it keeps surfacing brands too small for your audience, add a size floor.

## Running it by hand

To test a spec change without waiting for the schedule or opening an Issue:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install -r requirements.txt
python scripts/generate_report.py --type drops --local
```

`--local` prints the draft to your terminal instead of creating a GitHub Issue.
This is the fast loop for iterating on a spec.

## Setup

1. **Create a GitHub repo** (private recommended) and push this folder to it:
   ```bash
   cd /Users/beckettlong/fashion-linkedin-reports
   git init
   git add .
   git commit -m "Initial weekly report automation"
   git branch -M main
   git remote add origin <your-new-repo-url>
   git push -u origin main
   ```
2. **Add your Anthropic API key as a repo secret**: on GitHub, go to
   Settings → Secrets and variables → Actions → New repository secret.
   - Name: `ANTHROPIC_API_KEY`
   - Value: an API key from https://console.anthropic.com (create one under
     Settings → API Keys). You create and paste this yourself — nothing here
     needs your key to set up the code.
3. No other secret is needed — `GITHUB_TOKEN` is provided automatically by
   Actions and is scoped to this repo only.
4. **Adjust the schedule** in `.github/workflows/weekly-report.yml` if
   8am ET on Mon/Wed doesn't work for you — GitHub Actions cron is always UTC
   and doesn't shift for daylight saving, so the actual local time will drift
   by an hour twice a year unless you update it.
5. **Test it manually** before waiting for the schedule: on GitHub, go to
   Actions → "Weekly Fashion LinkedIn Report" → "Run workflow", pick
   `industry` or `drops`, and run it. Check the new Issue it creates.

## Getting notified

Since this skips email for now, the practical way to "get the report each
morning" is GitHub's own notifications: if you **watch** the repo (top-right
"Watch" button), GitHub emails you whenever a new Issue is opened — which is
exactly when a draft is ready. You can also just check the Issues tab, or use
the GitHub mobile app.

## Future: automated posting

When you're ready to stop copy-pasting into LinkedIn:

- **Fastest path**: connect a scheduler that already has LinkedIn API access
  approved (Buffer, Hootsuite, or an n8n LinkedIn node) via OAuth, and have
  this script push the draft there via that tool's API instead of a GitHub
  Issue.
- **More control, more setup**: register your own LinkedIn Developer app and
  go through LinkedIn's approval for posting scope (`w_member_social` for a
  personal profile, or the Community Management API for a Company Page).
  Approval isn't guaranteed and can take days to weeks.

Either way, keep a human-review step for at least the first several weeks —
the draft can misattribute a name, figure, or quote, and that's much cheaper
to catch here than after it's live on LinkedIn.
