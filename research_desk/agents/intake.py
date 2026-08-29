"""INTAKE agent.

Continuously pulls posts from RSSHub routes (users, lists, keywords) and the
optional X search fallback, then normalizes every item into a standard Post
record. Handles reposts/quotes as first-class (CORE PRINCIPLE: important news
often surfaces first as a quote/repost from a mid-tier account).
"""
from __future__ import annotations

from ..config import Config
from ..schema import Post, utcnow
from ..vault import Vault
from ..ingest import rsshub
from ..ingest.x_search import pull_queries


class IntakeAgent:
    def __init__(self, config: Config, vault: Vault):
        self.config = config
        self.vault = vault

    def run(self) -> list[Post]:
        posts: list[Post] = []
        try:
            posts.extend(rsshub.pull_all(self.config))
        except Exception as exc:  # defensive: never let intake kill a cycle
            print(f"[intake] rsshub error: {exc}")
        try:
            posts.extend(pull_queries(self.config))
        except Exception as exc:
            print(f"[intake] x_search error: {exc}")

        # Normalize: filter by language, drop seen posts, tag reposts/quotes.
        kept: list[Post] = []
        for p in posts:
            if p.language and p.language not in self.config.languages \
                    and p.language != "und":
                continue
            if self.vault.post_exists(p.post_id):
                continue
            p.is_quote = "rt @" in p.text.lower()[:4] or "qt @" in p.text.lower()[:4]
            p.is_repost = p.text.lower().startswith("rt @")
            self.vault.upsert_post(p)
            kept.append(p)
        print(f"[intake] ingested {len(kept)} new posts "
              f"({len(posts)} total fetched)")
        return kept
