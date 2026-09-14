# Metadata Standards — DataSpace, DCAT v3, Dublin Core, Croissant

This folder is CivicDataSpace's canonical reference for how its own dataset metadata schema
relates to the external metadata standards the platform is expected to interoperate with:
**DCAT v3** (plus the proposed India extension, **DCAT-IN**), **Dublin Core**, and
**Croissant** (MLCommons' ML-dataset metadata format). It is the "metadata supermodel" referenced
elsewhere on the platform — the single place that reconciles what CivicDataSpace currently
stores with what these standards expect, so publishing tooling, audits, and future schema
changes all work from the same mapping instead of re-deriving it.

Source: `DataSpace Metadata_Croissant_DCAT_mapping.xlsx` (CivicDataLab, 2026), transcribed into
[`mapping.yaml`](mapping.yaml) so it is versioned, diffable, and usable by code.

---

## Why these four standards

| Standard | Role |
|---|---|
| **DCAT v3** | W3C's vocabulary for describing datasets in a catalog — the closest thing to a lingua franca for open-data portals, and the target for India's OGD / National Data & Analytics Platform ecosystem. |
| **DCAT-IN** | A proposed India-specific extension to DCAT v3 (fields like `dcatin:jurisdictionLevel`, `dcatin:hvdCategory`) — not yet a stable published spec, but the direction India's OGD metadata is heading. |
| **Dublin Core** | The older, simpler element set DCAT itself builds on (`dcterms:*`). Included because CivicDataSpace's OGD-facing metadata is documented against it directly in places. |
| **Croissant** | Google/MLCommons' schema.org-based format for describing datasets *for machine learning consumption* (`RecordSet`, `Field`, `FileObject`, ML-specific data types). Relevant because CivicDataSpace wants datasets to be ML-ready, not just catalog-browsable. |

DCAT is catalog-shaped (what is this dataset, who published it, where do I download it).
Croissant is data-shaped (what are its columns, types, and semantics). CivicDataSpace's current
schema is closer to DCAT; the gaps recorded here are mostly where Croissant asks for structure
DCAT — and CivicDataSpace today — doesn't capture.

---

## Files

```
canonical_entities/metadata-standards/
├── mapping.yaml           The metadata supermodel — machine-readable, one section per source sheet
├── convert.py             Converts a DataSpace dataset's metadata to DCAT / Croissant JSON-LD
├── example_dataset.json   Sample dataset used by convert.py's usage examples below
└── README.md              This file
```

### `mapping.yaml`

Six sections, each corresponding to one sheet of the source workbook:

- **`dataspace_metadata_fields`** — CivicDataSpace's current dataset metadata fields, their
  input type (automated / free text / controlled), and definition, including fields the platform
  team itself flagged as unclear (`dataspace`, `accessType`, `metadata`, `promptMetadata`,
  `datasetType`) — these are recorded as-is, not resolved.
- **`dataspace_dcat_croissant_mapping`** — each named field (or, where `dataspace_field: null`,
  a structural DCAT/Croissant concept like the Dataset/Distribution container itself) mapped to
  its DCAT and Croissant equivalent, tagged with a `match_type`:
  - `exact` — one-to-one concept match, no loss
  - `partial` — the concept exists on both sides but cardinality, structure, or vocabulary differs
  - `gap` — the concept has no equivalent in the target standard
  - `unmappable` — a platform-internal field with no external-standard meaning
- **`controlled_vocabularies`** — placeholders for the canonical value lists (License,
  Geographies, Sectors) the platform still needs to author; currently empty in the source.
- **`data_registry_dcat_mapping`** — a separate mapping for an indicator/data registry
  (e.g. the kind of registry a collaborative like IDS-DRR maintains) onto DCAT v3 / Dublin Core,
  with DCAT v3 cardinality (Mandatory/Recommended/Optional) and value types per column.
- **`dcat_dublincore_catalog`** — the full DCAT v3 / Dublin Core element catalog independent of
  CivicDataSpace, grouped by `category`: `core` (agreed mapping), `contact_point` (vCard
  sub-properties of `dcat:contactPoint`), `ambiguous` (present on the OGD side, no single agreed
  mapping yet), `gap` (defined in the standards, not yet in OGD metadata).
- **`unmapped_elements`** — reserved for CivicDataSpace/OGD fields with no standards equivalent
  at all; empty for now (the source sheet left this section as blank placeholders).

### `convert.py`

A standalone script (only dependency: `pyyaml`, already used elsewhere in this repo) that reads
`mapping.yaml` and:

1. **Converts** a CivicDataSpace dataset's metadata into DCAT v3 or Croissant JSON-LD, using only
   the fields with an `exact` (or usable `partial`) mapping.
2. **Reports gaps** for a specific dataset — which of its populated fields won't survive a
   round-trip to a given standard without loss, so a publishing pipeline or audit can flag them.

```bash
pip install pyyaml   # if not already installed

python convert.py dcat example_dataset.json
python convert.py croissant example_dataset.json
python convert.py gaps example_dataset.json                    # gaps against DCAT (default)
python convert.py gaps example_dataset.json --standard croissant
```

`dataset.json` is a flat object using CivicDataSpace's own field names (`title`, `description`,
`organization`, `user`, `license`, `created`, `modified`, `tags`, `sectors`, `geographies`,
`resources[]`, ...) — see `example_dataset.json`. This mirrors the `DatasetInfo` shape already
used by [`audits/cds-audit`](../../audits/cds-audit/), so a dataset pulled from that tool's
GraphQL client can be fed into `convert.py` with minimal reshaping.

---

## Known open questions

Carried over from the source mapping, not resolved here — flagging them for whoever owns the
platform's dataset schema next:

- **`organization`/`user` vs. `creator`/`publisher`**: the source mapping has
  `organization -> dct:publisher` / Croissant `creator`, and `user -> dct:creator` / Croissant
  `publisher`. This looks backwards from the usual convention (the organization that publishes a
  dataset is normally the *publisher*; the person/system that produced it is the *creator*).
  Confirm intent before wiring this into a production converter.
- **Controlled vocabularies** (License, Geographies, Sectors) have no canonical value list yet —
  `mapping.yaml`'s `controlled_vocabularies` section is a placeholder until the platform team
  publishes one.
- **`metadata`, `promptMetadata`, `datasetType`, `dataspace`, `accessType`**: the current
  CivicDataSpace schema includes these fields, but their purpose isn't fully documented (see the
  `definition` values transcribed as-is in `dataspace_metadata_fields`). They're marked
  `unmappable` in `dataspace_dcat_croissant_mapping` only where the source explicitly said so
  (`dataspace`, `accessType`); the rest simply have no DCAT/Croissant equivalent recorded yet.

---

## Updating this reference

If the source spreadsheet changes (a new field, a resolved ambiguity, a published DCAT-IN spec),
update `mapping.yaml` to match and re-run the examples above to confirm `convert.py` still
produces sane output. Keep the one-section-per-sheet structure so this file stays diffable
against future spreadsheet revisions.
