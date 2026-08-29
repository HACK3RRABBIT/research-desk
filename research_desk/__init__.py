"""research-desk: a personal real-time X/Twitter news intelligence system.

Six specialized agents (Intake, SourceMapper, ClaimExtractor, RumorFilter,
ImportanceRanker, ChiefOfStaff) plus a LearningLoop share a single vault
(SQLite + markdown briefs) and run on a scheduler. Heuristic by default,
optionally upgraded to Claude when an API key is present.
"""
from .desk import ResearchDesk
from .config import Config, load_config

__version__ = "0.1.3"
__all__ = ["ResearchDesk", "Config", "load_config"]
