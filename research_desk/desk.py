"""Pipeline orchestrator for the research desk.

Wires the six agents + shared vault into one cycle and exposes a scheduler.
One cycle: Intake -> SourceMapper -> ClaimExtractor -> RumorFilter ->
ImportanceRanker -> ChiefOfStaff. The learning loop runs on demand (feedback).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .config import Config, load_config
from .vault import Vault
from .reasoning import get_reasoning
from .schema import Post
from .agents import (
    ClaimExtractorAgent,
    ChiefOfStaffAgent,
    ImportanceRankerAgent,
    IntakeAgent,
    LearningAgent,
    RumorFilterAgent,
    SourceMapperAgent,
)


class ResearchDesk:
    def __init__(self, config: Config | None = None, config_path=None):
        self.config = config or load_config(config_path)
        self.vault = Vault(self.config)
        self.reasoning = get_reasoning(self.config)
        self.engine = self.reasoning.engine

        self.intake = IntakeAgent(self.config, self.vault)
        self.mapper = SourceMapperAgent(self.config, self.vault)
        self.extractor = ClaimExtractorAgent(self.config, self.vault,
                                             self.reasoning)
        self.rumor = RumorFilterAgent(self.config, self.vault, self.reasoning)
        self.ranker = ImportanceRankerAgent(self.config, self.vault,
                                            self.reasoning)
        self.cos = ChiefOfStaffAgent(self.config, self.vault)
        self.learning = LearningAgent(self.config, self.vault)
        self.learning.reconcile_trust()

    def cycle(self):
        posts = self.intake.run()
        self.mapper.run(posts)
        self.extractor.run(posts)
        evaluated, noise = self.rumor.run()
        ranked = self.ranker.run(evaluated)
        posts_by_id = {p.post_id: p for p in posts}
        brief = self.cos.run(ranked, noise, posts_by_id)
        return brief

    def feedback(self, claim_id: str, label: str):
        from .schema import Feedback, utcnow
        self.learning.apply_feedback(Feedback(claim_id=claim_id, label=label,
                                              at=utcnow()))
        print(f"[learning] applied '{label}' to {claim_id}")

    def latest_brief(self) -> str:
        briefs = sorted(self.vault.briefs_dir.glob("brief_*.md"))
        if not briefs:
            return "_No briefs yet._"
        return briefs[-1].read_text(encoding="utf-8")

    def close(self):
        self.vault.close()
