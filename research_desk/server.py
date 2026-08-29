"""FastAPI web server for the research desk.

Serves a Twitter/Grok-styled React dashboard and a JSON API that controls the
pipeline: run a cycle, toggle the scheduler, give feedback, manage watched
accounts/keywords, and read agents/sources/themes. The app is built into
`webui/dist` and served statically; in dev, set VITE_API_BASE to the API root.

Run:  uvicorn research_desk.server:app --host 0.0.0.0 --port 8088
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Config, load_config
from .desk import ResearchDesk

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "webui" / "dist"

# One shared desk instance for the process.
_cfg = load_config()
_desk = ResearchDesk(config=_cfg)
_scheduler_thread: Optional[threading.Thread] = None
_scheduler_stop = threading.Event()
_scheduler_state = {"running": False, "last_cycle": None, "cycles": 0}


def _cycle_once():
    _desk.cycle()
    _scheduler_state["last_cycle"] = time.time()
    _scheduler_state["cycles"] += 1


def _scheduler_loop(interval: int):
    while not _scheduler_stop.wait(interval):
        try:
            _cycle_once()
        except Exception as exc:  # never let the loop die
            print(f"[scheduler] cycle error: {exc}")


def _start_scheduler(interval: int | None = None):
    global _scheduler_thread
    if _scheduler_state["running"]:
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(max(30, interval or _cfg.poll_interval),), daemon=True)
    _scheduler_thread.start()
    _scheduler_state["running"] = True


def _rebuild_desk():
    """Re-instantiate the desk so a fresh LLM engine is picked up."""
    global _desk
    try:
        _desk.close()
    except Exception:
        pass
    _desk = ResearchDesk(config=_cfg)


def _llm_payload():
    """Masked view of the engine for the UI — the raw key is never sent."""
    key = _cfg.llm_key()
    return {
        "provider": _cfg.llm_provider,
        "base_url": _cfg.llm.get("base_url", ""),
        "model": _cfg.llm.get("model", ""),
        "has_key": bool(key),
        "key_hint": ("…" + key[-4:]) if key else "",
        "needs_setup": _cfg.needs_setup(),
        "ready": _cfg.has_llm(),
    }


def _discovery_payload():
    return {"enabled": _cfg.discovery.get("enabled", True),
            "max_per_cycle": _cfg.discovery.get("max_per_cycle", 5),
            "max_total": _cfg.discovery.get("max_total", 50),
            "discovered": _cfg.discovered_users()}


app = FastAPI(title="research-desk", version="0.1.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# --------------------------------------------------------------------- schemas
class FeedbackReq(BaseModel):
    claim_id: str
    label: str


class WatchReq(BaseModel):
    handle: str


class KeywordReq(BaseModel):
    keyword: str


class EngineReq(BaseModel):
    """LLM engine configuration. `None` means "leave unchanged"; an empty string
    for api_key explicitly clears it (so the UI can keep or wipe the key)."""
    provider: str = "openai"
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[int] = None


class EngineTestReq(BaseModel):
    """Candidate config to test in place, before it is saved."""
    provider: str = "openai"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    max_tokens: int = 32
    timeout: int = 30


# --------------------------------------------------------------------- helpers
def _brief_payload():
    brief = _desk.latest_brief()
    # Re-open latest brief file as structured data.
    briefs = sorted(_desk.vault.briefs_dir.glob("brief_*.md"))
    return {
        "markdown": brief,
        "generated_at": briefs[-1].stem.replace("brief_", "") if briefs else None,
    }


def _agents_payload():
    return [
        {"name": "INTAKE", "desc": "Pull & normalize posts from RSSHub + X search"},
        {"name": "SOURCE MAPPER", "desc": "Living source graph & trust tiers"},
        {"name": "CLAIM EXTRACTOR", "desc": "Atomic claims per post"},
        {"name": "RUMOR FILTER", "desc": "Score, drop & quarantine"},
        {"name": "IMPORTANCE RANKER", "desc": "Rank by impact & preference"},
        {"name": "CHIEF OF STAFF", "desc": "Brief: main / watch / noise"},
        {"name": "LEARNING LOOP", "desc": "Feedback -> trust & themes"},
    ]


def _sources_payload():
    return [
        {"handle": s.handle, "tier": s.tier.value, "trust": round(s.trust, 3),
         "confirmations": s.confirmations, "misses": s.misses}
        for s in sorted(_desk.vault.all_sources(),
                        key=lambda x: x.trust, reverse=True)
    ]


def _themes_payload():
    prefs = _desk.config.preferences
    return {"boost": prefs.get("boost_themes", []),
            "ignore": prefs.get("ignore_themes", [])}


def _stats_payload():
    return {
        "posts": len(_desk.vault._all_posts()),
        "claims": len(_desk.vault.all_claims()),
        "sources": len(_desk.vault.all_sources()),
        "feedback": len(_desk.vault.all_feedback()),
    }


# --------------------------------------------------------------------- routes
@app.get("/api/state")
def get_state():
    return {
        "engine": _desk.engine,
        "scheduler": _scheduler_state,
        "config": {
            "rsshub_base_url": _desk.config.rsshub_base_url,
            "poll_interval": _desk.config.poll_interval,
            "languages": _desk.config.languages,
            "watched_users": _desk.config.watched_users,
            "watched_keywords": _desk.config.watched_keywords,
        },
        "agents": _agents_payload(),
        "sources": _sources_payload(),
        "themes": _themes_payload(),
        "stats": _stats_payload(),
        "brief": _brief_payload(),
        "llm": _llm_payload(),
        "discovery": _discovery_payload(),
    }


@app.post("/api/run")
def run_cycle():
    _cycle_once()
    return {"ok": True, "state": _scheduler_state, "brief": _brief_payload()}


@app.post("/api/scheduler/start")
def scheduler_start(interval: int = Query(default=_cfg.poll_interval)):
    _start_scheduler(interval)
    return {"ok": True, "running": _scheduler_state["running"]}


@app.post("/api/scheduler/stop")
def scheduler_stop():
    _scheduler_stop.set()
    _scheduler_state["running"] = False
    return {"ok": True, "running": False}


@app.post("/api/feedback")
def post_feedback(req: FeedbackReq):
    if req.label not in {"useful", "not_useful", "rumor", "too_local",
                          "too_political", "want_more"}:
        raise HTTPException(400, "invalid label")
    _desk.feedback(req.claim_id, req.label)
    return {"ok": True}


@app.post("/api/watch")
def add_watch(req: WatchReq):
    _desk.config.add_watched_user(req.handle.strip().lstrip("@"))
    return {"ok": True, "watched_users": _desk.config.watched_users}


@app.post("/api/keyword")
def add_keyword(req: KeywordReq):
    _desk.config.add_keyword(req.keyword.strip())
    return {"ok": True, "watched_keywords": _desk.config.watched_keywords}


@app.delete("/api/watch/{handle}")
def remove_watch(handle: str):
    users = _desk.config.raw["watched_users"]
    if handle in users:
        users.remove(handle)
    return {"ok": True, "watched_users": users}


@app.delete("/api/keyword/{keyword}")
def remove_keyword(keyword: str):
    kws = _desk.config.raw["watched_keywords"]
    if keyword in kws:
        kws.remove(keyword)
    return {"ok": True, "watched_keywords": kws}


@app.get("/api/briefs")
def list_briefs():
    out = []
    for b in sorted(_desk.vault.briefs_dir.glob("brief_*.md")):
        out.append({"id": b.stem.replace("brief_", ""),
                    "path": str(b.relative_to(ROOT))})
    return {"briefs": list(reversed(out))}


@app.post("/api/engine")
def set_engine(req: EngineReq):
    """Save the LLM engine config and rebuild the desk to use it."""
    _cfg.set_llm(
        provider=req.provider,
        base_url=(req.base_url or "").rstrip() if req.base_url is not None else None,
        model=req.model.strip() if isinstance(req.model, str) else req.model,
        api_key=req.api_key,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        timeout=req.timeout,
    )
    _cfg.save()
    _rebuild_desk()
    # Always-on: once the engine is ready, start polling if autostart is on.
    if _cfg.has_llm() and _cfg.scheduler.get("autostart", True):
        _start_scheduler(_cfg.poll_interval)
    return {"ok": True, "llm": _llm_payload()}


@app.post("/api/engine/reset")
def reset_engine():
    """Return to the offline heuristic (troubleshooting)."""
    _cfg.set_llm(provider="heuristic", base_url="", model="", api_key="")
    _cfg.save()
    _rebuild_desk()
    return {"ok": True, "llm": _llm_payload()}


@app.post("/api/engine/test")
def test_engine(req: EngineTestReq):
    """Probe the candidate provider in place, before saving."""
    try:
        if req.provider == "openai":
            import requests
            headers = {"Content-Type": "application/json"}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"
            r = requests.post(
                f"{req.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json={"model": req.model,
                      "messages": [{"role": "user",
                                    "content": "Reply with exactly: OK"}],
                      "max_tokens": req.max_tokens, "temperature": 0.0},
                timeout=req.timeout)
            r.raise_for_status()
            body = r.json()
            if "choices" not in body:
                return {"ok": False, "message": "Unexpected response shape."}
            msg = body["choices"][0]["message"]["content"].strip()
            return {"ok": True, "message": f"Connected — model replied “{msg[:60]}”"}
        elif req.provider == "anthropic":
            import anthropic
            c = anthropic.Anthropic(api_key=req.api_key)
            m = c.messages.create(
                model=req.model or "claude-haiku-4-5-20251001",
                max_tokens=req.max_tokens,
                messages=[{"role": "user", "content": "Reply with exactly: OK"}])
            msg = "".join(b.text for b in m.content if b.type == "text").strip()
            return {"ok": True, "message": f"Connected — model replied “{msg[:60]}”"}
        else:
            return {"ok": True, "message": "Heuristic engine is always available."}
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI as the message
        return {"ok": False, "message": str(exc)}


# --------------------------------------------------------------------- static
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="ui")
else:
    @app.get("/")
    def index_dev():
        return {"status": "research-desk api", "webui_dist": False,
                "note": "run `npm run build` in webui/ to enable the dashboard"}


def _close():
    _scheduler_stop.set()
    try:
        _desk.close()
    except Exception:
        pass


import atexit
atexit.register(_close)

# Always-on: if the engine is configured and autostart is enabled, begin polling
# immediately. When the engine needs setup, the webui gates on `/api/state`.
if _cfg.has_llm() and _cfg.scheduler.get("autostart", True):
    _start_scheduler(_cfg.poll_interval)
