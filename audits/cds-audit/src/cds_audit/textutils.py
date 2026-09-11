"""Small text helpers used by the checks."""

from __future__ import annotations

import html
import re
from typing import Iterable, List

_TAG_RE = re.compile(r"<[^>]+>")
_MD_RE = re.compile(r"(\*\*|__|\*|_|`|#+\s|>\s|\[([^\]]*)\]\([^)]*\))")
_YEAR_RE = re.compile(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)")
# 2018-26, 2000–2020, FY 2021-22, 2019/20
_RANGE_RE = re.compile(r"(?<!\d)(1[89]\d{2}|20\d{2})\s?[-–—/]\s?(\d{2}|\d{4})(?!\d)")
_ABBR_OK_ABBREV = {"i.e", "e.g", "etc", "vs", "no", "dr", "mr", "mrs", "st", "govt", "approx"}


def strip_markup(text: str) -> str:
    """Remove HTML tags / common markdown and collapse whitespace."""
    if not text:
        return ""
    t = html.unescape(_TAG_RE.sub(" ", text))
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"(\*\*|__|`|^#+\s)", "", t, flags=re.M)
    return re.sub(r"\s+", " ", t).strip()


def split_sentences(text: str) -> List[str]:
    """Rough sentence splitter that tolerates decimals, initials and common abbreviations."""
    t = strip_markup(text)
    if not t:
        return []
    # protect decimals like 3.5 and abbreviations like "e.g."
    t = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", t)
    for ab in _ABBR_OK_ABBREV:
        t = re.sub(rf"\b{re.escape(ab)}\.", ab + "<DOT>", t, flags=re.I)
    t = re.sub(r"\b([A-Z])\.", r"\1<DOT>", t)  # initials / U.P.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", t)
    return [p.replace("<DOT>", ".").strip() for p in parts if len(p.strip()) > 2]


def has_year(text: str) -> bool:
    return bool(_YEAR_RE.search(text or ""))


def has_year_range(text: str) -> bool:
    return bool(_RANGE_RE.search(text or ""))


def contains_any(text: str, terms: Iterable[str]) -> List[str]:
    """Return the terms found in text (case-insensitive, word-boundary aware)."""
    low = (text or "").lower()
    found = []
    for term in terms:
        t = term.lower()
        if re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", low):
            found.append(term)
    return found


def tokenize_identifier(name: str) -> List[str]:
    """Split a column/file identifier into lowercase tokens (snake, kebab, camel, spaces)."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name or "")
    return [t for t in re.split(r"[^A-Za-z0-9]+", s.lower()) if t]


def truncate(text: str, n: int = 80) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"
