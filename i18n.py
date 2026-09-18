"""Tiny string table: one JSON file per language in locales/, English as fallback.
Adding a language means dropping in a new file - no code changes."""
from __future__ import annotations

import ctypes
import json
import os

import paths

_DIR = paths.resource("locales")
_strings: dict[str, str] = {}
_fallback: dict[str, str] = {}


def _read(code: str) -> dict[str, str]:
    try:
        with open(os.path.join(_DIR, code + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def available() -> dict[str, str]:
    """code -> the language's own name."""
    out = {}
    for name in sorted(os.listdir(_DIR)):
        if name.endswith(".json"):
            code = name[:-5]
            out[code] = _read(code).get("_name", code)
    return out


def system_language() -> str:
    """Best match for the Windows display language among the available files."""
    try:
        buf = ctypes.create_unicode_buffer(85)
        ctypes.WinDLL("kernel32", winmode=0x800).GetUserDefaultLocaleName(buf, len(buf))
        tag = buf.value  # e.g. th-TH, zh-CN, en-US
    except (AttributeError, OSError):
        tag = "en"
    codes = available()
    if tag.lower().startswith("zh"):
        tag = "zh-Hant" if any(x in tag for x in ("TW", "HK", "MO", "Hant")) else "zh-Hans"
    for cand in (tag, tag.split("-")[0]):
        if cand in codes:
            return cand
    return "en"


def load(code: str | None) -> str:
    global _strings, _fallback
    _fallback = _read("en")
    code = code if code in available() else system_language()
    _strings = _read(code)
    return code


def t(key: str, **fmt) -> str:
    text = _strings.get(key) or _fallback.get(key) or key
    return text.format(**fmt) if fmt else text
