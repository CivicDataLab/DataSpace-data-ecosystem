# Metadata field superset — the import/export crosswalk

One row per thing you can say about a dataset, with how each supported standard says it, which
of them CivicDataSpace surfaces, and what an import or export function is allowed to do with it.

Currently covers **DCAT v3** (plus the proposed DCAT-IN extension), **Dublin Core**, and
**Croissant**. Adding a fourth is one new file in [`standards/`](standards/).

> **Two supersets, don't confuse them.** This one is about *fields* — what may be said.
> [`../../metadata-superset/`](../../metadata-superset/) is about *values* — which licences,
> places and sectors a field may take. They meet at `controlled_vocabulary`: three concepts here
> (`license`, `spatial_coverage`, `theme`) draw their values from there, and export is not
> correct until it resolves them.

---

## Why this exists

[`../mapping.yaml`](../mapping.yaml) is a faithful transcription of the source workbook —
five top-level keys, one per sheet. That makes it diffable against a future revision of the
spreadsheet, which is what it was for, but it is organised by *sheet*, so the same concept
appears several times with different spellings, some rows have no platform field, and nothing
says which direction a field may travel. You cannot write an importer against it.

This folder reorganises the same material by *concept* and adds what import/export needs and the
workbook never recorded: value types, cardinality, node placement, and a direction flag.

---

## Layout

```
superset/
├── concepts.yaml                  The spine — one entry per concept. Hand-authored.
├── standards/
│   ├── dcat.yaml                  One file per standard: concept -> property
│   ├── dublin_core.yaml
│   └── croissant.yaml
├── build-metadata-superset.py     Validates everything, writes out/
├── crosswalk.py                   Reference import/export, driven by crosswalk.json
└── out/                           Generated
    ├── metadata_field_superset.csv   Review artifact, one row per concept
    ├── crosswalk.json                The contract backend code loads
    └── run_manifest.json
```

```bash
python build-metadata-superset.py          # validate + regenerate out/
python build-metadata-superset.py --strict # non-zero exit if anything is flagged (for CI)
```

---

## For a backend developer

Load [`out/crosswalk.json`](out/crosswalk.json). Everything below is in it; nothing needs to be
re-derived from the spreadsheet or from this README.

### Export

Walk `standards.<id>.export`. Each entry gives you the platform field to read, the property to
write, which node it belongs on, and how to serialise it:

```json
{
  "concept": "spatial_coverage",
  "property": "dcterms:spatial",
  "node": "dataset",
  "parent_property": null,
  "value_type": "location",
  "repeatable": true,
  "obligation": "mandatory",
  "match": "exact",
  "dataspace_field": "geographies",
  "controlled_vocabulary": "geography"
}
```

`standards.<id>.context` and `.node_types` give you the JSON-LD `@context` and the `@type` for
each node. `uri_style` says whether a URI is written as `{"@id": …}` (DCAT, Dublin Core) or as a
plain string (Croissant).

### Import

Look each incoming property up in `standards.<id>.import[node][property]`. You get the concept
and the platform field to write. The value is a **list** because one property can legitimately
carry two concepts — Dublin Core puts both `keyword` and `theme` on `dcterms:subject`, and there
is no way to tell them apart on the way in. The build warns about every such case; there are
three today.

### `direction` — the flag that makes import safe

| Value | Meaning |
|---|---|
| `both` | Read on import, write on export |
| `export_only` | Platform-derived. Emit it; **never** let an incoming record overwrite it |
| `import_only` | Accept from a source; the platform has nowhere to put it or does not re-emit it |
| `none` | Platform-internal (`status`, `downloadCount`). Not metadata; ignore both ways |

`export_only` is the one that matters. `identifier` is the platform's own dataset ID — a
federated record must not be able to overwrite it. Import that ID into `source_identifier`
instead, which exists for exactly that.

Export-only properties are still present in the import index, so your importer can tell
*"this is ours and we refuse it"* from *"we have never heard of this property"*. The reference
implementation reports those separately.

### Controlled values are your job

`controlled_vocabulary` on a concept means the value must be resolved to a URI through
[`../../metadata-superset/out/`](../../metadata-superset/out/) before it goes out.
`crosswalk.json.controlled_vocabularies` gives the file path and the key/URI columns.

This is not optional polish. `dcterms:spatial` with the string `"Assam"` is not a spatial
reference, and a consumer cannot do anything with it. The reference implementation does not
resolve values — it emits what it was given and records every one in `report["unresolved"]`,
so an unresolved export is loud rather than silently wrong:

```
$ python crosswalk.py export dcat ../example_dataset.json
...
unresolved:
  {'concept': 'theme',            'value': 'Disaster Risk Reduction', 'vocabulary': 'sector'}
  {'concept': 'license',          'value': 'Government Open Data License - India', 'vocabulary': 'license'}
  {'concept': 'spatial_coverage', 'value': 'Assam', 'vocabulary': 'geography'}
```

Those three lines are the current state of the platform, not a bug in the example.

### Reference implementation

[`crosswalk.py`](crosswalk.py) does both directions with no standard named anywhere in it —
proof that the crosswalk is complete enough to drive code, and something to port.

```bash
python crosswalk.py standards                        # what is supported
python crosswalk.py export dcat ../example_dataset.json
python crosswalk.py export croissant ../example_dataset.json
python crosswalk.py import dcat exported.json
python crosswalk.py gaps croissant                   # what this standard cannot carry
```

Export returns a report with three lists: `unresolved` (above), `dropped` (the platform holds a
value this standard cannot express), and `missing_mandatory` (the standard requires it and the
platform had nothing).

---

## Current coverage

| Standard | Exact | Partial | Gaps | Exportable | Recognised on import |
|---|---|---|---|---|---|
| DCAT v3 | 51 | 13 | 16 | 25 | 64 |
| Dublin Core | 28 | 8 | 44 | 19 | 33 |
| Croissant | 25 | 11 | 44 | 21 | 33 |

80 concepts. 26 have a platform field. 20 are surfaced on DataSpace.

"Exportable" is much smaller than "exact" because export is limited by what the *platform*
holds, not by what the standard can express — 54 of the 80 concepts have no DataSpace field yet.
That difference is the roadmap.

The two gap lists are near mirror images, which is the point of supporting both: DCAT cannot
express `record_set`, `field`, `data_type`, `transform` or `checksum` — everything that makes a
dataset ML-readable. Croissant cannot express `theme`, `access_rights`, `contact_point`,
`accrual_periodicity` or catalog membership — everything that makes a dataset governable.

---

## Adding a standard

1. Write `standards/<id>.yaml`: `id`, `name`, `url`, `context`, `uri_style`, `node_types`, and a
   `bindings` block mapping concept keys to properties.
2. Run `python build-metadata-superset.py`. It fails loudly on a binding to an unknown concept,
   an unknown value type, or a node with no `node_types` entry.
3. That's it. The CSV grows two columns, `crosswalk.json` grows a standard, and `crosswalk.py`
   exports to it without modification.

Record a `match: gap` for concepts the standard genuinely cannot express, with a note saying
why. Omitting the concept means the same thing but records no reasoning, and the build
distinguishes the two (`gap` vs `unbound`) so you can see which gaps have been thought about.

## Adding a concept

Add it to `concepts.yaml`. It is a superset: a concept no current standard expresses is fine,
and a concept the platform has no field for is fine. Both are how the file records intent ahead
of implementation.

Never rename a `key` — bindings and any stored crosswalk data point at it.

---

## Editing `visible_on_dataspace`

`concepts.yaml` owns the flag; the CSV is generated from it. This is the opposite of the value
superset, where the CSV is the edit surface — there the rows number 8,000 and carry no prose,
here there are 80 and each carries a definition and notes that a CSV round-trip would destroy.

Edit the CSV anyway and the build will notice on the next run and tell you the exact YAML change
to make, rather than silently discarding it.

---

## What the build checks

Errors (nothing is written):

- a binding referencing a concept that does not exist
- an unknown `node`, `value_type`, `direction`, `obligation` or `match`
- a binding whose node has no `node_types` entry in that standard
- `match: gap` with a property, or a non-gap binding without one
- duplicate concept keys

Warnings (written, but reported, and fatal under `--strict`):

- one property importing to two concepts on the same node — ambiguous on the way in
- `export_only` with no platform field — the export has to construct the value
- any property mentioned in the source workbook that no standard binds

That last check is what keeps this folder from drifting behind the spreadsheet it came from.
Class names (`dcat:Dataset`, `foaf:Agent` — CapitalCase by RDF convention) are excluded, since
they are expressed here through `node_types` and `value_type` rather than bindings, and matching
is case-insensitive so the workbook's `dcat:ByteSize` and `dcat:Keywords` resolve to the real
`dcat:byteSize` and `dcat:keyword`.

One property is currently reported: **`dcterms:accessRight`**, which appears in the "Complete
DCAT metadata mapping" sheet. There is no such term — DCMI defines `dcterms:accessRights`,
plural, which is bound. Worth correcting in the workbook.

---

## Open questions carried over from the workbook

These are recorded in the bindings, not silently resolved. Each needs a decision from whoever
owns the platform schema.

- **`organization` / `user` look inverted.** The workbook maps `organization` → `dct:publisher`
  but → Croissant `creator`, and `user` → `dct:creator` but → Croissant `publisher`. One of the
  two mappings is wrong; both are transcribed as recorded. Until it is settled, a dataset
  round-tripped DCAT → Croissant swaps its publisher and creator.
- **`created` means two things.** The platform's `created` is bound to `dcterms:issued`, not
  `dcterms:created`. The workbook itself flags that it is unclear whether the field holds the
  original creation date or the upload date. If it is the upload date, `issued` is right and
  `created` stays empty; if not, both need populating.
- **`accessType` and `metadata` are guesses.** `accessType` is bound to `dcterms:accessRights`
  and `metadata` to `dcterms:conformsTo`, on the readings the workbook suggests. Both are marked
  unclear there. Confirm against the platform before relying on either.
- **`isIndividualDataset`** is currently `direction: none`. The workbook suspects it links to
  catalogs; if so it belongs with `in_catalog` / `in_series` and becomes real metadata.
- **DCAT-IN has no published namespace.** `dcatin:` is a placeholder in `standards/dcat.yaml`.
  Anything exported with a `dcatin:` property is not yet interoperable with anyone.
