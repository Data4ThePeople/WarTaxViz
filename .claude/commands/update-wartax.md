---
description: Weekly War Tax data refresh — fetch, verify, rebuild, commit, push, republish
---

Run the weekly War Tax data refresh. Follow these steps in order; stop and report
to the user if any check fails.

## 1. Save the previous snapshot, then run the pipeline

```bash
git show HEAD:site/data.json > /tmp/wartax-prev.json
source .venv/bin/activate && python pipeline/run.py
```

The pipeline fetches EIA (national gas, 16 regional series, diesel), FRED (S&P 500,
fallbacks), BLS (CPI + grocery basket), Fed DFA, and AAA, then rebuilds
`site/data.json`, `site/index.html`, `site/embed.html`, `site/schema.json` (the
JSON-LD graph for the Prismic post's schema field, with current dates and
figures) and `writeups/war-tax-faq.md` (the matching visible FAQ text).

## 2. Sanity checks (compare new site/data.json vs /tmp/wartax-prev.json)

- **Gas week advanced**: `gas.latest_date` must be newer than the previous run's.
  If unchanged, EIA likely hasn't published yet (holiday delay) — do NOT commit;
  tell the user to rerun tomorrow.
- **Market date advanced**: `market.latest_date` should be the last trading day.
- **No silent fallbacks**: `gas.source` should still say "EIA API v2"; if it fell
  back to FRED, mention it (fine, but worth knowing). `gas.aaa_latest` null means
  the AAA scrape broke — mention it (page degrades gracefully).
- **Nothing wild**: week-over-week change in `costs.total` should be modest
  (typically under ~$25). Gain % should be within a few points of last week. If a
  number jumps implausibly, show the user the old/new values and stop before
  committing.
- **CPI month**: note whether `food.latest_month` advanced (it only changes in the
  week BLS releases CPI, mid-month).

## 3. Report the week-over-week deltas to the user

A short table: total war tax, gas cost, gain %, breakeven, and each persona's net —
old vs new. Note the new as-of dates.

## 4. Commit and push

```bash
git add site/data.json site/index.html site/embed.html site/schema.json writeups/war-tax-faq.md
git commit -m "Weekly data refresh: gas through <gas.latest_date>, S&P through <market.latest_date>"
git push
```

(Include the standard Claude co-author trailer.)

## 5. Republish the artifact

Publish `site/index.html` with the Artifact tool, targeting the existing artifact:

- url: https://claude.ai/code/artifact/5a89c04f-93e8-4843-a843-39561fe7328c
- favicon: ⛽ (keep stable)
- label: `refresh-<gas.latest_date>`

## 6. Prismic schema (optional, monthly is plenty)

`site/schema.json` now carries this week's dateModified, temporalCoverage and
headline figures. The GitHub Pages copies pick it up automatically; the Prismic
post's `schema` field does not. Mention to the user that pasting the new
`site/schema.json` into the post's schema field refreshes the Dataset's
dateModified for Google Dataset Search. Not required weekly.

## 7. Confirm the live embed updated

The Prismic iframe points at GitHub Pages
(https://data4thepeople.github.io/WarTaxViz/site/embed.html), so the push in step 4
updates it automatically. Pages deploys take a minute or two; verify with a curl
that the live embed.html reflects the new data (e.g. grep for the new gas
latest_date), and tell the user it's live. No manual upload needed.
