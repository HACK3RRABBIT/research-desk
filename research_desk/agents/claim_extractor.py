"""CLAIM EXTRACTOR agent.

For each post, hands the text (+ source context) to the reasoning engine to
extract atomic claims. Records, per claim: who said it, whether they are a
primary source, whether primary evidence is attached, and whether it is
forward-looking speculation.
"""
from __future__ import annotations

from ..config import Config
from ..schema import Post
from ..vault import Vault
from ..reasoning import Reasoning


class ClaimExtractorAgent:
    def __init__(self, config: Config, vault: Vault, reasoning: Reasoning):
        self.config = config
        self.vault = vault
        self.reasoning = reasoning

    def run(self, posts: list[Post]) -> None:
        for p in posts:
            handle = p.author_handle or p.author
            source = self.vault.get_source(handle) if handle else None
            if source is None:
                continue
            claims = self.reasoning.extract_claims(p, source)
            for c in claims:
                self.vault.upsert_claim(c)
            if claims:
                print(f"[claim-extractor] {handle}: {len(claims)} claim(s)")
