"""Shared data records passed between agents.

Every agent reads/writes these plain dataclasses. They are the contract that
lets the heuristic engine and the LLM engine be swapped without touching
downstream agents.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceTier(str, Enum):
    OFFICIAL_GOV = "official_gov"
    OFFICIAL_COMPANY = "official_company"
    PRIMARY_JOURNALIST = "primary_journalist"
    SUBJECT_EXPERT = "subject_expert"
    AGGREGATOR = "aggregator"
    UNKNOWN = "unknown"
    LOW_TRUST = "low_trust"


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    LIKELY = "likely"
    UNCONFIRMED = "unconfirmed"


@dataclass
class Post:
    post_id: str
    author: str
    author_handle: str = ""
    timestamp: Optional[datetime] = None
    text: str = ""
    media: list[str] = field(default_factory=list)
    quoted_post: Optional["Post"] = None
    engagement: int = 0
    language: str = "en"
    raw_url: str = ""
    source_feed: str = ""          # which ingest route produced it
    is_repost: bool = False
    is_quote: bool = False

    def short_text(self, n: int = 140) -> str:
        t = self.text or ""
        return t if len(t) <= n else t[: n - 1] + "…"


@dataclass
class SourceNode:
    handle: str
    tier: SourceTier = SourceTier.UNKNOWN
    trust: float = 0.5               # 0.0 low .. 1.0 high
    confirmations: int = 0           # times their claims were later confirmed
    misses: int = 0                  # times their claims were debunked
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


@dataclass
class Claim:
    claim_id: str
    post_id: str
    text: str
    said_by: str                     # author handle
    is_primary_source: bool = False
    has_primary_evidence: bool = False   # official graphic/doc/legal text/video
    is_forward_looking: bool = False      # speculation / teaser
    is_specific_fact: bool = True
    corroborators: list[str] = field(default_factory=list)  # independent handles
    confidence: Confidence = Confidence.UNCONFIRMED
    importance: float = 0.0
    themes: list[str] = field(default_factory=list)
    verdict: str = ""                # kept / quarantined / dropped
    reason: str = ""


@dataclass
class BriefItem:
    headline: str
    why_it_matters: str
    confidence: Confidence
    primary_url: str
    supporting_accounts: list[str]
    timestamp: Optional[datetime]
    importance: float = 0.0
    source_feed: str = ""


@dataclass
class Brief:
    generated_at: datetime
    main_brief: list[BriefItem] = field(default_factory=list)
    watchlist: list[BriefItem] = field(default_factory=list)
    noise_log: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Feedback:
    claim_id: str
    label: str                       # useful / not_useful / rumor / too_local /
                                    # too_political / want_more
    at: datetime = field(default_factory=utcnow)
