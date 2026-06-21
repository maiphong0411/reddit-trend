# Reddit Tech Trends — POC

What Python, AI-agent, Claude, and ML communities are talking about right now,
aggregated from Reddit "hot" posts and rendered as a static leaderboard.

POC. Manually refreshed. Deployed via GitHub Pages.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync
```

## Refresh the snapshot

```bash
uv run scripts/scrape.py
```

Writes `data/latest.json`. Commit and push to update the live page:

```bash
git add data/latest.json
git commit -m "snapshot $(date +%Y-%m-%d)"
git push
```

## Deploy on GitHub Pages

1. Push this repo to GitHub (public).
2. Settings → Pages → Source: **Deploy from a branch**, Branch: `main` / root.
3. Open `https://<user>.github.io/<repo>/`.

## Configure

- **Keywords:** `scripts/keywords.json` (name, category, regex aliases)
- **Subreddits:** `SUBS` list in `scripts/scrape.py`

## Collect feedback from coworkers

The page has a 👍/😐/👎 + comment widget at the bottom. It posts to
[Formspree](https://formspree.io) — free, no backend required.

1. Sign up at formspree.io (free), click **New Form**, copy the endpoint URL
   (looks like `https://formspree.io/f/abcdwxyz`).
2. Open `app.js`, set `FEEDBACK_ENDPOINT` (top of file) to that URL.
3. Commit, push.

Until the endpoint is set, submissions log to the browser console (demo mode).

## Scope and decisions

See `CLAUDE.md`.
