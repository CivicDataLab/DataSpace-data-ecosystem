#!/usr/bin/env python3
"""
fetch-india-geographies.py
==========================

Populates the LGD source files that build-vocab-superset.py reads, so the
geography vocabulary covers India properly instead of stopping at "India".

Why this exists
---------------
lgdirectory.gov.in publishes the authoritative State / District / Subdistrict
masters but has no public API, so the superset build shipped with empty
templates and the geography list never got past 3 rows. Two sources do expose
the same codes programmatically:

    wikidata  (default)  LGD codes as properties, with a resolvable QID per
                         unit. This is the useful one: the QID is exactly the
                         canonical URI dcterms:spatial wants, which no scrape
                         of the LGD site would give you.
                             P12747  LGD State or UT Code
                             P12746  LGD District Code
                             P12748  LGD Subdistrict Code

    nic       (opt-in)   The NIC admin2024 MapServer behind the boundary
                         GeoJSONs in canonical_entities/india/maps. Queried
                         attributes-only (returnGeometry=false), it carries
                         both the LGD codes and the Census 2011 codes on the
                         same row, which is the only crosswalk between the two
                         numbering systems that we can fetch. It has no QIDs
                         and the host is frequently unreachable, so it enriches
                         the Wikidata rows rather than replacing them.

Object IDs
----------
Every unit gets an `object_id`: its LGD codes joined down the hierarchy,
following the convention already used in IDS-DRR (Maps/scripts/map_transformer.py,
which joins Census 2011 codes the same way).

    state        28
    district     28-461
    subdistrict  28-461-4850

LGD codes are unique per tier on their own, so the join is not needed for
uniqueness — it is there so an ID sorts and prefix-matches into its parent,
and so a dataset keyed on districts can be joined to one keyed on subdistricts
without a lookup table. Census 2011 codes travel alongside in their own
columns; they are a different numbering system (Andhra Pradesh is LGD 28 and
Census 37) and are never mixed into object_id.

Usage
-----
    python fetch-india-geographies.py                      # states + districts
    python fetch-india-geographies.py --tier subdistrict   # add ~7,200 rows
    python fetch-india-geographies.py --source both        # add Census crosswalk
    python fetch-india-geographies.py --dry-run

Writes sources/lgd_states.csv, lgd_districts.csv, lgd_subdistricts.csv.
Then re-run build-vocab-superset.py to fold them into the superset.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, List, Optional

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
NIC_BASE = "https://webgis1.nic.in/nicstreet/rest/services/admin2024/MapServer"
NIC_LAYER = {"district": 10, "subdistrict": 11}
NIC_PAGE_SIZE = 2000

USER_AGENT = "CivicDataSpace-vocab-builder/1.0 (https://civicdataspace.in)"
HTTP_TIMEOUT = 120

# wdt: properties carrying LGD codes, confirmed against wikidata.org.
P_LGD_STATE = "P12747"
P_LGD_DISTRICT = "P12746"
P_LGD_SUBDISTRICT = "P12748"
Q_UNION_TERRITORY = "Q467745"

TIERS = ("state", "district", "subdistrict")

OUT_FILES = {
    "state": "lgd_states.csv",
    "district": "lgd_districts.csv",
    "subdistrict": "lgd_subdistricts.csv",
}

COLUMNS = {
    "state": [
        "lgd_state_code", "state_name", "object_id", "is_union_territory",
        "iso_3166_2", "census_2011_code", "wikidata_uri", "deprecated", "notes",
    ],
    "district": [
        "lgd_district_code", "district_name", "lgd_state_code", "object_id",
        "census_2011_code", "wikidata_uri", "valid_from", "valid_to", "notes",
    ],
    "subdistrict": [
        "lgd_subdistrict_code", "subdistrict_name", "lgd_district_code",
        "lgd_state_code", "object_id", "census_2011_code", "wikidata_uri",
        "valid_from", "valid_to", "notes",
    ],
}


def info(msg: str) -> None:
    print(f"  - {msg}")


def warn(msg: str) -> None:
    print(f"  ! {msg}", file=sys.stderr)


# --------------------------------------------------------------------------
# Wikidata
# --------------------------------------------------------------------------

# A state may carry several P31 values (Delhi is both a union territory and a
# "capital district or territory"), so SAMPLE(?type) picks arbitrarily and
# mistypes it. Ask whether *any* P31 is a union territory instead.
STATE_QUERY = f"""
SELECT ?item ?itemLabel ?lgd ?iso ?isUT WHERE {{
  ?item wdt:{P_LGD_STATE} ?lgd .
  OPTIONAL {{ ?item wdt:P300 ?iso }}
  BIND(EXISTS {{ ?item wdt:P31/wdt:P279* wd:{Q_UNION_TERRITORY} }} AS ?isUT)
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""

# P131* rather than P131: a district's administrative parent is sometimes a
# division rather than the state itself, so walk up until something carries a
# state code.
DISTRICT_QUERY = f"""
SELECT ?item ?itemLabel ?lgd (SAMPLE(?stlgd) AS ?state) WHERE {{
  ?item wdt:{P_LGD_DISTRICT} ?lgd .
  OPTIONAL {{ ?item wdt:P131* ?st . ?st wdt:{P_LGD_STATE} ?stlgd . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
GROUP BY ?item ?itemLabel ?lgd
"""

SUBDISTRICT_QUERY = f"""
SELECT ?item ?itemLabel ?lgd (SAMPLE(?dtlgd) AS ?district)
       (SAMPLE(?stlgd) AS ?state) WHERE {{
  ?item wdt:{P_LGD_SUBDISTRICT} ?lgd .
  OPTIONAL {{ ?item wdt:P131* ?dt . ?dt wdt:{P_LGD_DISTRICT} ?dtlgd . }}
  OPTIONAL {{ ?item wdt:P131* ?st . ?st wdt:{P_LGD_STATE} ?stlgd . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
GROUP BY ?item ?itemLabel ?lgd
"""


def sparql(query: str) -> List[dict]:
    url = WIKIDATA_SPARQL + "?" + urllib.parse.urlencode(
        {"query": query, "format": "json"}
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        warn(f"Wikidata query failed: {exc}")
        return []
    try:
        return json.loads(body)["results"]["bindings"]
    except (json.JSONDecodeError, KeyError) as exc:
        warn(f"Wikidata response unusable: {exc}")
        return []


def _val(row: dict, key: str) -> str:
    return row.get(key, {}).get("value", "")


def _clean_label(label: str, item_uri: str) -> str:
    """Wikidata falls back to the QID when an item has no English label."""
    qid = item_uri.rsplit("/", 1)[-1]
    if label == qid:
        return ""
    # "Karauli district" / "Guwahati subdivision" read as tiers, not names.
    for suffix in (" district", " subdistrict", " subdivision", " tehsil", " taluk"):
        if label.lower().endswith(suffix):
            return label[: -len(suffix)]
    return label


def fetch_states() -> List[dict]:
    rows = sparql(STATE_QUERY)
    out = []
    for r in rows:
        code = _val(r, "lgd")
        if not code:
            continue
        is_ut = _val(r, "isUT") == "true"
        out.append(
            {
                "lgd_state_code": code,
                "state_name": _clean_label(_val(r, "itemLabel"), _val(r, "item")),
                "object_id": code,
                "is_union_territory": "true" if is_ut else "false",
                "iso_3166_2": _val(r, "iso"),
                "census_2011_code": "",
                "wikidata_uri": _val(r, "item"),
                "deprecated": "false",
                "notes": "",
            }
        )
    return sorted(out, key=lambda r: int(r["lgd_state_code"]))


def fetch_districts() -> List[dict]:
    rows = sparql(DISTRICT_QUERY)
    out = []
    for r in rows:
        code = _val(r, "lgd")
        if not code:
            continue
        state = _val(r, "state")
        out.append(
            {
                "lgd_district_code": code,
                "district_name": _clean_label(_val(r, "itemLabel"), _val(r, "item")),
                "lgd_state_code": state,
                "object_id": f"{state}-{code}" if state else code,
                "census_2011_code": "",
                "wikidata_uri": _val(r, "item"),
                "valid_from": "",
                "valid_to": "",
                "notes": "" if state else "no parent state on Wikidata",
            }
        )
    return sorted(out, key=lambda r: (r["lgd_state_code"], int(r["lgd_district_code"])))


def fetch_subdistricts() -> List[dict]:
    rows = sparql(SUBDISTRICT_QUERY)
    out = []
    for r in rows:
        code = _val(r, "lgd")
        if not code:
            continue
        state, district = _val(r, "state"), _val(r, "district")
        parts = [p for p in (state, district, code) if p]
        out.append(
            {
                "lgd_subdistrict_code": code,
                "subdistrict_name": _clean_label(_val(r, "itemLabel"), _val(r, "item")),
                "lgd_district_code": district,
                "lgd_state_code": state,
                "object_id": "-".join(parts),
                "census_2011_code": "",
                "wikidata_uri": _val(r, "item"),
                "valid_from": "",
                "valid_to": "",
                "notes": "" if (state and district) else "incomplete parentage on Wikidata",
            }
        )
    return sorted(
        out, key=lambda r: (r["lgd_state_code"], r["lgd_district_code"],
                            int(r["lgd_subdistrict_code"]))
    )


FETCHERS = {
    "state": fetch_states,
    "district": fetch_districts,
    "subdistrict": fetch_subdistricts,
}


# --------------------------------------------------------------------------
# NIC admin2024 — Census 2011 <-> LGD crosswalk
# --------------------------------------------------------------------------

# Field names as they appear in the NIC village/district attribute tables (see
# the CSVs produced by canonical_entities/india/maps/map_exporter.py). Asking
# for outFields=* and matching defensively, because the layers do not all
# carry the same set and an unknown field name fails the whole query.
NIC_FIELDS = {
    "district": {"lgd": "dist_lgd", "census": "dtcode11", "state_census": "stcode11"},
    "subdistrict": {"lgd": "subdt_lgd", "census": "sdtcode11", "state_census": "stcode11"},
}


def nic_attributes(tier: str) -> List[dict]:
    """Page through an NIC layer's attribute table, no geometry."""
    layer = NIC_LAYER.get(tier)
    if layer is None:
        return []
    url = f"{NIC_BASE}/{layer}/query"
    rows: List[dict] = []
    offset = 0
    while True:
        payload = urllib.parse.urlencode(
            {
                "f": "json",
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "false",
                "resultOffset": str(offset),
                "resultRecordCount": str(NIC_PAGE_SIZE),
            }
        ).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, TimeoutError, OSError,
                json.JSONDecodeError) as exc:
            warn(f"NIC {tier} query failed at offset {offset}: {exc}")
            return rows
        if "error" in data:
            warn(f"NIC error for {tier}: {data['error']}")
            return rows
        page = [f.get("attributes", {}) for f in data.get("features", [])]
        rows.extend(page)
        if len(page) < NIC_PAGE_SIZE:
            return rows
        offset += NIC_PAGE_SIZE
        time.sleep(0.1)


def enrich_with_census(tier: str, records: List[dict]) -> int:
    """Fill census_2011_code on rows we already have from Wikidata."""
    fields = NIC_FIELDS.get(tier)
    if not fields:
        return 0
    attrs = nic_attributes(tier)
    if not attrs:
        return 0
    code_key = {"district": "lgd_district_code",
                "subdistrict": "lgd_subdistrict_code"}[tier]
    by_lgd: Dict[str, str] = {}
    for a in attrs:
        lgd = str(a.get(fields["lgd"], "") or "").strip()
        census = str(a.get(fields["census"], "") or "").strip()
        state_census = str(a.get(fields["state_census"], "") or "").strip()
        if lgd and census:
            by_lgd[lgd] = f"{state_census}-{census}" if state_census else census
    hits = 0
    for rec in records:
        census = by_lgd.get(rec[code_key])
        if census:
            rec["census_2011_code"] = census
            hits += 1
    return hits


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def flag_duplicates(tier: str, records: List[dict]) -> int:
    """Two Wikidata items can claim the same LGD code; say so in the row.

    Real cases exist (e.g. "Anantapur mandal" and "Anantapur Rural Mandal"
    both asserting subdistrict 5330). The build merges them and raises a label
    conflict, but the source file should show the problem at its origin.
    """
    code_key = {
        "state": "lgd_state_code",
        "district": "lgd_district_code",
        "subdistrict": "lgd_subdistrict_code",
    }[tier]
    seen: Dict[str, List[dict]] = {}
    for rec in records:
        seen.setdefault(rec[code_key], []).append(rec)
    dupes = 0
    for code, group in seen.items():
        if len(group) < 2:
            continue
        dupes += 1
        names = ", ".join(sorted(r[f"{tier}_name" if tier != "state" else "state_name"]
                                 for r in group))
        for rec in group:
            rec["notes"] = (rec["notes"] + "; " if rec["notes"] else "") + (
                f"LGD code {code} claimed by {len(group)} Wikidata items: {names}"
            )
    return dupes


def write_csv(path: str, tier: str, records: List[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS[tier], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fetch India's LGD state / district / subdistrict masters "
        "into the superset's source files."
    )
    ap.add_argument("--sources", default="./sources", help="where to write")
    ap.add_argument(
        "--tier", choices=TIERS, action="append",
        help="tiers to fetch (repeatable; default: state district)",
    )
    ap.add_argument(
        "--source", choices=("wikidata", "nic", "both"), default="wikidata",
        help="'both' adds the NIC Census 2011 crosswalk where reachable",
    )
    ap.add_argument("--dry-run", action="store_true", help="fetch but do not write")
    args = ap.parse_args(argv)

    tiers = args.tier or ["state", "district"]
    os.makedirs(args.sources, exist_ok=True)

    total = 0
    for tier in TIERS:  # fixed order, so parents are fetched before children
        if tier not in tiers:
            continue
        print(f"\nFetching {tier}s from Wikidata…")
        records = FETCHERS[tier]()
        if not records:
            warn(f"no {tier} rows returned; leaving the source file alone")
            continue

        if args.source in ("nic", "both") and tier != "state":
            print(f"  cross-referencing NIC admin2024 for Census 2011 codes…")
            hits = enrich_with_census(tier, records)
            info(f"census codes: {hits}/{len(records)}")
            if not hits:
                warn(
                    "no Census 2011 crosswalk applied — webgis1.nic.in is often "
                    "unreachable; LGD codes and object_ids are unaffected"
                )

        dupes = flag_duplicates(tier, records)
        orphans = sum(1 for r in records if "no parent" in r["notes"]
                      or "incomplete" in r["notes"])
        print(
            f"  {len(records)} rows | {orphans} with incomplete parentage | "
            f"{dupes} duplicated LGD codes"
        )
        if dupes:
            warn(f"{dupes} LGD codes are claimed by more than one Wikidata item")

        if args.dry_run:
            info("dry run, nothing written")
        else:
            path = os.path.join(args.sources, OUT_FILES[tier])
            write_csv(path, tier, records)
            info(f"wrote {path}")
        total += len(records)

    print(f"\n{total} rows. Re-run build-vocab-superset.py to rebuild the superset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
