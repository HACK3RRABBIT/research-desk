"""IMPORTANCE RANKER agent.

Re-ranks claims by real-world impact, novelty, whether they move money/policy/
security/energy/tech/geopolitics, and the user's learned preferences. Prefers
one clean primary post over 50 derivative posts (de-duplication by fact).
"""
from __future__ import annotations

from ..config import Config
from ..schema import Claim
from ..vault import Vault
from ..reasoning import Reasoning


class ImportanceRankerAgent:
    def __init__(self, config: Config, vault: Vault, reasoning: Reasoning):
        self.config = config
        self.vault = vault
        self.reasoning = reasoning

    def run(self, claims: list[Claim]) -> list[Claim]:
        ranked = self.reasoning.rank_importance(claims)

        # De-duplicate by fact: keep the highest-importance claim for each
        # normalized fact cluster, recording all supporting accounts.
        best: dict[str, Claim] = {}
        for c in ranked:
            norm = self._norm(c.text)
            existing = best.get(norm)
            if existing is None or c.importance > existing.importance:
                if existing is not None:
                    c.corroborators = list({
                        *existing.corroborators, *c.corroborators})
                best[norm] = c
        deduped = sorted(best.values(), key=lambda c: c.importance,
                         reverse=True)
        print(f"[importance-ranker] {len(deduped)} unique items after "
              f"de-dup (from {len(claims)})")
        return deduped

    @staticmethod
    def _norm(text: str) -> str:
        return " ".join(text.lower().split()[:15])
