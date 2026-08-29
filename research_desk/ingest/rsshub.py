"""RSSHub ingestion.

Wraps RSSHub /twitter routes and normalizes items into Post records. Any route
failure is retried with backoff and logged; a single bad feed never crashes a
cycle (CORE PRINCIPLE: resilience). The base URL is fully configurable.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import quote

import requests

from ..schema import Post, utcnow
from ..config import Config


def _route(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def user_feed_url(base: str, handle: str) -> str:
    return _route(base, f"twitter/user/{quote(handle.strip().lstrip('@'))}")


def list_feed_url(base: str, list_id: str) -> str:
    return _route(base, f"twitter/list/{quote(str(list_id))}")


def keyword_feed_url(base: str, keyword: str) -> str:
    return _route(base, f"twitter/keyword/{quote(keyword)}")


def _parse_atom(xml_text: str) -> list[dict]:
    items = []
    root = ET.fromstring(xml_text)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("a:entry", ns):
        title = (entry.findtext("a:title", "", ns) or "").strip()
        content = (entry.findtext("a:content", "", ns) or "").strip()
        link = ""
        for l in entry.findall("a:link", ns):
            link = l.get("href", "")
            break
        author = ""
        ae = entry.find("a:author", ns)
        if ae is not None:
            author = (ae.findtext("a:name", "", ns) or "").strip()
        published = entry.findtext("a:published", "", ns) or \
            entry.findtext("a:updated", "", ns) or ""
        items.append({
            "title": title, "content": content, "link": link,
            "author": author, "published": published,
        })
    return items


def _parse_rss(xml_text: str) -> list[dict]:
    items = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "content": (item.findtext("description") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "author": (item.findtext("dc:creator", namespaces={
                "dc": "http://purl.org/dc/elements/1.1/"}) or "").strip(),
            "published": (item.findtext("pubDate") or "").strip(),
        })
    return items


# De-dupe the failure log: a permanently-dead route (e.g. a demo feed that 404s
# offline) would otherwise spam one line per per cycle. We log it once.
_logged_failed: set[str] = set()


def _fetch(url: str, timeout: int = 10, retries: int = 1) -> Optional[str]:
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, timeout=timeout,
                                headers={"User-Agent": "research-desk/0.1"})
            if resp.status_code == 200:
                return resp.text
            last_err = RuntimeError(f"HTTP {resp.status_code}")
        except Exception as exc:  # network / parse
            last_err = exc
        if attempt < retries:
            time.sleep(2 * (attempt + 1))
    if url not in _logged_failed:
        _logged_failed.add(url)
        print(f"[rsshub] FAILED after retries: {url} ({last_err})")
    return None


def _to_post(item: dict, source_feed: str) -> Post:
    text = item["content"] or item["title"]
    return Post(
        post_id=item["link"] or item["title"],
        author=item["author"],
        author_handle=item["author"].lstrip("@"),
        timestamp=_parse_date(item["published"]),
        text=text,
        raw_url=item["link"],
        source_feed=source_feed,
    )


def _parse_date(s: str) -> Optional[object]:
    if not s:
        return None
    from datetime import datetime, timezone
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%a, %d %b %Y %H:%M:%S %z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            dt = datetime.strptime(s, fmt)
            # Normalize to UTC so rendering can trust the "UTC" label (the
            # brief prints times as UTC; never label a local offset as UTC).
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def pull_user(base: str, handle: str) -> list[Post]:
    url = user_feed_url(base, handle)
    xml = _fetch(url)
    if not xml:
        return []
    return [_to_post(i, f"user:{handle}") for i in _parse(xml)]


def pull_list(base: str, list_id: str) -> list[Post]:
    url = list_feed_url(base, list_id)
    xml = _fetch(url)
    if not xml:
        return []
    return [_to_post(i, f"list:{list_id}") for i in _parse(xml)]


def pull_keyword(base: str, keyword: str) -> list[Post]:
    url = keyword_feed_url(base, keyword)
    xml = _fetch(url)
    if not xml:
        return []
    return [_to_post(i, f"keyword:{keyword}") for i in _parse(xml)]


def _parse(xml: str) -> list[dict]:
    try:
        if "<feed" in xml[:200]:
            return _parse_atom(xml)
        return _parse_rss(xml)
    except ET.ParseError as exc:
        print(f"[rsshub] parse error: {exc}")
        return []


def pull_all(config: Config) -> list[Post]:
    """Pull every configured feed. Failures are swallowed per-feed."""
    base = config.rsshub_base_url
    out: list[Post] = []
    for handle in config.watched_users:
        out.extend(pull_user(base, handle))
    for lid in config.watched_lists:
        out.extend(pull_list(base, lid))
    for kw in config.watched_keywords:
        out.extend(pull_keyword(base, kw))
    return out
