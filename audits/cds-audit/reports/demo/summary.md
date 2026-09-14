# CivicDataSpace dataset audit

Generated 2026-09-14 13:28 UTC · 8 datasets · mode: deep

**7 of 8 datasets need improvement** (graded below Good); 7 fail at least one guideline outright. Average score 76.5, median 87.9.

| Grade | Datasets |
|---|---|
| Good | 1 |
| Fair | 5 |
| Needs improvement | 1 |
| Poor | 1 |

## Where points are lost

| Guideline | Pass | Warn | Fail | Not assessed | Avg score | Points lost |
|---|---|---|---|---|---|---|
| 1.2 Description / Summary | 2 | 3 | 3 | 0 | 64.7 | 33.9 |
| 2.3 Column Naming | 3 | 1 | 3 | 1 | 63.6 | 17.9 |
| 2.1 File Format | 5 | 1 | 2 | 0 | 76.2 | 15.2 |
| 1.1 Dataset Title | 3 | 4 | 1 | 0 | 76.9 | 14.8 |
| 1.10 Source Website | 5 | 1 | 2 | 0 | 70.0 | 14.4 |
| 1.8 Date of Creation | 5 | 1 | 2 | 0 | 70.0 | 12.0 |
| 2.8 File Naming | 3 | 3 | 2 | 0 | 65.6 | 11.0 |
| 1.7 Spatial Coverage / Geography | 6 | 1 | 1 | 0 | 83.8 | 9.1 |
| 2.7 Data Quality Checks | 3 | 2 | 2 | 1 | 74.3 | 7.2 |
| 1.5 Tags | 5 | 2 | 1 | 0 | 82.5 | 7.0 |
| 2.5 Units of Measurement | 4 | 0 | 2 | 2 | 72.2 | 6.7 |
| 2.4 Data Types | 5 | 1 | 1 | 1 | 86.7 | 5.6 |
| 2.2 Encoding and Character Sets | 3 | 0 | 1 | 4 | 75.0 | 4.0 |
| 1.9 License and Terms of Use | 7 | 1 | 0 | 0 | 93.8 | 3.5 |
| 2.6 Missing Values | 5 | 1 | 1 | 1 | 84.3 | 3.3 |
| 1.3 Publisher / Data Provider | 7 | 1 | 0 | 0 | 95.0 | 2.0 |
| 1.6 Sectors | 8 | 0 | 0 | 0 | 100.0 | 0.0 |

## Datasets needing the most work

### [Annual report on anganwadi centres](https://civicdataspace.in/datasets/33333333-3333-4333-8333-333333333333) — 40.3 (Poor)
Publisher: Example Child Rights Trust

- [1.2] Expand the description to 2–5 sentences.
- [1.7] Set the geography (country / state / district) in metadata.
- [2.1] Publish the underlying data as CSV/JSON (keep the PDF only as supporting documentation).
- [1.10] Add the official page of the organisation that publishes the source data.
- [1.5] Add tags describing the dataset's themes, variables or use cases.

### [court cases pending](https://civicdataspace.in/datasets/55555555-5555-4555-8555-555555555555) — 62.9 (Needs improvement)
Publisher: A. Researcher

- [1.2] Expand the description to 2–5 sentences.
- [1.10] Add the official page of the organisation that publishes the source data.
- [1.8] Add the source's official creation date in YYYY-MM-DD format.
- [2.5] Document the unit of every measurement column (name suffix like _mm / _inr_crore, or column description).
- [1.1] Use sentence case for the title.

### [State Revenue & Receipts 2018-26](https://civicdataspace.in/datasets/22222222-2222-4222-8222-222222222222) — 70.2 (Fair)
Publisher: Example Budget Lab

- [1.2] State the years the data covers in the description.
- [2.3] Rename columns to snake_case (lowercase, words joined with underscores).
- [1.9] Set the license to Government Open Data License (GODL) for data sourced from government platforms.
- [2.8] Rename files as {theme}_{region}_{time_period}_v{version}.{format}, e.g. climate_bihar_precipitation_2000_2020_v1.0.csv.
- [1.8] Record the creation date as YYYY-MM-DD.

### [Sanitation survey — Assam districts 2021](https://civicdataspace.in/datasets/44444444-4444-4444-8444-444444444444) — 72.8 (Fair)
Publisher: Example WASH Collective

- [2.3] Rename columns to snake_case (lowercase, words joined with underscores).
- [2.1] Add a CSV version alongside every Excel file.
- [2.4] Format dates as YYYY-MM-DD (timestamps as YYYY-MM-DD hh:mm:ss UTC).
- [2.8] Rename files as {theme}_{region}_{time_period}_v{version}.{format}, e.g. climate_bihar_precipitation_2000_2020_v1.0.csv.
- [1.10] Enter the full URL including https://.

### [GUWAHATI WARD BOUNDARIES](https://civicdataspace.in/datasets/66666666-6666-4666-8666-666666666666) — 87.9 (Fair)
Publisher: Example Urban Observatory

- [2.1] State the spatial reference system; use WGS84 (EPSG:4326).
- [1.1] Use sentence case for the title.
- [2.7] Fix invalid geometries (closed rings, valid coordinates, no self-intersections).
- [2.8] Rename files as {theme}_{region}_{time_period}_v{version}.{format}, e.g. climate_bihar_precipitation_2000_2020_v1.0.csv.
- [1.2] Mention how often the data is recorded or updated (e.g. 'annual', 'daily').

### [NFHS-5 district fact sheet indicators on maternal and child health for Uttar Pradesh](https://civicdataspace.in/datasets/88888888-8888-4888-8888-888888888888) — 88.3 (Fair)
Publisher: Example Health Data Lab

- [1.1] Shorten the title to 60 characters or fewer.
- [2.5] Document the unit of every measurement column (name suffix like _mm / _inr_crore, or column description).
- [1.7] Add Uttar Pradesh to the dataset's geography.
- [1.2] Tighten the description to at most 5 sentences; move methodology detail to a resource description.
- [1.1] Spell out abbreviations in the title (e.g. 'India Meteorological Department', not 'IMD').

### [Literacy by district in Assam, Census 2011](https://civicdataspace.in/datasets/77777777-7777-4777-8777-777777777777) — 89.8 (Fair)
Publisher: Example Education Forum

- [2.2] Re-save the file as UTF-8.
- [2.3] Rename columns to snake_case (lowercase, words joined with underscores).
- [2.7] Remove duplicate records.
- [2.3] Use one convention (snake_case recommended) for every column.
- [2.7] Validate numeric ranges (percentages 0–100, plausible temperatures, non-negative counts).

### [Daily rainfall for Bihar districts (2000–2020)](https://civicdataspace.in/datasets/11111111-1111-4111-8111-111111111111) — 100.0 (Good)
Publisher: Example Climate Institute


## By publisher

| Publisher | Datasets | Avg score | Below 70 |
|---|---|---|---|
| Example Child Rights Trust | 1 | 40.3 | 1 |
| A. Researcher | 1 | 62.9 | 1 |
| Example Budget Lab | 1 | 70.2 | 0 |
| Example WASH Collective | 1 | 72.8 | 0 |
| Example Urban Observatory | 1 | 87.9 | 0 |
| Example Health Data Lab | 1 | 88.3 | 0 |
| Example Education Forum | 1 | 89.8 | 0 |
| Example Climate Institute | 1 | 100.0 | 0 |
