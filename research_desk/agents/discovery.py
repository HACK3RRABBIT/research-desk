"""AUTO-DISCOVERY agent.

The desk's coverage must grow, not stay pinned to a fixed watchlist. Every cycle
this agent reads the posts it ingested and proposes new accounts worth covering:
authors, quoted authors, and @mentions. An account earns a higher discovery
score the more it shows up and the more important the claims it produced are.
Worthwhile candidates are added to the watchlist (and persisted to
config.local.toml) so the next cycle pulls their feed. Discovery is bounded by
``max_per_cycle`` and ``max_total`` so it never runs away.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from ..config import Config
from ..schema import Claim, Post
from ..vault import Vault

_MENTION = re.compile(r"@\w+")


class DiscoveryAgent:
    def __init__(self, config: Config, vault: Vault):
        self.config = config
        self.vault = vault

    def run(self, posts: list[Post], claims: list[Claim]) -> list[str]:
        if not self.config.discovery.get("enabled", True):
            return []

        watched = {w.lower() for w in self.config.watched_users}
        already = {d.lower() for d in self.config.discovered_users()}

        appearances: Counter = Counter()
        mentions: Counter = Counter()
        for p in posts:
            h = (p.author_handle or p.author or "").lower()
            if h:
                appearances[h] += 1
            q = p.quoted_post
            if q is not None:
                qh = (q.author_handle or q.author or "").lower()
                if qh:
                    appearances[qh] += 1
            for m in _MENTION.findall(p.text or ""):
                mentions[m[1:].lower()] += 1

        # Weight by how important the claims an account produced actually were.
        claim_weight: defaultdict = defaultdict(float)
        for c in claims:
            h = (c.said_by or "").lower()
            if h:
                claim_weight[h] = max(claim_weight[h], c.importance)

        candidates = []
        for h in set(appearances) | set(mentions):
            if h in watched or h in already:
                continue
            # An account mentioned/seen counts; one whose claims we kept and
            # rated important counts much more.
            score = appearances[h] + mentions[h] + 2.0 * claim_weight[h]
            if score > 0:
                candidates.append((h, score))

        candidates.sort(key=lambda t: (t[1], t[0]), reverse=True)
        cap = int(self.config.discovery.get("max_per_cycle", 5))
        added: list[str] = []
        for h, _ in candidates[:cap]:
            if h.isalnum() and self.config.add_discovered_user(h):
                added.append(h)

        if added:
            self.config.save()
        print(f"[discovery] added {len(added)} accounts: {added}")
        return added
