# research-desk

A personal, real-time **X / Twitter news intelligence system** inspired by a
multi-agent research desk. It continuously monitors X, separates *what is being
said* from *what is confirmed*, drops rumors and clickbait, learns your
preferences, and delivers one clean ranked brief you can read in 3–5 minutes.

Source of truth is X only (plus RSSHub feeds that mirror X).

## Principles

- Watches original posts **and** reposts / quotes / reply chains. Important news
  often surfaces first as a quote or repost from a mid-tier account.
- Does **not** rely on a fixed list of accounts. New sources are discovered
  dynamically when many independent accounts amplify the same fact.
- High importance = official statements, first-party announcements,
  market-moving facts, government/company/org actions, verified breaking
  events with primary evidence.
- Low value = speculation, "sources say" with no primary post, recycled outrage,
  engagement bait, unsourced screenshots, conspiracy framing, "huge
  announcement incoming" teasers.

## Architecture

Six specialized agents share one **vault** and run on a scheduler.

| Agent | Job |
|-------|-----|
| **INTAKE** | Pull posts from RSSHub (users / lists / keywords) + optional X search; normalize to a standard record. |
| **SOURCE MAPPER** | Maintain a living source graph; tag trust tiers; upgrade/downgrade from confirmation history; discover new accounts. |
| **CLAIM EXTRACTOR** | Extract atomic claims; note primary-source status, attached evidence, forward-looking speculation. |
| **RUMOR FILTER** | Score each claim; drop/quarantine teasers, anonymous-source piles, screenshot-only & vague claims; keep a watchlist. |
| **IMPORTANCE RANKER** | Rank by real-world impact, novelty, money/policy/security/energy/tech/geopolitics, and learned preferences; de-dupe. |
| **CHIEF OF STAFF** | Read the others; de-dupe; discard single-source unverified items; emit MAIN BRIEF + WATCHLIST + NOISE LOG. |

A **LEARNING LOOP** agent turns your feedback into trust/theme adjustments.

### Engine: always-on AI, configurable from the web

Every qualitative call goes through a single `Reasoning` interface
(`research_desk/reasoning.py`). Three implementations satisfy it:

- **`OpenAICompatibleReasoning`** — the **default** engine. Calls any
  OpenAI-compatible endpoint (`POST /chat/completions`) with plain `requests` —
  works with OpenAI, OpenRouter, vLLM, LM Studio, Ollama, Groq, etc. Base URL,
  API key, and model name are configured live from the web UI (or `config.local.toml`),
  reconfigurable at any time without touching agent code.
- **`AnthropicReasoning`** — calls Claude directly. Selected when
  `llm.provider = "anthropic"` and an API key is present.
- **`HeuristicReasoning`** — pure Python rules, **zero external dependencies,
  runs offline immediately**. Used when no engine is configured yet.

Only `reasoning.py` + `config.llm` decide the engine. Agents never hard-code it.
The engine is **always-on**: on startup the web UI gates until a model is wired
up, then the scheduler begins polling. Any backend failure falls back to
heuristics rather than crashing the cycle. It is also self-learning — feedback
re-ranks importance over time, and new accounts are discovered from deep post
analysis (importance is judged by substance, never by fame or a blue tick).

## Quick start (Docker) — recommended

One command builds the image and launches the whole desk (backend + web UI):

```bash
docker compose up -d
```

Open `http://localhost:8088` → the AI Engine gate asks for your provider, base
URL, API key, and model name. Save it; the desk starts polling immediately.
Runtime state (engine config, your interests, learned sources, briefs) is stored
in the `research-desk-data` volume, so it survives restarts. To stop:
`docker compose down` (data is kept); `docker compose down -v` also deletes it.

## Setup (from source)

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

**Launch the desk** (always-on web UI + API):

```bash
uvicorn research_desk.server:app --host 0.0.0.0 --port 8088
```

Open `http://localhost:8088` → the AI Engine gate asks for your provider, base
URL, API key, and model name (OpenAI-compatible by default). Save it; the desk
starts polling immediately. Secrets go to the gitignored `config.local.toml` —
never to git.

You can also configure it from the CLI by editing `config.local.toml`
(copied from `config.toml`): `watched_users`, `watched_keywords`,
`watched_lists`, `languages`, `poll_interval`, `rsshub_base_url` (self-host
RSSHub for reliability — docs at https://docs.rsshub.app/). RSSHub `/twitter`
routes require RSSHub's Twitter radar access; if a route 404s the system logs
and continues.

> The X web-search route (`x_search_queries`) only runs when you export
> `X_API_BEARER="<your token>"`. Without it, the desk runs on free news RSS
> feeds (see below) plus RSSHub.

## Engines (where the intelligence comes from)

The desk is **always-on**: every qualitative call (extract claims, judge rumors,
rank importance) goes through one `Reasoning` engine, configurable live from the
web UI. Three options:

- **OpenAI-compatible (default)** — any endpoint speaking
  `POST /v1/chat/completions`. Covers OpenAI, OpenRouter, Groq, vLLM, **and your
  own offline/local model**.
- **Anthropic / Claude** — set `provider = anthropic` + an API key.
- **Heuristic (offline, no model)** — pure-Python rules; works with zero setup
  but is less nuanced than an LLM.

### Offline / local model (no API key, no cloud)

Point the **OpenAI-compatible** engine at a local server — the desk needs no
code change, because Ollama, LM Studio, llama.cpp and unsloth GGUF servers all
speak the same `/v1/chat/completions` protocol:

| Server | Base URL | Notes |
|--------|----------|-------|
| **Ollama** | `http://localhost:11434/v1` | `ollama pull qwen3` then use model `qwen3` |
| **LM Studio** | `http://localhost:1234/v1` | load any GGUF, copy its model name |
| **llama.cpp / vLLM / unsloth** | `http://localhost:<port>/v1` | serve your `Qwen3-*.GGUF` and use its model id |

In the web UI: set **Provider = OpenAI-compatible**, **Base URL** to the local
server, **Model** to the loaded model id (e.g. `qwen3.8-27b` for an unsloth
Qwen3 GGUF), and leave **API key blank**. Save — the desk runs fully offline.
The "Test connection" button tolerates streaming/SSE proxies and
reasoning-heavy models that return empty `content`.

## Free news feeds (no X API needed)

X/Twitter's API is paid and the public RSSHub instance blocks Twitter routes, so
out of the box the desk ingests **standard news RSS/Atom** instead — free, no
auth, real-time. Configure via `news_feeds` in `config.toml` (seeded with BBC
World, Hacker News, The Verge, WSJ). Items carry real text, timestamps, and
source links, so the rumor filter and ranker have genuine input. To add X
coverage, either self-host RSSHub or set `X_API_BEARER`.

## Usage

```bash
research-desk once        # run one cycle and print the brief
research-desk run         # run continuously on poll_interval (Ctrl-C to stop)
research-desk run --max-cycles 5
research-desk brief       # print the latest brief markdown
research-desk sources     # list known sources and their trust scores
research-desk config      # show resolved config
```

Each cycle writes a timestamped brief to `data/briefs/brief_YYYYMMDD_HHMMSS.md`
and stores structured state in `data/db/vault.db`.

## Giving feedback (learning loop)

After reading a brief, label the claim id you care about:

```bash
research-desk feedback <claim_id> useful
research-desk feedback <claim_id> rumor
# labels: useful | not_useful | rumor | too_local | too_political | want_more
```

Feedback lowers/raises source trust, marks low-trust accounts, and boosts
themes you want more of — so the next brief adapts to you.

## Milestone status

**v0.1.2 — localization, themes, personalization, fidelity.** The web UI gained
a full **Persian (فارسی) version**: Vazirmatn font, right-aligned RTL layout, and
news content **auto-translated headlessly** — the desk calls the same free Google
web endpoint a normal browser's Translate uses (`clients5.google.com/translate_a/t`,
no API key, no paid quota), cached in the vault so Persian renders are stable. A
**multi-theme** system (Hermes stays default) adds Night / Sea / Ivory skins,
switchable from the topbar or Settings. **First-run onboarding** now requires the
user to pick from a long categorized interest list, plus a free-text **manual
directive** that is injected into the judgment core so it personalises verdicts
and actively searches for those subjects. Timestamps are shown as **relative
times ("6 min ago") and absolute times in the user's chosen timezone**. The brief
now renders the **exact published post text verbatim** with an **accurate link to
the original X post**. (Fixes: RSSHub dates are normalized to UTC so the brief's
`UTC` label is truthful; SQLite runs in WAL with a cycle/rebuild lock so engine
and profile changes can't trigger "database is locked".)
**v0.1.1 — always-on intelligence + Hermes web UI.** Every agent uses AI via an
**OpenAI-compatible** engine configured live from the browser (provider, base
URL, API key, model name). The whole web UI is redesigned in the **Hermes**
house style (real webfonts, ultramarine field, chartreuse accents, noise/vignette
surfaces) and served at `0.0.0.0:8088`. The engine is always-on: it gates on
setup at first start, then polls continuously, reconfigurable and resettable at
any time. New accounts are auto-discovered from deep post analysis, importance is
judged by substance (not fame/blue-tick), and the system continuously learns and
re-ranks from feedback. Control the desk from the browser: run a cycle, toggle
the scheduler, give feedback, manage watched accounts/keywords, and watch the
source-trust and theme dashboards.
**v0.1.0 — first working version.** Ingests from RSSHub Twitter feeds (+ X
keyword search when a bearer token is set), extracts claims, filters obvious
rumors, and writes one markdown brief.

## Notes & limits

- RSSHub `/twitter` routes depend on RSSHub's upstream Twitter access; a failing
  route is retried then logged — it never crashes the cycle.
- Corroboration requires two independent accounts to state the *same specific
  fact*; reworded posts do not count as independent confirmation.
- Default demo feeds in `config.toml` are placeholders — replace them with real
  accounts/keywords you follow.
