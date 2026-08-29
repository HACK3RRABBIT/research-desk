# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local, real-time **news intelligence system** (v0.1.4). A multi-agent
"research desk" that ingests posts/feeds, filters rumors, ranks importance, and
writes a markdown brief. Source of truth is **configurable feeds**: free news
RSS/Atom (`news_feeds`, the default — no X API needed), optional RSSHub Twitter
routes, and optional X API v2 search (`X_API_BEARER`). X's API is paid and the
public RSSHub blocks Twitter routes, so `news_feeds` is the out-of-box source.
All agents use an always-on, OpenAI-compatible AI engine configured live from the
built-in Hermes-styled web UI; the desk serves a React dashboard at `0.0.0.0:8088`.
The web UI is **localized (English / فارسی, RTL with Vazirmatn)**, **multi-theme**
(Hermes default + Night/Sea/Ivory), requires first-run **interest onboarding** plus
a free-text **manual directive**, renders **verbatim post text with accurate links**,
and shows **timezone-aware relative timestamps**. News content auto-translates
headlessly (free browser-style endpoint, no API key) when Persian is active.

## Commands

```bash
source .venv/bin/activate                       # uv-managed venv (no pip available)
uv pip install -e ".[dev]"                       # install; add [llm] for Claude backend
research-desk once    # one pipeline cycle -> prints brief
research-desk run     # continuous loop on poll_interval (Ctrl-C to stop)
research-desk run --max-cycles N
research-desk brief   # print latest brief markdown
research-desk sources  # list sources + trust scores
research-desk feedback <claim_id> <useful|not_useful|rumor|too_local|too_political|want_more>
python -m pytest tests/ -q                       # offline pipeline tests
```

## Architecture

- `research_desk/config.py` — loads `config.toml` over `CONFIG_DEFAULTS`. RSSHub
  base URL, watched users/lists/keywords, languages, poll interval, preferences.
  `set_llm()` / `save()` write the engine config to the gitignored
  `config.local.toml`; `has_llm()` / `needs_setup()` gate the always-on engine.
- `research_desk/server.py` — FastAPI app serving the Hermes webui (`webui/dist`)
  and the JSON API: engine config, run cycle, scheduler start/stop, feedback,
  watched accounts/keywords, agents/sources/themes, plus `/api/profile` and
  `/api/translate` for the localized/personalized UI. Secrets are masked in
  `/api/state` (never the raw key).
- `research_desk/i18n.py` — headless translation (`Translator`). Hits the free
  browser-style Google web endpoint (`clients5.google.com/translate_a/t`,
  `client=dict-chrome-ex`) with no API key; caches by `sha1(text):lang` in the
  vault; returns the original string on any failure (never breaks the desk).
- `research_desk/profile.py` — `INTEREST_CATEGORIES` taxonomy + `apply_interests()`
  (merges selected tags into `preferences.boost_themes` and a few into
  `watched_keywords`, marks onboarding complete). The `profile` config block
  holds language/theme/timezone/interests/`user_instructions`/`interests_complete`;
  `user_instructions` is injected into the reasoning `SYSTEM` message.
- `research_desk/reasoning.py` — **the engine seam.** `Reasoning` ABC with
  `OpenAICompatibleReasoning` (default, plain `requests` to any OpenAI-compatible
  `/chat/completions`), `AnthropicReasoning` (auto-activates when
  `ANTHROPIC_API_KEY` set + `llm.provider=anthropic`), and `HeuristicReasoning`
  (pure-Python, offline fallback). `get_reasoning(config)` picks by provider +
  `config.has_llm()`. Agents call `reasoning.*` for qualitative judgment and
  NEVER hard-code it — keep that boundary when editing. Switching engines touches
  only `reasoning.py` + `config.llm`, never the agents.
- `research_desk/schema.py` — dataclasses passed between agents: `Post`, `Claim`,
  `SourceNode`, `Brief`, `Feedback`, enums `SourceTier` / `Confidence`.
- `research_desk/vault.py` — **single shared store** (SQLite `data/db/vault.db` +
  markdown briefs in `data/briefs/`). All agents read/write this. Key methods:
  `pending_claims()`, `all_claims()`, `get_claim()`, `get_source()`, `upsert_*`.
- `research_desk/ingest/rsshub.py` — RSSHub `/twitter/user|list|keyword` adapters,
  Atom/RSS parsing, per-feed retry (failures are logged, not raised).
- `research_desk/ingest/news.py` — **free, no-auth news RSS/Atom** intake
  (`news_feeds` config). Default source of posts (X is paid/blocked). Strips HTML
  from feed content so the agents judge clean prose. Reuses rsshub's parser.
- `research_desk/ingest/x_search.py` — optional X API v2 recent-search, silent
  unless `X_API_BEARER` is set.
- `research_desk/agents/` — the six agents + `learning.py`. Each owns one stage:
  `intake`, `source_mapper`, `claim_extractor`, `rumor_filter`, `importance_ranker`,
  `chief_of_staff`, `learning`.
- `research_desk/desk.py` — `ResearchDesk` orchestrator wiring agents + vault; one
  `cycle()` runs the full pipeline. `research_desk/cli.py` — argparse entrypoint.

## Pipeline order (one cycle)

`intake → source_mapper → claim_extractor → rumor_filter → importance_ranker →
chief_of_staff`. Learning loop runs on demand via `feedback`.

## Key invariants / gotchas

- Rumor filter keys corroboration on **identical normalized fact text** (first 15
  tokens). Reworded posts do NOT corroborate each other — by design.
- Never let a failed RSSHub route or X call crash a cycle; ingest swallows errors.
- `config.toml` is committed with placeholder demo feeds — they 404 offline, which
  is expected. Real feeds must be supplied by the user.
- Switching heuristic↔LLM touches only `reasoning.py` + `config.llm`; do not push
  model logic into the agents.
- First run gates on **interests onboarding** (`profile.interests_complete`). The
  user's selected tags merge into `preferences.boost_themes`; a few high-signal
  ones also become `watched_keywords`. `user_instructions` is injected into the
  LLM `SYSTEM` message (offline heuristic ignores it).
- `BriefItem.quote` carries the **exact verbatim post text**; `headline` stays for
  the title. Never truncate/paraphrase `quote` — the whole point is fidelity. The
  primary-link accuracy depends on `post.raw_url` from RSSHub.
- Timestamps are stored in **UTC**; the UI renders relative "X min ago" + absolute
  times in the user's configured `profile.timezone` (client-side, via `Intl`).
  `ingest/rsshub.py::_parse_date` normalizes to UTC so the brief's `UTC` label is
  truthful.
- Persian auto-translation is **best-effort**: `i18n.py` hits a free endpoint and
  returns the original string on any failure, so localization never breaks the
  desk. Translations are cached in the vault by `sha1(text):lang`.
- Vault runs SQLite in **WAL** and the server serializes cycles/rebuilds with a
  lock, so an engine or profile change can't cause "database is locked".
