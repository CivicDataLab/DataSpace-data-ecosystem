#!/usr/bin/env python3
"""
build-metadata-superset.py
==========================

Builds the metadata *field* superset: one row per canonical concept, with how
each supported standard spells it, and the flags an import/export function
needs to decide what to do with it.

This is the field-level sibling of ../../metadata-superset/, which builds the
*value* lists behind the three fixed-entry fields. That one answers "which
licences may a dataset claim"; this one answers "what may you say about a
dataset at all, and how does each standard say it".

Inputs
------
    concepts.yaml        the concept spine - one entry per thing you can say
    standards/*.yaml     one file per standard, binding concepts to properties
    ../DataSpace Metadata_Croissant_DCAT_mapping.xlsx
                         the source workbook, used only to check coverage:
                         any property it mentions that no standard file binds
                         is reported, so the superset cannot silently drift
                         behind the sheet it came from

Adding a standard is one new file in standards/. Nothing else changes.

Outputs (to --out, default ./out)
---------------------------------
    metadata_field_superset.csv   the superset, one row per concept, one
                                  column group per standard. Review artifact.
    crosswalk.json                the machine-readable contract: per standard,
                                  an export list and an import index, plus the
                                  concept model and the declared gaps. This is
                                  the file import/export code should load.
    run_manifest.json             counts, coverage, and what the workbook check
                                  turned up

Usage
-----
    python build-metadata-superset.py
    python build-metadata-superset.py --strict     # non-zero exit on any warning
    python build-metadata-superset.py --no-workbook-check
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit("Missing dependency: PyYAML. Install with: pip install pyyaml")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKBOOK = os.path.join(
    SCRIPT_DIR, os.pardir, "DataSpace Metadata_Croissant_DCAT_mapping.xlsx"
)

# Where the fixed-entry value lists live, for concepts that carry a
# controlled_vocabulary. Relative to this script.
VOCAB_DIR = os.path.join(os.pardir, os.pardir, "metadata-superset", "out")
VOCAB_FILES = {
    "license": "licenses.csv",
    "geography": "geographies.csv",
    "sector": "sectors.csv",
}

VALUE_TYPES = {
    "literal": "A plain string.",
    "langstring": "A string that may carry a language tag.",
    "date": "ISO 8601 date (xsd:date).",
    "datetime": "ISO 8601 datetime (xsd:dateTime).",
    "uri": "An absolute URI, serialised as a node reference not a string.",
    "number": "A numeric literal.",
    "bytes": "A non-negative integer count of bytes.",
    "duration": "ISO 8601 duration (xsd:duration).",
    "media_type": "An IANA media type, or a format token where none exists.",
    "agent": "A person or organisation; a node with at least a name.",
    "concept": "A term from a controlled scheme; prefer its URI.",
    "location": "A place; prefer a resolvable URI over a name string.",
    "period": "A time interval, expressed as start and end.",
    "frequency": "A term from the Dublin Core Frequency vocabulary.",
    "checksum": "A hash digest, with its algorithm.",
    "vcard": "A contact, serialised as a vCard node.",
    "structured": "A nested object whose shape the standard defines.",
}

NODES = {"dataset", "distribution", "contact_point", "record_set", "period"}
DIRECTIONS = {"both", "export_only", "import_only", "none"}
OBLIGATIONS = {"mandatory", "recommended", "optional"}
INPUT_TYPES = {"automated", "free_text", "controlled", "semi_controlled", None}
MATCHES = {"exact", "partial", "gap"}

# Concept attributes a binding may override for its own standard.
OVERRIDABLE = ("node", "value_type", "repeatable", "obligation")


class Problems:
    """Collects errors and warnings so one run reports everything, not the first."""

    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def report(self) -> None:
        for w in self.warnings:
            print(f"  ! {w}", file=sys.stderr)
        for e in self.errors:
            print(f"  ERROR {e}", file=sys.stderr)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def info(msg: str) -> None:
    print(f"  - {msg}")


# --------------------------------------------------------------------------
# Load and validate
# --------------------------------------------------------------------------


def load_concepts(path: str, p: Problems) -> Dict[str, dict]:
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    concepts: Dict[str, dict] = {}
    for entry in doc.get("concepts", []):
        key = entry.get("key")
        if not key:
            p.error(f"concept with no key: {entry!r}")
            continue
        if key in concepts:
            p.error(f"duplicate concept key '{key}'")
            continue
        entry.setdefault("repeatable", False)
        entry.setdefault("direction", "both")
        entry.setdefault("obligation", "optional")
        entry.setdefault("controlled_vocabulary", None)
        entry.setdefault("notes", None)
        # visible_on_dataspace is written "yes"/"no" in YAML so the column and
        # the file agree; normalise once, here.
        entry["visible_on_dataspace"] = str(
            entry.get("visible_on_dataspace", "no")
        ).strip().lower() in {"yes", "true", "y"}

        if entry.get("node") not in NODES:
            p.error(f"{key}: unknown node '{entry.get('node')}'")
        if entry.get("value_type") not in VALUE_TYPES:
            p.error(f"{key}: unknown value_type '{entry.get('value_type')}'")
        if entry["direction"] not in DIRECTIONS:
            p.error(f"{key}: unknown direction '{entry['direction']}'")
        if entry["obligation"] not in OBLIGATIONS:
            p.error(f"{key}: unknown obligation '{entry['obligation']}'")
        if entry.get("dataspace_input_type") not in INPUT_TYPES:
            p.error(
                f"{key}: unknown dataspace_input_type "
                f"'{entry.get('dataspace_input_type')}'"
            )
        if entry["controlled_vocabulary"] and entry["controlled_vocabulary"] not in VOCAB_FILES:
            p.error(
                f"{key}: controlled_vocabulary '{entry['controlled_vocabulary']}' "
                f"is not one of {sorted(VOCAB_FILES)}"
            )
        # A concept the platform cannot supply cannot be exported from it.
        if not entry.get("dataspace_field") and entry["direction"] in {"both", "export_only"}:
            if entry["direction"] == "export_only":
                p.warn(
                    f"{key}: direction=export_only but no dataspace_field - "
                    "the export must construct this value itself"
                )
        concepts[key] = entry
    return concepts


def load_standards(dirname: str, concepts: Dict[str, dict], p: Problems) -> Dict[str, dict]:
    standards: Dict[str, dict] = {}
    for name in sorted(os.listdir(dirname)):
        if not name.endswith((".yaml", ".yml")):
            continue
        with open(os.path.join(dirname, name), encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        sid = doc.get("id")
        if not sid:
            p.error(f"{name}: no id")
            continue
        node_types = doc.get("node_types") or {}
        bindings = doc.get("bindings") or {}
        for ckey, binding in bindings.items():
            if ckey not in concepts:
                p.error(f"{sid}: binding for unknown concept '{ckey}'")
                continue
            match = binding.get("match")
            if match not in MATCHES:
                p.error(f"{sid}.{ckey}: unknown match '{match}'")
            if match == "gap":
                if binding.get("property"):
                    p.error(f"{sid}.{ckey}: match=gap but a property is given")
                continue
            if not binding.get("property"):
                p.error(f"{sid}.{ckey}: match={match} but no property")
            node = binding.get("node") or concepts[ckey]["node"]
            # A period node is nested inside its parent, so it needs no @type
            # of its own; anything else must be a node this standard declares.
            if node not in node_types and node != "period":
                p.error(
                    f"{sid}.{ckey}: node '{node}' has no entry in node_types "
                    f"({sorted(node_types)})"
                )
            if binding.get("value_type") and binding["value_type"] not in VALUE_TYPES:
                p.error(f"{sid}.{ckey}: unknown value_type '{binding['value_type']}'")
        standards[sid] = doc
    return standards


# --------------------------------------------------------------------------
# Resolve: concept + binding -> one effective row
# --------------------------------------------------------------------------


def resolve(concept: dict, binding: Optional[dict]) -> dict:
    """Merge a binding over its concept. Absent binding fields inherit."""
    out = {k: concept.get(k) for k in OVERRIDABLE}
    out["match"] = binding.get("match") if binding else None
    out["property"] = binding.get("property") if binding else None
    out["parent_property"] = binding.get("parent_property") if binding else None
    out["notes"] = binding.get("notes") if binding else None
    if binding:
        for k in OVERRIDABLE:
            if binding.get(k) is not None:
                out[k] = binding[k]
    return out


# --------------------------------------------------------------------------
# Workbook coverage check
# --------------------------------------------------------------------------

PROPERTY_RE = re.compile(r"\b(dct|dcterms|dcat|dcatin|foaf|vcard|prov|owl|skos):\s?([A-Za-z][\w-]*)")

# Prefix spellings that mean the same property. The workbook uses dct: and
# dcterms: interchangeably; the superset standardises on dcterms:.
PREFIX_ALIASES = {"dct": "dcterms"}


def workbook_properties(path: str, p: Problems) -> Set[str]:
    try:
        import openpyxl
    except ImportError:
        p.warn("openpyxl not installed; skipping the workbook coverage check")
        return set()
    if not os.path.exists(path):
        p.warn(f"workbook not found at {path}; skipping coverage check")
        return set()
    wb = openpyxl.load_workbook(path, data_only=True)
    found: Set[str] = set()
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if not isinstance(cell, str):
                    continue
                for prefix, local in PROPERTY_RE.findall(cell):
                    found.add(f"{PREFIX_ALIASES.get(prefix, prefix)}:{local}")
    return found


def normalise_property(prop: str) -> str:
    if ":" not in prop:
        return prop
    prefix, local = prop.split(":", 1)
    return f"{PREFIX_ALIASES.get(prefix, prefix)}:{local.strip()}"


def _is_class_name(prop: str) -> bool:
    """RDF classes are CapitalCase, properties lowerCamelCase.

    The workbook names classes (dcat:Dataset, foaf:Agent, skos:Concept) in the
    same columns as properties. Classes are expressed here through node_types
    and value_type, not bindings, so they are not missing coverage.
    """
    local = prop.split(":", 1)[-1]
    return bool(local) and local[0].isupper()


def unbound_workbook_properties(mentioned: Set[str], bound: Set[str]) -> List[str]:
    """What the workbook names that no standard file binds.

    Matched case-insensitively first: the workbook writes dcat:ByteSize and
    dcat:Keywords for dcat:byteSize and dcat:keyword, and those are bound, not
    missing. What survives is either a real gap or a typo worth seeing.
    """
    bound_ci = {b.lower() for b in bound}
    out = []
    for prop in sorted(mentioned):
        if prop.lower() in bound_ci:
            continue
        if _is_class_name(prop):
            continue
        out.append(prop)
    return out


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

BASE_COLUMNS = [
    "concept", "label", "node", "value_type", "repeatable", "obligation",
    "visible_on_dataspace", "dataspace_field", "dataspace_input_type",
    "controlled_vocabulary", "direction", "definition", "notes",
]


def write_superset_csv(
    path: str, concepts: Dict[str, dict], standards: Dict[str, dict]
) -> List[str]:
    sids = sorted(standards)
    columns = BASE_COLUMNS + [
        f"{sid}_{suffix}" for sid in sids for suffix in ("property", "match")
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for key, concept in concepts.items():
            row = {
                "concept": key,
                "label": concept.get("label", ""),
                "node": concept.get("node", ""),
                "value_type": concept.get("value_type", ""),
                "repeatable": "yes" if concept.get("repeatable") else "no",
                "obligation": concept.get("obligation", ""),
                "visible_on_dataspace": "yes" if concept["visible_on_dataspace"] else "no",
                "dataspace_field": concept.get("dataspace_field") or "",
                "dataspace_input_type": concept.get("dataspace_input_type") or "",
                "controlled_vocabulary": concept.get("controlled_vocabulary") or "",
                "direction": concept.get("direction", ""),
                "definition": concept.get("definition", ""),
                "notes": (concept.get("notes") or "").strip(),
            }
            for sid in sids:
                binding = (standards[sid].get("bindings") or {}).get(key)
                eff = resolve(concept, binding)
                row[f"{sid}_property"] = eff["property"] or ""
                # No binding at all is an unstated gap; say so in the column
                # rather than leaving a blank that reads as "not checked".
                row[f"{sid}_match"] = eff["match"] or "unbound"
            writer.writerow(row)
    return columns


def build_crosswalk(
    concepts: Dict[str, dict], standards: Dict[str, dict], p: Problems
) -> dict:
    """The contract import/export code loads.

    Per standard: an `export` list (walk it, emit each entry) and an `import`
    index keyed by property (look the incoming key up, get the concept and the
    platform field to write). Gaps and coverage are carried so a caller can
    warn about what it is dropping.
    """
    out_standards: Dict[str, dict] = {}
    for sid, doc in sorted(standards.items()):
        bindings = doc.get("bindings") or {}
        export: List[dict] = []
        import_index: Dict[str, Dict[str, List[dict]]] = {}
        gaps: List[dict] = []
        coverage = {"exact": 0, "partial": 0, "gap": 0, "unbound": 0}

        for key, concept in concepts.items():
            binding = bindings.get(key)
            if binding is None:
                coverage["unbound"] += 1
                gaps.append({"concept": key, "reason": "unbound", "notes": None})
                continue
            eff = resolve(concept, binding)
            if eff["match"] == "gap":
                coverage["gap"] += 1
                gaps.append(
                    {"concept": key, "reason": "declared gap", "notes": eff["notes"]}
                )
                continue
            coverage[eff["match"]] += 1

            entry = {
                "concept": key,
                "property": eff["property"],
                "node": eff["node"],
                "parent_property": eff["parent_property"],
                "value_type": eff["value_type"],
                "repeatable": bool(eff["repeatable"]),
                "obligation": eff["obligation"],
                "match": eff["match"],
                "dataspace_field": concept.get("dataspace_field"),
                "controlled_vocabulary": concept.get("controlled_vocabulary"),
                "notes": eff["notes"],
            }
            if concept["direction"] in {"both", "export_only"}:
                export.append(entry)
            # export_only concepts are indexed too, so an importer can tell
            # "this property is ours but we refuse to overwrite it" from
            # "we have never heard of this property". Only direction=none is
            # left out entirely.
            if concept["direction"] != "none":
                import_index.setdefault(eff["node"], {}).setdefault(
                    normalise_property(eff["property"]), []
                ).append(entry)

        # One property carrying two concepts is legitimate (Dublin Core puts
        # keyword and theme both on dcterms:subject) but it means an importer
        # cannot tell them apart. Flag it here so the caller sees it in the
        # data rather than discovering it in production.
        for node, props in import_index.items():
            for prop, entries in props.items():
                if len(entries) > 1:
                    p.warn(
                        f"{sid}: '{prop}' on {node} imports to {len(entries)} "
                        f"concepts ({', '.join(e['concept'] for e in entries)}) "
                        "- ambiguous on import"
                    )

        out_standards[sid] = {
            "name": doc.get("name"),
            "version": doc.get("version"),
            "url": doc.get("url"),
            "serialisation": doc.get("serialisation"),
            "uri_style": doc.get("uri_style", "node"),
            "context": doc.get("context") or {},
            "node_types": doc.get("node_types") or {},
            "export": export,
            "import": import_index,
            "gaps": gaps,
            "coverage": coverage,
        }

    platform_fields: Dict[str, str] = {}
    for key, concept in concepts.items():
        field = concept.get("dataspace_field")
        if field:
            platform_fields.setdefault(field, key)

    return {
        "generated_at": _now(),
        "version": 1,
        "value_types": VALUE_TYPES,
        "nodes": sorted(NODES),
        "directions": {
            "both": "Read on import, write on export.",
            "export_only": "Platform-derived. Emit it; never let an import overwrite it.",
            "import_only": "Accept from a source; the platform does not re-emit it.",
            "none": "Platform-internal. Not metadata; ignore in both directions.",
        },
        "controlled_vocabularies": {
            name: {
                "path": os.path.normpath(os.path.join(VOCAB_DIR, filename)),
                "key_field": "key",
                "uri_field": "uri",
                "visibility_field": "visible_on_dataspace",
            }
            for name, filename in VOCAB_FILES.items()
        },
        "concepts": {
            key: {
                "label": c.get("label"),
                "definition": c.get("definition"),
                "node": c.get("node"),
                "value_type": c.get("value_type"),
                "repeatable": bool(c.get("repeatable")),
                "obligation": c.get("obligation"),
                "dataspace_field": c.get("dataspace_field"),
                "dataspace_input_type": c.get("dataspace_input_type"),
                "visible_on_dataspace": c["visible_on_dataspace"],
                "controlled_vocabulary": c.get("controlled_vocabulary"),
                "direction": c.get("direction"),
                "notes": (c.get("notes") or "").strip() or None,
            }
            for key, c in concepts.items()
        },
        "platform_fields": platform_fields,
        "standards": out_standards,
    }


def check_csv_edits(path: str, concepts: Dict[str, dict], p: Problems) -> None:
    """concepts.yaml owns visible_on_dataspace; the CSV is derived.

    Unlike the value superset - where the CSV is the edit surface because it
    has thousands of rows - the concept spine is hand-authored YAML carrying
    definitions and notes. Writing an edit back would destroy those comments,
    so instead an edit is detected and reported with the change to make.
    """
    if not os.path.exists(path):
        return
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            key = row.get("concept")
            if key not in concepts:
                continue
            was = str(row.get("visible_on_dataspace", "")).strip().lower() == "yes"
            now = concepts[key]["visible_on_dataspace"]
            if was != now:
                p.warn(
                    f"{key}: visible_on_dataspace was edited to "
                    f"'{'yes' if was else 'no'}' in the CSV, which is generated. "
                    f"Set visible_on_dataspace: \"{'yes' if was else 'no'}\" on "
                    f"'{key}' in concepts.yaml instead - the CSV edit is about "
                    "to be overwritten."
                )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build the metadata field superset and the import/export crosswalk."
    )
    ap.add_argument("--concepts", default=os.path.join(SCRIPT_DIR, "concepts.yaml"))
    ap.add_argument("--standards", default=os.path.join(SCRIPT_DIR, "standards"))
    ap.add_argument("--out", default=os.path.join(SCRIPT_DIR, "out"))
    ap.add_argument("--workbook", default=WORKBOOK)
    ap.add_argument(
        "--no-workbook-check", action="store_true",
        help="skip checking the superset against the source spreadsheet",
    )
    ap.add_argument(
        "--strict", action="store_true", help="exit non-zero if anything was flagged"
    )
    args = ap.parse_args(argv)

    p = Problems()
    os.makedirs(args.out, exist_ok=True)

    print("Loading concepts…")
    concepts = load_concepts(args.concepts, p)
    info(f"{len(concepts)} concepts")

    print("Loading standards…")
    standards = load_standards(args.standards, concepts, p)
    info(f"{len(standards)} standards: {', '.join(sorted(standards))}")

    csv_path = os.path.join(args.out, "metadata_field_superset.csv")
    check_csv_edits(csv_path, concepts, p)

    if p.errors:
        p.report()
        print(f"\n{len(p.errors)} error(s); nothing written.", file=sys.stderr)
        return 1

    crosswalk = build_crosswalk(concepts, standards, p)

    # --- workbook coverage -------------------------------------------------
    unbound_in_workbook: List[str] = []
    if not args.no_workbook_check:
        print("Checking against the source workbook…")
        bound = {
            normalise_property(e["property"])
            for s in crosswalk["standards"].values()
            for e in s["export"]
        } | {
            prop
            for s in crosswalk["standards"].values()
            for props in s["import"].values()
            for prop in props
        }
        mentioned = workbook_properties(args.workbook, p)
        unbound_in_workbook = unbound_workbook_properties(mentioned, bound)
        info(f"{len(mentioned)} properties mentioned in the workbook")
        if unbound_in_workbook:
            p.warn(
                f"{len(unbound_in_workbook)} workbook properties are bound to no "
                f"concept: {', '.join(unbound_in_workbook)}"
            )

    # --- write -------------------------------------------------------------
    write_superset_csv(csv_path, concepts, standards)
    with open(os.path.join(args.out, "crosswalk.json"), "w", encoding="utf-8") as fh:
        json.dump(crosswalk, fh, indent=2, ensure_ascii=False)

    print()
    for sid, s in sorted(crosswalk["standards"].items()):
        c = s["coverage"]
        print(
            f"  {sid:14} {c['exact']:3} exact | {c['partial']:3} partial | "
            f"{c['gap'] + c['unbound']:3} gap | "
            f"{len(s['export']):3} exportable | "
            f"{sum(len(v) for v in s['import'].values()):3} recognised on import"
        )

    visible = sum(1 for c in concepts.values() if c["visible_on_dataspace"])
    platform = sum(1 for c in concepts.values() if c.get("dataspace_field"))
    print(
        f"\n  {len(concepts)} concepts | {platform} have a platform field | "
        f"{visible} visible on DataSpace"
    )

    with open(os.path.join(args.out, "run_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_at": _now(),
                "concepts": len(concepts),
                "concepts_with_platform_field": platform,
                "concepts_visible_on_dataspace": visible,
                "standards": {
                    sid: s["coverage"] for sid, s in crosswalk["standards"].items()
                },
                "workbook_properties_unbound": unbound_in_workbook,
                "warnings": p.warnings,
            },
            fh,
            indent=2,
        )

    if p.warnings:
        print()
        p.report()
    print(f"\nWritten to {args.out}")
    return 1 if (args.strict and p.warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
