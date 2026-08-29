"""Shared vault: single source of truth for every agent.

Backed by SQLite for structured state (posts, claims, sources, feedback,
briefs) plus a markdown/json export directory for human-readable briefs.
All agents read/write the same vault, so the desk stays consistent across
cycles and learns between runs.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .schema import (
    Brief,
    Claim,
    Confidence,
    Feedback,
    Post,
    SourceNode,
    SourceTier,
    utcnow,
)
from .config import Config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    post_id TEXT PRIMARY KEY,
    author TEXT,
    author_handle TEXT,
    ts TEXT,
    text TEXT,
    media TEXT,
    quoted_post_id TEXT,
    engagement INTEGER,
    language TEXT,
    raw_url TEXT,
    source_feed TEXT,
    is_repost INTEGER,
    is_quote INTEGER
);
CREATE TABLE IF NOT EXISTS sources (
    handle TEXT PRIMARY KEY,
    tier TEXT,
    trust REAL,
    confirmations INTEGER,
    misses INTEGER,
    first_seen TEXT,
    last_seen TEXT
);
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    post_id TEXT,
    text TEXT,
    said_by TEXT,
    is_primary_source INTEGER,
    has_primary_evidence INTEGER,
    is_forward_looking INTEGER,
    is_specific_fact INTEGER,
    corroborators TEXT,
    confidence TEXT,
    importance REAL,
    themes TEXT,
    verdict TEXT,
    reason TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    claim_id TEXT,
    label TEXT,
    at TEXT
);
CREATE TABLE IF NOT EXISTS briefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT,
    payload TEXT
);
CREATE TABLE IF NOT EXISTS translations (
    key TEXT,
    lang TEXT,
    value TEXT,
    PRIMARY KEY (key, lang)
);
"""


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _from_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


class Vault:
    def __init__(self, config: Config):
        self.config = config
        self.data_dir = config.data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "db" / "vault.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.briefs_dir = self.data_dir / "briefs"
        self.briefs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        # WAL lets the scheduler thread write while the webui reads, and
        # busy_timeout makes concurrent cycles/rebuilds back off rather than
        # raising "database is locked". (The desk swaps the vault on engine or
        # profile changes, so two connections can touch the same file briefly.)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        with self._lock:
            self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- post ---------------------------------------------------------------
    def _exec(self, sql: str, params=()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def _query(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, params)

    def upsert_post(self, post: Post) -> None:
        self._exec(
            """INSERT OR REPLACE INTO posts VALUES
               (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (post.post_id, post.author, post.author_handle,
             _iso(post.timestamp), post.text, json.dumps(post.media),
             post.quoted_post.post_id if post.quoted_post else None,
             post.engagement, post.language, post.raw_url,
             post.source_feed, int(post.is_repost), int(post.is_quote)))

    def post_exists(self, post_id: str) -> bool:
        cur = self._query("SELECT 1 FROM posts WHERE post_id=?", (post_id,))
        return cur.fetchone() is not None

    def recent_claim_texts(self, since_minutes: int = 120) -> list[str]:
        cur = self._query(
            "SELECT text FROM claims WHERE verdict IN ('kept','quarantined')")
        return [r[0] for r in cur.fetchall()]

    # -- sources ------------------------------------------------------------
    def get_source(self, handle: str) -> SourceNode:
        cur = self._query(
            "SELECT tier,trust,confirmations,misses,first_seen,last_seen "
            "FROM sources WHERE handle=?", (handle,))
        row = cur.fetchone()
        if row:
            return SourceNode(handle=handle, tier=SourceTier(row[0]),
                              trust=row[1], confirmations=row[2],
                              misses=row[3],
                              first_seen=_from_iso(row[4]),
                              last_seen=_from_iso(row[5]))
        now = utcnow()
        node = SourceNode(handle=handle, first_seen=now, last_seen=now)
        self.upsert_source(node)
        return node

    def upsert_source(self, node: SourceNode) -> None:
        node.last_seen = node.last_seen or utcnow()
        self._exec(
            """INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?,?)""",
            (node.handle, node.tier.value, node.trust, node.confirmations,
             node.misses, _iso(node.first_seen), _iso(node.last_seen)))

    def all_sources(self) -> list[SourceNode]:
        cur = self._query("SELECT handle,tier,trust,confirmations,"
                                 "misses,first_seen,last_seen FROM sources")
        return [SourceNode(handle=r[0], tier=SourceTier(r[1]), trust=r[2],
                           confirmations=r[3], misses=r[4],
                           first_seen=_from_iso(r[5]),
                           last_seen=_from_iso(r[6])) for r in cur.fetchall()]

    # -- claims -------------------------------------------------------------
    def upsert_claim(self, claim: Claim) -> None:
        self._exec(
            """INSERT OR REPLACE INTO claims VALUES
               (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (claim.claim_id, claim.post_id, claim.text, claim.said_by,
             int(claim.is_primary_source), int(claim.has_primary_evidence),
             int(claim.is_forward_looking), int(claim.is_specific_fact),
             json.dumps(claim.corroborators), claim.confidence.value,
             claim.importance, json.dumps(claim.themes),
             claim.verdict, claim.reason))

    def claims_by_verdict(self, verdict: str) -> list[Claim]:
        cur = self._query(
            "SELECT * FROM claims WHERE verdict=?", (verdict,))
        return [self._row_to_claim(r) for r in cur.fetchall()]

    def all_kept_and_watch(self) -> list[Claim]:
        cur = self._query(
            "SELECT * FROM claims WHERE verdict IN ('kept','quarantined')")
        return [self._row_to_claim(r) for r in cur.fetchall()]

    def pending_claims(self) -> list[Claim]:
        """Claims not yet scored by the rumor filter (verdict empty)."""
        cur = self._query(
            "SELECT * FROM claims WHERE verdict='' OR verdict IS NULL")
        return [self._row_to_claim(r) for r in cur.fetchall()]

    def all_claims(self) -> list[Claim]:
        cur = self._query("SELECT * FROM claims")
        return [self._row_to_claim(r) for r in cur.fetchall()]

    def _all_posts(self) -> list[object]:
        cur = self._query(
            "SELECT post_id,author,author_handle,ts,text,language,source_feed "
            "FROM posts")
        return cur.fetchall()

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        cur = self._query(
            "SELECT * FROM claims WHERE claim_id=?", (claim_id,))
        row = cur.fetchone()
        return self._row_to_claim(row) if row else None

    @staticmethod
    def _row_to_claim(r) -> Claim:
        return Claim(
            claim_id=r[0], post_id=r[1], text=r[2], said_by=r[3],
            is_primary_source=bool(r[4]), has_primary_evidence=bool(r[5]),
            is_forward_looking=bool(r[6]), is_specific_fact=bool(r[7]),
            corroborators=json.loads(r[8]), confidence=Confidence(r[9]),
            importance=r[10], themes=json.loads(r[11]),
            verdict=r[12], reason=r[13])

    # -- feedback -----------------------------------------------------------
    def add_feedback(self, fb: Feedback) -> None:
        self._exec("INSERT INTO feedback VALUES (?,?,?)",
                   (fb.claim_id, fb.label, _iso(fb.at)))

    def all_feedback(self) -> list[Feedback]:
        cur = self._query("SELECT claim_id,label,at FROM feedback")
        return [Feedback(claim_id=r[0], label=r[1], at=_from_iso(r[2]))
                for r in cur.fetchall()]

    # -- translations (headless i18n cache) ---------------------------------
    def get_translation(self, key: str, lang: str) -> Optional[str]:
        cur = self._query(
            "SELECT value FROM translations WHERE key=? AND lang=?",
            (key, lang))
        row = cur.fetchone()
        return row[0] if row else None

    def put_translation(self, key: str, lang: str, value: str) -> None:
        self._exec(
            "INSERT OR REPLACE INTO translations VALUES (?,?,?)",
            (key, lang, value))

    # -- briefs -------------------------------------------------------------
    def latest_brief_record(self) -> Optional[dict]:
        """Most recent brief as a plain dict (structured items, not markdown)."""
        cur = self._query(
            "SELECT payload FROM briefs ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def save_brief(self, brief: Brief) -> Path:
        self._exec("INSERT INTO briefs (generated_at,payload) VALUES (?,?)",
                   (_iso(brief.generated_at), _brief_to_json(brief)))
        path = self.briefs_dir / f"brief_{brief.generated_at:%Y%m%d_%H%M%S}.md"
        path.write_text(render_brief_markdown(brief), encoding="utf-8")
        return path

    def close(self) -> None:
        self._conn.close()


def _utc_str(dt: datetime) -> str:
    """Format a timestamp as UTC (never trust its own tzinfo label)."""
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _brief_to_json(brief: Brief) -> str:
    def item(i):
        return {"headline": i.headline, "why_it_matters": i.why_it_matters,
                "confidence": i.confidence.value, "primary_url": i.primary_url,
                "supporting_accounts": i.supporting_accounts,
                "timestamp": _iso(i.timestamp), "importance": i.importance,
                "quote": i.quote}
    return json.dumps({
        "generated_at": _iso(brief.generated_at),
        "main_brief": [item(i) for i in brief.main_brief],
        "watchlist": [item(i) for i in brief.watchlist],
        "noise_log": brief.noise_log,
    })


def render_brief_markdown(brief: Brief) -> str:
    lines = [f"# Research Desk Brief — {brief.generated_at:%Y-%m-%d %H:%M UTC}",
             ""]
    lines.append("## MAIN BRIEF — high-confidence important news")
    if not brief.main_brief:
        lines.append("_Nothing cleared the bar this cycle._")
    for i, item in enumerate(brief.main_brief, 1):
        time_str = _utc_str(item.timestamp) if item.timestamp else "n/a"
        lines += [
            f"### {i}. {item.headline}",
            f"- **Text:** {item.quote or item.headline}",
            f"- **Why it matters:** {item.why_it_matters}",
            f"- **Confidence:** {item.confidence.value}",
            f"- **Primary post:** {item.primary_url or 'n/a'}",
            f"- **Supporting accounts:** {', '.join(item.supporting_accounts) or '—'}",
            f"- **Time:** {time_str}",
            "",
        ]
    lines.append("## WATCHLIST — possibly important, unconfirmed")
    if not brief.watchlist:
        lines.append("_Nothing on watch._")
    for item in brief.watchlist:
        lines += [
            f"- **{item.headline}** — {item.why_it_matters} "
            f"[{item.confidence.value}] {item.primary_url}",
        ]
    lines.append("")
    lines.append("## NOISE LOG — why items were rejected")
    if not brief.noise_log:
        lines.append("_No items rejected._")
    for n in brief.noise_log:
        lines.append(f"- {n.get('text','?')[:120]} — {n.get('reason','?')}")
    lines.append("")
    return "\n".join(lines)
