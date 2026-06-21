# reddit-trend

A POC that shows which Python / AI-agent / Claude / ML topics are currently being
talked about on Reddit, so coworkers can skim a single page and decide what to read
or learn next.

This is a **proof of concept**, not a product. Scope is intentionally narrow.
Get feedback, then decide what to expand.

## Status

POC, single snapshot, manually refreshed. No automation yet.

## Architecture

```
                                  ┌─ reddit.com/r/<sub>/hot.rss (public, no auth)
   ┌──────────────────────┐       │
   │  scripts/scrape.py   │───────┤
   │  (Python + requests) │       │
   └──────────┬───────────┘       └─ api.github.com/search/repositories (unauth, 10/min)
              │ reads
              ▼
   ┌──────────────────────┐
   │ scripts/keywords.json│   shared whitelist used against both sources
   │ (whitelist + regexes)│
   └──────────────────────┘

              ↓ counts keyword hits per source, merges into one ranked list
              ↓ each technology carries: count (total), reddit_count, github_count,
              ↓ top posts (Reddit), top repos (GitHub)

   ┌──────────────────────┐
   │  data/latest.json    │  ← committed to git
   └────────────┬─────────┘
                │ fetched by browser
                ▼
   ┌────────────────────────┐
   │ index.html + app.js +  │  ← served by GitHub Pages, no build step
   │ style.css              │     renders summary, leaderboard, drilldown, feedback
   └────────────────────────┘
```

Refresh loop is manual:

1. `uv run scripts/scrape.py` → updates `data/latest.json`
2. `git commit && git push` → GitHub Pages rebuilds within ~1 minute
3. Coworkers reload the URL

## Scope (POC)

In scope:
- One topic scope: **Python, AI agents, Claude, machine learning**. Keywords and source list reflect that.
- One signal: **most-mentioned right now**. Reddit = hot-post mentions. GitHub = mentions across recently-pushed, well-starred repo metadata. No history, no week-over-week deltas.
- Detection: **curated whitelist + regex match**. No LLM extraction.
- Two sources, unified ranking: **Reddit RSS (no auth)** + **GitHub Search API (unauth, 10 req/min for search)**. Each tech shows total + per-source subtotals.
- Deployment: **GitHub Pages, served from `main` branch root**. Static files only. No build step.
- Dependency management: **uv**. Python 3.11+. Only runtime dep is `requests`.
- Feedback: **Formspree endpoint set in `app.js`** (or demo mode if unset).

Out of scope (intentionally — do not add until POC feedback says so):
- GitHub Actions / cron / automated refresh
- Authenticated GitHub access (raises rate limit but adds secret management)
- Week-over-week deltas, time-series charts
- LLM-based extraction of new tech terms
- Other sources (HN, X/Twitter, Stack Overflow). Reddit + GitHub are the two we keep for now.
- Slack digests, email push
- Auth / private hosting
- Database, backend, or any non-static infra
- Coverage of non-Python / non-AI tech (web frameworks, mobile, etc.)

## Layout

```
.
├── CLAUDE.md                  This file. Read first.
├── README.md                  Human-facing setup notes.
├── pyproject.toml             uv-managed Python project. Pinned to 3.11+. Only dep: requests.
├── .nojekyll                  Prevents GitHub Pages from running Jekyll.
├── index.html                 Static page shell: summary card, leaderboard, feedback widget.
├── style.css                  Styling for the page.
├── app.js                     Fetches data/latest.json, renders summary + leaderboard + feedback.
│                              Top of file: FEEDBACK_ENDPOINT — paste Formspree URL to collect feedback.
├── scripts/
│   ├── scrape.py              The scraper. Fetches RSS per sub, counts keywords.
│   └── keywords.json          Whitelist of tech terms with regex aliases + category.
└── data/
    └── latest.json            Generated snapshot. Committed.
```

## Page sections

1. **Header** — title, subhead, snapshot timestamp + per-source counts.
2. **Summary card** — computed client-side in `renderSummary()`:
   - Lede: "Across N Reddit communities and M GitHub queries we found X techs."
   - Top 5 mentions
   - Leader per category
   - Cross-signal panel: techs appearing on BOTH Reddit and GitHub (strongest signal)
3. **Two-column content** — main on left, sidebar on right (collapses below 880px wide):
   - **Left:** category filter pills → paginated leaderboard (10 per page, prev/next).
     Each row shows total count + per-source breakdown (`Nr · Ng`). Expand → "From Reddit"
     (top posts) and "From GitHub" (top repos by stars, with description).
   - **Right:** sticky "Most-starred overall" sidebar — top 15 canonical repos in this
     topic space, regardless of trend window. Different query set from the trend leaderboard.
4. **Feedback widget** — 👍/😐/👎 + optional comment. Posts to `FEEDBACK_ENDPOINT` (Formspree).
   With endpoint empty, runs in "demo mode" — logs payload to browser console.
5. **Footer** — sources, "Made by Peter", mailto link for questions.

## SEO

- Real `<title>` and `<meta description>` targeting "trending Python AI Claude MCP ML" queries.
- Open Graph + Twitter Card tags pointing to absolute `https://maiphong0411.github.io/reddit-trend/` URLs.
- `og-image.png` (1200×630) — generated by `scripts/make_og_image.py` using Pillow. Regenerate
  after design changes; commit the PNG.
- JSON-LD structured data: WebSite + Dataset + Person publisher.
- `robots.txt` allows everything, points to `sitemap.xml`.
- `sitemap.xml` — `lastmod` is auto-updated by `scripts/scrape.py` on each run.
- Honest caveat: github.io subdomain ranks slowly. Biggest immediate win is the social-share
  preview card, not Google traffic.

## Key decisions and why

- **Reddit's unauthenticated `hot.json` endpoint, not PRAW/OAuth.** No secrets to manage,
  no API keys in CI. Trade-off: rate limit ~60 req/min per IP. Fine for ~10 subs.
  If we hit limits later, switch to PRAW + GH Action secrets.

- **Curated whitelist over LLM extraction.** Predictable, free, debuggable. Misses
  brand-new tech until it's added to `scripts/keywords.json`. Acceptable for POC.

- **Regex aliases with explicit word boundaries / negative lookaheads** to avoid
  obvious false positives ("java" matching "javascript", "claude" matching artist names,
  "cursor" matching DB cursors). See `keywords.json` patterns — they have nuances.

- **Static page on GitHub Pages from `main`.** No build pipeline. Zero deploy infra.
  Pages refreshes whenever data/ is pushed.

- **No Jekyll** (`.nojekyll`). Default Pages behavior would try to render this as a Jekyll site.

- **No history yet.** Adding day-over-day or week-over-week deltas needs ≥7 days of
  prior snapshots, plus more storage thought. POC asks "is the signal interesting at all?"
  first.

- **Summary computed client-side, not in scrape.py.** Aggregations (top 5, leader per
  category, broadest reach) are pure functions of `data/latest.json`. Keeps the JSON
  schema minimal and lets us iterate the summary view without re-scraping. If summary
  computation grows expensive, move it server-side then.

- **Feedback widget posts to Formspree, not a custom backend.** Static-site-friendly,
  free for 50/month, no auth wiring. If we outgrow it: Cloudflare Worker + KV would be
  the next stop. Do NOT add a server just for feedback.

## How to refresh

```bash
uv sync                          # one-time: install requests in .venv
uv run scripts/scrape.py         # ~25 seconds, hits 9 subs with 2s delay between
git add data/latest.json
git commit -m "snapshot $(date +%Y-%m-%d)"
git push
```

## Deploying to GitHub Pages

1. Create a public repo, push this directory to `main`.
2. Repo Settings → Pages → Source: **Deploy from a branch**, Branch: `main` / `/ (root)`.
3. URL appears at `https://<user>.github.io/<repo>/`.

## When changing things

- **Adding/removing keywords:** edit `scripts/keywords.json`. Each entry needs `name`,
  `category`, and `aliases` (list of regex strings). Patterns are joined with `|` and
  compiled case-insensitive, so use `\b` and lookaheads as needed.

- **Adding/removing subreddits:** edit the `SUBS` list in `scripts/scrape.py`.
  Keep delay between requests ≥ 2 seconds.

- **Changing the UI:** edit `index.html`, `style.css`, `app.js`. No framework, no build,
  no transpile. Drop-in vanilla JS. Don't introduce a build step without checking
  CLAUDE.md scope first.

## Things to NOT do without asking the user

- Add GitHub Actions or any cron. POC is manually refreshed by design.
- Add a JS framework, bundler, or build step. Page is intentionally buildless.
- Add an LLM call to scrape.py or anywhere else. Adds keys, cost, and non-determinism.
- Expand keyword coverage outside Python / AI / agents / ML scope.
- Add history files, deltas, charts, or any "trend over time" feature before the user
  asks for it. POC = snapshot only.
- Switch to PRAW unless rate-limit failures actually happen in practice.
