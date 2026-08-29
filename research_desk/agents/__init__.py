"""Specialized agents of the research desk.

Each agent owns one stage of the pipeline and reads/writes the shared vault.
They are deliberately small and independent so they can be swapped, tested, or
upgraded to the LLM engine individually (see reasoning.py).
"""
from .intake import IntakeAgent
from .source_mapper import SourceMapperAgent
from .claim_extractor import ClaimExtractorAgent
from .rumor_filter import RumorFilterAgent
from .importance_ranker import ImportanceRankerAgent
from .chief_of_staff import ChiefOfStaffAgent
from .learning import LearningAgent
from .discovery import DiscoveryAgent

__all__ = [
    "IntakeAgent", "SourceMapperAgent", "ClaimExtractorAgent",
    "RumorFilterAgent", "ImportanceRankerAgent", "ChiefOfStaffAgent",
    "LearningAgent", "DiscoveryAgent",
]
