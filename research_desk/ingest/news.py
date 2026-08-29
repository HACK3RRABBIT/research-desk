"""Free, no-auth news ingestion.

The desk's intelligence layer (rumor filter, ranker, brief) runs on *any* Post
stream — X was only ever the default source. X/Twitter's API is paid and the
public RSSHub instance blocks Twitter routes, so out of the box there is nothing
to ingest. This adapter pulls **standard RSS/Atom news feeds** (BBC, Reuters-
via-syndication, Hacker News, Verge, WSJ, etc.) which are free, need no API key,
and carry real, time-stamped, link-backed posts. The same parser the RSSHub
adapter uses handles them, so the rest of the pipeline is unchanged.

Configure via ``config.news_feeds`` (a list of feed URLs). The desk ships with a
few working defaults so it has real input on first run; override them in
config.toml or the web UI.
"""
from __future__ import annotations

import re
from typing import Optional

import requests

from ..schema import Post, utcnow
from .rsshub import _fetch, _parse, _parse_date, _to_post

_TAG = re.compile(r"<[^>]+>")
_ENT = re.compile(r"&(?:[a-zA-Z]+|#\d+);")
_WS = re.compile(r"\s+")

# Feeds that wrap the real link/text in HTML markup (e.g. "... <a href=...>")
# — strip tags so the agents judge content, not markup.
def _strip_html(s: str) -> str:
    if not s:
        return ""
    s = _TAG.sub(" ", s)
    s = _ENT.sub(" ", s)
    return _WS.sub(" ", s).strip()

# Working defaults: free, no-auth, real-time news RSS/Atom. These are a starting
# point — edit config.news_feeds to match the outlets you care about. (RSSHub
# Twitter routes are intentionally NOT here because the public instance blocks
# them; self-host RSSHub or an X bearer token is the only way to add X.)
DEFAULT_NEWS_FEEDS: list[str] = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/world/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://www.theverge.com/rss/index.xml",
]


def pull_feeds(config) -> list[Post]:
    """Pull every configured news RSS/Atom feed. Failures are swallowed per feed."""
    urls = list(getattr(config, "news_feeds", None) or DEFAULT_NEWS_FEEDS)
    out: list[Post] = []
    for url in urls:
        try:
            xml = _fetch(url)
            if not xml:
                continue
            for item in _parse(xml):
                post = _to_post(item, f"news:{url}")
                # Feeds often embed HTML (links, paragraphs) in title/content;
                # strip it so the judgement agents see clean prose, not markup.
                clean = _strip_html(post.text)
                if clean:
                    post.text = clean
                post.raw_url = _strip_html(post.raw_url)
                out.append(post)
        except Exception as exc:  # never let one bad feed kill intake
            print(f"[news] feed error {url}: {exc}")
    return out
