"""Section 1 of the guidelines: metadata checks.

Each function takes a DatasetInfo and the rules dict and returns a CheckResult with a
0..1 score. Sub-checks inside a guideline carry fractional weights that sum to 1.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..models import CheckResult, DatasetInfo
from ..textutils import (
    contains_any,
    has_year,
    split_sentences,
    strip_markup,
    truncate,
)

Rules = Dict[str, Any]


class _Scorer:
    """Accumulates weighted sub-checks into one CheckResult."""

    def __init__(self, check_id: str, guideline: str):
        self.result = CheckResult(check_id=check_id, guideline=guideline, score=0.0)
        self._earned = 0.0
        self._total = 0.0

    def sub(self, ok: float, weight: float, issue: str = "", fix: str = "") -> None:
        """ok is 0..1 (bool accepted). Records the issue/fix when ok < 1."""
        ok = float(ok)
        self._total += weight
        self._earned += weight * ok
        if ok < 0.999:
            if issue:
                self.result.issues.append(issue)
            if fix:
                self.result.fixes.append(fix)

    def done(self, **evidence: Any) -> CheckResult:
        self.result.score = round(self._earned / self._total, 3) if self._total else None
        self.result.evidence.update(evidence)
        return self.result


def _find_metadata(ds: DatasetInfo, data_types: List[str], label_pattern: str) -> List[Dict[str, Any]]:
    rx = re.compile(label_pattern, re.I)
    return [
        m for m in ds.metadata
        if (m.get("data_type") or "").upper() in data_types or rx.search(m.get("label") or "")
    ]


# ---------------------------------------------------------------- 1.1 Title
def check_title(ds: DatasetInfo, rules: Rules) -> CheckResult:
    cfg = rules["title"]
    s = _Scorer("1.1_title", "1.1 Dataset Title")
    title = (ds.title or "").strip()
    if not title:
        s.sub(0, 1, "Title is empty.", "Add a short, descriptive title.")
        return s.done(title="")

    n = len(title)
    s.sub(n <= cfg["max_length"], 0.25,
          f"Title is {n} characters (limit {cfg['max_length']}).",
          f"Shorten the title to {cfg['max_length']} characters or fewer.")

    allowed = set(cfg["allowed_punctuation"])
    bad = sorted({ch for ch in title if not (ch.isalnum() or ch.isspace() or ch in allowed)})
    s.sub(not bad, 0.20,
          f"Title contains special characters: {' '.join(bad)}",
          "Remove special characters from the title (write 'and' instead of '&').")

    letters = [c for c in title if c.isalpha()]
    upper_ratio = sum(c.isupper() for c in letters) / max(len(letters), 1)
    shouting = upper_ratio > 0.8 and len(letters) > 4

    allow = {a.upper() for a in cfg.get("abbreviation_allowlist", [])}
    abbrs = [] if shouting else [w for w in re.findall(r"\b[A-Z][A-Z0-9.]{1,}[a-z]?\b", title)
             if w.rstrip("s").rstrip(".").upper() not in allow and not w.isdigit()
             and sum(ch.isupper() for ch in w) >= 2]
    s.sub(not abbrs, 0.20,
          f"Title uses abbreviations: {', '.join(sorted(set(abbrs)))}",
          "Spell out abbreviations in the title (e.g. 'India Meteorological Department', not 'IMD').")

    starts_ok = title[0].isupper() or title[0].isdigit()
    casing_ok = starts_ok and not shouting and not title.islower()
    s.sub(casing_ok, 0.10,
          "Title is not in sentence case or Title Case.",
          "Use sentence case for the title.")

    s.sub(has_year(title), 0.25,
          "Title does not mention the time period covered.",
          "Add the period covered to the title, e.g. '(2000–2020)'.")
    return s.done(title=title, length=n)


# ---------------------------------------------------------- 1.2 Description
def check_description(ds: DatasetInfo, rules: Rules) -> CheckResult:
    cfg = rules["description"]
    s = _Scorer("1.2_description", "1.2 Description / Summary")
    text = strip_markup(ds.description or "")
    if not text:
        s.sub(0, 1, "Description is empty.",
              "Write a 2–5 sentence summary: what, where, when, how often, who compiled it, why.")
        return s.done(sentences=0)

    sentences = split_sentences(text)
    k = len(sentences)
    lo, hi = cfg["min_sentences"], cfg["max_sentences"]
    if lo <= k <= hi:
        s.sub(1, 0.15)
    elif k < lo:
        s.sub(0, 0.15, f"Description is only {k} sentence.",
              f"Expand the description to {lo}–{hi} sentences.")
    else:
        s.sub(0.5, 0.15, f"Description runs to {k} sentences (guideline: {lo}–{hi}).",
              f"Tighten the description to at most {hi} sentences; move methodology detail to a resource description.")

    if ds.title and text.strip().lower() == ds.title.strip().lower():
        s.sub(0, 0.10, "Description just repeats the title.", "Replace the repeated title with a real summary.")
    else:
        s.sub(1, 0.10)

    s.sub(has_year(text), 0.20,
          "Description does not state the time period covered.",
          "State the years the data covers in the description.")

    geo_terms = list(rules.get("geography_terms", [])) + [g.get("name", "") for g in ds.geographies if g.get("name")]
    geo_hits = contains_any(text, geo_terms)
    s.sub(bool(geo_hits), 0.20,
          "Description does not state the geographic coverage.",
          "Say which geography the data covers (country / state / district level).")

    # A source counts only when named as the source: "compiled by …", "from the Census…",
    # "by the X Department". A bare mention of "government" in a sentence does not count.
    src_hits = contains_any(text, cfg["source_terms"])
    ent = "|".join(re.escape(t) for t in cfg["source_entity_terms"])
    m = re.search(rf"\b(by|from)\s+(the\s+)?([\w&.'-]+\s+){{0,6}}?({ent})\b", text, re.I)
    if m:
        src_hits.append(m.group(0))
    if ds.organization and ds.organization.lower() in text.lower():
        src_hits.append(ds.organization)
    s.sub(bool(src_hits), 0.15,
          "Description does not say who collected or compiled the data.",
          "Name the organisation that collected or compiled the data (and the method if derived).")

    per_hits = contains_any(text, cfg["periodicity_terms"])
    per_hits += [m.group(0) for p in cfg.get("periodicity_patterns", []) for m in [re.search(p, text, re.I)] if m]
    s.sub(bool(per_hits), 0.10,
          "Description does not state the periodicity (daily, monthly, annual…).",
          "Mention how often the data is recorded or updated (e.g. 'annual', 'daily').")

    pur_hits = contains_any(text, cfg["purpose_terms"])
    s.sub(bool(pur_hits), 0.10,
          "Description does not state the purpose or intended use.",
          "Add one line on what the dataset is intended to support.")

    return s.done(sentences=k, geography_found=geo_hits[:3], source_found=src_hits[:3],
                  periodicity_found=per_hits[:3], excerpt=truncate(text, 160))


# ------------------------------------------------------------ 1.3 Publisher
def check_publisher(ds: DatasetInfo, rules: Rules) -> CheckResult:
    s = _Scorer("1.3_publisher", "1.3 Publisher / Data Provider")
    if ds.organization:
        s.sub(1, 1)
    elif ds.user:
        s.sub(0.6, 1, f"Published by an individual ({ds.user}), not an organisation.",
              "Publish under the responsible organisation, or name the original data provider in the description.")
    else:
        s.sub(0, 1, "No publisher or data provider is recorded.", "Attach the dataset to the responsible organisation.")
    return s.done(publisher=ds.publisher)


# ------------------------------------------------------------------ 1.5 Tags
def check_tags(ds: DatasetInfo, rules: Rules) -> CheckResult:
    s = _Scorer("1.5_tags", "1.5 Tags")
    tags = [t for t in ds.tags if t and t.strip()]
    if not tags:
        s.sub(0, 1, "No tags.", "Add tags describing the dataset's themes, variables or use cases.")
        return s.done(tags=[])
    s.sub(1, 0.6)
    sectors_low = {x.lower() for x in ds.sectors}
    dup = [t for t in tags if t.lower() in sectors_low]
    s.sub(len(dup) < len(tags), 0.2,
          "Every tag just repeats a sector name.",
          "Use tags for specific themes/variables; sectors already cover the broad domain.")
    predefined = {p.lower() for p in rules.get("tags", {}).get("predefined", [])}
    if predefined:
        off = [t for t in tags if t.lower() not in predefined]
        s.sub(1 - len(off) / len(tags), 0.2,
              f"Tags not in the predefined list: {', '.join(off[:5])}",
              "Replace free-text tags with the platform's predefined tags.")
    else:
        # Near-duplicate tags (case/plural variants) are a consistency smell.
        norm = {}
        for t in tags:
            norm.setdefault(re.sub(r"s$", "", t.lower().strip()), []).append(t)
        dups = [v for v in norm.values() if len(v) > 1]
        s.sub(not dups, 0.2, f"Near-duplicate tags: {dups[:3]}", "Merge duplicate tag variants.")
    return s.done(tags=tags)


# --------------------------------------------------------------- 1.6 Sectors
def check_sectors(ds: DatasetInfo, rules: Rules) -> CheckResult:
    s = _Scorer("1.6_sectors", "1.6 Sectors")
    s.sub(bool(ds.sectors), 1, "No sector assigned.", "Assign at least one predefined sector.")
    return s.done(sectors=ds.sectors)


# ------------------------------------------------------------- 1.7 Geography
def check_geography(ds: DatasetInfo, rules: Rules) -> CheckResult:
    s = _Scorer("1.7_geography", "1.7 Spatial Coverage / Geography")
    names = [g.get("name", "") for g in ds.geographies if g.get("name")]
    if not names:
        s.sub(0, 1, "No geographic coverage recorded.", "Set the geography (country / state / district) in metadata.")
        return s.done(geographies=[])
    s.sub(1, 0.7)
    # Title names a state that is missing from the geography field?
    states = [t for t in rules.get("geography_terms", []) if t[0].isupper() and t not in ("India",)]
    mentioned = contains_any(ds.title, states)
    missing = [m for m in mentioned if m.lower() not in {n.lower() for n in names}]
    s.sub(not missing, 0.3,
          f"Title mentions {', '.join(missing)} but the geography field does not.",
          f"Add {', '.join(missing)} to the dataset's geography.")
    return s.done(geographies=names)


# ------------------------------------------------------- 1.8 Date of creation
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_date_of_creation(ds: DatasetInfo, rules: Rules) -> CheckResult:
    s = _Scorer("1.8_date_of_creation", "1.8 Date of Creation")
    items = [m for m in _find_metadata(ds, ["DATE"], r"(creat|date)") if (m.get("value") or "").strip()]
    if not items:
        s.sub(0, 1, "No date of creation in the metadata.",
              "Add the source's official creation date in YYYY-MM-DD format.")
        return s.done()
    value = str(items[0]["value"]).strip()
    iso = bool(_ISO_DATE.match(value))
    parsed: Optional[date] = None
    if iso:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            iso = False
    s.sub(1, 0.5)
    s.sub(iso, 0.4, f"Date of creation '{value}' is not ISO-8601 (YYYY-MM-DD).",
          "Record the creation date as YYYY-MM-DD.")
    s.sub(not (parsed and parsed > date.today()), 0.1,
          f"Date of creation {value} is in the future.", "Correct the creation date.")
    return s.done(label=items[0].get("label"), value=value)


# --------------------------------------------------------------- 1.9 License
def _source_urls(ds: DatasetInfo) -> List[str]:
    return [str(m.get("value")).strip() for m in _find_metadata(ds, ["URL"], r"(source|website|url|link)")
            if m.get("value")]


def _is_gov_source(ds: DatasetInfo, rules: Rules) -> bool:
    lic = rules["license"]
    for u in _source_urls(ds):
        host = (urlparse(u if "//" in u else "http://" + u).hostname or "").lower()
        if any(host.endswith(d.lstrip(".")) or host == d.lstrip(".") for d in lic["government_domains"]):
            return True
    return False


def check_license(ds: DatasetInfo, rules: Rules) -> CheckResult:
    lic = rules["license"]
    s = _Scorer("1.9_license", "1.9 License and Terms of Use")
    value = (ds.license or "").strip()
    if not value:
        s.sub(0, 1, "No license specified.", "Choose a license from the platform list.")
        return s.done(license="")
    s.sub(1, 0.5)
    gov = _is_gov_source(ds, rules)
    if gov:
        s.sub(value == lic["godl_value"], 0.5,
              f"Source is an Indian government site but the license is {value}"
              + (" (the platform default — likely never set)." if value == lic["platform_default"] else "."),
              "Set the license to Government Open Data License (GODL) for data sourced from government platforms.")
    else:
        s.sub(1, 0.5)
    return s.done(license=value, government_source=gov)


# ------------------------------------------------------- 1.10 Source website
def check_source_website(ds: DatasetInfo, rules: Rules, link_status: Optional[Dict[str, int]] = None) -> CheckResult:
    s = _Scorer("1.10_source_website", "1.10 Source Website")
    urls = _source_urls(ds)
    if not urls:
        s.sub(0, 1, "No source website recorded.",
              "Add the official page of the organisation that publishes the source data.")
        return s.done(urls=[])
    u = urls[0]
    parsed = urlparse(u)
    valid = parsed.scheme in ("http", "https") and bool(parsed.netloc) and "." in parsed.netloc
    s.sub(1, 0.4)
    s.sub(valid, 0.4, f"Source website '{truncate(u, 60)}' is not a valid http(s) URL.",
          "Enter the full URL including https://.")
    self_ref = "civicdataspace" in parsed.netloc.lower()
    status = (link_status or {}).get(u)
    if status is not None:
        s.sub(status < 400 and not self_ref, 0.2,
              f"Source website returned HTTP {status}." if status >= 400 else "Source website points back to CivicDataSpace.",
              "Replace with a working link to the original publisher.")
    else:
        s.sub(not self_ref, 0.2, "Source website points back to CivicDataSpace rather than the original publisher.",
              "Link to the original publisher's page.")
    return s.done(urls=urls, http_status=status)


ALL_METADATA_CHECKS = [
    check_title,
    check_description,
    check_publisher,
    check_tags,
    check_sectors,
    check_geography,
    check_date_of_creation,
    check_license,
    check_source_website,
]
