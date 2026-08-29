"""Configuration for research-desk.

All runtime settings live here, loaded from config.toml (or config.yaml).
Missing or partial config files fall back to CONFIG_DEFAULTS, so the system
runs out of the box with zero setup.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CONFIG_DEFAULTS: dict[str, Any] = {
    # RSSHub instance. Point this at your own deploy for reliability.
    "rsshub_base_url": "https://rsshub.app",

    # How often the scheduler wakes each cycle (seconds).
    "poll_interval": 300,

    # Languages we keep. Two-letter ISO codes.
    "languages": ["en"],

    # RSSHub /twitter/user/:id feeds.
    "watched_users": [
        "FloodProtocol",   # demo account likely to exist; replace with real ones
    ],

    # RSSHub /twitter/list/:id feeds (numeric list ids).
    "watched_lists": [],

    # RSSHub /twitter/keyword/:keyword feeds.
    "watched_keywords": [
        "breaking",
        "sanctions",
        "oil",
        "Iran",
    ],

    # X web-search fallback keywords (used if X_API_BEARER is set, else skipped).
    "x_search_queries": [
        "from:???"   # placeholder; see README for enabling real X search
    ],

    # Preference knobs consumed by the agents (heuristic + learning loop).
    "preferences": {
        "boost_themes": [
            "official announcement",
            "energy", "oil", "gas", "sanctions", "shipping", "markets",
            "ai", "x", "tech platform",
            "geopolitics", "iran", "policy", "security",
        ],
        "ignore_themes": [
            "celebrity", "sports", "teaser marketing", "gossip",
        ],
        "min_importance": 0.0,   # items below this are noise
    },

    # Optional LLM backend. When provider is "anthropic" and a key is present,
    # individual agents transparently upgrade from heuristics to Claude.
    "llm": {
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "temperature": 0.0,
        "max_tokens": 1024,
        # Override the API key via env ANTHROPIC_API_KEY or set it here.
        "api_key": "",
    },

    # Where we store state.
    "data_dir": "data",
}


@dataclass
class Config:
    raw: dict[str, Any] = field(default_factory=dict)

    # ---- convenience accessors -------------------------------------------
    @property
    def rsshub_base_url(self) -> str:
        return self.raw["rsshub_base_url"].rstrip("/")

    @property
    def poll_interval(self) -> int:
        return int(self.raw["poll_interval"])

    @property
    def languages(self) -> list[str]:
        return self.raw["languages"]

    @property
    def watched_users(self) -> list[str]:
        return self.raw["watched_users"]

    @property
    def watched_lists(self) -> list[str]:
        return self.raw["watched_lists"]

    @property
    def watched_keywords(self) -> list[str]:
        return self.raw["watched_keywords"]

    @property
    def x_search_queries(self) -> list[str]:
        return self.raw["x_search_queries"]

    @property
    def preferences(self) -> dict[str, Any]:
        return self.raw["preferences"]

    @property
    def data_dir(self) -> Path:
        return Path(self.raw["data_dir"])

    @property
    def llm(self) -> dict[str, Any]:
        return self.raw["llm"]

    def has_llm(self) -> bool:
        """True when the LLM backend should be used this run."""
        if self.llm.get("provider") != "anthropic":
            return False
        key = self.llm.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        return bool(key)

    def llm_key(self) -> str:
        return self.llm.get("api_key") or os.environ.get("ANTHROPIC_API_KEY", "")

    def add_watched_user(self, user: str) -> None:
        if user and user not in self.raw["watched_users"]:
            self.raw["watched_users"].append(user)

    def add_keyword(self, kw: str) -> None:
        if kw and kw not in self.raw["watched_keywords"]:
            self.raw["watched_keywords"].append(kw)

    def save(self, path: Path) -> None:
        import tomli_w  # optional dep; only needed when persisting edits
        path.write_text(tomli_w.dumps(self.raw), encoding="utf-8")


def load_config(path: str | Path | None = None) -> Config:
    """Merge file config (if any) over CONFIG_DEFAULTS."""
    path = Path(path) if path else Path("config.toml")
    raw = dict(CONFIG_DEFAULTS)
    if path.exists():
        with path.open("rb") as fh:
            user_cfg = tomllib.load(fh)
        _deep_update(raw, user_cfg)
    return Config(raw=raw)


def _deep_update(base: dict, override: dict) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
