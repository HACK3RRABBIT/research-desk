"""FastAPI web server for the research desk.

Serves a Twitter/Grok-styled React dashboard and a JSON API that controls the
pipeline: run a cycle, toggle the scheduler, give feedback, manage watched
accounts/keywords, and read agents/sources/themes. The app is built into
`webui/dist` and served statically; in dev, set VITE_API_BASE to the API root.

Run:  uvicorn research_desk.server:app --host 0.0.0.0 --port 8088
"""
from __future__ import annotations

import html as _html
import json
import re
import threading
import time
from http import HTTPStatus
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Mount, Route

from .config import Config, load_config
from .desk import ResearchDesk
from .i18n import Translator
from .profile import apply_interests

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "webui" / "dist"

# One shared desk instance for the process.
_cfg = load_config()
_desk = ResearchDesk(config=_cfg)
_scheduler_thread: Optional[threading.Thread] = None
_scheduler_stop = threading.Event()
_scheduler_state = {"running": False, "last_cycle": None, "cycles": 0}
# Guards the desk so a cycle and a rebuild (engine/profile change) never touch
# the vault concurrently — that was a "database is locked" source.
_cycle_lock = threading.RLock()


def _cycle_once():
    with _cycle_lock:
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
    """Re-instantiate the desk so a fresh LLM engine (or directive) is picked up."""
    global _desk
    with _cycle_lock:
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


app = FastAPI(title="research-desk", version="0.1.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ------------------------------------------------------------------ brand / seo
# robots.txt, sitemap and webmanifest are served from code (not the static
# build) so they exist even before webui/dist is produced, and so they can't
# drift out of sync with the API. The error pages below are stamped with the
# same Hermes tokens as the SPA.

ROBOTS_TXT = "User-agent: *\nDisallow:\nSitemap: /sitemap.xml\n"

SITEMAP_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    '  <url><loc>/</loc><changefreq>hourly</changefreq></url>\n'
    "</urlset>\n"
)

SITE_MANIFEST = (
    "{"
    '"name":"Research Desk","short_name":"Research Desk",'
    '"description":"An always-on X/Twitter news intelligence desk.",'
    '"start_url":"/","scope":"/","display":"standalone",'
    '"background_color":"#0000f2","theme_color":"#0000f2",'
    '"icons":['
    '{"src":"/logo-192.png","sizes":"192x192","type":"image/png","purpose":"any"},'
    '{"src":"/logo-512.png","sizes":"512x512","type":"image/png","purpose":"any"},'
    '{"src":"/logo.svg","sizes":"any","type":"image/svg+xml"}'
    "]}"
)


# ------------------------------------------------------------- error pages
# A self-contained, JS-free Hermes-skinned error page. Rendered server-side so
# it always renders even when the SPA bundle can't load, and so API 404/5xx can
# stay JSON while browser-facing failures get the branded page.

_ERROR_CSS = """
@font-face{font-family:"Sigurd";src:url("/fonts/sigurd.woff2") format("woff2");font-weight:100 800;font-style:normal;font-display:swap}
@font-face{font-family:"CourierPrime";src:url("/fonts/courierprime.woff2") format("woff2");font-weight:400;font-style:normal;font-display:swap}
:root{--blue:#0000F2;--fg:#F5F5F5;--fg-dim:rgba(245,245,245,.62);--accent:#EDFF45;--font-display:"Sigurd","Times New Roman",serif;--font-mono:"CourierPrime","Courier New",monospace;--noise:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.72' numOctaves='4' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
*{box-sizing:border-box;margin:0}
html,body{height:100%}
body{min-height:100vh;display:grid;place-items:center;background:var(--blue);color:var(--fg);font-family:var(--font-display);font-weight:300;letter-spacing:.03em;text-transform:uppercase;-webkit-font-smoothing:antialiased;text-align:center;position:relative;overflow:hidden;padding:24px}
body::before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.05;background-image:var(--noise)}
body::after{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(120% 90% at 50% 8%,transparent 55%,rgba(0,0,0,.30))}
.card{position:relative;z-index:1;max-width:680px}
.eyebrow{font-family:var(--font-mono);font-size:12px;letter-spacing:.32em;color:var(--accent)}
.eyebrow .sep{color:var(--fg-dim)}
.num{font-size:clamp(104px,24vw,220px);font-weight:300;line-height:.86;letter-spacing:.02em;margin:.16em 0 0}
.rule{width:64px;height:3px;background:var(--accent);margin:22px auto 28px}
h1{font-size:clamp(20px,4vw,32px);font-weight:300;letter-spacing:.04em}
.msg{font-family:var(--font-mono);font-size:13px;letter-spacing:.08em;line-height:1.7;color:var(--fg-dim);max-width:520px;margin:14px auto 0}
.btn{display:inline-block;margin-top:38px;padding:16px 30px;background:var(--accent);color:#0000F2;font-family:var(--font-mono);font-size:13px;letter-spacing:.14em;text-decoration:none;box-shadow:0 4px 14px rgba(0,0,0,.25)}
.btn:hover{background:#fff}
@media (prefers-reduced-motion:no-preference){.card{animation:rise .5s ease-out}.rule{animation:grow .6s ease-out;transform-origin:center}@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}@keyframes grow{from{width:0}to{width:64px}}}
"""

# Specific, plain-voice copy per status — never vague, never apologetic.
_ERROR_COPY = {
    400: ("Bad request", "The request wasn't well-formed. Check what you sent and try again."),
    401: ("Unauthorized", "You're not signed in. Authenticate to reach this route."),
    403: ("Forbidden", "You don't have access to this route."),
    404: ("Page not found", "This URL isn't on the desk. Check the address, or return to the brief."),
    405: ("Method not allowed", "This route doesn't accept that kind of request. Use the app to act."),
    408: ("Request timeout", "The request took too long. Try again."),
    413: ("Payload too large", "That request was too big. Trim it and resend."),
    422: ("Unprocessable", "The request couldn't be processed because the input is invalid."),
    429: ("Too many requests", "The desk is busy. Ease off and retry in a moment."),
    500: ("Internal error", "Something on the desk broke. Retry; if it keeps happening, restart the server."),
    501: ("Not implemented", "This action isn't wired up yet."),
    502: ("Bad gateway", "An upstream feed or model didn't answer. The desk is retrying."),
    503: ("Service restarting", "The desk is briefly offline. Retry in a moment."),
    504: ("Gateway timeout", "An upstream feed or model took too long. The scheduler will retry."),
}


def _error_html(status: int, title: str, message: str) -> str:
    t = _html.escape(title)
    m = _html.escape(message)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0000f2">
<title>{status} · {t} · Research Desk</title>
<style>{_ERROR_CSS}</style>
</head>
<body>
  <div class="card">
    <div class="eyebrow">Research<span class="sep">—</span>Desk <span class="sep">·</span> Signal</div>
    <div class="num">{status}</div>
    <div class="rule"></div>
    <h1>{t}</h1>
    <p class="msg">{m}</p>
    <a class="btn" href="/">Return to the desk</a>
  </div>
</body>
</html>"""


def _error_payload(status: int):
    title, message = _ERROR_COPY.get(status, (None, None))
    if title is None:
        try:
            title = HTTPStatus(status).phrase or "Error"
        except ValueError:
            title = "Error"
        message = "The desk can't complete this request."
    return title, message


@app.exception_handler(StarletteHTTPException)
async def _http_exception(request: Request, exc: StarletteHTTPException):
    """Branded error page for browser hits, JSON for API hits (404/405/5xx…)."""
    status = exc.status_code
    if request.url.path.startswith("/api"):
        return JSONResponse(
            {"error": str(exc.detail), "status": status}, status_code=status)
    title, message = _error_payload(status)
    return HTMLResponse(_error_html(status, title, message), status_code=status)


@app.exception_handler(RequestValidationError)
async def _validation_exception(request: Request, exc: RequestValidationError):
    status = 422
    if request.url.path.startswith("/api"):
        return JSONResponse(
            {"error": "Unprocessable entity", "detail": exc.errors(),
             "status": status}, status_code=status)
    title, message = _error_payload(status)
    return HTMLResponse(_error_html(status, title, message), status_code=status)


@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception):
    status = 500
    if request.url.path.startswith("/api"):
        return JSONResponse(
            {"error": "Internal server error", "status": status},
            status_code=status)
    title, message = _error_payload(status)
    return HTMLResponse(_error_html(status, title, message), status_code=status)


@app.api_route("/robots.txt", methods=["GET", "HEAD"], include_in_schema=False)
def robots_txt():
    return Response(content=ROBOTS_TXT, media_type="text/plain")


@app.api_route("/sitemap.xml", methods=["GET", "HEAD"], include_in_schema=False)
def sitemap_xml():
    return Response(content=SITEMAP_XML, media_type="application/xml")


@app.api_route("/site.webmanifest", methods=["GET", "HEAD"], include_in_schema=False)
def site_manifest():
    return Response(content=SITE_MANIFEST, media_type="application/manifest+json")


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


class ProfileReq(BaseModel):
    """User profile updates. `None` means "leave unchanged"."""
    language: Optional[str] = None
    theme: Optional[str] = None
    timezone: Optional[str] = None
    interests: Optional[list[str]] = None
    user_instructions: Optional[str] = None
    interests_complete: Optional[bool] = None


class TranslateReq(BaseModel):
    texts: list[str]
    lang: str = "en"


# --------------------------------------------------------------------- helpers
def _profile_payload():
    p = _cfg.profile
    return {
        "language": p.get("language", "en"),
        "theme": p.get("theme", "hermes"),
        "timezone": p.get("timezone", "Etc/UTC"),
        "interests": p.get("interests", []),
        "user_instructions": p.get("user_instructions", ""),
        "has_instructions": bool((p.get("user_instructions") or "").strip()),
        "interests_complete": bool(p.get("interests_complete")),
    }


def _t_item(d: dict, tx):
    """Structured brief item, with text fields machine-translated when `tx`."""
    return {
        "headline": tx(d.get("headline", "")) if tx else d.get("headline", ""),
        "quote": tx(d.get("quote") or d.get("headline", "")) if tx
                 else (d.get("quote") or d.get("headline", "") or ""),
        "why": tx(d.get("why_it_matters", "")) if tx
               else d.get("why_it_matters", ""),
        "why_it_matters": tx(d.get("why_it_matters", "")) if tx
                          else d.get("why_it_matters", ""),
        "confidence": d.get("confidence", "unconfirmed"),
        "url": d.get("primary_url", ""),
        "support": d.get("supporting_accounts", []),
        "ts": d.get("timestamp", ""),   # ISO; the UI formats it in the user's tz
    }


def _brief_payload(lang: str = "en"):
    md = _desk.latest_brief()
    record = _desk.vault.latest_brief_record()
    generated_at = record.get("generated_at") if record else None
    if not record:
        items = {"main": [], "watch": [], "noise": []}
    else:
        translator = Translator(_desk.vault) if lang not in ("", "en") else None
        tx = (lambda s: translator.one(s, lang)) if translator else None
        items = {
            "main": [_t_item(i, tx) for i in record.get("main_brief", [])],
            "watch": [_t_item(i, tx) for i in record.get("watchlist", [])],
            "noise": [{
                "text": (tx(n.get("text", "")) if tx else n.get("text", "")),
                "reason": (tx(n.get("reason", "")) if tx
                           else n.get("reason", "")),
            } for n in record.get("noise_log", [])],
        }
    return {
        "markdown": md,
        "generated_at": generated_at,
        "items": items,
        "lang": lang,
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
def get_state(lang: str = Query(default="en")):
    # Hold the desk lock the whole read so an in-flight cycle/rebuild can't
    # close the vault underneath us ("Cannot operate on a closed database").
    with _cycle_lock:
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
            "brief": _brief_payload(lang),
            "llm": _llm_payload(),
            "discovery": _discovery_payload(),
            "profile": _profile_payload(),
        }


@app.post("/api/run")
def run_cycle():
    with _cycle_lock:
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
    with _cycle_lock:
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
                      "max_tokens": req.max_tokens, "temperature": 0.0,
                      "stream": False},
                timeout=req.timeout)
            r.raise_for_status()
            # Some OpenAI-compatible proxies stream by default (SSE) even when
            # asked not to, so parse both shapes. (Logic mirrors reasoning.py.)
            ctype = (r.headers.get("content-type") or "").lower()
            if "text/event-stream" in ctype:
                parts, found = [], False
                for line in (r.text or "").splitlines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        continue
                    try:
                        obj = json.loads(payload)
                    except Exception:
                        continue
                    for ch in obj.get("choices", []):
                        d = ch.get("delta") or {}
                        if d.get("content"):
                            parts.append(d["content"])
                body = {"choices": [{"message": {"content": "".join(parts)}}]} \
                    if parts else {}
            else:
                body = r.json()
            if "choices" not in body:
                return {"ok": False, "message": "Unexpected response shape."}
            # The model may wrap the answer in prose or leave `content` empty
            # (reasoning-heavy proxies). Harvest a JSON/text block and also
            # accept a bare "OK" reply so the connectivity check still passes.
            msg_obj = body["choices"][0]["message"]
            msg = (msg_obj.get("content") or "").strip()
            if not msg:
                msg = (msg_obj.get("reasoning_content")
                       or msg_obj.get("reasoning") or "").strip()
            # Strip a markdown code fence if the model added one.
            fenced = re.search(r"```(?:json)?\s*(.*?)```", msg, re.S)
            if fenced:
                msg = fenced.group(1).strip()
            msg = msg.strip() or "(empty reply)"
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


@app.post("/api/profile")
def save_profile(req: ProfileReq):
    """Save user profile (language/theme/timezone/interests/instructions).

    Applying interests also merges the tags into boost_themes and (for a few
    high-signal ones) watched keywords, and marks onboarding complete.
    """
    if req.interests is not None:
        apply_interests(_cfg, req.interests)
    if req.user_instructions is not None:
        _cfg.set_profile(user_instructions=req.user_instructions.strip())
    if req.language is not None:
        _cfg.set_profile(language=req.language)
    if req.theme is not None:
        _cfg.set_profile(theme=req.theme)
    if req.timezone is not None:
        _cfg.set_profile(timezone=req.timezone)
    if req.interests_complete is not None:
        _cfg.set_profile(interests_complete=req.interests_complete)
    _cfg.save()
    # The directive feeds the reasoning SYSTEM, so pick up a fresh engine.
    _rebuild_desk()
    return {"ok": True, "profile": _profile_payload()}


@app.post("/api/translate")
def translate(req: TranslateReq):
    """Batch-translate strings via the headless free endpoint (cached)."""
    with _cycle_lock:
        translator = Translator(_desk.vault)
        return {"ok": True, "translations": translator.translate(req.texts, req.lang)}

# --------------------------------------------------------------------- static
def _allowed_methods(path: str) -> set[str]:
    """Allowed HTTP verbs for a matched route, ignoring the api catch-all and
    the static mount — lets us report a genuine 405 instead of a swallowed 404."""
    allowed: set[str] = set()
    for route in app.routes:
        if getattr(route, "path", None) == "/api/{path:path}":
            continue
        if isinstance(route, Mount):
            continue
        if not isinstance(route, Route):
            continue
        path_re = getattr(route, "path_regex", None)
        if path_re is not None and path_re.match(path):
            methods = getattr(route, "methods", None)
            if methods:
                allowed |= set(methods)
    return allowed


# Any /api path the specific routes didn't fully match lands here. Registered
# BEFORE the static mount so the mount can't shadow it with a 404, giving
# correct 404 (unknown) and 405 (wrong method) JSON for API clients.
@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def _api_catchall(request: Request):
    allowed = _allowed_methods(request.url.path)
    if request.method in allowed:
        return JSONResponse({"error": "Not Found", "status": 404}, status_code=404)
    if allowed:
        return JSONResponse(
            {"error": "Method Not Allowed", "status": 405}, status_code=405,
            headers={"Allow": ", ".join(sorted(allowed))})
    return JSONResponse({"error": "Not Found", "status": 404}, status_code=404)


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
