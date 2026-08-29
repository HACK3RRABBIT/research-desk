"""Offline end-to-end test of the research desk pipeline.

Injects synthetic posts directly (no network) and verifies the six agents
produce a coherent brief, applying the rumor filter and learning loop.
"""
from datetime import datetime, timezone

from research_desk.config import Config, CONFIG_DEFAULTS
from research_desk.vault import Vault
from research_desk.reasoning import HeuristicReasoning
from research_desk.schema import Post
from research_desk.agents import (
    IntakeAgent, SourceMapperAgent, ClaimExtractorAgent,
    RumorFilterAgent, ImportanceRankerAgent, ChiefOfStaffAgent,
    LearningAgent,
)


def _cfg(tmp_path):
    raw = dict(CONFIG_DEFAULTS)
    raw["data_dir"] = str(tmp_path / "data")
    # deterministic: no network feeds
    raw["watched_users"] = []
    raw["watched_keywords"] = []
    return Config(raw=raw)


def _post(post_id, handle, text, media=None, feed="test"):
    return Post(post_id=post_id, author=handle, author_handle=handle,
                timestamp=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
                text=text, media=media or [], raw_url=f"https://x.com/{handle}/status/{post_id}",
                source_feed=feed)


def test_pipeline_filters_rumors_and_ranks(tmp_path):
    cfg = _cfg(tmp_path)
    vault = Vault(cfg)
    reason = HeuristicReasoning(cfg)

    posts = [
        # Primary official statement with evidence + specifics -> confirmed/kept
        _post("1", "energy_gov", "2.1 million barrels of oil now under new "
               "sanctions, official filing published today", media=["doc.pdf"]),
        # Independent corroboration: SAME fact stated by a different account
        # (this is what triggers the 2+ corroborators -> CONFIRMED path)
        _post("2", "oil_analyst", "2.1 million barrels of oil now under new "
               "sanctions, official filing published today"),
        # Teaser with no evidence -> dropped
        _post("3", "hypeman", "HUGE announcement incoming about markets, stay tuned!"),
        # Screenshot-only rumor -> dropped
        _post("4", "randouser", "See this screenshot, something big happened (image attached)",
              media=["img.png"]),
        # Vague unsourced speculation -> quarantined
        _post("5", "randouser", "Sources say something might happen with Iran soon."),
    ]

    intake = IntakeAgent(cfg, vault)
    # intake.run would hit network; inject directly instead
    for p in posts:
        vault.upsert_post(p)
    kept = posts

    SourceMapperAgent(cfg, vault).run(kept)
    ClaimExtractorAgent(cfg, vault, reason).run(kept)
    evaluated, noise = RumorFilterAgent(cfg, vault, reason).run()
    ranked = ImportanceRankerAgent(cfg, vault, reason).run(evaluated)
    posts_by_id = {p.post_id: p for p in kept}
    brief = ChiefOfStaffAgent(cfg, vault).run(ranked, noise, posts_by_id)

    # The teaser + screenshot must be dropped
    dropped_texts = [n["text"] for n in noise]
    assert any("HUGE announcement incoming" in t for t in dropped_texts), noise
    assert any("screenshot" in t for t in dropped_texts), noise

    # The confirmed oil sanctions fact should reach the MAIN BRIEF
    assert brief.main_brief, "expected at least one main-brief item"
    joined = " ".join(i.headline for i in brief.main_brief)
    assert "sanctions" in joined.lower() and "oil" in joined.lower(), joined

    # Main brief item carries primary url + corroborators
    item = brief.main_brief[0]
    assert item.primary_url.startswith("https://x.com/")
    assert any(c in item.supporting_accounts for c in ("energy_gov", "oil_analyst"))

    # The watchlist holds the unconfirmed vague claim
    assert any("Sources say" in w.headline for w in brief.watchlist), brief.watchlist

    vault.close()


def test_learning_adjusts_trust(tmp_path):
    cfg = _cfg(tmp_path)
    vault = Vault(cfg)
    reason = HeuristicReasoning(cfg)
    learning = LearningAgent(cfg, vault)

    post = _post("10", "randouser", "Specific oil price move of $3 confirmed by filing.",
                 media=["doc.pdf"])
    vault.upsert_post(post)
    SourceMapperAgent(cfg, vault).run([post])
    ClaimExtractorAgent(cfg, vault, reason).run([post])
    evaluated, _ = RumorFilterAgent(cfg, vault, reason).run()
    claim = evaluated[0]

    # Mark the source as a rumor-monger; trust should drop and tier downgrade.
    before = vault.get_source("randouser")
    learning.apply_feedback(__import__("research_desk.schema",
                              fromlist=["Feedback"]).Feedback(
        claim_id=claim.claim_id, label="rumor"))
    after = vault.get_source("randouser")
    assert after.trust < before.trust, (before.trust, after.trust)
    assert after.tier.value == "low_trust"

    vault.close()
