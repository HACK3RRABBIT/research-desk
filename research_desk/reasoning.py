"""Judgement engine.

This is the single seam between *rules* and *models*. Every agent that has to
make a qualitative call (extract claims, decide if something is a rumor, rank
importance) delegates to a Reasoning instance instead of hard-coding logic.

Two implementations satisfy the same interface:
  * HeuristicReasoning  -- pure Python, zero network, always available
  * AnthropicReasoning -- calls Claude when an API key is configured

get_reasoning(config) returns whichever is appropriate. Agents never import a
concrete class, so the rest of the pipeline is model-agnostic.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from typing import Optional

from .config import Config
from .schema import (
    Claim,
    Confidence,
    Post,
    SourceNode,
    SourceTier,
    utcnow,
)

# ---------------------------------------------------------------- heuristics
_PRIMARY_EVIDENCE = re.compile(
    r"\b(official|statement|press release|document|fil[ei]d|announce|"
    r"photo|video|footage|transcript|legal|court|verdict|order|"
    r"confirmed by|first.?hand|primary)\b", re.I)
_TEASER = re.compile(
    r"\b(huge|major|breaking|big|insane|unbelievable|you won'?t believe|"
    r"incoming|dropping (soon|later|tonight)|stay tuned|announcement"
    r" (coming|incoming)|something (big|huge) (is )?(coming|about to))\b", re.I)
_RUMOR = re.compile(
    r"\b(sources say|reportedly|rumor|rumour|allegedly|unconfirmed|"
    r"i'?ve heard|word is|apparently|leaked|whispers|chatter)\b", re.I)
_SPECIFIC = re.compile(r"\b\d{1,3}([.,]\d+)?\s?(%|billion|million|k|m|trillion|"
                       r"\$|bbl|barrels|mt|tons)|jan|feb|mar|apr|may|jun|jul|"
                       r"aug|sep|oct|nov|dec|20\d\d|@\w+|http", re.I)
_SCREENSHOT_ONLY = re.compile(r"\b(screenshot|screen shot|pic\.twitter|"
                              r"image attached|see (the )?image)\b", re.I)

_PRIMARY_TIERS = {SourceTier.OFFICIAL_GOV, SourceTier.OFFICIAL_COMPANY,
                  SourceTier.PRIMARY_JOURNALIST}
_HIGH_TRUST_TIERS = _PRIMARY_TIERS | {SourceTier.SUBJECT_EXPERT}

_BOOST_THEMES = ["energy", "oil", "gas", "sanctions", "shipping", "markets",
                 "ai", "x ", "tech", "geopolit", "iran", "policy", "security",
                 "official announcement", "government", "military", "economy"]
_IGNORE_THEMES = ["celebrity", "sports", "gossip", "drama", "teaser marketing"]


def _theme_hits(text: str, themes: list[str]) -> list[str]:
    low = text.lower()
    return [t for t in themes if t in low]


# Some OpenAI-compatible proxies (esp. free "deep-think" gateways) spend the
# token budget on chain-of-thought (reasoning_content) and only emit an answer
# inside it, leaving `content` empty when max_tokens is small. We harvest a
# JSON object from whichever field actually carries it.
def _extract_json_text(msg: dict) -> str:
    """Return JSON-bearing text from a message, tolerant of surrounding prose,
    markdown code fences, and reasoning-heavy proxies that leave `content`
    empty. Returns the first balanced `{...}` (or `[...]`) block."""
    raw = (msg.get("content") or "").strip()
    if not raw:
        raw = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
    if not raw:
        return ""
    # Strip a markdown code fence if present.
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    if fenced:
        raw = fenced.group(1).strip()
    # Find the outermost balanced JSON object (or array).
    return _first_json_block(raw)


def _first_json_block(text: str):
    """Extract the first balanced `{...}` or `[...]` substring from `text`."""
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return ""


def _parse_completion(resp) -> dict:
    """Turn a chat/completions response into a JSON dict, tolerating both the
    normal JSON body and an SSE stream (some OpenAI-compatible proxies stream
    by default and ignore ``stream: false``)."""
    ctype = (resp.headers.get("content-type") or "").lower()
    if "text/event-stream" not in ctype:
        try:
            return resp.json()
        except Exception:
            pass
    # SSE fallback: accumulate delta.content from each `data:` chunk.
    parts: list[str] = []
    for line in (resp.text or "").splitlines():
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
    return {"choices": [{"message": {"content": "".join(parts)}}]} if parts else {}


class Reasoning(ABC):
    engine: str = "base"

    @abstractmethod
    def extract_claims(self, post: Post, source: SourceNode) -> list[Claim]:
        ...

    @abstractmethod
    def evaluate_claim(self, claim: Claim, source: SourceNode,
                       independent_corroborators: list[str]) -> Claim:
        """Fill in verdict / confidence / importance / themes / reason."""
        ...

    @abstractmethod
    def rank_importance(self, claims: list[Claim]) -> list[Claim]:
        ...


class HeuristicReasoning(Reasoning):
    engine = "heuristic"

    def __init__(self, config: Config):
        self.prefs = config.preferences
        self.boost = self.prefs.get("boost_themes", _BOOST_THEMES)
        self.ignore = self.prefs.get("ignore_themes", _IGNORE_THEMES)
        self.min_importance = float(self.prefs.get("min_importance", 0.0))
        # allow config to override theme lists
        self._boost = list(set(self.boost)) if self.boost else _BOOST_THEMES
        self._ignore = list(set(self.ignore)) if self.ignore else _IGNORE_THEMES

    # -- claim extraction --------------------------------------------------
    def extract_claims(self, post: Post, source: SourceNode) -> list[Claim]:
        text = (post.text or "").strip()
        if not text:
            return []
        # News RSS items are published articles, not X chatter: a posted article
        # is inherently primary, evidence-backed, and a specific fact. The
        # X-tuned signals below would otherwise quarantine every news item.
        is_news = (post.source_feed or "").startswith("news:")
        cid = f"{post.post_id}:claim0"
        claim = Claim(
            claim_id=cid,
            post_id=post.post_id,
            text=text,
            said_by=source.handle,
            is_primary_source=(source.tier in _PRIMARY_TIERS) or is_news,
            has_primary_evidence=bool(_PRIMARY_EVIDENCE.search(text)
                                      or post.media or is_news),
            is_forward_looking=bool(_TEASER.search(text)),
            is_specific_fact=bool(_SPECIFIC.search(text)) or is_news,
            themes=_theme_hits(text, self._boost + self._ignore),
        )
        return [claim]

    # -- evaluation / rumor filter ----------------------------------------
    def evaluate_claim(self, claim: Claim, source: SourceNode,
                       independent_corroborators: list[str]) -> Claim:
        corrob = [c for c in independent_corroborators if c != claim.said_by]
        n_corr = len(corrob)
        claim.corroborators = corrob

        primary = claim.is_primary_source
        evidence = claim.has_primary_evidence
        specific = claim.is_specific_fact
        teaser = claim.is_forward_looking
        screenshot_only = bool(_SCREENSHOT_ONLY.search(claim.text)
                                and not primary
                                and not _PRIMARY_EVIDENCE.search(claim.text))

        # ---- rumor filter: hard drops -----------------------------------
        if teaser and not (primary or evidence):
            claim.verdict = "dropped"
            claim.reason = "Teaser/'incoming' post with no primary evidence."
            claim.confidence = Confidence.UNCONFIRMED
            claim.importance = 0.0
            return claim

        if screenshot_only and not primary:
            claim.verdict = "dropped"
            claim.reason = "Screenshot-only claim with no first-party post."
            claim.confidence = Confidence.UNCONFIRMED
            claim.importance = 0.0
            return claim

        if _RUMOR.search(claim.text) and not (primary or evidence
                                              or n_corr >= 2):
            claim.verdict = "quarantined"
            claim.reason = ("Anonymous/'sources say' claim lacking primary "
                            "evidence or 2+ corroborators.")
            claim.confidence = Confidence.UNCONFIRMED
            return claim

        if not specific and not primary:
            claim.verdict = "quarantined"
            claim.reason = "Vague claim, not a specific checkable fact."
            claim.confidence = Confidence.UNCONFIRMED
            return claim

        # ---- confidence --------------------------------------------------
        if primary and (n_corr >= 2 or evidence):
            claim.confidence = Confidence.CONFIRMED
        elif primary or n_corr >= 2:
            claim.confidence = Confidence.LIKELY
        else:
            claim.confidence = Confidence.UNCONFIRMED

        # ---- importance --------------------------------------------------
        importance = 0.0
        if any(t in self._boost for t in claim.themes):
            importance += 0.45
        elif any(t in self._ignore for t in claim.themes):
            importance -= 0.4
        importance += 0.30 * source.trust
        importance += 0.05 * min(n_corr, 4)
        if primary:
            importance += 0.15
        if evidence:
            importance += 0.10
        if claim.confidence == Confidence.CONFIRMED:
            importance += 0.10
        importance = max(0.0, min(1.0, importance))

        claim.importance = round(importance, 3)
        claim.reason = (f"primary={primary} corrob={n_corr} evidence={evidence} "
                        f"trust={source.trust:.2f}")

        # ---- verdict -----------------------------------------------------
        if claim.confidence == Confidence.CONFIRMED and importance >= 0.5:
            claim.verdict = "kept"
        elif claim.confidence == Confidence.UNCONFIRMED and importance >= 0.4:
            claim.verdict = "quarantined"   # -> watchlist
        else:
            claim.verdict = "kept" if importance >= self.min_importance else "dropped"
        return claim

    # -- ranking ----------------------------------------------------------
    def rank_importance(self, claims: list[Claim]) -> list[Claim]:
        return sorted(claims, key=lambda c: c.importance, reverse=True)


# --------------------------------------------------------------------- LLM
class LLMReasoning(Reasoning):
    """Shared judgement core for any model-backed backend.

    Holds the prompt strategy, the system message, and the mapping of model
    JSON back onto the Claim schema. Subclasses implement only ``_ask`` (the
    transport) and ``engine``. Any parse/transport failure falls back to the
    offline heuristic, so a flaky connection never kills the desk.
    """

    SYSTEM = (
        "You are the judgement core of a real-time X/Twitter news desk. You "
        "extract atomic claims from posts, decide whether each is a verified "
        "fact or an unverified rumor, and rank real-world importance. You are "
        "strict: drop teaser/'incoming' posts, anonymous source piles, "
        "screenshot-only claims, and vague non-checkable statements.\n"
        "Judge importance by the real-world impact and verifiability of the "
        "FACT itself. NEVER weight an account's follower count, verification "
        "badge ('blue tick'), celebrity, or fame — a famous account can spread "
        "gossip and a small account can break real news. Favor first-party "
        "official statements and facts that move money/policy/security/energy/"
        "tech/geopolitics, plus primary evidence (official docs, video, legal "
        "text). Respond ONLY with valid JSON matching the requested schema."
    )

    def __init__(self, config: Config):
        self.config = config
        self.heuristic = HeuristicReasoning(config)  # fallback on any error
        # Personalise the judgment core with the user's manual directive so the
        # model biases toward what this user cares about (see profile).
        self.SYSTEM = self._system_message(config)

    @staticmethod
    def _system_message(config: Config) -> str:
        base = LLMReasoning.SYSTEM
        directive = (config.profile.get("user_instructions") or "").strip()
        if not directive:
            return base
        return (
            base
            + "\n\n"
            + "The user set a personal directive. Bias your judgment toward "
            + "the subjects and sources this user cares about; still keep the "
            + "rules above (no rumors, no fame-weighting).\n"
            + "DIRECTIVE: " + directive
        )

    @abstractmethod
    def _ask(self, user_prompt: str) -> Optional[dict]:
        ...

    # -- shared claim mapping ---------------------------------------------
    def extract_claims(self, post: Post, source: SourceNode) -> list[Claim]:
        prompt = (
            "Extract atomic, independently-checkable claims from this post.\n"
            f"author={source.handle} tier={source.tier.value} trust={source.trust:.2f}\n"
            f"text={post.text!r}\nhas_media={bool(post.media)}\n"
            "Return JSON: {\"claims\":[{\"text\":str,\"is_primary_source\":bool,"
            "\"has_primary_evidence\":bool,\"is_forward_looking\":bool,"
            "\"is_specific_fact\":bool,\"themes\":[str]}]}"
        )
        data = self._ask(prompt)
        if not data:
            return self.heuristic.extract_claims(post, source)
        out = []
        for i, c in enumerate(data.get("claims", [])):
            out.append(Claim(
                claim_id=f"{post.post_id}:claim{i}",
                post_id=post.post_id,
                text=c.get("text", post.text),
                said_by=source.handle,
                is_primary_source=bool(c.get("is_primary_source", False)),
                has_primary_evidence=bool(c.get("has_primary_evidence", False)),
                is_forward_looking=bool(c.get("is_forward_looking", False)),
                is_specific_fact=bool(c.get("is_specific_fact", True)),
                themes=c.get("themes", []),
            ))
        return out or self.heuristic.extract_claims(post, source)

    def evaluate_claim(self, claim: Claim, source: SourceNode,
                       independent_corroborators: list[str]) -> Claim:
        prompt = (
            "Evaluate this claim. Independent corroborators (other handles "
            "who stated the same fact): "
            f"{independent_corroborators or 'none'}.\n"
            f"claim={claim.text!r}\nsource_tier={source.tier.value} "
            f"trust={source.trust:.2f}\n"
            f"is_primary_source={claim.is_primary_source} "
            f"has_primary_evidence={claim.has_primary_evidence} "
            f"is_forward_looking={claim.is_forward_looking} "
            f"is_specific_fact={claim.is_specific_fact}\n"
            "Return JSON: {\"verdict\":'kept'|'quarantined'|'dropped',"
            "\"confidence\":'confirmed'|'likely'|'unconfirmed',"
            "\"importance\":0.0-1.0,\"reason\":str}"
        )
        data = self._ask(prompt)
        if not data:
            return self.heuristic.evaluate_claim(claim, source,
                                                independent_corroborators)
        conf = data.get("confidence", "unconfirmed")
        claim.confidence = (Confidence(conf)
                            if conf in Confidence._value2member_map_
                            else Confidence.UNCONFIRMED)
        claim.verdict = data.get("verdict", "kept")
        claim.importance = max(
            0.0, min(1.0, float(data.get("importance", 0.0))))
        claim.reason = data.get("reason", "")
        claim.corroborators = [c for c in independent_corroborators
                               if c != claim.said_by]
        return claim

    def rank_importance(self, claims: list[Claim]) -> list[Claim]:
        return self.heuristic.rank_importance(claims)


class OpenAICompatibleReasoning(LLMReasoning):
    """Any OpenAI-chat-completions endpoint: OpenAI, OpenRouter, vLLM, LM Studio,
    Ollama, etc. Uses plain `requests` (a hard dependency) so no extra package is
    needed. Key is optional — keyless local servers work too."""

    engine = "openai"

    def _ask(self, user_prompt: str) -> Optional[dict]:
        try:
            import requests  # hard dependency
            base = self.config.llm.get("base_url", "").rstrip("/")
            model = self.config.llm.get("model", "")
            key = self.config.llm_key()
            headers = {"Content-Type": "application/json"}
            if key:
                headers["Authorization"] = f"Bearer {key}"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": self.SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": float(self.config.llm.get("temperature", 0.0)),
                "max_tokens": int(self.config.llm.get("max_tokens", 1024)),
                # Ask for a single JSON response. Some proxies still stream, so
                # _parse_completion tolerates SSE as well (see above).
                "stream": False,
            }
            resp = requests.post(
                f"{base}/chat/completions", headers=headers, json=payload,
                timeout=float(self.config.llm.get("timeout", 60)))
            resp.raise_for_status()
            data = _parse_completion(resp)
            msg = data["choices"][0]["message"]
            # `content` may be empty on reasoning-heavy proxies; fall back to
            # scraping a JSON block out of reasoning_content (see _extract_json_text).
            text = _extract_json_text(msg)
            if not text:
                return None
            return json.loads(text)
        except Exception as exc:  # pragma: no cover - network/parse
            print(f"[reasoning] OpenAI-compatible call failed, using heuristic: "
                  f"{exc}")
            return None


class AnthropicReasoning(LLMReasoning):
    engine = "anthropic"

    def __init__(self, config: Config):
        super().__init__(config)
        try:
            import anthropic  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "anthropic package not installed; run `pip install anthropic` "
                "or remove ANTHROPIC_API_KEY") from exc
        self._client = None  # lazy

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.config.llm_key())
        return self._client

    def _ask(self, user_prompt: str) -> Optional[dict]:
        try:
            resp = self.client.messages.create(
                model=self.config.llm.get("model", "claude-haiku-4-5-20251001"),
                max_tokens=int(self.config.llm.get("max_tokens", 1024)),
                temperature=float(self.config.llm.get("temperature", 0.0)),
                system=self.SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text")
            return json.loads(text)
        except Exception as exc:  # pragma: no cover - network/parse
            print(f"[reasoning] LLM call failed, using heuristic: {exc}")
            return None


def get_reasoning(config: Config) -> Reasoning:
    """Pick the engine: openai-compatible, anthropic, or the offline heuristic.

    The desk is always-on by design. When an LLM backend is configured but
    momentarily unavailable (bad key, no network), `_ask` already downgraded to
    the heuristic for the API call rather than crashing; here we only guard
    against a backend that cannot even be constructed (e.g. missing package).
    """
    provider = config.llm_provider
    if provider == "openai" and config.has_llm():
        try:
            return OpenAICompatibleReasoning(config)
        except RuntimeError as exc:
            print(f"[reasoning] OpenAI-compatible unavailable ({exc}); "
                  f"using heuristics.")
    elif provider == "anthropic" and config.has_llm():
        try:
            return AnthropicReasoning(config)
        except RuntimeError as exc:
            print(f"[reasoning] LLM unavailable ({exc}); using heuristics.")
    return HeuristicReasoning(config)
