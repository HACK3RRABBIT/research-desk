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

### Engine: heuristic by default, LLM opt-in

Every qualitative call goes through a single `Reasoning` interface
(`research_desk/reasoning.py`). Two implementations satisfy it:

- **`HeuristicReasoning`** — pure Python rules, **zero external dependencies,
  runs offline immediately**. This is the default.
- **`AnthropicReasoning`** — calls Claude for smarter extraction / filtering /
  ranking. Auto-activates when `llm.provider = "anthropic"` **and** an API key
  is present (env `ANTHROPIC_API_KEY` or `config.toml`). Falls back to
  heuristics if the call fails.

You never touch agent code to switch engines.

## Setup

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"          # add [llm] for the Claude backend
```

Copy and edit the config:

```bash
cp config.toml config.local.toml     # optional; config.toml is used by default
```

Edit `watched_users`, `watched_keywords`, `watched_lists`, `languages`,
`poll_interval`, and `rsshub_base_url` (self-host RSSHub for reliability:
https://docs.rsshub.app/). RSSHub `/twitter` routes require RSSHub's Twitter
radar access — see RSSHub docs; if a route 404s the system logs and continues.

> The X web-search route (`x_search_queries`) only runs when you export
> `X_API_BEARER="<your token>"`. Without it, the desk runs on RSSHub alone.

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

**v0.1.0 — first working version.** Ingests from RSSHub Twitter feeds (+ X
keyword search when a bearer token is set), extracts claims, filters obvious
rumors, and writes one markdown brief. Iterating from here.

## Notes & limits

- RSSHub `/twitter` routes depend on RSSHub's upstream Twitter access; a failing
  route is retried then logged — it never crashes the cycle.
- Corroboration requires two independent accounts to state the *same specific
  fact*; reworded posts do not count as independent confirmation.
- Default demo feeds in `config.toml` are placeholders — replace them with real
  accounts/keywords you follow.
