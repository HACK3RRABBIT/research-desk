"""Headless translation for the localized UI.

The Persian (فارسی) version of the desk auto-translates the news content the
same way a normal user's browser does — by calling the free Google Translate
**web** endpoint (`translate.googleapis.com/translate_a/single`). No API key,
no account, no paid quota. On any network/parse failure we return the original
strings, so a flaky connection never breaks the desk (mirrors the ingest
resilience rule).

Translations are cached in the vault by `sha1(english_text) + lang`, so a
brief's Persian render is stable across reloads and we don't re-translate the
same sentence every cycle.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

# Characters that indicate a string is already right-to-left / Persian (or
# Arabic) — we skip translating anything that already reads as Persian.
_RTL = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")

# The Chrome translation-extension client. This is the "headless, like the
# browser" route: a browser UA + client=dict-chrome-ex mirrors a normal user
# translating in the browser, no API key. clients5 mirrors translate.googleapis;
# gtx is the fallback (it 429s under load).
_TRANSLATE_ENDPOINTS = [
    ("https://clients5.google.com/translate_a/t", lambda: "dict-chrome-ex"),
    ("https://translate.googleapis.com/translate_a/single", lambda: "gtx"),
]
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def is_persian(text: str) -> bool:
    return bool(_RTL.search(text or ""))


def _extract(data) -> str:
    """The two endpoints return different shapes; turn either into a string."""
    if not isinstance(data, (list, tuple)) or not data:
        return ""
    top = data[0]
    if isinstance(top, str):
        return top                                   # chrome-ext: [str,...]
    if isinstance(top, (list, tuple)):               # gtx: [[seg,orig,...],...]
        parts = []
        for seg in top:
            if isinstance(seg, (list, tuple)) and seg:
                parts.append(str(seg[0]))
            elif isinstance(seg, str):
                parts.append(seg)
        return "".join(parts)
    return str(top)


def _one(text: str, target: str = "fa") -> str:
    """Translate a single string EN -> target via the free web endpoint."""
    if not text or not text.strip() or target == "en" or is_persian(text):
        return text
    import requests  # hard dependency

    for url, client in _TRANSLATE_ENDPOINTS:
        try:
            resp = requests.get(
                url,
                params={"q": text, "sl": "en", "tl": target,
                        "client": client(), "dt": "t"},
                timeout=12, headers={"User-Agent": _UA})
            resp.raise_for_status()
            return _extract(resp.json())
        except Exception as exc:  # noqa: BLE001 - try the next endpoint
            print(f"[i18n] translate failed via {client()} ({target}): {exc}")
    return text


class Translator:
    """Translate + cache strings. ``vault`` is optional (falls back to no cache)."""

    def __init__(self, vault=None):
        self.vault = vault

    def _key(self, text: str, lang: str) -> str:
        return f"{hashlib.sha1(text.encode('utf-8')).hexdigest()}:{lang}"

    def _one_cached(self, text: str, target: str) -> str:
        if not text or not text.strip() or target == "en" or is_persian(text):
            return text
        key = self._key(text, target)
        if self.vault is not None:
            cached = self.vault.get_translation(key, target)
            if cached is not None:
                return cached
        translated = _one(text, target)
        if self.vault is not None:
            try:
                self.vault.put_translation(key, target, translated)
            except Exception:  # noqa: BLE001 - cache is best-effort
                pass
        return translated

    def translate(self, texts: list[str], target: str = "fa") -> list[str]:
        """Translate a list of strings; missing/None entries pass through."""
        return [self._one_cached(t, target) if t else t for t in (texts or [])]

    def one(self, text: str, target: str = "fa") -> str:
        return self.translate([text], target)[0]
