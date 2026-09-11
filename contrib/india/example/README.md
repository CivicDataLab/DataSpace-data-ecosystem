# Reference Example — India (Assam)

This directory holds a complete, **real-world** configuration of the risk-score
model for the state of **Assam, India** — the deployment the model was originally
built for. It exists so adopters can see a fully-populated configuration and a
genuine input dataset rather than only the synthetic sample produced by
`drsm generate-sample-data`.

Everything here is India-specific and is intentionally kept *outside* the generic
core:

- **Government finance schemes** — SDRF (State Disaster Response Fund), SOPD, RIDF,
  LTIF, CIDF tender and expenditure columns.
- **Administrative concepts** — LGD `unit_id` codes (`AA-BBB-CCCCC`), revenue-circle
  area (`rc_area`), embankment infrastructure, relief camps.
- **Fiscal calendar** — April–March (`fiscal_year.start_month = 4`).
- **Data sources** — IMD (rainfall), ISRO Bhuvan (inundation), WorldPop, NASADEM,
  Mission Antyodaya, BharatMaps, WRIS, and the Assam government tender/finance portals.

The administrative-boundary download and transformation tooling for India lives in
the sibling directory [`../maps/`](../maps/).

## Contents

```
config/   Full Assam configuration (scores_config.toml + topsis_config.toml)
data/     Assam MASTER_VARIABLES.csv, district_objectid.csv, data_dictionary.csv,
          and Transformed_Assam_Data.csv
```

## Running the example

Point `drsm` at this directory's `config/` and `data/` folders. Unlike the old
script-based workflow, this no longer has to run from the repository root — the
data directory is supplied explicitly:

```bash
drsm run \
  --config-dir contrib/india/example/config \
  --data-dir   contrib/india/example/data
```

All inputs are read from, and all outputs are written to, the directory given by
`--data-dir`. The generated factor-score and risk-score CSVs are git-ignored;
the committed `MASTER_VARIABLES.csv` and `district_objectid.csv` are the real
Assam inputs. Individual steps accept the same flags (e.g.
`drsm hazard --config-dir … --data-dir …`).

Equivalently, you can set the `RISK_MODEL_CONFIG_DIR` / `RISK_MODEL_DATA_DIR`
environment variables instead of passing the flags on every call.

## License

The Assam sample/derived datasets in this directory are released under
**Creative Commons Attribution 4.0 International** (CC-BY 4.0), unless a more
restrictive licence applies to a specific upstream source, in which case the
upstream licence governs that file.
