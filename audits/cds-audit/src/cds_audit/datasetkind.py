"""Classify datasets whose guideline requirements differ from the default.

Language datasets (text and speech corpora, dictionaries, NLP benchmarks, prompt libraries) describe a
language, not a place or a period, so the geography and time-period requirements do not apply to them.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .models import DatasetInfo
from .textutils import strip_markup

Rules = Dict[str, Any]


def language_signals(ds: DatasetInfo, rules: Rules) -> List[str]:
    """Return the phrases that mark ds as a language dataset (empty list when it is not one)."""
    cfg = rules.get("language_datasets") or {}
    if ds.id in cfg.get("exclude_ids", []):
        return []
    if ds.id in cfg.get("include_ids", []):
        return ["listed in language_datasets.include_ids"]
    tags = " | ".join(t.strip() for t in ds.tags if t)
    text = " | ".join([ds.title or "", tags, strip_markup(ds.description or "")])
    if any(re.search(p, text, re.I) for p in cfg.get("counter_patterns", [])):
        return []
    hits: List[str] = []
    for pattern in cfg.get("patterns", []):
        m = re.search(pattern, text, re.I)
        if m:
            hits.append(m.group(0).strip())
    for pattern in cfg.get("tag_patterns", []):
        m = re.search(pattern, tags, re.I)
        if m:
            hits.append(m.group(0).strip())
    return list(dict.fromkeys(hits))


def is_language_dataset(ds: DatasetInfo, rules: Rules) -> bool:
    return bool(language_signals(ds, rules))
