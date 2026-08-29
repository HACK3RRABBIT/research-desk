"""SOURCE MAPPER agent.

Maintains a living source graph. Tags accounts by tier (official gov/company,
primary journalist, subject expert, aggregator, unknown, low-trust) and
updates trust from feedback + confirmation signals. Discovers new accounts when
many independent users suddenly amplify the same fact (CORE PRINCIPLE: dynamic
discovery, not a fixed list).
"""
from __future__ import annotations

from collections import Counter

from ..config import Config
from ..schema import Post, SourceNode, SourceTier
from ..vault import Vault

# Handle-segment heuristics for initial tiering. Overridden by confirmation
# history once the source has enough signal.
_GOV_MARKERS = ("gov", "state", "department", "ministry", "treasury", "defense",
                "whitehouse", "kremlin", "fars", "irna", "reuters", "ap_", "afp")
_COMPANY_MARKERS = ("official", "_com", "corp", "inc", "news", "times", "post",
                    "journal", "bloomberg", "cnbc")


class SourceMapperAgent:
    def __init__(self, config: Config, vault: Vault):
        self.config = config
        self.vault = vault

    def _initial_tier(self, handle: str) -> SourceTier:
        h = handle.lower()
        if any(m in h for m in _GOV_MARKERS):
            return SourceTier.OFFICIAL_GOV
        if any(m in h for m in _COMPANY_MARKERS):
            return SourceTier.AGGREGATOR
        return SourceTier.UNKNOWN

    def run(self, posts: list[Post]) -> None:
        for p in posts:
            handle = p.author_handle or p.author
            if not handle:
                continue
            node = self.vault.get_source(handle)
            if node.tier == SourceTier.UNKNOWN:
                node.tier = self._initial_tier(handle)
            node.last_seen = p.timestamp
            self.vault.upsert_source(node)

        self._discover_amplifiers(posts)

    def _discover_amplifiers(self, posts: list[Post]) -> None:
        """When 3+ independent accounts state the same short fact within a
        cycle, any unknown account in that cluster gets a small trust bump
        (CORE PRINCIPLE: discover new sources dynamically)."""
        clusters: Counter[tuple] = Counter()
        by_key: dict[tuple, set] = {}
        for p in posts:
            handle = p.author_handle or p.author
            if not handle:
                continue
            key = tuple(p.text.lower().split()[:10])
            clusters[key] += 1
            by_key.setdefault(key, set()).add(handle)
        for key, count in clusters.items():
            if count >= 3:
                for handle in by_key[key]:
                    node = self.vault.get_source(handle)
                    if node.tier in (SourceTier.UNKNOWN, SourceTier.AGGREGATOR) \
                            and not node.confirmations:
                        node.trust = min(1.0, node.trust + 0.05)
                        self.vault.upsert_source(node)
