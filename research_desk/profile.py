"""User profile: interests + a free-text directive that tunes the desk.

The first-run onboarding asks the user to pin down a long list of interests
(see INTEREST_CATEGORIES below) and optionally write a short manual directive
("what should research-desk search for?"). Both are stored in config.profile
and applied to the desk: selected tags feed `preferences.boost_themes` so the
importance ranker and learning loop favour them, and the directive is injected
into the LLM judgment core so it personalises its verdicts.

The taxonomy is the single source of truth for both the backend validator and
the webui picker, so a tag the user picks is always a real one.
"""
from __future__ import annotations

from typing import Any

# Categorized interest taxonomy. Each category has a label and a list of
# (tag, human label) pairs. The webui renders the same structure; the backend
# validates selections against the flat tag set.
INTEREST_CATEGORIES: list[dict[str, Any]] = [
    {
        "label": "Energy & Commodities",
        "items": [
            ("energy", "Energy"),
            ("oil", "Oil"),
            ("gas", "Gas & LNG"),
            ("uranium", "Uranium / Nuclear"),
            ("renewables", "Renewables"),
            ("electricity", "Electricity & Grid"),
            ("shipping", "Shipping & Maritime"),
            ("commodities", "Commodities"),
        ],
    },
    {
        "label": "Markets & Money",
        "items": [
            ("markets", "Global markets"),
            ("stocks", "Equities"),
            ("crypto", "Crypto / Digital assets"),
            ("rates", "Rates & bonds"),
            ("inflation", "Inflation & CPI"),
            ("central_banks", "Central banks"),
            ("macro", "Macro economy"),
            ("debt", "Sovereign & corporate debt"),
        ],
    },
    {
        "label": "Geopolitics",
        "items": [
            ("geopolitics", "Geopolitics"),
            ("iran", "Iran"),
            ("china", "China"),
            ("russia", "Russia"),
            ("us_policy", "US policy"),
            ("europe", "Europe"),
            ("middle_east", "Middle East"),
            ("nato", "NATO / Defense pacts"),
            ("trade", "Trade & tariffs"),
            ("india", "India"),
        ],
    },
    {
        "label": "Security & Defense",
        "items": [
            ("security", "Security"),
            ("defense", "Defense & arms"),
            ("military", "Military operations"),
            ("cyber", "Cyber / Infosec"),
            ("intelligence", "Intelligence & signals"),
            ("sanctions", "Sanctions & export controls"),
        ],
    },
    {
        "label": "Technology",
        "items": [
            ("ai", "AI / Machine learning"),
            ("x", "X / Twitter"),
            ("tech_platform", "Tech platforms"),
            ("semiconductors", "Semiconductors / chips"),
            ("space", "Space & launch"),
            ("telecom", "Telecom & networks"),
            ("software", "Software & cloud"),
        ],
    },
    {
        "label": "Science & Climate",
        "items": [
            ("climate", "Climate & environment"),
            ("health", "Health & biotech"),
            ("science", "Science"),
            ("energy_tech", "Energy tech"),
        ],
    },
    {
        "label": "Regions",
        "items": [
            ("mena", "Middle East & North Africa"),
            ("asia", "Asia-Pacific"),
            ("europe_region", "Europe"),
            ("americas", "Americas"),
            ("africa", "Africa"),
        ],
    },
]

# Flat tag set for validation + quick membership checks.
INTEREST_TAGS: set[str] = {
    tag for cat in INTEREST_CATEGORIES for tag, _ in cat["items"]
}

# Tags that map to a *likely* X keyword feed worth pulling on their own. Kept
# deliberately short and high-signal — the desk should not chase noise.
_KEYWORD_HINTS: dict[str, str] = {
    "oil": "oil",
    "gas": "gas",
    "sanctions": "sanctions",
    "iran": "Iran",
    "markets": "markets",
    "crypto": "crypto",
    "ai": "AI",
    "cyber": "cyber",
}


def validate_interests(tags: list[str]) -> list[str]:
    """Dedupe and keep only real taxonomy tags."""
    out: list[str] = []
    for t in tags or []:
        t = str(t).strip().lower()
        if t and t in INTEREST_TAGS and t not in out:
            out.append(t)
    return out


def apply_interests(config, tags: list[str]) -> list[str]:
    """Merge selected interests into the desk's preference knobs.

    Selected tags become boost themes (so the importance ranker + learning loop
    favour them) and a few high-signal ones also become watched keywords so
    intake actively searches for them. Returns the applied tag list.
    """
    from .config import Config

    if not isinstance(config, Config):
        raise TypeError("config must be a Config")

    applied = validate_interests(tags)
    config.set_profile(interests=applied, interests_complete=True)

    # Boost themes: the tags themselves (the heuristic already recognises many
    # of these exact strings), deduped.
    boost = config.preferences.setdefault("boost_themes", [])
    for t in applied:
        if t not in boost:
            boost.append(t)

    # A few tags also seed watched keywords so the desk actively hunts them.
    kws = config.raw["watched_keywords"]
    for t in applied:
        kw = _KEYWORD_HINTS.get(t)
        if kw and kw not in kws:
            kws.append(kw)

    config.save()
    return applied
