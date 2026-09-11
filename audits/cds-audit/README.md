# cds-audit

Audits every dataset on [CivicDataSpace](https://civicdataspace.in/datasets) against the
*Dataset uploading guidelines for CivicDataSpace* and scores each one out of 100. The output shows which datasets
need work, which guidelines the catalogue misses most often, and the specific fix for each problem.

```
$ make demo          # synthetic fixture data — not the live catalogue
8 datasets · average 76.5 · 7 need improvement · 7 fail a guideline outright
  Good               1
  Fair               5
  Needs improvement  1
  Poor               1
Reports written to reports/demo/  (report.html, summary.md, scores.csv, issues.csv, audit.json)
```

## Quick start

```bash
git clone <this repo> && cd civicdataspace-audit
python -m venv .venv && source .venv/bin/activate
pip install -e ".[deep]"          # or: pip install -e .   (minimal)

cds-audit probe                   # confirm the API is reachable and shaped as expected
cds-audit run                     # audit the whole catalogue → reports/
open reports/report.html
```

To try it without network access, run `make demo`. This builds a report from a synthetic snapshot of eight
invented datasets in `tests/fixtures/`. The snapshot mirrors the real API responses but contains no real data.

## What it checks

Each check maps to a numbered section of the guidelines. [`docs/scoring.md`](docs/scoring.md) lists every
sub-check and its weight.

| Guideline | Checked automatically |
|---|---|
| 1.1 Title | ≤ 60 characters, no special characters, no abbreviations, sentence/Title case, time period mentioned |
| 1.2 Description | 2–5 sentences, and states time period, geography, who compiled it, periodicity, purpose |
| 1.3 Publisher | Organisation recorded (individual publishers get partial credit) |
| 1.5 Tags | Present, not just repeating sector names, no near-duplicates (or in the predefined list, if supplied) |
| 1.6 Sectors | At least one assigned |
| 1.7 Geography | Recorded, and includes any state named in the title |
| 1.8 Date of creation | Present and ISO-8601 (`YYYY-MM-DD`), not in the future |
| 1.9 License | Present; government-sourced data (`.gov.in`, `.nic.in`, `data.gov.in`) must use GODL |
| 1.10 Source website | Present, valid `https://` URL, not pointing back at CivicDataSpace; optionally checked live |
| 2.1 File format | Open formats; every Excel file has a CSV twin; no PDF-only data; geospatial CRS stated / WGS84 |
| 2.2 Encoding | Valid UTF-8, no BOM, no garbled characters, no decimal commas |
| 2.3 Column naming | One convention (snake_case or camelCase), no spaces/special characters, not ambiguous (`col1`) |
| 2.4 Data types | ISO dates, raw numbers (no `1,234` / `₹` / `%`), consistent booleans, consistent decimals |
| 2.5 Units | Every measurement column documents its unit (name suffix or column description); SI units |
| 2.6 Missing values | Blank/NULL/NaN only — flags `-999`-style sentinels, `NA`, `-`, `nil`, and mixed markers |
| 2.7 Data quality | Duplicate rows, percentages outside 0–100, implausible temperatures, negative counts, bad lat/long, invalid geometries |
| 2.8 File naming | `{theme}_{region}_{time_period}_v{version}.{format}` |

## Modes

**Light (default).** This mode uses dataset metadata, the column schema the platform inferred, and the preview
rows the API exposes (up to 1,000 per file). It downloads nothing, so it is safe to schedule. Byte-level
encoding cannot be assessed in this mode. Checks with nothing to assess are shown as *not assessable* and are
left out of the score.

**Deep (`--deep`).** This mode also downloads each resource file (up to 25 MB by default) and inspects it
directly: UTF-8 validity, full-file duplicates, GeoJSON CRS and geometry validity, and shapefile `.prj` files.

> ⚠️ **Deep mode inflates download counts.** The backend increments `download_count` on every call to
> `/api/download/resource/{id}`, so a deep audit adds one download per file to the public stats. Run it
> sparingly, or exclude the auditor's User-Agent (`cds-audit/…`) from counting on the backend.

## Outputs

All outputs are written to `--out` (default `reports/`):

| File | For |
|---|---|
| `report.html` | Self-contained, offline report. It has a grid of every dataset against every guideline, where the catalogue loses points, a searchable dataset table with check-by-check fixes, and publisher averages. |
| `summary.md` | The same headline findings as Markdown, for pasting into an email or issue. |
| `issues.csv` | One row per failing check, sorted by points lost. Works as a fix-it tracker to share with publishers. |
| `scores.csv` | One row per dataset with every check score. |
| `audit.json` | Everything, for further analysis. |
| `snapshot/` | Raw API responses. Re-score later without the network: `cds-audit run --offline --cache reports/snapshot`. |

## Scoring in one paragraph

Each check scores 0–1, and the weights add up to 100: 60 for metadata (section 1) and 40 for the data
itself (section 2). Grades are **Good** (85+), **Fair** (70–85), **Needs improvement** (50–70) and **Poor**
(below 50). A dataset that fails any guideline outright is capped at *Fair*, so a strong average cannot hide a
PDF-only upload or a missing licence. Weights, thresholds, vocabularies and the grade cap all live in
[`src/cds_audit/rules.yaml`](src/cds_audit/rules.yaml).

## Configuration

```bash
cp config/overrides.example.yaml config/overrides.yaml   # edit only what you want to change
cds-audit run --rules config/overrides.yaml
```

Useful options:
- `--api https://dev.api.civicdataspace.in` points the audit at a different backend.
- `--limit 36` audits only the most recent N datasets.
- `--filter sectors=Climate%20Action` passes a search filter through to the API.
- `--check-links` requests each source website to confirm it resolves.
- `--fail-under 70` exits with status 1 if the catalogue average drops below 70. Use it in CI.

## Scheduling

`.github/workflows/weekly-audit.yml` runs a light audit every Monday. It adds `summary.md` to the job page
and keeps the reports and snapshot as an artifact for 90 days. `.github/workflows/tests.yml` runs the test
suite on every push.

## Things to know

- **API host.** The default is `https://api.datakeep.civicdays.in`, the production `BACKEND_GRAPHQL_URL`
  named in `DataSpaceFrontend/docs/GOOGLE_SEARCH_CONSOLE.md`. Run `cds-audit probe` first. If the host has
  moved, set `api.base_url` in an overrides file or pass `--api`.
- **Heuristic checks are prompts, not verdicts.** Checks for abbreviations, units, purpose statements and
  source attribution are pattern-based, and will occasionally miss or over-flag. The report always shows the
  specific text that triggered a flag so a person can confirm it.
- **Interpretation choices.** Where the guidelines are ambiguous or self-contradictory, the choice made is
  listed in [`docs/scoring.md`](docs/scoring.md#interpretation-choices).
- **Platform findings.** Some problems are better fixed at upload time than dataset by dataset. See
  [`docs/platform-recommendations.md`](docs/platform-recommendations.md).

## Development

```bash
make install && make test
python tests/make_fixtures.py     # regenerate the synthetic snapshot after changing it
```

Layout:

```
src/cds_audit/
  cli.py            command line (run, probe)
  client.py         REST search + GraphQL + downloads, with caching and offline mode
  runner.py         search → details → (deep) downloads → checks
  checks/metadata.py  guideline section 1
  checks/data.py      guideline section 2
  fileinspect.py    parses downloaded CSV/JSON/GeoJSON/XLSX/Parquet/zip
  scoring.py        weights, grades, grade cap
  rules.yaml        every tunable number and word list
  report/           HTML, Markdown, CSV and JSON writers
tests/              unit + end-to-end tests against the synthetic snapshot
```

To add a check, write a function `(DatasetInfo, rules) -> CheckResult` in `checks/`. Then register it in that
module's `ALL_*_CHECKS` list, give it a weight in `rules.yaml`, and add a short label in `report/html.py`.
