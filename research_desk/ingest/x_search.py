"""X web-search fallback ingest.

Uses the X (Twitter) API v2 recent-search endpoint when a bearer token is
available via X_API_BEARER. This is optional: if no token is set we silently
skip so the desk still runs on RSSHub alone. Results are normalized to Post.
"""
from __future__ import annotations

import os
from typing import Optional

import requests

from ..schema import Post, utcnow
from ..config import Config


def pull_queries(config: Config) -> list[Post]:
    token = os.environ.get("X_API_BEARER")
    if not token:
        return []
    queries = config.x_search_queries
    if not queries or all("???" in q for q in queries):
        return []
    out: list[Post] = []
    for q in queries:
        out.extend(_search(q, token))
    return out


def _search(query: str, token: str, max_results: int = 25) -> list[Post]:
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": f"{query} -is:retweet lang:en",
        "max_results": max_results,
        "tweet.fields": "created_at,public_metrics,attachments,lang",
        "expansions": "author_id",
        "user.fields": "username,name,verified",
    }
    try:
        resp = requests.get(url, params=params, timeout=20,
                            headers={"Authorization": f"Bearer {token}"})
        if resp.status_code != 200:
            print(f"[x_search] HTTP {resp.status_code} for {query!r}")
            return []
        data = resp.json()
    except Exception as exc:
        print(f"[x_search] error: {exc}")
        return []

    users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
    posts = []
    for tw in data.get("data", []):
        author = users.get(tw.get("author_id", ""), {})
        posts.append(Post(
            post_id=tw["id"],
            author=author.get("name", ""),
            author_handle=author.get("username", ""),
            timestamp=_parse_dt(tw.get("created_at")),
            text=tw.get("text", ""),
            engagement=int((tw.get("public_metrics", {}) or {})
                           .get("retweet_count", 0)),
            language=tw.get("lang", "en"),
            raw_url=f"https://x.com/{author.get('username','')}/status/{tw['id']}",
            source_feed="x_search",
        ))
    return posts


def _parse_dt(s: Optional[str]):
    if not s:
        return None
    from datetime import datetime
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=__import__("datetime").timezone.utc)
    except ValueError:
        return None
