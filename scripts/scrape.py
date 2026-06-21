"""POC scraper: pulls trending signal from Reddit (RSS) and GitHub (Search API),
counts keyword mentions against the shared whitelist, merges into one ranking,
writes data/latest.json. Run:  uv run scripts/scrape.py

Reddit  signal = mentions in hot-post titles + body across N subs.
GitHub  signal = mentions in recently-pushed, well-starred repo name/description/topics
                  across N focused topic queries.
Both sources feed the same `technologies` list; each tech carries a total count
plus per-source subtotals (reddit_count / github_count)."""

import datetime
import html
import json
import pathlib
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

# --- Reddit ---
SUBS = [
    "Python",
    "MachineLearning",
    "LocalLLaMA",
    "LLMDevs",
    "ClaudeAI",
    "OpenAI",
    "learnmachinelearning",
    "ChatGPTCoding",
    "artificial",
]
REDDIT_POSTS_PER_SUB = 50
REDDIT_USER_AGENT = "macos:reddit-trend-poc:v0.1 (by /u/anonymous)"
REDDIT_REQUEST_DELAY_SEC = 20
REDDIT_RETRY_AFTER_429_SEC = 45

# --- GitHub ---
# `created:>{since}` returns repos that are NEW in the trend window — the right
# "what just launched and is getting starred" signal. `pushed:>` would return
# stale-but-active repos and let huge established projects dominate.
# `{since}` is set to GITHUB_TREND_WINDOW_DAYS ago at scrape time.
GITHUB_TREND_WINDOW_DAYS = 30
GITHUB_QUERIES = [
    "topic:llm created:>{since}",
    "topic:ai-agents created:>{since}",
    "topic:rag created:>{since} stars:>3",
    "topic:mcp created:>{since}",
    "topic:machine-learning language:python created:>{since} stars:>10",
]

# Separate query set for the "Most stars overall" sidebar. NOT used for trend counting —
# these return canonical, established projects in the same topic space.
GITHUB_STAR_QUERIES = [
    "topic:llm stars:>1000",
    "topic:ai-agents stars:>500",
    "topic:mcp stars:>100",
    "topic:rag stars:>500",
]
GITHUB_TOP_STARRED_KEEP = 15

GITHUB_PER_PAGE = 100
GITHUB_USER_AGENT = "reddit-trend-poc/0.1"
GITHUB_REQUEST_DELAY_SEC = 6  # search API: ~10 req/min unauth

ATOM = "{http://www.w3.org/2005/Atom}"
TAG_RE = re.compile(r"<[^>]+>")
ROOT = pathlib.Path(__file__).resolve().parent.parent


def build_matchers(keywords: list[dict]) -> list[tuple[str, str, re.Pattern]]:
    out = []
    for k in keywords:
        pattern = r"(?:" + "|".join(k["aliases"]) + r")"
        out.append((k["name"], k.get("category", "misc"), re.compile(pattern, re.IGNORECASE)))
    return out


# --- Reddit fetcher ---

def fetch_sub(session: requests.Session, sub: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{sub}/hot.rss?limit={REDDIT_POSTS_PER_SUB}"
    resp = session.get(url, timeout=30)
    if resp.status_code == 429:
        wait = int(resp.headers.get("Retry-After", REDDIT_RETRY_AFTER_429_SEC))
        print(f"  r/{sub}: 429, sleeping {wait}s and retrying once...", file=sys.stderr)
        time.sleep(wait)
        resp = session.get(url, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    posts = []
    for entry in root.findall(f"{ATOM}entry"):
        title_el = entry.find(f"{ATOM}title")
        content_el = entry.find(f"{ATOM}content")
        link_el = entry.find(f"{ATOM}link")
        title = (title_el.text or "") if title_el is not None else ""
        raw_content = (content_el.text or "") if content_el is not None else ""
        text_content = TAG_RE.sub(" ", html.unescape(raw_content))
        link = link_el.get("href") if link_el is not None else ""
        posts.append({"title": title, "content": text_content, "permalink": link})
    return posts


def scrape_reddit(matchers):
    print("Reddit:")
    counts: dict[str, dict] = {}
    fetched = []
    failed = []

    session = requests.Session()
    session.headers["User-Agent"] = REDDIT_USER_AGENT
    session.headers["Accept"] = "application/atom+xml, application/xml"

    for i, sub in enumerate(SUBS):
        if i > 0:
            time.sleep(REDDIT_REQUEST_DELAY_SEC)
        try:
            posts = fetch_sub(session, sub)
        except requests.HTTPError as e:
            print(f"[warn] r/{sub}: HTTP {e.response.status_code}", file=sys.stderr)
            failed.append(sub)
            continue
        except Exception as e:
            print(f"[warn] r/{sub}: {e}", file=sys.stderr)
            failed.append(sub)
            continue

        fetched.append({"name": sub, "posts": len(posts)})
        print(f"  r/{sub}: {len(posts)} posts")

        for p in posts:
            text = (p["title"] + "\n" + p["content"])[:8000]
            for name, _, pat in matchers:
                if pat.search(text):
                    counts.setdefault(name, {"count": 0, "posts": []})
                    counts[name]["count"] += 1
                    counts[name]["posts"].append({
                        "title": p["title"],
                        "subreddit": sub,
                        "permalink": p["permalink"],
                    })

    return counts, fetched, failed


# --- GitHub fetcher ---

def fetch_github_query(session: requests.Session, q: str) -> list[dict]:
    url = "https://api.github.com/search/repositories"
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": GITHUB_PER_PAGE}
    resp = session.get(url, params=params, timeout=30)
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        raise RuntimeError("GitHub rate-limit hit (unauthenticated). Wait and retry.")
    resp.raise_for_status()
    return resp.json().get("items", [])


def _repo_summary(repo: dict) -> dict:
    return {
        "name": repo["full_name"],
        "description": (repo.get("description") or "")[:200],
        "url": repo["html_url"],
        "stars": repo.get("stargazers_count", 0),
        "language": repo.get("language") or "",
    }


def scrape_github(matchers):
    print("\nGitHub:")
    counts: dict[str, dict] = {}
    queries_log = []
    failed_queries = []
    seen_ids: set[int] = set()

    since = (
        datetime.datetime.now(datetime.timezone.utc).date()
        - datetime.timedelta(days=GITHUB_TREND_WINDOW_DAYS)
    ).isoformat()

    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    session.headers["User-Agent"] = GITHUB_USER_AGENT
    session.headers["X-GitHub-Api-Version"] = "2022-11-28"

    call_idx = 0
    for q_template in GITHUB_QUERIES:
        q = q_template.format(since=since)
        if call_idx > 0:
            time.sleep(GITHUB_REQUEST_DELAY_SEC)
        call_idx += 1
        try:
            repos = fetch_github_query(session, q)
        except Exception as e:
            print(f"[warn] github query failed: {q} ({e})", file=sys.stderr)
            failed_queries.append({"q": q, "error": str(e)})
            continue

        new_repos = [r for r in repos if r["id"] not in seen_ids]
        for r in new_repos:
            seen_ids.add(r["id"])
        queries_log.append({"q": q, "returned": len(repos), "new": len(new_repos)})
        print(f"  trend: {q}  → {len(repos)} repos ({len(new_repos)} new)")

        for repo in new_repos:
            text = (
                repo.get("name", "") + " "
                + (repo.get("description") or "") + " "
                + " ".join(repo.get("topics") or [])
            )
            for name, _, pat in matchers:
                if pat.search(text):
                    counts.setdefault(name, {"count": 0, "repos": []})
                    counts[name]["count"] += 1
                    counts[name]["repos"].append(_repo_summary(repo))

    # Most-starred sidebar — separate from trend counting.
    starred: dict[int, dict] = {}
    for q in GITHUB_STAR_QUERIES:
        if call_idx > 0:
            time.sleep(GITHUB_REQUEST_DELAY_SEC)
        call_idx += 1
        try:
            repos = fetch_github_query(session, q)
        except Exception as e:
            print(f"[warn] github star query failed: {q} ({e})", file=sys.stderr)
            failed_queries.append({"q": q, "error": str(e)})
            continue
        print(f"  star : {q}  → {len(repos)} repos")
        for repo in repos[:30]:
            starred[repo["id"]] = _repo_summary(repo)

    top_starred = sorted(starred.values(), key=lambda r: -r["stars"])[:GITHUB_TOP_STARRED_KEEP]

    return counts, queries_log, failed_queries, len(seen_ids), top_starred


# --- Merge + output ---

def merge_and_rank(matchers, reddit_counts, github_counts):
    cat_by_name = {name: cat for name, cat, _ in matchers}
    techs = []
    all_names = set(reddit_counts) | set(github_counts)
    for name in all_names:
        r = reddit_counts.get(name, {"count": 0, "posts": []})
        g = github_counts.get(name, {"count": 0, "repos": []})
        total = r["count"] + g["count"]
        if total == 0:
            continue

        seen_posts = set()
        posts = []
        for p in r.get("posts", []):
            if p["permalink"] in seen_posts:
                continue
            seen_posts.add(p["permalink"])
            posts.append(p)

        repos = sorted(g.get("repos", []), key=lambda x: -x.get("stars", 0))

        techs.append({
            "name": name,
            "category": cat_by_name.get(name, "misc"),
            "count": total,
            "reddit_count": r["count"],
            "github_count": g["count"],
            "posts": posts[:5],
            "repos": repos[:5],
        })
    techs.sort(key=lambda x: (-x["count"], -x["reddit_count"], -x["github_count"]))
    return techs


def main() -> int:
    keywords = json.loads((ROOT / "scripts" / "keywords.json").read_text())
    matchers = build_matchers(keywords)

    reddit_counts, reddit_subs, reddit_failed = scrape_reddit(matchers)
    github_counts, github_queries, github_failed, github_total_repos, top_starred = scrape_github(matchers)
    techs = merge_and_rank(matchers, reddit_counts, github_counts)

    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reddit": {
            "subreddits": reddit_subs,
            "failed_subreddits": reddit_failed,
            "total_posts_scanned": sum(s["posts"] for s in reddit_subs),
        },
        "github": {
            "queries": github_queries,
            "failed_queries": github_failed,
            "total_repos_scanned": github_total_repos,
            "trend_window_days": GITHUB_TREND_WINDOW_DAYS,
            "top_starred": top_starred,
        },
        "technologies": techs,
    }

    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "latest.json").write_text(json.dumps(out, indent=2))

    sitemap = ROOT / "sitemap.xml"
    if sitemap.exists():
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        text = sitemap.read_text()
        text = re.sub(r"<lastmod>[^<]+</lastmod>", f"<lastmod>{today}</lastmod>", text)
        sitemap.write_text(text)

    print(f"\nWrote data/latest.json")
    print(f"  reddit: {len(reddit_subs)}/{len(SUBS)} subs ok, {out['reddit']['total_posts_scanned']} posts")
    print(f"  github: {len(github_queries)}/{len(GITHUB_QUERIES)} queries ok, {github_total_repos} unique repos")
    print(f"  merged: {len(techs)} technologies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
