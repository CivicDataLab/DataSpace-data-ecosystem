# How datasets are scored

Each guideline section becomes one check that scores between 0 and 1. A check is made of weighted sub-checks
whose weights add up to 1 within that check. The dataset score is

    100 × Σ(weight × check score) / Σ(weight)       over checks that could be assessed

A check with no evidence to work with is marked *not assessable* and dropped from the denominator. For example,
column naming cannot be assessed on a PDF-only dataset. File format already penalises that dataset, so it
isn't penalised twice.

The status shown in the report is **pass** (1.0), **partly meets** (0.5–0.99) or **does not meet** (< 0.5).

The grade comes from the score: Good 85+, Fair 70+, Needs improvement 50+, Poor below that. Any *does not meet*
check caps the grade at Fair (`grade_cap_on_fail` in `rules.yaml`).

## Section 1 — Metadata (60 points)

| Check | Pts | Sub-checks (share of the check) |
|---|---|---|
| 1.1 Title | 8 | ≤ 60 chars (25%) · no special characters outside `- – — ( ) , . : '` (20%) · no upper-case abbreviations such as `IMD`, `NFHS` (20%) · sentence/Title case, not ALL CAPS or all lower (10%) · mentions a year (25%) |
| 1.2 Description | 12 | 2–5 sentences (15%; over 5 gets half) · not a copy of the title (10%) · a year (20%) · a geography term or the dataset's own geography (20%) · names who compiled it — "compiled by", "from the Census…", "by the X Department" (15%) · periodicity (10%) · purpose (10%) |
| 1.3 Publisher | 5 | Organisation = 1 · individual only = 0.6 · none = 0 |
| 1.5 Tags | 5 | Any tags (60%) · not all duplicates of sector names (20%) · no near-duplicates, or all in `tags.predefined` if you supply it (20%) |
| 1.6 Sectors | 5 | At least one |
| 1.7 Geography | 7 | Recorded (70%) · every state named in the title is in the geography field (30%) |
| 1.8 Date of creation | 5 | A DATE-type metadata field present (50%) · ISO `YYYY-MM-DD` (40%) · not in the future (10%) |
| 1.9 License | 7 | Present (50%) · GODL when the source website is a government domain (50%) |
| 1.10 Source website | 6 | Present (40%) · valid `http(s)` URL (40%) · resolves (with `--check-links`) and isn't a CivicDataSpace link (20%) |

## Section 2 — Data (40 points)

These checks run per file and are averaged across the dataset's files.

| Check | Pts | How |
|---|---|---|
| 2.1 File format | 8 | CSV/TSV/JSON/GeoJSON/Parquet/Shapefile = 1 · Excel without a CSV twin = 0.3 · PDF/DOC/images = 0.2 · unknown = 0.5 · geospatial without a stated or WGS84 CRS ≤ 0.6 |
| 2.2 Encoding | 4 | Deep: invalid UTF-8 = 0, BOM = 0.9. Any mode: garbled characters (`Ã©`, `�`) ≤ 0.2, decimal commas ≤ 0.6 |
| 2.3 Column naming | 7 | 60% × share of clean names (no spaces or special characters, not ambiguous, ≤ 40 chars) + 40% × one consistent convention. Duplicate names cap at 0.4 |
| 2.4 Data types | 6 | 1 − share of columns with non-ISO dates, formatted numbers, or yes/no booleans. Inconsistent decimals count half |
| 2.5 Units | 4 | Share of measurement columns with a unit in the name or description. Identifier columns (`*_id`, `*_code`, `year`, `lat`…) are excluded. Non-SI units cap at 0.3 |
| 2.6 Missing values | 3 | −0.5 for numeric sentinels (`-999`), −0.3 for placeholder strings (`NA`, `-`, `nil`), −0.2 for mixed markers |
| 2.7 Data quality | 4 | Duplicate rows −(0.1 + share), up to 0.4 · each range violation −0.2, up to 0.5 · invalid or unclosed geometries −0.6 |
| 2.8 File naming | 4 | Share of: lowercase snake_case · contains a year · `_v{version}` suffix · extension matches format |

## Interpretation choices

The guidelines leave some points open. These are the choices the checker makes. Each can be changed in
`rules.yaml` or in the code.

- **Abbreviations (1.1).** The guideline says "no abbreviations", yet the 1.2 example relies on "IMD".
  Titles are checked strictly. Add agreed exceptions to `title.abbreviation_allowlist`.
- **Time period in title (1.1).** The guideline says to "try to mention" the period, so a missing year is a
  partial miss, not a failure.
- **File-naming pattern (2.8).** The stated pattern `{theme}_{region}_{time_period}` does not match the example
  `climate_bihar_precipitation_2000_2020_v1.0.csv`, which puts a sub-theme after the region. Token order is
  not enforced. The check requires lowercase snake_case, a year and a `_v{version}` suffix.
- **Stored file names (2.8).** Django appends a 7-character suffix when two uploads share a name
  (`cases_aB3xYz1.csv`). The suffix is stripped before checking.
- **Section 1.4 is missing** from the guidelines. The numbering here follows the document.
- **Units (2.5).** Counts (`population`, `households`, `*_count`) and indices, ratios and scores count as
  documented. Currency (INR) is accepted even though it isn't SI. Acres and bighas are flagged as non-SI.
- **Placeholder column descriptions.** The platform auto-fills column descriptions with
  `Description of column X`. These are treated as empty.
- **GeoJSON CRS (2.1).** RFC 7946 GeoJSON is WGS84 by definition. A file is flagged only if it declares another
  CRS, or its coordinates fall outside longitude/latitude range.
