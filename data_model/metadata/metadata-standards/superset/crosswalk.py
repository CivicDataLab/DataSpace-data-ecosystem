#!/usr/bin/env python3
"""
crosswalk.py
============

Reference implementation of import and export driven entirely by
out/crosswalk.json. No standard is named in this file — adding a standard to
standards/ and re-running the build is enough for `export(ds, "<new>")` to
work.

It exists for two reasons: to give a backend developer something to read and
port, and to keep the crosswalk honest. A binding that cannot be walked
mechanically is a binding that is under-specified, and this file is where that
shows up.

    from crosswalk import Crosswalk

    cw = Crosswalk.load()
    doc = cw.export(dataset, "dcat")             # platform dict -> JSON-LD
    dataset, report = cw.import_(doc, "dcat")    # JSON-LD -> platform dict

The platform dict is the flat shape CivicDataSpace and cds-audit already use
(see ../example_dataset.json): dataset fields at the top level, files under
`resources`, each with download_url / format / size / name.

What this deliberately does not do
----------------------------------
  * resolve controlled values. license, sectors and geographies must be looked
    up in ../../metadata-superset/out/*.csv and emitted as URIs. Where a value
    has not been resolved, export leaves it as the string it was given and
    records an entry in the report — it does not silently ship a name string
    where the standard requires a URI.
  * validate obligations. `report["missing_mandatory"]` lists what a profile
    would reject; enforcing that is the caller's policy decision.
  * handle the structured ML concepts (record_set, field, transform). They are
    import-only gaps against the platform today; when the platform grows a
    data dictionary, they become real and need their own walker.

Usage
-----
    python crosswalk.py export dcat ../example_dataset.json
    python crosswalk.py import dcat exported.json
    python crosswalk.py gaps croissant
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CROSSWALK_PATH = os.path.join(SCRIPT_DIR, "out", "crosswalk.json")

# Value types whose value is a reference to a thing, not a literal. How they
# are written depends on the standard's uri_style.
REFERENCE_TYPES = {"uri", "location", "concept", "agent"}

# Value types that must carry a resolvable URI to be worth anything. Emitting
# a bare name string here is the exact failure the vocabulary superset exists
# to prevent, so it is reported rather than passed through quietly.
MUST_RESOLVE = {"uri", "location", "concept"}


def _is_uri(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(
        ("http://", "https://", "urn:", "mailto:", "doi:")
    )


class Crosswalk:
    def __init__(self, data: dict):
        self.data = data
        self.concepts: Dict[str, dict] = data["concepts"]
        self.standards: Dict[str, dict] = data["standards"]

    @classmethod
    def load(cls, path: str = CROSSWALK_PATH) -> "Crosswalk":
        if not os.path.exists(path):
            raise SystemExit(
                f"{path} not found — run build-metadata-superset.py first."
            )
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh))

    def standard(self, sid: str) -> dict:
        if sid not in self.standards:
            raise SystemExit(
                f"unknown standard '{sid}'. Known: {', '.join(sorted(self.standards))}"
            )
        return self.standards[sid]

    # ------------------------------------------------------------- export
    def export(self, dataset: dict, sid: str) -> dict:
        """Platform dict -> a JSON-LD document in the given standard."""
        std = self.standard(sid)
        doc, report = self._export(dataset, std)
        doc["_report"] = report
        return doc

    def export_with_report(self, dataset: dict, sid: str) -> Tuple[dict, dict]:
        return self._export(dataset, self.standard(sid))

    def _export(self, dataset: dict, std: dict) -> Tuple[dict, dict]:
        node_types = std["node_types"]
        uri_style = std.get("uri_style", "node")

        doc: Dict[str, Any] = {"@context": std["context"]}
        if "dataset" in node_types:
            doc["@type"] = node_types["dataset"]

        report = {
            "dropped": [],            # concept had a value, standard has no binding
            "unresolved": [],         # needs a URI, got a name string
            "missing_mandatory": [],  # standard wants it, platform had nothing
        }

        # Entries that nest inside another property (a period, a vCard address)
        # are collected per parent and attached once at the end.
        nested: Dict[Tuple[str, str], Dict[str, Any]] = {}

        by_node: Dict[str, List[dict]] = {}
        for entry in std["export"]:
            by_node.setdefault(entry["node"], []).append(entry)

        # --- dataset-level and anything nested under it ---------------------
        for entry in by_node.get("dataset", []) + by_node.get("period", []):
            value = self._platform_value(dataset, entry)
            if value in (None, "", [], {}):
                if entry["obligation"] == "mandatory":
                    report["missing_mandatory"].append(entry["concept"])
                continue
            rendered = self._render(value, entry, uri_style, report)
            if entry.get("parent_property"):
                nested.setdefault(("dataset", entry["parent_property"]), {})[
                    entry["property"]
                ] = rendered
            else:
                doc[entry["property"]] = rendered

        for (owner, parent_property), payload in nested.items():
            if owner == "dataset":
                doc[parent_property] = payload

        # --- distributions --------------------------------------------------
        dist_entries = by_node.get("distribution", [])
        link = next(
            (e for e in std["export"] if e["concept"] == "distribution"), None
        )
        if dist_entries and link:
            distributions = []
            for resource in dataset.get("resources") or []:
                dist: Dict[str, Any] = {}
                if "distribution" in node_types:
                    dist["@type"] = node_types["distribution"]
                for entry in dist_entries:
                    if entry["concept"] == "distribution":
                        continue
                    value = resource.get(entry["dataspace_field"])
                    # DCAT requires accessURL on every Distribution; the
                    # platform only stores a download URL, so fall back to it
                    # rather than emitting an invalid Distribution.
                    if value in (None, "") and entry["concept"] == "access_url":
                        value = resource.get("download_url")
                    if value in (None, "", [], {}):
                        if entry["obligation"] == "mandatory":
                            report["missing_mandatory"].append(
                                f"{entry['concept']} (distribution)"
                            )
                        continue
                    dist[entry["property"]] = self._render(
                        value, entry, uri_style, report
                    )
                if len(dist) > (1 if "@type" in dist else 0):
                    distributions.append(dist)
            if distributions:
                doc[link["property"]] = distributions

        # --- what this standard cannot carry --------------------------------
        for gap in std["gaps"]:
            concept = self.concepts.get(gap["concept"], {})
            field = concept.get("dataspace_field")
            if field and dataset.get(field) not in (None, "", [], {}):
                report["dropped"].append(
                    {
                        "concept": gap["concept"],
                        "dataspace_field": field,
                        "reason": gap.get("notes") or gap["reason"],
                    }
                )

        return doc, report

    def _platform_value(self, dataset: dict, entry: dict) -> Any:
        field = entry.get("dataspace_field")
        if not field:
            return None
        value = dataset.get(field)
        if value in (None, "", [], {}):
            return None
        if not entry["repeatable"] and isinstance(value, list):
            value = value[0] if value else None
        return value

    def _render(
        self, value: Any, entry: dict, uri_style: str, report: dict
    ) -> Any:
        vtype = entry["value_type"]

        if isinstance(value, list):
            return [self._render_one(v, entry, vtype, uri_style, report) for v in value]
        rendered = self._render_one(value, entry, vtype, uri_style, report)
        return [rendered] if entry["repeatable"] else rendered

    def _render_one(
        self, value: Any, entry: dict, vtype: str, uri_style: str, report: dict
    ) -> Any:
        # The platform stores geographies as {"name": ..., "type": ...}.
        if isinstance(value, dict):
            value = value.get("uri") or value.get("name") or value.get("label")

        if vtype in MUST_RESOLVE and not _is_uri(value):
            report["unresolved"].append(
                {
                    "concept": entry["concept"],
                    "value": value,
                    "vocabulary": entry.get("controlled_vocabulary"),
                    "expected": f"{vtype} — a resolvable URI",
                }
            )
            return value  # emit what we have; the report says it is not a URI

        if vtype in REFERENCE_TYPES and uri_style == "node" and _is_uri(value):
            return {"@id": value}
        if vtype == "bytes":
            try:
                return int(value)
            except (TypeError, ValueError):
                return value
        return value

    # ------------------------------------------------------------- import
    def import_(self, document: dict, sid: str) -> Tuple[dict, dict]:
        """A JSON-LD document in the given standard -> platform dict."""
        std = self.standard(sid)
        index = std["import"]
        dataset: Dict[str, Any] = {}
        report = {"ignored": [], "no_platform_field": [], "export_only_skipped": []}

        def take(node_key: str, payload: dict, target: dict) -> None:
            props = index.get(node_key, {})
            for prop, raw in payload.items():
                if prop.startswith("@") or prop == "_report":
                    continue
                entries = props.get(prop)
                if not entries:
                    report["ignored"].append({"node": node_key, "property": prop})
                    continue
                # Ambiguous properties (dcterms:subject carrying both keyword
                # and theme) resolve to the first binding; the build warns
                # about every one of these, so the choice is visible.
                entry = entries[0]
                concept = self.concepts[entry["concept"]]
                if concept["direction"] == "export_only":
                    report["export_only_skipped"].append(entry["concept"])
                    continue
                field = entry.get("dataspace_field")
                if not field:
                    report["no_platform_field"].append(entry["concept"])
                    continue
                target[field] = self._unrender(raw, entry)

        take("dataset", document, dataset)

        link = next(
            (e for e in std["export"] if e["concept"] == "distribution"), None
        )
        if link and link["property"] in document:
            resources = []
            for raw_dist in document[link["property"]] or []:
                if not isinstance(raw_dist, dict):
                    continue
                resource: Dict[str, Any] = {}
                take("distribution", raw_dist, resource)
                if resource:
                    resources.append(resource)
            if resources:
                dataset["resources"] = resources

        return dataset, report

    def _unrender(self, raw: Any, entry: dict) -> Any:
        def one(v: Any) -> Any:
            if isinstance(v, dict):
                return v.get("@id") or v.get("@value") or v
            return v

        if isinstance(raw, list):
            values = [one(v) for v in raw]
            return values if entry["repeatable"] else (values[0] if values else None)
        value = one(raw)
        return [value] if entry["repeatable"] else value

    # -------------------------------------------------------------- report
    def gaps(self, sid: str) -> List[dict]:
        return self.standard(sid)["gaps"]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Export/import via crosswalk.json.")
    ap.add_argument("action", choices=("export", "import", "gaps", "standards"))
    ap.add_argument("standard", nargs="?", help="dcat | dublin_core | croissant")
    ap.add_argument("path", nargs="?", help="JSON file to read")
    args = ap.parse_args(argv)

    cw = Crosswalk.load()

    if args.action == "standards":
        for sid, std in sorted(cw.standards.items()):
            c = std["coverage"]
            print(f"{sid:14} {std['name']}")
            print(
                f"{'':14} {c['exact']} exact, {c['partial']} partial, "
                f"{c['gap'] + c['unbound']} gaps"
            )
        return 0

    if not args.standard:
        ap.error("a standard is required for this action")

    if args.action == "gaps":
        for gap in cw.gaps(args.standard):
            concept = cw.concepts.get(gap["concept"], {})
            marker = "*" if concept.get("dataspace_field") else " "
            print(f" {marker} {gap['concept']:24} {gap.get('notes') or gap['reason']}")
        print("\n* = the platform has a field for this; exporting will drop it.")
        return 0

    if not args.path:
        ap.error("a JSON file is required for this action")
    with open(args.path, encoding="utf-8") as fh:
        payload = json.load(fh)

    if args.action == "export":
        doc, report = cw.export_with_report(payload, args.standard)
        print(json.dumps(doc, indent=2, ensure_ascii=False))
        for key, items in report.items():
            if items:
                print(f"\n{key}:", file=sys.stderr)
                for item in items:
                    print(f"  {item}", file=sys.stderr)
    else:
        dataset, report = cw.import_(payload, args.standard)
        print(json.dumps(dataset, indent=2, ensure_ascii=False))
        for key, items in report.items():
            if items:
                print(f"\n{key}: {items}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
