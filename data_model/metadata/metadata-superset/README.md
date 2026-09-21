# Metadata Superset — controlled vocabularies for DataSpace's fixed-entry fields

Three fields on a CivicDataSpace dataset are fixed-entry: **license**, **geographies**, and
**sectors**. This folder builds the list of values each one may take, by merging the values
currently live on the platform with the canonical authorities those values ought to map to
(SPDX, LGD, Wikidata, EU data themes, OECD DAC CRS, ISO 3166).

It is the operational counterpart to [`metadata-standards/`](../metadata-standards/). That folder
maps DataSpace's *fields* to DCAT v3, Dublin Core and Croissant. This one supplies the *values*
those fields must carry for the mapping to actually serialise:

| Field | Serialises as | Needs |
|---|---|---|
| `license` | `dcterms:license` | a resolvable LicenseDocument URI, not an enum label |
| `geographies` | `dcterms:spatial` | a resolvable place URI, not a name string |
| `sectors` | `dcat:theme` | a concept from a published scheme, not a free-text sector |

Today the platform stores licences as a Django enum and geographies as free-text names. Neither
resolves to a URI. This folder produces the URIs, the codes behind them, and the crosswalk back to
what the platform holds now — which is the input a migration needs.

---

## Layout

```
metadata-superset/
├── build-vocab-superset.py      Merges sources into one list per vocabulary
├── fetch-india-geographies.py   Populates the LGD source files from Wikidata (+ NIC)
├── sources/                     Local inputs — committed, hand-edited or generated
└── out/                         Generated. One CSV per vocabulary, plus manifests
```

---

## The superset idea

The output is deliberately larger than what the contributor UI should show. A picker with 788
districts in it is unusable; a platform that *rejects* a federated record because it carries
`CC-BY-NC-4.0` is broken. Those are different problems, so they get different answers.

Every row therefore carries one binary flag:

| `visible_on_dataspace` | Meaning |
|---|---|
| `yes` | Offered in the contributor picker and as a search facet |
| `no` | Loaded, known to the system, resolvable by URI — but never offered for selection |

**`no` is not the same as absent.** Rows flagged `no` still load into the platform. That is what
lets a federated record carrying a non-open licence be ingested and labelled, a dataset pinned to
a district reference it precisely, and a historical dataset pointing at a since-merged district
still resolve. They are simply never put in front of a contributor.

### The flag is meant to be edited

`VISIBILITY_RULES` in [build-vocab-superset.py](build-vocab-superset.py) sets a *default* — first
matching rule wins, so the order of the rules is the policy. But the CSV is the source of truth:
change a `yes` to a `no`, re-run, and the edit survives.

The build detects an edit by comparing `visible_on_dataspace` against `visible_rule_default` — the
value the rule produced on the previous run, written into the row beside it. Where the two
disagree, a human changed it, so the build carries the change forward and records
`manual override (was: <rule>)` in `visibility_rule`. Where they agree, the rules stay in charge,
so a policy change in `VISIBILITY_RULES` still propagates everywhere it hasn't been overruled.
No second file, nothing for the editor to remember to update.

Two guards: an override cannot make a deprecated or inactive row visible (it is noted and
skipped), and `--ignore-overrides` rebuilds purely from the rules.

---

## Usage

Standard library only. `openpyxl` is optional and only for `--xlsx`.

```bash
# 1. Populate India's geography source files (~8,000 rows, a few minutes)
python fetch-india-geographies.py --tier state --tier district --tier subdistrict

# 2. Build all three vocabularies
python build-vocab-superset.py

# Useful variants
python build-vocab-superset.py --only sectors      # one vocabulary
python build-vocab-superset.py --offline           # cached HTTP + local files only
python build-vocab-superset.py --xlsx              # also write the review workbook
python build-vocab-superset.py --ignore-overrides  # discard hand edits, rules only
python build-vocab-superset.py --init              # scaffold missing source templates
```

`--init` never overwrites a source file that already exists.

### Outputs

| File | What it is |
|---|---|
| `out/licenses.csv`, `out/geographies.csv`, `out/sectors.csv` | One file per vocabulary. The thing you edit, the thing you review. |
| `out/load_manifest.json` | Loader payload for a Django management command. Carries **every** row, `visible_on_dataspace` included as a boolean. |
| `out/run_manifest.json` | Row counts, review counts, and the HTTP fetch log with timestamps. |
| `out/superlists.xlsx` | `--xlsx` only. A colour-coded review workbook, one sheet per vocabulary. Derived — editing it changes nothing. |

### Columns

`key` is the merge identity and is stable across runs. `object_id` is the hierarchical ID
(geography and sector). `visible_on_dataspace` / `visible_rule_default` / `visibility_rule` are
the flag, its rule default, and the rule's name. `in_build` marks rows present on the live
platform today. `sources` and `alt_codes` carry provenance and every other code the concept is
known by. `needs_review` / `review_reason` flag conflicts the build could not resolve.

---

## Geography, and the LGD object ID

`lgdirectory.gov.in` is the authority for Indian administrative units but has no public API, so
the build originally shipped with empty templates and the geography list never got past three
rows. [`fetch-india-geographies.py`](fetch-india-geographies.py) fixes that from two sources that
*are* programmatic:

- **Wikidata** (default) publishes the LGD codes as properties — `P12747` state/UT, `P12746`
  district, `P12748` subdistrict — and gives each unit a QID. The QID matters: it is exactly the
  resolvable URI `dcterms:spatial` wants, which no scrape of the LGD site would provide.
- **NIC admin2024** (`--source both`) is the MapServer behind the boundary GeoJSONs in
  [`canonical_entities/india/maps/`](../../../canonical_entities/india/maps/). Queried
  attributes-only, it carries the LGD codes and the Census 2011 codes on the same row — the only
  fetchable crosswalk between the two numbering systems. It has no QIDs and the host is often
  unreachable, so it enriches the Wikidata rows rather than replacing them.

Current coverage: **36 states and UTs, 788 districts, 7,221 subdistricts**, each with a Wikidata
URI.

### Object IDs

Each unit gets an `object_id` — its LGD codes joined down the hierarchy, the same convention
IDS-DRR uses in `Maps/scripts/map_transformer.py` (which joins Census 2011 codes this way):

```
state        28
district     28-461
subdistrict  28-461-4850
```

LGD codes are already unique per tier, so the join isn't needed for uniqueness. It's there so an
ID sorts and prefix-matches into its parent, and so a district-keyed dataset joins to a
subdistrict-keyed one without a lookup table.

**Census 2011 codes are a different numbering system** — Andhra Pradesh is LGD `28` and Census
`37`. They travel in `alt_codes` and are never mixed into `object_id`.

### Default visibility

States, UTs, the country and the CDL regional groupings are `yes`. Districts and subdistricts are
`no` — they're loaded and resolvable, and the UI is expected to reach them through typeahead or
state drill-down rather than a flat picker of 8,000 entries.

---

## Known gaps

These are flagged in the output, not hidden:

- **37 subdistricts have no parent district on Wikidata**, so they can't be drilled into. They're
  marked `needs_review` with reason `no parent`.
- **6 subdistrict LGD codes are claimed by two Wikidata items each** (e.g. "Anantapur mandal" and
  "Anantapur Rural Mandal" both asserting `5330`). The fetcher notes the collision in the source
  row; the build merges them and raises a label conflict.
- **No Census 2011 codes are populated.** `webgis1.nic.in` was unreachable when this was last run.
  Re-run with `--source both` when it responds; LGD codes and object IDs are unaffected either way.
- **`platform_geographies.csv` is empty.** Export `SELECT name, type FROM geography` from the live
  database into it and re-run — `_mark_platform_geographies` joins on name and reports how many
  live rows have no canonical match. That count *is* the migration's work item, and it can't be
  produced without the export.
- **`dac_crs.csv` and `eu_licence_nal.csv` are empty.** Both are optional: DAC CRS purpose codes
  for UNICEF/IATI-facing mapping, the EU Licence authority table for EU federation.
- **SPDX openness is heuristic.** `is_open` is `isOsiApproved` OR a prefix match on a short
  allowlist, so older CC licences (`CC-BY-3.0`) come out as `is_open=false` and default to hidden.
  Override the flag on any that should be offered.
- **`is_active` is always true.** The field mirrors `ResourceType.is_active` but no source sets it
  yet; it will matter once the platform export carries it.

---

## Adding a vocabulary

1. Write a `build_<name>()` returning `List[VocabRecord]`, one record per concept per source — the
   merge, not the builder, resolves duplicates on `(vocabulary, key)`.
2. Register it in `BUILDERS`.
3. Add its rules to `VISIBILITY_RULES`. Order is the policy; end with a `default` rule.
4. If it needs a local source file, add a template to `TEMPLATES` so `--init` scaffolds it.

Everything downstream — merge, override preservation, CSV, manifests, workbook — is shared.
