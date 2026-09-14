#!/usr/bin/env python3
"""
Convert a CivicDataSpace dataset's metadata into DCAT v3 JSON-LD or Croissant JSON-LD, using
the field mapping recorded in mapping.yaml (the metadata supermodel reference in this folder).

Usage:
    python convert.py dcat dataset.json
    python convert.py croissant dataset.json
    python convert.py gaps dataset.json
    python convert.py gaps dataset.json --standard croissant

dataset.json is a single dataset's metadata in the shape CivicDataSpace/cds-audit already use
(see example_dataset.json in this folder): a flat object with the fields listed under
`dataspace_metadata_fields` in mapping.yaml (title, description, organization, user, license,
created, modified, tags, sectors, geographies, formats, resources[]).

`gaps` reports, for one dataset, which of its populated fields have no "exact" match to the
target standard (--standard dcat|croissant, default dcat) — i.e. what would be lossy or
require manual handling if this dataset were published as DCAT / Croissant metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
MAPPING_PATH = SCRIPT_DIR / "mapping.yaml"


def load_mapping(path: Path = MAPPING_PATH) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def field_rows(mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rows of dataspace_dcat_croissant_mapping that are tied to a named CivicDataSpace field."""
    return [r for r in mapping["dataspace_dcat_croissant_mapping"] if r.get("dataspace_field")]


def _first_geography(dataset: Dict[str, Any]) -> Optional[str]:
    geos = dataset.get("geographies") or []
    for g in geos:
        name = g.get("name") if isinstance(g, dict) else g
        if name:
            return name
    return None


# ------------------------------------------------------------------ DCAT v3 JSON-LD
def to_dcat_jsonld(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Map a CivicDataSpace dataset onto a DCAT v3 dcat:Dataset, per the 'exact'/'partial' rows
    of dataspace_dcat_croissant_mapping. Fields with no DCAT equivalent are dropped."""
    out: Dict[str, Any] = {
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
        },
        "@type": "dcat:Dataset",
    }
    if dataset.get("id") is not None:
        out["dct:identifier"] = str(dataset["id"])
    if dataset.get("title"):
        out["dct:title"] = dataset["title"]
    if dataset.get("description"):
        out["dct:description"] = dataset["description"]
    if dataset.get("organization"):
        out["dct:publisher"] = dataset["organization"]
    if dataset.get("user"):
        out["dct:creator"] = dataset["user"]
    if dataset.get("license"):
        out["dct:license"] = dataset["license"]
    if dataset.get("created"):
        out["dct:issued"] = dataset["created"]
    if dataset.get("modified"):
        out["dct:modified"] = dataset["modified"]
    geography = _first_geography(dataset)
    if geography:
        out["dcterms:spatial"] = geography
    if dataset.get("sectors"):
        out["dcat:theme"] = list(dataset["sectors"])
    if dataset.get("tags"):
        out["dcat:keyword"] = list(dataset["tags"])

    distributions = []
    for resource in dataset.get("resources") or []:
        dist: Dict[str, Any] = {"@type": "dcat:Distribution"}
        if resource.get("download_url"):
            dist["dcat:downloadURL"] = resource["download_url"]
        if resource.get("format"):
            dist["dct:format"] = resource["format"]
        if resource.get("size") is not None:
            dist["dcat:byteSize"] = resource["size"]
        distributions.append(dist)
    if distributions:
        out["dcat:distribution"] = distributions

    return out


# ---------------------------------------------------------------- Croissant JSON-LD
def to_croissant_jsonld(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Map a CivicDataSpace dataset onto a Croissant Dataset, per the 'exact'/'partial' rows
    of dataspace_dcat_croissant_mapping. Croissant-only concepts (RecordSet, Field, etc.) are
    not populated here since CivicDataSpace has no source data for them (see the 'gap' rows)."""
    out: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Dataset",
    }
    if dataset.get("id") is not None:
        out["identifier"] = str(dataset["id"])
    if dataset.get("title"):
        out["name"] = dataset["title"]
    if dataset.get("description"):
        out["description"] = dataset["description"]
    # Per mapping.yaml: organization -> creator, user -> publisher on the Croissant side.
    if dataset.get("organization"):
        out["creator"] = dataset["organization"]
    if dataset.get("user"):
        out["publisher"] = dataset["user"]
    if dataset.get("license"):
        out["license"] = dataset["license"]
    if dataset.get("created"):
        out["datePublished"] = dataset["created"]
    if dataset.get("modified"):
        out["dateModified"] = dataset["modified"]
    if dataset.get("tags"):
        out["keywords"] = list(dataset["tags"])

    file_objects = []
    for resource in dataset.get("resources") or []:
        obj: Dict[str, Any] = {"@type": "cr:FileObject"}
        if resource.get("id") is not None:
            obj["@id"] = str(resource["id"])
        if resource.get("download_url"):
            obj["contentUrl"] = resource["download_url"]
        if resource.get("format"):
            obj["encodingFormat"] = resource["format"]
        if resource.get("size") is not None:
            obj["contentSize"] = resource["size"]
        file_objects.append(obj)
    if file_objects:
        out["distribution"] = file_objects

    return out


# ------------------------------------------------------------------------ Gaps
def report_gaps(dataset: Dict[str, Any], mapping: Dict[str, Any], standard: str) -> List[Dict[str, Any]]:
    """For each populated field on `dataset`, look up its match_type against `standard`
    (dcat or croissant) and return the ones that are not an exact match."""
    if standard not in ("dcat", "croissant"):
        raise ValueError(f"standard must be 'dcat' or 'croissant', got {standard!r}")

    by_field = {r["dataspace_field"]: r for r in field_rows(mapping)}
    findings = []
    for field, value in dataset.items():
        if value in (None, "", [], {}):
            continue
        row = by_field.get(field)
        if row is None:
            findings.append({"field": field, "match_type": "not_in_supermodel", "notes": None})
            continue
        target = row.get(standard)
        match_type = row["match_type"] if target or row["match_type"] in ("gap", "unmappable") else "gap"
        if match_type != "exact":
            findings.append({
                "field": field,
                "match_type": match_type,
                standard: target,
                "notes": row.get("notes"),
            })
    return findings


# --------------------------------------------------------------------------- CLI
def _load_dataset(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("dcat", "croissant"):
        p = sub.add_parser(name, help=f"Emit {name} JSON-LD for a dataset")
        p.add_argument("dataset_json", type=Path)

    p = sub.add_parser("gaps", help="Report fields that don't map exactly onto a standard")
    p.add_argument("dataset_json", type=Path)
    p.add_argument("--standard", choices=["dcat", "croissant"], default="dcat")

    args = parser.parse_args(argv)
    mapping = load_mapping()
    dataset = _load_dataset(args.dataset_json)

    if args.command == "dcat":
        print(json.dumps(to_dcat_jsonld(dataset), indent=2, ensure_ascii=False))
    elif args.command == "croissant":
        print(json.dumps(to_croissant_jsonld(dataset), indent=2, ensure_ascii=False))
    elif args.command == "gaps":
        findings = report_gaps(dataset, mapping, args.standard)
        print(json.dumps(findings, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
