"""LEARNING LOOP agent.

Turns user feedback into adjustments of topics, accounts, languages, and what
counts as "important." On each call it: (1) applies stored feedback to source
trust and to preference theme weights, (2) returns the live preference knobs
other agents should use. Feedback labels: useful, not_useful, rumor,
too_local, too_political, want_more.

Trust update rule: a source whose claims you mark 'rumor'/'not_useful' loses
trust; one whose claims you mark 'useful'/'want_more' gains trust. Confirmation
history (later confirmed) also moves trust (handled here on feedback too).
"""
from __future__ import annotations

from collections import defaultdict

from ..config import Config
from ..schema import Feedback, SourceTier
from ..vault import Vault

_LABEL_BUMP = {
    "useful": +0.10,
    "want_more": +0.08,
    "not_useful": -0.10,
    "rumor": -0.20,
    "too_local": -0.05,
    "too_political": -0.05,
}


class LearningAgent:
    def __init__(self, config: Config, vault: Vault):
        self.config = config
        self.vault = vault

    def apply_feedback(self, fb: Feedback) -> None:
        self.vault.add_feedback(fb)
        claim = self.vault.get_claim(fb.claim_id)
        if claim is None:
            return
        node = self.vault.get_source(claim.said_by)
        delta = _LABEL_BUMP.get(fb.label, 0.0)
        node.trust = max(0.0, min(1.0, node.trust + delta))
        if fb.label == "rumor":
            node.misses += 1
            if node.tier not in (SourceTier.LOW_TRUST,):
                node.tier = SourceTier.LOW_TRUST
        elif fb.label in ("useful", "want_more"):
            node.confirmations += 1
        self.vault.upsert_source(node)

        if fb.label in ("want_more", "useful") and claim.themes:
            self._boost_themes(claim.themes)

    def _boost_themes(self, themes: list[str]) -> None:
        boost = self.config.preferences.setdefault("boost_themes", [])
        for t in themes:
            if t and t not in boost:
                boost.append(t)

    def reconcile_trust(self) -> None:
        """Re-derive trust from confirmation history for all sources."""
        for node in self.vault.all_sources():
            if node.confirmations or node.misses:
                score = node.confirmations / max(1, node.confirmations
                                                 + node.misses)
                node.trust = round(0.4 + 0.6 * score, 3)
                if node.trust < 0.25 and node.tier != SourceTier.LOW_TRUST:
                    node.tier = SourceTier.LOW_TRUST
                self.vault.upsert_source(node)
