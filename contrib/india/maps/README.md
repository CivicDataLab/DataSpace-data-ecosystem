# Maps — Administrative Boundary Tooling (India)

> These scripts are India-specific. They download from India's NIC admin2024 ArcGIS service and apply LGD urban/rural classification.

Two scripts for downloading and preparing India administrative boundary data for use with the IDS-DRR risk score model. Run them in order: **export → transform**.

---

## Scripts

### 1. `map_exporter.py` — Download boundaries from NIC

Downloads state, district, subdistrict, and village boundaries from the [NIC admin2024 ArcGIS REST service](https://webgis1.nic.in/nicstreet/rest/services/admin2024/MapServer/) and writes them as GeoJSON to `Geojson/`.

**Source layers used**

| Layer | ID |
|-------|----|
| State boundary | 9 |
| Districts | 10 |
| Subdistricts | 11 |
| Villages | 12 |

**Usage**

```bash
cd contrib/india/maps
python map_exporter.py
# You will be prompted: enter your state name (e.g. Assam, Odisha)
```

**Outputs** (written to `Geojson/` next to the scripts; created on first run)

```
{state}_state.geojson
{state}_districts.geojson
{state}_subdistricts.geojson
{state}_villages.geojson
```

Village downloads are large and paginate at 2 000 records per request — expect a few minutes for large states.

If you enter an unrecognised state name the script will print the list of valid names from the service.

---

### 2. `map_transformer.py` — Enrich and classify boundaries

Reads the GeoJSONs produced by `map_exporter.py`, adds `unit_id` join keys, applies urban/rural classification to the village layer, and writes flat CSV exports.

Run from the `contrib/india/maps/` directory (the script resolves paths relative to its own location):

```bash
cd contrib/india/maps
python map_transformer.py
```

**What it does**

| Step | Detail |
|------|--------|
| Districts `unit_id` | Concatenates Census 2011 codes: `stcode11-dtcode11` |
| Subdistricts `unit_id` | Concatenates: `stcode11-dtcode11-sdtcode11` |
| Urban/rural split | Classifies villages by their LGD name suffix (see below) |
| Forest/reserved area filter | Removes rows whose `vilnam_soi` contains FOREST, R.F., D.P.F., JUNGLE, HILL, R F |

**Urban classification**

Villages are classified as urban if their `vilname11` field ends with one of the following LGD suffixes:

`M Corp.`, `M`, `NP`, `NPP`, `NAC`, `CB`, `CT`, `OG`, `INA`, `IT`

Census Towns (CT) and Out Growths (OG) appear in the village layer. Statutory towns (Municipal Corporations, Municipalities, etc.) are also captured via the same suffix check.

**Outputs**

| File | Location |
|------|----------|
| `{state}_districts.csv` | `csv/` |
| `{state}_subdistricts.csv` | `csv/` |
| `{state}_villages.csv` | `csv/` |
| `{state}_urban.geojson` | `Geojson/` |

---

## Folder structure

```
contrib/india/maps/
├── map_exporter.py       Download boundaries from NIC ArcGIS REST API
├── map_transformer.py    Enrich, classify, and export as CSV
├── Geojson/              Created by map_exporter on first run
└── csv/                  Created by map_transformer on first run
```

---

## Prerequisites

```
geopandas>=0.14
requests>=2.32
numpy>=1.26
pandas>=2.2
```

These come in with the project's `pyproject.toml` dependencies (`pip install -e .`).

---

## Notes

- All outputs use **EPSG:4326 (WGS 84)**.
- The `unit_id` keys produced here match the `unit_id` column expected by the risk score model.
- The NIC service uses 2024 administrative boundaries; Census 2011 codes (`stcode11`, `dtcode11`, `sdtcode11`) are retained as attributes for joining to statistical datasets.
