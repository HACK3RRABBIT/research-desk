"""RUMOR FILTER agent.

Scores each claim (primary source? independently corroborated by 2+ unrelated
high-trust accounts? original post exists, not just screenshots? specific vs
vague?) and drops/quarantines low-value noise. Unconfirmed-but-important claims
go to a watchlist, never the main brief. Also upgrades/downgrades source trust
based on whether their past claims later got confirmed.

CORE PRINCIPLE: separate "what is being said" from "what is confirmed."
"""
from __future__ import annotations

from collections import defaultdict

from ..config import Config
from ..schema import Claim, Confidence, SourceTier
from ..vault import Vault
from ..reasoning import Reasoning


class RumorFilterAgent:
    def __init__(self, config: Config, vault: Vault, reasoning: Reasoning):
        self.config = config
        self.vault = vault
        self.reasoning = reasoning

    def run(self) -> tuple[list[Claim], list[dict]]:
        claims = self.vault.pending_claims()
        if not claims:
            return [], []

        # Build the same-fact cluster map across ALL historical claims so a
        # brand-new claim can be corroborated by something a prior cycle saw.
        same_fact: dict[str, set] = defaultdict(set)
        for c in self.vault.all_claims():
            same_fact[self._norm(c.text)].add(c.said_by)

        evaluated: list[Claim] = []
        noise: list[dict] = []
        for c in claims:
            source = self.vault.get_source(c.said_by)
            corrob = [h for h in same_fact[self._norm(c.text)]
                      if h != c.said_by]
            c = self.reasoning.evaluate_claim(c, source, corrob)
            self.vault.upsert_claim(c)
            if c.verdict == "dropped":
                noise.append({"text": c.text, "reason": c.reason,
                              "said_by": c.said_by})
            else:
                evaluated.append(c)

        print(f"[rumor-filter] kept/quarantined {len(evaluated)}, "
              f"dropped {len(noise)}")
        return evaluated, noise

    @staticmethod
    def _norm(text: str) -> str:
        return " ".join(text.lower().split()[:15])
