"""
Generate a small, geography-neutral synthetic sample dataset.

This module produces the synthetic sample inputs that let the risk-score model
run end-to-end without first running a real data pipeline:

    <data-dir>/MASTER_VARIABLES.csv    one row per geographic unit per month
    <data-dir>/district_objectid.csv   parent_unit name -> parent-level unit_id

The data is entirely fictional. Place names, identifiers and values are
invented and chosen only so that the pipeline exercises all of its branches
(every factor produces a spread of 1-5 classes). The column set matches the
generic ``scores_config.toml``. For a real-world example with genuine
administrative units and data sources, see ``contrib/india/example/``.

The generator is deterministic (fixed RNG seed), so re-running it reproduces
the same CSVs exactly.

Usage:
    drsm generate-sample-data [--data-dir DIR] [--input-file NAME]
"""

import numpy as np
import pandas as pd

from disaster_risk_score_model.common import DISTRICT_LOOKUP_FILE
from disaster_risk_score_model.config import resolve_data_dir, resolve_input_file

SEED = 42

# Fictional districts, each with a handful of sub-district units.
DISTRICTS = [
    ("Northmere", 4),
    ("Eastfen", 4),
    ("Southwater", 4),
    ("Westmoor", 3),
    ("Riverend", 3),
    ("Lakeshire", 3),
]

# 24 consecutive months across two calendar years.
YEARS = [2021, 2022]
MONTHS = list(range(1, 13))

# Northern-hemisphere style monsoon: heavy rain mid-year.
WET_MONTHS = {6, 7, 8, 9}


def _season_factor(month: int) -> float:
    """Return a 0..1 wetness weight peaking in the wet season."""
    return 1.0 if month in WET_MONTHS else 0.15


def build_units():
    """
    Return (units, district_lookup_rows).

    units: list of dicts with unit_id, parent_unit, district_object_id and a
    set of static per-unit characteristics.
    """
    rng = np.random.default_rng(SEED)
    units = []
    lookup = []
    for d_idx, (district, n_sub) in enumerate(DISTRICTS, start=1):
        district_object_id = f"R01-D{d_idx:02d}"
        lookup.append({"parent_unit": district, "unit_id": district_object_id})
        # Per-district "development level" gives correlated infrastructure.
        development = rng.uniform(0.3, 0.9)
        for s_idx in range(1, n_sub + 1):
            area = rng.uniform(200, 2000)
            population = rng.uniform(40_000, 1_500_000)
            dev = float(np.clip(development + rng.uniform(-0.15, 0.15), 0.05, 0.98))
            units.append(
                {
                    "unit_id": f"{district_object_id}-S{s_idx:02d}",
                    "parent_unit": district,
                    "area_sqkm": area,
                    "_population_base": population,
                    "_dev": dev,
                    "drainage_density": rng.uniform(0.5, 4.0),
                    "mean_sex_ratio": rng.uniform(900, 1050),
                    "_flood_prone": rng.uniform(0.1, 1.0),
                }
            )
    return units, lookup


def generate(data_dir=None, input_file=None):
    rng = np.random.default_rng(SEED + 1)
    units, lookup = build_units()

    rows = []
    for year in YEARS:
        for month in MONTHS:
            season = _season_factor(month)
            for u in units:
                pop = u["_population_base"] * rng.uniform(0.98, 1.02)
                hhd = pop / rng.uniform(4.0, 5.0)
                dev = u["_dev"]
                area = u["area_sqkm"]
                flood = u["_flood_prone"]

                # --- Hazard inputs (rainfall / inundation) ---
                mean_rain = max(0.0, rng.normal(40 + 220 * season, 25))
                max_rain = mean_rain * rng.uniform(1.4, 2.6)
                inund_mean = max(0.0, rng.normal(season * flood * 6, 1.2))
                inund_sum = inund_mean * rng.uniform(80, 200)

                # --- Exposure ---
                aged = pop * rng.uniform(0.07, 0.13)

                # --- Vulnerability condition variables ---
                schools = dev * area * rng.uniform(0.05, 0.2)
                health = dev * area * rng.uniform(0.01, 0.05)
                rail = dev * area * rng.uniform(0.0, 0.1)
                road = dev * area * rng.uniform(0.5, 2.0)
                sown = area * rng.uniform(0.1, 0.5)
                electricity = float(np.clip(dev + rng.uniform(-0.1, 0.1), 0.3, 1.0))
                piped = float(np.clip(dev * 100 + rng.uniform(-15, 15), 5, 98))
                no_san = float(np.clip((1 - dev) * 45 + rng.uniform(-5, 5), 1, 45))

                # --- Flood-damage outputs ---
                # Seasonal and flood-proneness drive the overall level, but each
                # variable gets an independent multiplier and a small positive floor.
                # The independence matters: the DEA step rescales each damage column
                # per month, so if a single unit were the maximum in *every* damage
                # column its scaled outputs would all collapse to zero and the LP
                # objective would be empty. Decorrelating the column maxima (and
                # keeping a floor) avoids that degenerate case for small samples.
                damage_scale = season * flood

                def dmg(level):
                    return max(0.01, rng.normal(level, level * 0.5) * rng.uniform(0.3, 1.7))

                fp_failures = dmg(damage_scale * 4)
                fp_damaged = dmg(damage_scale * 5)
                lives = dmg(damage_scale * (pop / 1e5) * 1.5)
                affected = dmg(damage_scale * pop * 0.05)
                crop = dmg(damage_scale * sown * 0.3)
                roads_dmg = dmg(damage_scale * 30)
                bridge_dmg = dmg(damage_scale * 6)

                # --- Government response (spending; rises during/after the season) ---
                resp_scale = (season + 0.2) * (0.5 + flood)
                total_proc = max(0.0, rng.normal(resp_scale * 5_000_000, 1_500_000))
                fund_sanctions = max(0.0, rng.normal(resp_scale * 2_000_000, 600_000))
                fund_proc = max(0.0, rng.normal(resp_scale * 1_200_000, 400_000))

                rows.append(
                    {
                        "unit_id": u["unit_id"],
                        "parent_unit": u["parent_unit"],
                        "time_period": f"{year}-{month:02d}",
                        "area_sqkm": round(area, 2),
                        # hazard
                        "inundation_intensity_mean_nonzero": round(inund_mean, 4),
                        "inundation_intensity_sum": round(inund_sum, 2),
                        "drainage_density": round(u["drainage_density"], 3),
                        "mean_rain": round(mean_rain, 2),
                        "max_rain": round(max_rain, 2),
                        # exposure
                        "total_population": round(pop, 0),
                        "total_households": round(hhd, 0),
                        # vulnerability condition
                        "mean_sex_ratio": round(u["mean_sex_ratio"], 1),
                        "schools_count": round(schools, 0),
                        "health_centres_count": round(health, 0),
                        "rail_length": round(rail, 2),
                        "road_length": round(road, 2),
                        "net_sown_area_ha": round(sown, 2),
                        "electricity_access": round(electricity, 3),
                        "piped_water_households_pct": round(piped, 2),
                        "no_sanitation_households_pct": round(no_san, 2),
                        "elderly_population": round(aged, 0),
                        "flood_protection_failures": round(fp_failures, 2),
                        # vulnerability damage
                        "human_lives_lost": round(lives, 0),
                        "population_affected_total": round(affected, 0),
                        "crop_area": round(crop, 2),
                        "flood_protection_damaged": round(fp_damaged, 2),
                        "roads_damaged": round(roads_dmg, 2),
                        "bridges_damaged": round(bridge_dmg, 2),
                        # government response
                        "total_procurement_value": round(total_proc, 0),
                        "disaster_fund_sanctions_value": round(fund_sanctions, 0),
                        "disaster_fund_procurement_value": round(fund_proc, 0),
                    }
                )

    df = pd.DataFrame(rows)
    lookup_df = pd.DataFrame(lookup)

    data_dir = resolve_data_dir(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    master_path = data_dir / resolve_input_file(input_file)
    lookup_path = data_dir / DISTRICT_LOOKUP_FILE
    df.to_csv(master_path, index=False)
    lookup_df.to_csv(lookup_path, index=False)

    print(f"Wrote {len(df):,} rows x {df.shape[1]} columns -> {master_path}")
    print(f"Wrote {len(lookup_df)} districts -> {lookup_path}")
