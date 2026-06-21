"""POC scraper: fetch hot posts per subreddit via RSS, count keyword mentions,
write data/latest.json. Run via:  uv run scripts/scrape.py

Uses Reddit's public RSS feed because the JSON endpoint now blocks
unauthenticated requests. RSS is open but slower and exposes less metadata
(no score, no comment count)."""

import datetime
import html
import json
import pathlib
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

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

POSTS_PER_SUB = 50
USER_AGENT = "macos:reddit-trend-poc:v0.1 (by /u/anonymous)"
REQUEST_DELAY_SEC = 20
RETRY_AFTER_429_SEC = 45
ATOM = "{http://www.w3.org/2005/Atom}"
TAG_RE = re.compile(r"<[^>]+>")
ROOT = pathlib.Path(__file__).resolve().parent.parent


def fetch_sub(session: requests.Session, sub: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{sub}/hot.rss?limit={POSTS_PER_SUB}"
    resp = session.get(url, timeout=30)
    if resp.status_code == 429:
        wait = int(resp.headers.get("Retry-After", RETRY_AFTER_429_SEC))
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


def build_matchers(keywords: list[dict]) -> list[tuple[str, str, re.Pattern]]:
    out = []
    for k in keywords:
        pattern = r"(?:" + "|".join(k["aliases"]) + r")"
        out.append((k["name"], k.get("category", "misc"), re.compile(pattern, re.IGNORECASE)))
    return out


def main() -> int:
    keywords = json.loads((ROOT / "scripts" / "keywords.json").read_text())
    matchers = build_matchers(keywords)
    counts: dict[str, dict] = {
        name: {"name": name, "category": cat, "count": 0, "posts": []}
        for name, cat, _ in matchers
    }

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.headers["Accept"] = "application/atom+xml, application/xml"

    fetched_subs = []
    failed_subs = []
    for i, sub in enumerate(SUBS):
        if i > 0:
            time.sleep(REQUEST_DELAY_SEC)
        try:
            posts = fetch_sub(session, sub)
        except requests.HTTPError as e:
            print(f"[warn] r/{sub}: HTTP {e.response.status_code}", file=sys.stderr)
            failed_subs.append(sub)
            continue
        except Exception as e:
            print(f"[warn] r/{sub}: {e}", file=sys.stderr)
            failed_subs.append(sub)
            continue

        fetched_subs.append({"name": sub, "posts": len(posts)})
        print(f"  r/{sub}: {len(posts)} posts")

        for p in posts:
            text = (p["title"] + "\n" + p["content"])[:8000]
            for name, _, pat in matchers:
                if pat.search(text):
                    counts[name]["count"] += 1
                    counts[name]["posts"].append({
                        "title": p["title"],
                        "subreddit": sub,
                        "permalink": p["permalink"],
                    })

    techs = []
    for entry in counts.values():
        if entry["count"] == 0:
            continue
        seen = set()
        unique_posts = []
        for p in entry["posts"]:
            if p["permalink"] in seen:
                continue
            seen.add(p["permalink"])
            unique_posts.append(p)
        entry["posts"] = unique_posts[:5]
        techs.append(entry)
    techs.sort(key=lambda x: -x["count"])

    out = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "subreddits": fetched_subs,
        "failed_subreddits": failed_subs,
        "total_posts_scanned": sum(s["posts"] for s in fetched_subs),
        "technologies": techs,
    }

    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "latest.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote data/latest.json: {len(techs)} techs from {len(fetched_subs)} subs")
    if failed_subs:
        print(f"Failed subs: {', '.join(failed_subs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
