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

    # Free, no-auth news RSS/Atom feeds. X/Twitter's API is paid and the public
    # RSSHub instance blocks Twitter routes, so these give the desk real input
    # out of the box. Standard RSS/Atom — no key required. Edit to taste.
    "news_feeds": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://www.theguardian.com/world/rss",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://www.theverge.com/rss/index.xml",
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

    # Optional LLM backend — the intelligence engine. Every agent that makes a
    # qualitative call delegates here. On startup the webui gates on this being
    # configured (see Config.needs_setup): the agent is ALWAYS-ON by design, so
    # we default to the OpenAI-compatible provider and only fall back to the
    # offline heuristic when a call fails at runtime (never by choice).
    # "provider": "openai" | "anthropic" | "heuristic" (troubleshoot fallback)
    "llm": {
        "provider": "openai",
        # base_url/model start empty so the webui rings the setup bell until
        # the user supplies them (see Config.needs_setup). The UI prefills
        # OpenAI-compatible placeholders to make that one click.
        "base_url": "",
        "model": "",
        "temperature": 0.0,
        "max_tokens": 1024,
        "timeout": 60,
        # Override via env OPENAI_API_KEY / ANTHROPIC_API_KEY, or set it here.
        "api_key": "",
    },

    # Automatic account discovery: the desk keeps watching the accounts on its
    # roadmap, but instead of being a fixed list it learns new ones as it reads
    # posts (authors, quotes, @mentions) and finds them worth covering.
    "discovery": {
        "enabled": True,
        "max_per_cycle": 5,      # how many new accounts to add per cycle
        "max_total": 50,         # ceiling on auto-discovered accounts
    },

    # Scheduler: on server start, if the engine is configured, begin polling
    # immediately. The desk is meant to run continuously.
    "scheduler": {
        "autostart": True,
    },

    # User profile: the personalization + localization knobs the desk is tuned
    # to. Persisted to config.local.toml. `interests_complete` gates the first-run
    # onboarding: the user picks interests before they can use the desk.
    "profile": {
        "language": "en",             # "en" | "fa"
        "theme": "hermes",            # hermes | night | sea | ivory
        "timezone": "Etc/UTC",        # IANA name, used to render "X min ago"
        "interests": [],              # selected tags from profile.INTEREST_TAXONOMY
        "user_instructions": "",      # free-text directive the user gives the AI
        "interests_complete": False,  # False -> show the onboarding gate
    },

    # Where we store state.
    "data_dir": "data",
}


@dataclass
class Config:
    raw: dict[str, Any] = field(default_factory=dict)
    local_path: Path = field(default_factory=lambda: Path("config.local.toml"))

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
    def news_feeds(self) -> list[str]:
        return self.raw.get("news_feeds", [])

    @property
    def preferences(self) -> dict[str, Any]:
        return self.raw["preferences"]

    @property
    def data_dir(self) -> Path:
        return Path(self.raw["data_dir"])

    @property
    def llm(self) -> dict[str, Any]:
        return self.raw["llm"]

    @property
    def discovery(self) -> dict[str, Any]:
        return self.raw["discovery"]

    @property
    def scheduler(self) -> dict[str, Any]:
        return self.raw["scheduler"]

    @property
    def profile(self) -> dict[str, Any]:
        return self.raw["profile"]

    def set_profile(self, **kw: Any) -> "Config":
        """Apply a partial update to the user profile block (used by the webui)."""
        for k, v in kw.items():
            if v is not None:
                self.profile[k] = v
        return self

    def needs_onboarding(self) -> bool:
        """True on first run when the user hasn't picked interests yet."""
        return not bool(self.profile.get("interests_complete"))

    # ---- LLM readiness ---------------------------------------------------
    @property
    def llm_provider(self) -> str:
        return self.llm.get("provider", "heuristic")

    def _llm_ready(self) -> bool:
        """True when the configured provider has what it needs to run."""
        p = self.llm_provider
        if p == "openai":
            return bool(self.llm.get("base_url", "").strip()) and bool(
                self.llm.get("model", "").strip())
        if p == "anthropic":
            return bool(self.llm_key())
        return False

    def has_llm(self) -> bool:
        """True when the intelligence engine should be used this run."""
        return self._llm_ready()

    def needs_setup(self) -> bool:
        """True when the engine is unconfigured and must be set up before use.

        The desk is always-on by design; when the active provider is not yet
        configured we block on a setup screen rather than silently downgrading.
        """
        if self.llm_provider not in ("openai", "anthropic"):
            return False
        return not self._llm_ready()

    @property
    def llm_env_var(self) -> str:
        return "OPENAI_API_KEY" if self.llm_provider == "openai" \
            else "ANTHROPIC_API_KEY"

    def llm_key(self) -> str:
        return self.llm.get("api_key") or os.environ.get(self.llm_env_var, "")

    # ---- LLM mutation ----------------------------------------------------
    def set_llm(self, **kw: Any) -> "Config":
        """Apply a partial update to the llm block (used by the webui)."""
        for k, v in kw.items():
            if v is not None:
                self.llm[k] = v
        return self

    def add_watched_user(self, user: str) -> None:
        user = user.strip().lstrip("@")
        if user and user not in self.raw["watched_users"]:
            self.raw["watched_users"].append(user)

    def add_keyword(self, kw: str) -> None:
        kw = kw.strip()
        if kw and kw not in self.raw["watched_keywords"]:
            self.raw["watched_keywords"].append(kw)

    def discovered_users(self) -> list[str]:
        return list(self.raw.get("discovered_users", []))

    def add_discovered_user(self, user: str) -> bool:
        user = user.strip().lstrip("@")
        if not user:
            return False
        disc = self.raw.setdefault("discovered_users", [])
        if user in self.raw["watched_users"] or user in disc:
            return False
        if len(disc) >= int(self.discovery.get("max_total", 50)):
            return False
        disc.append(user)
        self.raw["watched_users"].append(user)
        return True

    def save(self, path: Path | None = None) -> None:
        import tomli_w  # optional dep; only needed when persisting edits
        path = path or self.local_path
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Persist only the runtime-managed keys (never the whole snapshot, so a
        # user's committed config.toml keeps authority for preferences, etc.).
        snapshot = {
            "llm": self.llm,
            "watched_users": self.raw["watched_users"],
            "watched_keywords": self.raw["watched_keywords"],
            "discovered_users": self.raw.get("discovered_users", []),
            "news_feeds": self.raw.get("news_feeds", []),
            "profile": self.profile,
        }
        path.write_text(tomli_w.dumps(snapshot), encoding="utf-8")


def load_config(path: str | Path | None = None) -> Config:
    """Merge config.toml, then gitignored config.local.toml, over defaults.

    config.local.toml holds runtime state (LLM credentials, discovered/watched
    accounts, profile) so secrets and auto-learned sources never touch git.

    The local file is *read* from next to config.toml (backward compatible), but
    *written* under ``data_dir`` — which is the path operators mount as a
    volume (e.g. in Docker). That keeps user setup (engine, interests, learned
    sources) durable across container restarts, instead of vanishing with the
    image's writable layer.
    """
    base = Path(path) if path else Path("config.toml")
    legacy_local = base.with_name(f"{base.stem}.local.toml") \
        if base.suffix == ".toml" else Path(str(base) + ".local")

    raw = dict(CONFIG_DEFAULTS)
    # Read legacy local file (alongside config.toml) if it exists.
    if legacy_local.exists():
        with legacy_local.open("rb") as fh:
            _deep_update(raw, tomllib.load(fh))

    cfg = Config(raw=raw)
    # Write path: <data_dir>/config.local.toml. data_dir defaults to "data".
    data_dir = Path(raw.get("data_dir", "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg.local_path = data_dir / "config.local.toml"
    # If we read a legacy file but the volume copy doesn't exist yet, seed it so
    # an existing local setup survives the first run in a container.
    if legacy_local.exists() and not cfg.local_path.exists():
        try:
            cfg.local_path.write_text(
                legacy_local.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    # If a fresh volume copy exists, re-merge it so it wins over the legacy read.
    if cfg.local_path.exists():
        with cfg.local_path.open("rb") as fh:
            _deep_update(raw, tomllib.load(fh))
        cfg.raw = raw
    return cfg


def _deep_update(base: dict, override: dict) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
