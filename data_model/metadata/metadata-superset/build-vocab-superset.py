#!/usr/bin/env python3
"""
build_vocab_superlists.py
=========================

Builds a "super list" for each DataSpace fixed-entry vocabulary (license,
geography, sector) by merging a range of canonical sources with the values
currently live in the platform.

The output is deliberately a *superset*. Most rows are not meant to appear in
the contributor UI. Every row therefore carries a visibility decision:

    PICKABLE    shown in the contributor picker and as a search facet
    RESOLVABLE  accepted on ingest / federation and resolvable by URI,
                but hidden from human selection (e.g. non-open licences)
    HIDDEN      known to the system, never offered, never auto-applied
                (deprecated codes, superseded districts)

Visibility is decided by declarative rules in VISIBILITY_RULES, not scattered
through the merge code, so changing what the platform shows is a config edit
and a re-run rather than a patch.

Sources
-------
Fetched over the network (when available):
    SPDX License List        raw.githubusercontent.com/spdx/license-list-data
    EU Data Theme NAL        publications.europa.eu authority table
    EU Licence NAL           publications.europa.eu authority table
    Wikidata                 SPARQL, for dcterms:spatial URIs

Local files (no usable public API — download once, commit, re-run):
    LGD state / district masters     lgdirectory.gov.in
    CDL sector list                  platform export or hand-maintained
    Platform current state           export of the live enum / tables
    OECD DAC CRS purpose codes       oecd.org

Run `--init` to write templates for every local source, then fill them in.
Run `--offline` to build from local files only.

Outputs (to --out, default ./out):
    licenses.csv  geographies.csv  sectors.csv   full superlists
    *_pickable.csv                               visible subset only
    superlists.xlsx                              one sheet per vocabulary
    load_manifest.json                           backend loader payload
    run_manifest.json                            source versions + fetch times

Usage
-----
    python build_vocab_superlists.py --init
    python build_vocab_superlists.py --sources ./sources --out ./out
    python build_vocab_superlists.py --offline --only sectors
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

CDL_NAMESPACE = "https://civicdataspace.in/id"

SPDX_LICENSES_URL = (
    "https://raw.githubusercontent.com/spdx/license-list-data/main/json/licenses.json"
)
EU_DATA_THEME_URL = (
    "http://publications.europa.eu/resource/authority/data-theme"
    "?useVersionInformation=true"
)
EU_LICENCE_NAL_URL = "http://publications.europa.eu/resource/authority/licence"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"

USER_AGENT = "CivicDataSpace-vocab-builder/1.0 (https://civicdataspace.in)"
HTTP_TIMEOUT = 30

PICKABLE = "PICKABLE"
RESOLVABLE = "RESOLVABLE"
HIDDEN = "HIDDEN"


# --------------------------------------------------------------------------
# Record model
# --------------------------------------------------------------------------


@dataclass
class VocabRecord:
    """One concept in a superlist, merged across sources."""

    vocabulary: str                   # license | geography | sector
    key: str                          # stable internal key (the merge identity)
    label: str                        # human-readable, platform-facing
    code: str = ""                    # authority code (SPDX id, LGD code, theme code)
    uri: str = ""                     # canonical resolvable URI
    scheme: str = ""                  # authority the code belongs to
    tier: str = ""                    # geography: COUNTRY/STATE/UT/DISTRICT/REGION
    parent_key: str = ""              # hierarchy, where the vocabulary has one

    # --- flags -------------------------------------------------------------
    in_build: bool = False            # present in the live platform today
    visibility: str = RESOLVABLE      # PICKABLE | RESOLVABLE | HIDDEN
    is_active: bool = True            # mirrors ResourceType.is_active semantics
    is_open: Optional[bool] = None    # licences only: Open Definition conformant
    deprecated: bool = False
    needs_review: bool = False        # conflict or missing canonical URI
    review_reason: str = ""

    # --- provenance --------------------------------------------------------
    sources: List[str] = field(default_factory=list)
    alt_codes: Dict[str, str] = field(default_factory=dict)
    notes: str = ""

    @property
    def visible_on_platform(self) -> bool:
        """Single boolean the API/UI can filter on."""
        return self.visibility == PICKABLE and self.is_active and not self.deprecated

    def to_row(self) -> dict:
        d = asdict(self)
        d["sources"] = "|".join(sorted(set(self.sources)))
        d["alt_codes"] = "|".join(f"{k}={v}" for k, v in sorted(self.alt_codes.items()))
        d["visible_on_platform"] = self.visible_on_platform
        return d


COLUMNS = [
    "vocabulary", "key", "label", "code", "uri", "scheme", "tier", "parent_key",
    "in_build", "visible_on_platform", "visibility", "is_active", "is_open",
    "deprecated", "needs_review", "review_reason", "sources", "alt_codes", "notes",
]


# --------------------------------------------------------------------------
# Visibility rules
# --------------------------------------------------------------------------
#
# Each rule is (name, predicate, visibility). The FIRST matching rule wins, so
# order is the policy. Edit here to change what the platform offers.

VisibilityRule = tuple


def _rule(name: str, pred: Callable[[VocabRecord], bool], vis: str) -> VisibilityRule:
    return (name, pred, vis)


VISIBILITY_RULES: Dict[str, List[VisibilityRule]] = {
    "license": [
        _rule("deprecated-or-superseded", lambda r: r.deprecated, HIDDEN),
        # Non-open licences are never offered, but must resolve so that
        # federated records carrying them can still be ingested and labelled.
        _rule("not-open", lambda r: r.is_open is False, RESOLVABLE),
        _rule("already-in-build", lambda r: r.in_build, PICKABLE),
        # Curated additions: the open licences we want contributors to reach.
        _rule(
            "curated-open-additions",
            lambda r: r.is_open is True
            and r.code in {"CC0-1.0", "PDDL-1.0", "ODC-By-1.0", "CC-BY-4.0"},
            PICKABLE,
        ),
        _rule("default", lambda r: True, RESOLVABLE),
    ],
    "geography": [
        _rule("superseded-unit", lambda r: r.deprecated, HIDDEN),
        _rule("country-and-above", lambda r: r.tier in {"COUNTRY", "REGION"}, PICKABLE),
        _rule("state-and-ut", lambda r: r.tier in {"STATE", "UT"}, PICKABLE),
        # ~800 districts would swamp a picker and a facet list. They stay
        # resolvable so dataset metadata can reference them precisely, and the
        # UI reaches them through typeahead or state drill-down instead.
        _rule("district", lambda r: r.tier == "DISTRICT", RESOLVABLE),
        _rule("default", lambda r: True, RESOLVABLE),
    ],
    "sector": [
        _rule("deprecated", lambda r: r.deprecated, HIDDEN),
        # Only CDL's own scheme is contributor-facing. External schemes are
        # loaded as mapping targets for dcat:theme serialisation, not choices.
        _rule("cdl-scheme", lambda r: r.scheme == "cdl", PICKABLE),
        _rule("default", lambda r: True, RESOLVABLE),
    ],
}


def apply_visibility(records: Iterable[VocabRecord]) -> None:
    for rec in records:
        for name, pred, vis in VISIBILITY_RULES.get(rec.vocabulary, []):
            if pred(rec):
                rec.visibility = vis
                if not rec.notes:
                    rec.notes = f"visibility rule: {name}"
                break


# --------------------------------------------------------------------------
# Fetch helpers
# --------------------------------------------------------------------------


class Fetcher:
    """HTTP with a cache directory and a hard offline switch."""

    def __init__(self, cache_dir: str, offline: bool = False):
        self.cache_dir = cache_dir
        self.offline = offline
        self.log: List[dict] = []
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, url: str) -> str:
        safe = urllib.parse.quote(url, safe="")[:180]
        return os.path.join(self.cache_dir, safe + ".cache")

    def get(self, url: str, accept: str = "application/json") -> Optional[str]:
        path = self._cache_path(url)
        if self.offline:
            if os.path.exists(path):
                self.log.append({"url": url, "status": "cache", "at": _now()})
                return open(path, encoding="utf-8").read()
            self.log.append({"url": url, "status": "skipped-offline", "at": _now()})
            return None
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": accept}
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
            self.log.append({"url": url, "status": "fetched", "at": _now()})
            return body
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if os.path.exists(path):
                self.log.append(
                    {"url": url, "status": f"stale-cache ({exc})", "at": _now()}
                )
                return open(path, encoding="utf-8").read()
            self.log.append({"url": url, "status": f"failed ({exc})", "at": _now()})
            warn(f"could not fetch {url}: {exc}")
            return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def warn(msg: str) -> None:
    print(f"  ! {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"  - {msg}")


def read_csv(path: str) -> List[dict]:
    if not os.path.exists(path):
        warn(f"missing local source: {path} (run --init to scaffold it)")
        return []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        # Templates carry "#" guidance lines; they are comments, not data.
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return [
        {k.strip(): (v or "").strip() for k, v in row.items() if k}
        for row in csv.DictReader(lines)
    ]


def as_bool(value: str, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


# --------------------------------------------------------------------------
# Merge
# --------------------------------------------------------------------------


def merge(records: List[VocabRecord]) -> List[VocabRecord]:
    """Union records on (vocabulary, key), recording provenance and conflicts."""
    merged: Dict[tuple, VocabRecord] = {}
    for rec in records:
        ident = (rec.vocabulary, rec.key)
        if ident not in merged:
            merged[ident] = rec
            continue
        base = merged[ident]
        # The platform's display label is expected to differ from an authority's
        # official name ("CC Attribution 4.0" vs "... 4.0 International"), so the
        # platform label wins and the authority name is kept alongside it.
        # A disagreement between two *authorities* is a genuine conflict.
        if rec.label and base.label and rec.label.lower() != base.label.lower():
            display_sources = {"platform", "cdl"}
            base_is_display = bool(set(base.sources) & display_sources)
            rec_is_display = bool(set(rec.sources) & display_sources)
            if base_is_display and not rec_is_display:
                base.alt_codes["authority_label"] = rec.label
            elif rec_is_display and not base_is_display:
                base.alt_codes["authority_label"] = base.label
                base.label = rec.label
            else:
                base.needs_review = True
                base.review_reason = _append(
                    base.review_reason,
                    f"label conflict: '{base.label}' vs '{rec.label}' "
                    f"({'|'.join(rec.sources)})",
                )
        for attr in ("code", "uri", "scheme", "tier", "parent_key", "label"):
            if not getattr(base, attr) and getattr(rec, attr):
                setattr(base, attr, getattr(rec, attr))
        base.in_build = base.in_build or rec.in_build
        base.deprecated = base.deprecated or rec.deprecated
        if base.is_open is None:
            base.is_open = rec.is_open
        base.sources.extend(rec.sources)
        base.alt_codes.update(rec.alt_codes)
    out = list(merged.values())
    for rec in out:
        if not rec.uri:
            rec.needs_review = True
            rec.review_reason = _append(rec.review_reason, "no canonical URI")
    return out


def _append(existing: str, msg: str) -> str:
    return f"{existing}; {msg}" if existing else msg


# --------------------------------------------------------------------------
# Vocabulary: LICENSE
# --------------------------------------------------------------------------

# Steward URIs are what dcterms:license actually wants (a LicenseDocument
# resource). SPDX gives the identifier; this gives the resolvable thing.
LICENSE_STEWARD_URI = {
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY-4.0": "http://creativecommons.org/licenses/by/4.0/",
    "CC-BY-SA-4.0": "http://creativecommons.org/licenses/by-sa/4.0/",
    "CC-BY-NC-4.0": "http://creativecommons.org/licenses/by-nc/4.0/",
    "ODbL-1.0": "https://opendatacommons.org/licenses/odbl/1-0/",
    "ODC-By-1.0": "https://opendatacommons.org/licenses/by/1-0/",
    "PDDL-1.0": "https://opendatacommons.org/licenses/pddl/1-0/",
}

# Licences with no SPDX identifier and no entry in any external authority.
# These need CDL-minted IRIs; that is the whole reason this list exists.
LOCAL_LICENSES = [
    {
        "key": "GODL-India",
        "label": "Government Open Data License – India",
        "code": "GODL-India",
        "uri": f"{CDL_NAMESPACE}/licence/godl-india",
        "scheme": "cdl",
        "is_open": True,
        "notes": "No SPDX ID, no EU NAL entry. dcterms:source = "
                 "https://data.gov.in/government-open-data-license-india",
    },
]


def build_licenses(fetcher: Fetcher, sources_dir: str) -> List[VocabRecord]:
    records: List[VocabRecord] = []

    # 1. Current platform state -------------------------------------------
    for row in read_csv(os.path.join(sources_dir, "platform_licenses.csv")):
        if not row.get("spdx_id") and not row.get("key"):
            continue
        key = row.get("spdx_id") or row["key"]
        records.append(
            VocabRecord(
                vocabulary="license",
                key=key,
                label=row.get("label", ""),
                code=row.get("spdx_id", ""),
                uri=LICENSE_STEWARD_URI.get(key, ""),
                scheme="spdx" if row.get("spdx_id") else "cdl",
                in_build=True,
                is_open=as_bool(row.get("is_open", "true"), True),
                sources=["platform"],
                alt_codes={"dataspace_enum": row.get("enum_value", "")},
                notes=row.get("notes", ""),
            )
        )

    # 2. SPDX --------------------------------------------------------------
    body = fetcher.get(SPDX_LICENSES_URL)
    if body:
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            warn(f"SPDX payload unparseable: {exc}")
            data = {}
        existing_keys = {r.key for r in records}
        for lic in data.get("licenses", []):
            sid = lic.get("licenseId", "")
            # The full SPDX list is ~600 software licences. Keep the data
            # families plus anything already referenced by the platform.
            if not (
                sid.startswith(("CC-", "CC0", "ODbL", "ODC-", "PDDL"))
                or sid in existing_keys
            ):
                continue
            records.append(
                VocabRecord(
                    vocabulary="license",
                    key=sid,
                    label=lic.get("name", ""),
                    code=sid,
                    uri=LICENSE_STEWARD_URI.get(sid, f"https://spdx.org/licenses/{sid}"),
                    scheme="spdx",
                    is_open=bool(lic.get("isOsiApproved")) or sid.startswith(
                        ("CC-BY-4", "CC-BY-SA-4", "CC0", "ODbL", "ODC-By", "PDDL")
                    ),
                    deprecated=bool(lic.get("isDeprecatedLicenseId")),
                    sources=["spdx"],
                    alt_codes={"spdx_detail": lic.get("detailsUrl", "")},
                )
            )
        info(f"SPDX: {sum(1 for r in records if 'spdx' in r.sources)} data licences")

    # 3. EU Licence authority table (optional, for EU federation) ----------
    for row in read_csv(os.path.join(sources_dir, "eu_licence_nal.csv")):
        if not row.get("code"):
            continue
        records.append(
            VocabRecord(
                vocabulary="license",
                key=row.get("spdx_id") or row["code"],
                label=row.get("label", ""),
                code=row.get("spdx_id", ""),
                scheme="eu-licence-nal",
                sources=["eu-licence-nal"],
                alt_codes={"eu_nal": row["code"]},
            )
        )

    # 4. CDL-minted -------------------------------------------------------
    for spec in LOCAL_LICENSES:
        records.append(
            VocabRecord(vocabulary="license", sources=["cdl"], **spec)
        )

    return records


# --------------------------------------------------------------------------
# Vocabulary: GEOGRAPHY
# --------------------------------------------------------------------------

ISO_COUNTRY = {"IN": ("India", "https://www.wikidata.org/entity/Q668")}


def build_geographies(fetcher: Fetcher, sources_dir: str) -> List[VocabRecord]:
    records: List[VocabRecord] = []

    # 1. Country tier ------------------------------------------------------
    for iso2, (label, wd) in ISO_COUNTRY.items():
        records.append(
            VocabRecord(
                vocabulary="geography",
                key=f"country:{iso2}",
                label=label,
                code=iso2,
                uri=wd,
                scheme="iso3166-1",
                tier="COUNTRY",
                sources=["iso3166"],
            )
        )

    # 2. LGD states / UTs --------------------------------------------------
    # lgdirectory.gov.in has no public API. Download the state and district
    # masters once and commit them; this reads them as-is.
    for row in read_csv(os.path.join(sources_dir, "lgd_states.csv")):
        code = row.get("lgd_state_code", "")
        if not code:
            continue
        tier = "UT" if as_bool(row.get("is_union_territory")) else "STATE"
        records.append(
            VocabRecord(
                vocabulary="geography",
                key=f"state:{code}",
                label=row.get("state_name", ""),
                code=code,
                uri=row.get("wikidata_uri", ""),
                scheme="lgd",
                tier=tier,
                parent_key="country:IN",
                sources=["lgd"],
                alt_codes={
                    "iso3166_2": row.get("iso_3166_2", ""),
                    "census_2011": row.get("census_2011_code", ""),
                },
                deprecated=as_bool(row.get("deprecated")),
                notes=row.get("notes", ""),
            )
        )

    # 3. LGD districts -----------------------------------------------------
    # Districts split and rename often. valid_from / valid_to travel with the
    # row so a dataset can still point at the unit as it stood at capture time.
    for row in read_csv(os.path.join(sources_dir, "lgd_districts.csv")):
        code = row.get("lgd_district_code", "")
        if not code:
            continue
        valid_to = row.get("valid_to", "")
        records.append(
            VocabRecord(
                vocabulary="geography",
                key=f"district:{code}",
                label=row.get("district_name", ""),
                code=code,
                uri=row.get("wikidata_uri", ""),
                scheme="lgd",
                tier="DISTRICT",
                parent_key=f"state:{row.get('lgd_state_code', '')}",
                sources=["lgd"],
                alt_codes={
                    "census_2011": row.get("census_2011_code", ""),
                    "valid_from": row.get("valid_from", ""),
                    "valid_to": valid_to,
                },
                deprecated=bool(valid_to),
                notes="superseded unit; retained for historical references"
                if valid_to else "",
            )
        )

    # 4. CDL regional groupings (no external authority covers these) -------
    for row in read_csv(os.path.join(sources_dir, "cdl_regions.csv")):
        slug = row.get("slug", "")
        if not slug:
            continue
        records.append(
            VocabRecord(
                vocabulary="geography",
                key=f"region:{slug}",
                label=row.get("label", ""),
                code=slug,
                uri=f"{CDL_NAMESPACE}/geography/region/{slug}",
                scheme="cdl",
                tier="REGION",
                sources=["cdl"],
                alt_codes={"un_m49": row.get("un_m49", "")},
                notes=row.get("notes", ""),
            )
        )

    # 5. Wikidata backfill for rows still missing a spatial URI -----------
    _backfill_wikidata(fetcher, records)

    # 6. What the platform holds today ------------------------------------
    _mark_platform_geographies(records, sources_dir)

    return records


WIKIDATA_BATCH_SIZE = 400


def _backfill_wikidata(fetcher: Fetcher, records: List[VocabRecord]) -> None:
    """Resolve Wikidata QIDs by LGD code for rows lacking a dcterms:spatial URI."""
    missing = [r for r in records if not r.uri and r.scheme == "lgd" and r.code]
    if not missing:
        return
    # P8119 is the LGD local body code; states/districts use their own props,
    # so this is a best-effort match on code and label, reviewed afterwards.
    # Wikidata's query length/timeout limits mean a single VALUES clause can't
    # carry all ~800 districts, so this queries in batches rather than
    # silently truncating to the first one.
    by_code: Dict[str, str] = {}
    attempted = 0
    for start in range(0, len(missing), WIKIDATA_BATCH_SIZE):
        batch = missing[start:start + WIKIDATA_BATCH_SIZE]
        attempted += len(batch)
        values = " ".join(f'"{r.code}"' for r in batch)
        query = f"""
        SELECT ?item ?code WHERE {{
          VALUES ?code {{ {values} }}
          ?item wdt:P8119 ?code .
        }}
        """
        url = WIKIDATA_SPARQL + "?" + urllib.parse.urlencode(
            {"query": query, "format": "json"}
        )
        body = fetcher.get(url, accept="application/sparql-results+json")
        if not body:
            info(f"Wikidata backfill skipped for batch of {len(batch)}; QIDs left blank for review")
            continue
        try:
            rows = json.loads(body)["results"]["bindings"]
        except (json.JSONDecodeError, KeyError) as exc:
            warn(f"Wikidata response unusable: {exc}")
            continue
        by_code.update({r["code"]["value"]: r["item"]["value"] for r in rows})

    hits = 0
    for rec in missing:
        if rec.code in by_code:
            rec.uri = by_code[rec.code]
            rec.sources.append("wikidata")
            hits += 1
    info(f"Wikidata: resolved {hits}/{len(missing)} URIs ({attempted} queried)")


def _mark_platform_geographies(records: List[VocabRecord], sources_dir: str) -> None:
    """The platform joins geographies on NAME, so match on name to find them."""
    live = {
        row.get("name", "").strip().lower()
        for row in read_csv(os.path.join(sources_dir, "platform_geographies.csv"))
        if row.get("name")
    }
    if not live:
        return
    matched = 0
    for rec in records:
        if rec.label.strip().lower() in live:
            rec.in_build = True
            rec.sources.append("platform")
            matched += 1
    info(f"platform geographies: {matched} of {len(live)} matched to a canonical code")
    if matched < len(live):
        warn(
            f"{len(live) - matched} live geography rows have no canonical match — "
            "these are the name-string entries that will break on federation"
        )


# --------------------------------------------------------------------------
# Vocabulary: SECTOR
# --------------------------------------------------------------------------

EU_DATA_THEMES = {
    "AGRI": "Agriculture, fisheries, forestry and food",
    "ECON": "Economy and finance",
    "EDUC": "Education, culture and sport",
    "ENER": "Energy",
    "ENVI": "Environment",
    "GOVE": "Government and public sector",
    "HEAL": "Health",
    "INTR": "International issues",
    "JUST": "Justice, legal system and public safety",
    "REGI": "Regions and cities",
    "SOCI": "Population and society",
    "TECH": "Science and technology",
    "TRAN": "Transport",
}
EU_THEME_BASE = "http://publications.europa.eu/resource/authority/data-theme/"


def build_sectors(fetcher: Fetcher, sources_dir: str) -> List[VocabRecord]:
    records: List[VocabRecord] = []

    # 1. EU data themes — the vocabulary dcat:theme must carry -------------
    for code, label in EU_DATA_THEMES.items():
        records.append(
            VocabRecord(
                vocabulary="sector",
                key=f"eu-theme:{code}",
                label=label,
                code=code,
                uri=EU_THEME_BASE + code,
                scheme="eu-data-theme",
                sources=["eu-data-theme"],
            )
        )

    # 2. CDL sectors — the internal model, and the only pickable scheme ----
    for row in read_csv(os.path.join(sources_dir, "cdl_sectors.csv")):
        slug = row.get("slug", "")
        if not slug:
            continue
        theme = row.get("eu_data_theme", "").strip().upper()
        match_type = row.get("match_type", "")
        rec = VocabRecord(
            vocabulary="sector",
            key=f"cdl:{slug}",
            label=row.get("name", ""),
            code=slug,
            uri=f"{CDL_NAMESPACE}/sector/{slug}",
            scheme="cdl",
            parent_key=f"cdl:{row['parent_slug']}" if row.get("parent_slug") else "",
            in_build=as_bool(row.get("in_build", "true"), True),
            sources=["cdl"],
            alt_codes={
                "eu_data_theme": theme,
                "eu_match_type": match_type,
                "dac_crs": row.get("dac_crs", ""),
                "sdg": row.get("sdg", ""),
            },
            notes=row.get("notes", ""),
        )
        if theme and theme not in EU_DATA_THEMES:
            rec.needs_review = True
            rec.review_reason = _append(
                rec.review_reason, f"'{theme}' is not a valid EU data-theme code"
            )
        if not theme:
            rec.needs_review = True
            rec.review_reason = _append(rec.review_reason, "no dcat:theme mapping")
        records.append(rec)

    # 3. OECD DAC CRS purpose codes — secondary scheme for UNICEF work ----
    for row in read_csv(os.path.join(sources_dir, "dac_crs.csv")):
        code = row.get("code", "")
        if not code:
            continue
        records.append(
            VocabRecord(
                vocabulary="sector",
                key=f"dac:{code}",
                label=row.get("name", ""),
                code=code,
                uri=f"http://reference.iatistandard.org/codelists/Sector/{code}",
                scheme="oecd-dac-crs",
                sources=["oecd-dac-crs"],
            )
        )

    _report_theme_collapse(records)
    return records


def _report_theme_collapse(records: List[VocabRecord]) -> None:
    """Many-to-one CDL→EU theme mappings are lossy; surface them explicitly."""
    by_theme: Dict[str, List[str]] = {}
    for rec in records:
        if rec.scheme != "cdl":
            continue
        theme = rec.alt_codes.get("eu_data_theme", "")
        if theme:
            by_theme.setdefault(theme, []).append(rec.label)
    for theme, names in sorted(by_theme.items()):
        if len(names) > 1:
            info(f"dcat:theme {theme} <- {len(names)} CDL sectors: {', '.join(names)}")


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def write_csv(path: str, records: List[VocabRecord]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for rec in sorted(records, key=lambda r: (r.scheme, r.tier, r.label)):
            writer.writerow(rec.to_row())


def write_xlsx(path: str, groups: Dict[str, List[VocabRecord]]) -> bool:
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        warn("openpyxl not installed; skipping xlsx (CSV and JSON still written)")
        return False

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    bold = Font(name="Arial", size=10, bold=True)
    body = Font(name="Arial", size=10)
    head_fill = PatternFill("solid", fgColor="FFEFEFEF")
    pick_fill = PatternFill("solid", fgColor="FFD9EAD3")
    review_fill = PatternFill("solid", fgColor="FFFFF2CC")

    for vocab, records in groups.items():
        ws = wb.create_sheet(vocab.capitalize())
        for i, col in enumerate(COLUMNS, start=1):
            c = ws.cell(row=1, column=i, value=col)
            c.font, c.fill = bold, head_fill
        for r_i, rec in enumerate(
            sorted(records, key=lambda r: (r.scheme, r.tier, r.label)), start=2
        ):
            row = rec.to_row()
            for c_i, col in enumerate(COLUMNS, start=1):
                c = ws.cell(row=r_i, column=c_i, value=row.get(col))
                c.font = body
                c.alignment = Alignment(wrap_text=True, vertical="top")
                if rec.needs_review:
                    c.fill = review_fill
                elif rec.visible_on_platform:
                    c.fill = pick_fill
        ws.freeze_panes = "C2"
        for i, col in enumerate(COLUMNS, start=1):
            letter = openpyxl.utils.get_column_letter(i)
            ws.column_dimensions[letter].width = 38 if col in {
                "label", "uri", "notes", "review_reason", "alt_codes"
            } else 16
    wb.save(path)
    return True


def write_load_manifest(path: str, groups: Dict[str, List[VocabRecord]]) -> None:
    """Payload a Django management command can consume directly.

    HIDDEN rows (deprecated codes, superseded districts, ...) are still
    written here: the whole point of HIDDEN is that they stay "known to
    the system" and resolvable by URI, just never offered or auto-applied.
    Dropping them would break resolution for federated records or
    historical datasets that still carry those codes.
    """
    payload = {
        "generated_at": _now(),
        "namespace": CDL_NAMESPACE,
        "vocabularies": {
            vocab: [
                {
                    "key": r.key,
                    "label": r.label,
                    "code": r.code,
                    "uri": r.uri,
                    "scheme": r.scheme,
                    "tier": r.tier,
                    "parent_key": r.parent_key,
                    "visibility": r.visibility,
                    "visible_on_platform": r.visible_on_platform,
                    "is_active": r.is_active,
                    "is_open": r.is_open,
                    "deprecated": r.deprecated,
                    "alt_codes": {k: v for k, v in r.alt_codes.items() if v},
                }
                for r in records
            ]
            for vocab, records in groups.items()
        },
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------
# --init scaffolding
# --------------------------------------------------------------------------

TEMPLATES = {
    "platform_licenses.csv": (
        "enum_value,spdx_id,key,label,is_open,notes\n"
        "GOVERNMENT_OPEN_DATA_LICENSE,,GODL-India,Government Open Data License – India,true,\n"
        "CC_BY_4_0_ATTRIBUTION,CC-BY-4.0,,Creative Commons Attribution 4.0,true,\n"
        "CC_BY_SA_4_0_ATTRIBUTION_SHARE_ALIKE,CC-BY-SA-4.0,,Creative Commons Attribution-ShareAlike 4.0,true,platform default\n"
        "OPEN_DATA_COMMONS_BY_ATTRIBUTION,ODC-By-1.0,,Open Data Commons Attribution License 1.0,true,\n"
        "OPEN_DATABASE_LICENSE,ODbL-1.0,,Open Database License 1.0,true,\n"
    ),
    "lgd_states.csv": (
        "lgd_state_code,state_name,is_union_territory,iso_3166_2,census_2011_code,"
        "wikidata_uri,deprecated,notes\n"
        "# download the State master from lgdirectory.gov.in and paste rows here\n"
    ),
    "lgd_districts.csv": (
        "lgd_district_code,district_name,lgd_state_code,census_2011_code,"
        "wikidata_uri,valid_from,valid_to,notes\n"
        "# download the District master from lgdirectory.gov.in and paste rows here\n"
        "# set valid_to on districts that have since been split or merged\n"
    ),
    "cdl_regions.csv": (
        "slug,label,un_m49,notes\n"
        "north-east-india,North East India,,no external authority covers this grouping\n"
        "southern-asia,Southern Asia,034,UN M49 region\n"
    ),
    "platform_geographies.csv": (
        "name,type\n"
        "# export from the live Geography table: SELECT name, type FROM geography;\n"
    ),
    "cdl_sectors.csv": (
        "name,slug,parent_slug,in_build,eu_data_theme,match_type,dac_crs,sdg,notes\n"
        "Child Rights,child-rights,,true,SOCI,broadMatch,16010,,\n"
        "Climate Action,climate-action,,true,ENVI,broadMatch,,13,\n"
        "Coastal,coastal,,true,ENVI,broadMatch,,14,\n"
        "Gender,gender,,true,SOCI,broadMatch,15170,5,cross-cutting; may belong as a facet\n"
        "Disaster Risk Reduction,disaster-risk-reduction,,true,ENVI,broadMatch,74020,,\n"
        "Law and Justice,law-and-justice,,true,JUST,closeMatch,,16,\n"
        "Public Finance,public-finance,,true,GOVE,closeMatch,,,\n"
        "Urban Development,urban-development,,true,REGI,closeMatch,,11,\n"
    ),
    "dac_crs.csv": (
        "code,name\n"
        "# optional: OECD DAC CRS purpose codes, for UNICEF/IATI-facing mapping\n"
    ),
    "eu_licence_nal.csv": (
        "code,spdx_id,label\n"
        "# optional: EU Publications Office Licence authority table\n"
    ),
}


def scaffold(sources_dir: str) -> None:
    os.makedirs(sources_dir, exist_ok=True)
    for name, content in TEMPLATES.items():
        path = os.path.join(sources_dir, name)
        if os.path.exists(path):
            info(f"exists, left alone: {name}")
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        info(f"wrote template: {name}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

BUILDERS = {
    "licenses": ("license", build_licenses),
    "geographies": ("geography", build_geographies),
    "sectors": ("sector", build_sectors),
}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build superset vocabularies (license, geography, sector) "
        "for the DataSpace platform."
    )
    ap.add_argument("--sources", default="./sources", help="local source files")
    ap.add_argument("--out", default="./out", help="output directory")
    ap.add_argument("--cache", default="./.vocab_cache", help="HTTP cache")
    ap.add_argument("--offline", action="store_true", help="use cache/local only")
    ap.add_argument("--init", action="store_true", help="write source templates")
    ap.add_argument(
        "--only", choices=sorted(BUILDERS), action="append",
        help="build a subset (repeatable)",
    )
    args = ap.parse_args(argv)

    if args.init:
        print(f"Scaffolding source templates in {args.sources}")
        scaffold(args.sources)
        print("\nFill these in, then re-run without --init.")
        return 0

    os.makedirs(args.out, exist_ok=True)
    fetcher = Fetcher(args.cache, offline=args.offline)
    wanted = args.only or list(BUILDERS)

    groups: Dict[str, List[VocabRecord]] = {}
    for name in wanted:
        vocab, builder = BUILDERS[name]
        print(f"\nBuilding {name}…")
        records = merge(builder(fetcher, args.sources))
        apply_visibility(records)
        groups[vocab] = records

        write_csv(os.path.join(args.out, f"{name}.csv"), records)
        pickable = [r for r in records if r.visible_on_platform]
        write_csv(os.path.join(args.out, f"{name}_pickable.csv"), pickable)

        review = sum(1 for r in records if r.needs_review)
        print(
            f"  {len(records)} rows | {len(pickable)} pickable | "
            f"{sum(1 for r in records if r.in_build)} in build | "
            f"{review} need review"
        )
        if review:
            warn(f"{review} rows flagged — see needs_review / review_reason")

    if groups:
        write_xlsx(os.path.join(args.out, "superlists.xlsx"), groups)
        write_load_manifest(os.path.join(args.out, "load_manifest.json"), groups)

    with open(os.path.join(args.out, "run_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_at": _now(),
                "offline": args.offline,
                "vocabularies": {k: len(v) for k, v in groups.items()},
                "http": fetcher.log,
            },
            fh,
            indent=2,
        )

    print(f"\nWritten to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())