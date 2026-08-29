"""CHIEF OF STAFF agent.

Reads the other agents' outputs each cycle, de-duplicates, and discards
single-source unverified items from the main brief. Produces the three-part
brief: MAIN BRIEF (high-confidence important news), WATCHLIST (possibly
important but unconfirmed), NOISE LOG (why items were rejected). Writes one
markdown brief to the vault.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import Config
from ..schema import Brief, BriefItem, Claim, Confidence, Post
from ..vault import Vault


class ChiefOfStaffAgent:
    def __init__(self, config: Config, vault: Vault):
        self.config = config
        self.vault = vault

    def run(self, claims: list[Claim], noise: list[dict],
            posts_by_id: dict[str, Post]) -> Brief:
        main: list[BriefItem] = []
        watch: list[BriefItem] = []

        for c in claims:
            item = self._to_item(c, posts_by_id)
            if c.verdict == "quarantined":
                watch.append(item)
            elif c.confidence == Confidence.CONFIRMED and c.importance >= 0.5:
                main.append(item)
            elif c.confidence == Confidence.LIKELY and c.importance >= 0.6:
                main.append(item)
            elif c.importance >= 0.4:
                watch.append(item)
            else:
                noise.append({"text": c.text[:120],
                              "reason": "below importance bar",
                              "said_by": c.said_by})

        brief = Brief(
            generated_at=datetime.now(timezone.utc),
            main_brief=main,
            watchlist=watch,
            noise_log=noise,
        )
        path = self.vault.save_brief(brief)
        print(f"[chief-of-staff] brief written: {path} "
              f"({len(main)} main, {len(watch)} watch, {len(noise)} noise)")
        return brief

    @staticmethod
    def _to_item(c: Claim, posts_by_id: dict[str, Post]) -> BriefItem:
        post = posts_by_id.get(c.post_id)
        return BriefItem(
            headline=c.text[:140],
            why_it_matters=_why(c),
            confidence=c.confidence,
            primary_url=post.raw_url if post else "",
            supporting_accounts=c.corroborators,
            timestamp=post.timestamp if post else None,
            importance=c.importance,
            source_feed=post.source_feed if post else "",
            quote=(post.text if post else ""),   # verbatim, untruncated
        )


def _why(c: Claim) -> str:
    bits = []
    if c.is_primary_source:
        bits.append("first-party source")
    if c.has_primary_evidence:
        bits.append("primary evidence attached")
    if c.corroborators:
        bits.append(f"{len(c.corroborators)} independent corroborator(s)")
    if c.themes:
        bits.append("themes: " + ", ".join(c.themes[:4]))
    return "; ".join(bits) if bits else "pending verification"
