# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local, real-time **X / Twitter news intelligence system** (v0.1.0). A multi-agent
"research desk" that ingests X posts via RSSHub (+ optional X API search), filters
rumors, ranks importance, and writes a markdown brief. Source of truth is X only.

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
- `research_desk/schema.py` — dataclasses passed between agents: `Post`, `Claim`,
  `SourceNode`, `Brief`, `Feedback`, enums `SourceTier` / `Confidence`.
- `research_desk/vault.py` — **single shared store** (SQLite `data/db/vault.db` +
  markdown briefs in `data/briefs/`). All agents read/write this. Key methods:
  `pending_claims()`, `all_claims()`, `get_claim()`, `get_source()`, `upsert_*`.
- `research_desk/reasoning.py` — **the engine seam.** `Reasoning` ABC with
  `HeuristicReasoning` (default, pure-Python, offline) and `AnthropicReasoning`
  (auto-activates when `ANTHROPIC_API_KEY` set + `llm.provider=anthropic`).
  `get_reasoning(config)` picks. Agents call `reasoning.*` for qualitative judgment
  and NEVER hard-code it — keep that boundary when editing.
- `research_desk/ingest/rsshub.py` — RSSHub `/twitter/user|list|keyword` adapters,
  Atom/RSS parsing, per-feed retry (failures are logged, not raised).
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
