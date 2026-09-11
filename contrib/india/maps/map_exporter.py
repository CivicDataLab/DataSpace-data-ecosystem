#!/usr/bin/env python3
"""
Download NIC admin2024 boundaries for a given state and export as GeoJSON.

Usage:
    python map_exporter.py [level]

level can be one of: state, district, subdistrict, village, all (default: all)

Examples:
    python map_exporter.py village      # only village map + village CSV
    python map_exporter.py district
    python map_exporter.py all          # state, districts, subdistricts, villages

Source service:
https://webgis1.nic.in/nicstreet/rest/services/admin2024/MapServer/
Layers:
- State Boundary: 9  (field: stname)
- District boundary: 10
- Subdistrict boundary: 11
- Village boundary: 12

"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

try:
    import geopandas as gpd
except ImportError as e:
    raise SystemExit("Missing dependency: geopandas. Install with: pip install geopandas") from e


VALID_LEVELS = {"state", "district", "subdistrict", "village", "all"}

# compute a base directory relative to this script so that the exporter
# always writes into the repo tree regardless of the current working
# directory
script_dir = Path(__file__).resolve().parent
base_dir = script_dir.parent
OUTPUT_DIR = base_dir / "Geojson"


BASE_URL = "https://webgis1.nic.in/nicstreet/rest/services/admin2024/MapServer"

STATE_LAYER = 9
DISTRICT_LAYER = 10
SUBDISTRICT_LAYER = 11
VILLAGE_LAYER = 12

MAX_RECORD_COUNT = 2000  # service maxRecordCount is 2000


def _escape_sql_string(s: str) -> str:
    # ArcGIS REST uses SQL-like where clauses; escape single quotes
    return s.replace("'", "''")


def arcgis_query_geojson(
    layer_id: int,
    where: str = "1=1",
    geometry: str | None = None,
    geometry_type: str | None = None,
    spatial_rel: str = "esriSpatialRelIntersects",
    in_sr: int = 4326,
    out_sr: int = 4326,
    out_fields: str = "*",
    return_geometry: bool = True,
    timeout: int = 60,
    sleep_s: float = 0.1,
) -> dict[str, Any]:
    """
    Query an ArcGIS REST layer and return a GeoJSON FeatureCollection.

    Uses pagination (resultOffset/resultRecordCount).
    """
    url = f"{BASE_URL}/{layer_id}/query"
    session = requests.Session()

    all_features: list[dict[str, Any]] = []
    offset = 0

    while True:
        data = {
            "f": "geojson",
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true" if return_geometry else "false",
            "outSR": str(out_sr),
            "resultOffset": str(offset),
            "resultRecordCount": str(MAX_RECORD_COUNT),
        }

        if geometry is not None and geometry_type is not None:
            data.update(
                {
                    "geometry": geometry,
                    "geometryType": geometry_type,
                    "spatialRel": spatial_rel,
                    "inSR": str(in_sr),
                }
            )

        # POST avoids URL-length issues and is generally safer for complex queries
        resp = session.post(url, data=data, timeout=timeout)
        resp.raise_for_status()

        try:
            fc = resp.json()
        except json.JSONDecodeError as err:
            raise RuntimeError(f"Non-JSON response from server for layer {layer_id}: {resp.text[:500]}") from err

        if "error" in fc:
            raise RuntimeError(f"ArcGIS error for layer {layer_id}: {fc['error']}")

        features = fc.get("features", [])
        all_features.extend(features)

        # If fewer than max, we're done
        if len(features) < MAX_RECORD_COUNT:
            break

        offset += MAX_RECORD_COUNT
        time.sleep(sleep_s)

    # Return a FeatureCollection-like dict
    return {"type": "FeatureCollection", "features": all_features}


def fetch_distinct_state_names(timeout: int = 60) -> list[str]:
    """Fetch distinct state names from layer 9 (stname)."""
    url = f"{BASE_URL}/{STATE_LAYER}/query"
    resp = requests.post(
        url,
        data={
            "f": "json",
            "where": "1=1",
            "outFields": "stname",
            "returnDistinctValues": "true",
            "returnGeometry": "false",
            "outSR": "4326",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"ArcGIS error fetching distinct state names: {data['error']}")
    names = []
    for feat in data.get("features", []):
        attrs = feat.get("attributes", {})
        if attrs.get("stname"):
            names.append(str(attrs["stname"]))
    return sorted(set(names))


def _export_villages(gdf_vil: gpd.GeoDataFrame, outdir: Path, state_name_lower: str) -> tuple[Path, Path]:
    vil_path = outdir / f"{state_name_lower}_villages.geojson"
    gdf_vil.to_file(vil_path, driver="GeoJSON")
    print(f"✓ Saved: {vil_path}")

    csv_path = outdir / f"{state_name_lower}_villages.csv"
    attr_cols = [c for c in gdf_vil.columns if c != gdf_vil.geometry.name]
    gdf_vil[attr_cols].to_csv(csv_path, index=False)
    print(f"✓ Saved: {csv_path}")

    return vil_path, csv_path


def main() -> int:
    # Parse optional positional argument for boundary level
    level = "all"
    if len(sys.argv) > 1:
        level = sys.argv[1].strip().lower()
        if level not in VALID_LEVELS:
            print(f"ERROR: Unknown level '{level}'. Choose from: {', '.join(sorted(VALID_LEVELS))}", file=sys.stderr)
            return 2

    state_input = input("Enter your state name: ").strip()
    outdir = OUTPUT_DIR.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading '{level}' boundaries for: {state_input}")
    print(f"Output directory: {outdir}")
    print("-" * 50)

    if not state_input:
        print("ERROR: State name cannot be empty.", file=sys.stderr)
        return 2

    # Always fetch the state polygon (needed for bbox and clipping)
    print("Fetching state boundary...")
    state_sql = f"UPPER(stname)=UPPER('{_escape_sql_string(state_input)}')"
    state_fc = arcgis_query_geojson(STATE_LAYER, where=state_sql)

    if not state_fc["features"]:
        print(f'ERROR: No match for state="{state_input}"', file=sys.stderr)
        try:
            valid = fetch_distinct_state_names()
            print("Valid state names include:", file=sys.stderr)
            for name in valid:
                print(f"  - {name}", file=sys.stderr)
        except Exception:
            print("Also failed to fetch valid state names.", file=sys.stderr)
        return 1

    gdf_state = gpd.GeoDataFrame.from_features(state_fc, crs="EPSG:4326")
    state_geom = gdf_state.unary_union
    gdf_state = gpd.GeoDataFrame(
        gdf_state.drop(columns="geometry", errors="ignore"), geometry=[state_geom], crs="EPSG:4326"
    )

    state_name_lower = state_input.lower().replace(" ", "_")
    minx, miny, maxx, maxy = gdf_state.total_bounds
    bbox_str = f"{minx},{miny},{maxx},{maxy}"

    saved: list[Path] = []

    if level in ("state", "all"):
        state_path = outdir / f"{state_name_lower}_state.geojson"
        gdf_state.to_file(state_path, driver="GeoJSON")
        print(f"✓ Saved: {state_path}")
        saved.append(state_path)

    if level in ("district", "all"):
        print("Fetching districts...")
        dist_fc = arcgis_query_geojson(
            DISTRICT_LAYER,
            where="1=1",
            geometry=bbox_str,
            geometry_type="esriGeometryEnvelope",
            in_sr=4326,
            out_sr=4326,
        )
        gdf_dist = gpd.GeoDataFrame.from_features(dist_fc, crs="EPSG:4326")
        if not gdf_dist.empty:
            gdf_dist = gpd.clip(gdf_dist, gdf_state)
        dist_path = outdir / f"{state_name_lower}_districts.geojson"
        gdf_dist.to_file(dist_path, driver="GeoJSON")
        print(f"✓ Saved: {dist_path}")
        saved.append(dist_path)

    if level in ("subdistrict", "all"):
        print("Fetching subdistricts...")
        subdist_fc = arcgis_query_geojson(
            SUBDISTRICT_LAYER,
            where="1=1",
            geometry=bbox_str,
            geometry_type="esriGeometryEnvelope",
            in_sr=4326,
            out_sr=4326,
        )
        gdf_subdist = gpd.GeoDataFrame.from_features(subdist_fc, crs="EPSG:4326")
        if not gdf_subdist.empty:
            gdf_subdist = gpd.clip(gdf_subdist, gdf_state)
        subdist_path = outdir / f"{state_name_lower}_subdistricts.geojson"
        gdf_subdist.to_file(subdist_path, driver="GeoJSON")
        print(f"✓ Saved: {subdist_path}")
        saved.append(subdist_path)

    if level in ("village", "all"):
        print("Fetching villages (this may take a while)...")
        vil_fc = arcgis_query_geojson(
            VILLAGE_LAYER,
            where="1=1",
            geometry=bbox_str,
            geometry_type="esriGeometryEnvelope",
            in_sr=4326,
            out_sr=4326,
        )
        gdf_vil = gpd.GeoDataFrame.from_features(vil_fc, crs="EPSG:4326")
        if not gdf_vil.empty:
            gdf_vil = gpd.clip(gdf_vil, gdf_state)
        vil_path, csv_path = _export_villages(gdf_vil, outdir, state_name_lower)
        saved.extend([vil_path, csv_path])

    print("-" * 50)
    print(f"SUCCESS! {len(saved)} file(s) saved:")
    for p in saved:
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
