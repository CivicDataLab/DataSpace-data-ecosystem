from pathlib import Path

import geopandas as gpd
import numpy as np

script_dir = Path.cwd()
base_dir = script_dir.parent
geojsons = sorted((base_dir / "Geojson").glob("*.geojson"))
state = geojsons[0].stem.split("_")[0]

# export villages csv
villages_geojson = base_dir / "Geojson" / f"{state}_villages.geojson"
villages_gdf = gpd.read_file(villages_geojson)

# build path for the districts geojson of the current state
district_geojson = base_dir / "Geojson" / f"{state}_districts.geojson"
district = gpd.read_file(district_geojson)
district["unit_id"] = district["stcode11"] + "-" + district["dtcode11"]
district.to_file(base_dir / "csv" / f"{state}_districts.csv", driver="GeoJSON")  # Fix 1

subdistrict_geojson = base_dir / "Geojson" / f"{state}_subdistricts.geojson"
subdistrict = gpd.read_file(subdistrict_geojson)
subdistrict["unit_id"] = subdistrict["stcode11"] + "-" + subdistrict["dtcode11"] + "-" + subdistrict["sdtcode11"]
subdistrict.to_file(base_dir / "csv" / f"{state}_subdistricts.csv", driver="GeoJSON")  # Fix 2


### Prepare urban shapefile
village_df_unfiltered = villages_gdf.copy()
village_urban = village_df_unfiltered.replace(r"^\s*$", np.nan, regex=True)
village_urban = village_urban.dropna(subset=["vilnam_soi"])
village_urban = village_urban.dropna(subset=["vilname11"])
village_urban = village_urban.dropna(subset=["gp_name"])
village_urban = village_urban.loc[village_urban["stname"] == state.upper()]
village_urban["vilnam_soi"] = village_urban["vilnam_soi"].str.upper()
village_urban = village_urban[~village_urban["vilnam_soi"].str.contains("FOREST", na=False)]
village_urban = village_urban[~village_urban["vilnam_soi"].str.contains("R.F", na=False, regex=False)]
village_urban = village_urban[~village_urban["vilnam_soi"].str.contains("D.P.F", na=False, regex=False)]
village_urban = village_urban[~village_urban["vilnam_soi"].str.contains("JUNGLE", na=False)]
village_urban = village_urban[~village_urban["vilnam_soi"].str.contains(" HILL", na=False)]
village_urban = village_urban[~village_urban["vilnam_soi"].str.contains("R F", na=False)]

# --- LGD urban classification from vilname11 suffix ---
suffix_pattern = r"\(([^)]+)\)$"
village_urban = village_urban.copy()
village_urban["_ulb_type"] = village_urban["vilname11"].str.extract(suffix_pattern, expand=False)

# CT (Census Town) and OG (Out Growth) are the urban types in the village shapefile.
# Statutory towns (M Corp., M, etc.) are in a separate town shapefile.
urban_types = ["M Corp.", "M", "NP", "NPP", "NAC", "CB", "CT", "OG", "INA", "IT"]
village_urban["is_urban"] = village_urban["_ulb_type"].isin(urban_types)

urban_gdf = village_urban[village_urban["is_urban"]]
rural_gdf = village_urban[~village_urban["is_urban"]]

print(f"Urban (CT + OG): {len(urban_gdf)}")
print(f"Rural          : {len(rural_gdf)}")
print(f"Total          : {len(village_urban)}")

urban_gdf.to_file(base_dir / "Geojson" / f"{state}_urban.geojson", driver="GeoJSON")

villages_csv = villages_gdf.drop(columns=["geometry"])
villages_csv.to_csv(base_dir / "csv" / f"{state}_villages.csv", index=False)  # Fix 3
