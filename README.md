# DataSpace Data Ecosystem

**A single point of access to CivicDataSpace's collaboratives, dataset audits, data models, and canonical
reference entities.**

[![License: AGPL v3](https://www.gnu.org/licenses/agpl-3.0)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## Overview

[CivicDataSpace](https://civicdataspace.in) brings together datasets and data collaboratives across sectors —
Climate Action, Disaster Risk Reduction, Gender, Public Finance, and more — each with its own contributors,
pipelines, and publishing cadence. This repository is the ecosystem's front door: it doesn't run any one
collaborative's pipeline, but it is where you go to find all of them, audit what's published, and reuse the
reference data and models shared across all of them.

This repository provides:

- **A single place of access to all of DataSpace's collaboratives and datasets** — [`collaboratives/`](collaboratives/)
- **Scripts to audit DataSpace datasets** for metadata completeness, data quality, and AI-readiness — [`audits/`](audits/)
- **Knowledge graphs, tools, and data models for platform intelligence** — [`data_model/`](data_model/)
- **Documentation of the platform's datasets, tooling, and data infrastructure** — [`docs/`](docs/)
- **A single point of access to canonical entities** — admin boundary shapefiles, metadata standards, analysis
  skills — [`canonical_entities/`](canonical_entities/)

For how these fit together, see [`docs/architecture.md`](docs/architecture.md).

---

## Repository layout

```
DataSpace-data-ecosystem/
├── collaboratives/          Git submodules, one per data collaborative (their own repos, own history)
│   └── femhealth-data-collaborative/
│
├── audits/                  Tooling that audits datasets published to CivicDataSpace
│   └── cds-audit/           Metadata, completeness, and AI-readiness scoring against upload guidelines
│
├── data_model/               Knowledge graphs and shared schemas for platform intelligence
│   ├── knowledge-graph/
│   └── schemas/
│       └── data_dictionary_template.csv  Reusable indicator data-dictionary schema
│
├── canonical_entities/       Canonical reference data, organised by source/region
│   └── india/
│       ├── maps/            Admin boundary download + transformation tooling (NIC ArcGIS service)
│       └── example/         Reference dataset showing the shape canonical outputs should take
│
├── docs/                     Platform + repo documentation
│   ├── architecture.md
│   └── collaboratives.md
│
├── CITATION.cff
├── LICENSE
└── README.md
```

---

## Getting started

### Clone with all collaboratives

```bash
git clone --recurse-submodules https://github.com/CivicDataLab/DataSpace-data-ecosystem.git
cd DataSpace-data-ecosystem
```

Already cloned without `--recurse-submodules`? Run `git submodule update --init --recursive`.

### Run a dataset audit

```bash
cd audits/cds-audit
python -m venv .venv && source .venv/bin/activate
pip install -e ".[deep]"
cds-audit probe   # confirm the CivicDataSpace API is reachable
cds-audit run     # audit the whole catalogue -> reports/
```

See [`audits/cds-audit/README.md`](audits/cds-audit/README.md) for the full guide, scoring rules, and CI
scheduling.

### Fetch admin boundaries (India)

```bash
cd canonical_entities/india/maps
pip install geopandas requests numpy pandas
python map_exporter.py --state Assam
python map_transformer.py --state assam
```

See [`canonical_entities/india/maps/README.md`](canonical_entities/india/maps/README.md).

### Add or update a collaborative

See [`docs/collaboratives.md`](docs/collaboratives.md).

---

## Data extraction and interoperability

All inputs and outputs across this ecosystem favour non-proprietary, machine-readable formats:

- **Tabular data** — CSV (UTF-8) with documented schemas
- **Geometries** — GeoJSON in EPSG:4326 (WGS 84)
- **Documentation** — Markdown

Each collaborative and tool documents its own schemas and outputs inline. `data_model/schemas/` holds a
reusable data-dictionary template (`indicatorSlug,indicatorTitle,factor,unit,description,datasource`) for
documenting indicator columns consistently across collaboratives.

---

## Citation

If you use this work in research or operational practice, please cite it. A `CITATION.cff` file is included
for reference managers; in plain text:

> CivicDataLab. (2026). *DataSpace Data Ecosystem*. https://github.com/CivicDataLab/DataSpace-data-ecosystem

---

## License

All source code in this repository is licensed under the **GNU Affero General Public License v3.0**
(AGPL-3.0). The full license text is in [`LICENSE`](LICENSE). Each submodule under `collaboratives/` carries
its own license — check the submodule's own repository before reusing its code or data.

Sample and derived datasets included directly in this repository are released under the **Creative Commons
Attribution 4.0 International** license (CC-BY 4.0), unless a more restrictive licence applies to a specific
upstream source (in which case the upstream licence governs that file).

---

## Contact

CivicDataLab · <info@civicdatalab.in> · https://civicdatalab.in
