# Spec: Candidate ranking

Used in the **collect** stage, when building the reviewable shortlist. Every
candidate gets two independent 1–10 scores. Edit this file to change how
things get ranked — no code changes needed.

## RELEVANCE (1–10) — does this belong in the newsletter at all?

Judge fit to the beat, not excitement.

- **9–10** — Squarely on-beat: a fashion/footwear/apparel collaboration or
  limited release from brands the audience knows and tracks.
- **7–8** — On-beat but narrower: a strong drop from a smaller label, or a
  category-adjacent release (eyewear, luggage, fragrance) from a fashion house.
- **5–6** — Tangential: lifestyle or homeware collabs with a fashion brand
  attached; sports-team merchandise with no design story.
- **3–4** — Weak fit: beauty-only, food/beverage crossovers, pure licensing
  plays with no design point of view.
- **1–2** — Off-beat. Should not have been surfaced; flag rather than include.

## HYPE (1–10) — how much attention is this drop actually getting?

Judge momentum and cultural heat, not your own taste. Evidence beats vibes:
weigh how many outlets covered it, whether it was picked up beyond trade press,
whether it sold out, and whether the pairing itself is a talking point.

- **9–10** — Major cultural moment. Multiple mainstream outlets, immediate
  sellout, or a pairing people are actively discussing.
- **7–8** — Strong trade and enthusiast coverage; a genuinely unexpected pairing
  or a marquee name involved.
- **5–6** — Solid trade coverage, no wider pickup. A competent collab that
  isn't generating conversation.
- **3–4** — Announced and reported once, little traction.
- **1–2** — Barely covered; a press release with no pickup.

**Do not inflate hype for large brands.** A predictable capsule from a huge
brand can be a 4. An unexpected pairing between two mid-size labels can be a 9.
Novelty of the pairing matters more than the size of the names.

## How many candidates to surface

Aim for **15–25**. Over-collect deliberately — the point of the review step is
that a human picks, so err toward including a borderline item at a low score
rather than silently dropping it. Never omit something purely because it scored
low; that is the reviewer's call, not yours.

## Sort order

Rank by combined score (relevance + hype), highest first. Where two items tie,
put the higher **relevance** first — fit to the beat breaks ties, not heat.

## Per-candidate output

Every candidate needs: exact article title, direct URL, publishing outlet,
brands involved, **both dates** (see below), both scores, and a single-sentence
justification saying what the drop is and why it scored the way it did. The
justification is what the reviewer reads to decide — make it concrete and
specific, never generic praise.

## The two dates — keep them separate

These are different facts and must never be conflated:

- **`published_at`** — when the *article* ran. Tells the reviewer how fresh the
  coverage is and whether a story has already been widely reported.
- **`released_at`** — when the *product* becomes available. Tells the reviewer
  whether they are writing a preview or a retrospective.

Include a time of day whenever one is reported — sneaker and streetwear drops
routinely launch at a stated hour (e.g. `2026-08-15 10:00 ET`), and that detail
is useful to the reader. Use `unknown` when a date genuinely isn't stated, and
`TBC` when a release is explicitly announced-but-undated. **Never infer one date
from the other**; a preview published three weeks ahead of launch is normal, and
guessing collapses exactly the distinction this field exists to preserve.
