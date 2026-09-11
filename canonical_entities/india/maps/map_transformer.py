#!/usr/bin/env python3
"""
Enrich boundary GeoJSONs produced by map_exporter.py and export flat CSVs.

Usage:
    python map_transformer.py [--state assam] [--geojson-dir Geojson] [--out-dir csv]

If --state is omitted, it is inferred from the first GeoJSON file found in --geojson-dir.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent

# CT (Census Town) and OG (Out Growth) are the urban types in the village shapefile.
# Statutory towns (M Corp., M, etc.) are in a separate town shapefile.
URBAN_LGD_SUFFIXES = ["M Corp.", "M", "NP", "NPP", "NAC", "CB", "CT", "OG", "INA", "IT"]

# Keywords in `vilnam_soi` that mark a row as a forest/reserved area rather than a settlement.
FOREST_KEYWORDS = ["FOREST", "R.F", "D.P.F", "JUNGLE", " HILL", "R F"]


def _infer_state(geojson_dir: Path) -> str:
    geojsons = sorted(geojson_dir.glob("*.geojson"))
    if not geojsons:
        raise SystemExit(f"No .geojson files found in {geojson_dir}. Run map_exporter.py first, or pass --state.")
    return geojsons[0].stem.split("_")[0]


def _add_unit_ids(geojson_dir: Path, out_dir: Path, state: str) -> None:
    district = gpd.read_file(geojson_dir / f"{state}_districts.geojson")
    district["unit_id"] = district["stcode11"] + "-" + district["dtcode11"]
    district.drop(columns="geometry").to_csv(out_dir / f"{state}_districts.csv", index=False)

    subdistrict = gpd.read_file(geojson_dir / f"{state}_subdistricts.geojson")
    subdistrict["unit_id"] = (
        subdistrict["stcode11"] + "-" + subdistrict["dtcode11"] + "-" + subdistrict["sdtcode11"]
    )
    subdistrict.drop(columns="geometry").to_csv(out_dir / f"{state}_subdistricts.csv", index=False)


def _classify_urban(villages_gdf: gpd.GeoDataFrame, state: str) -> gpd.GeoDataFrame:
    village_urban = villages_gdf.replace(r"^\s*$", np.nan, regex=True)
    village_urban = village_urban.dropna(subset=["vilnam_soi", "vilname11", "gp_name"])
    village_urban = village_urban.loc[village_urban["stname"] == state.upper()]
    village_urban = village_urban.copy()
    village_urban["vilnam_soi"] = village_urban["vilnam_soi"].str.upper()

    for keyword in FOREST_KEYWORDS:
        village_urban = village_urban[~village_urban["vilnam_soi"].str.contains(keyword, na=False, regex=False)]

    # LGD urban classification: the ULB type is the parenthesised suffix on vilname11.
    suffix_pattern = r"\(([^)]+)\)$"
    village_urban["_ulb_type"] = village_urban["vilname11"].str.extract(suffix_pattern, expand=False)
    village_urban["is_urban"] = village_urban["_ulb_type"].isin(URBAN_LGD_SUFFIXES)
    return village_urban


def run(state: str, geojson_dir: Path, out_dir: Path) -> None:
    geojson_dir = geojson_dir.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    _add_unit_ids(geojson_dir, out_dir, state)

    villages_gdf = gpd.read_file(geojson_dir / f"{state}_villages.geojson")
    villages_gdf.drop(columns="geometry").to_csv(out_dir / f"{state}_villages.csv", index=False)

    village_urban = _classify_urban(villages_gdf, state)
    urban_gdf = village_urban[village_urban["is_urban"]]
    rural_gdf = village_urban[~village_urban["is_urban"]]

    print(f"Urban (CT + OG): {len(urban_gdf)}")
    print(f"Rural          : {len(rural_gdf)}")
    print(f"Total          : {len(village_urban)}")

    urban_gdf.to_file(geojson_dir / f"{state}_urban.geojson", driver="GeoJSON")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich and classify India admin boundary GeoJSONs into CSVs.")
    parser.add_argument("--state", help="State name in the file prefix used by map_exporter.py (e.g. assam).")
    parser.add_argument(
        "--geojson-dir", type=Path, default=SCRIPT_DIR / "Geojson", help="Directory of exporter GeoJSON output."
    )
    parser.add_argument("--out-dir", type=Path, default=SCRIPT_DIR / "csv", help="Directory to write CSV output to.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    state = args.state.lower() if args.state else _infer_state(args.geojson_dir)
    run(state, args.geojson_dir, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
