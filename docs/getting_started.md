# Getting Started — Adapting the Model to a New Geography

This guide walks through everything required to run the risk score model for a new geography, from collecting input data to producing the final composite risk score.

For methodology detail on any individual score, see the [document index](./README.md).

---

## Pipeline Overview

```mermaid
flowchart TD
    A([MASTER_VARIABLES.csv\nOne row per geographic unit per month]) --> B & C & D & E

    B[drsm hazard] --> B1[factor_scores_l1_flood-hazard.csv]
    C[drsm exposure] --> C1[factor_scores_l1_exposure.csv]
    D[drsm vulnerability] --> D1[factor_scores_l1_vulnerability.csv]
    E[drsm govtresponse] --> E1[factor_scores_l1_government-response.csv]

    B1 & C1 & D1 & E1 --> F[drsm topsis]

    F --> G([risk_score_district.csv\nComposite risk score — block and district level])
```

The four factor steps are independent of each other and can run in any order. The TOPSIS step must run after all four have completed; `drsm run` does all five in the correct order.

---

## Step 1 — Collect Your Input Data

All scripts read from a single master CSV file:

**`data/MASTER_VARIABLES.csv`**

One row per geographic unit per month. The following columns are required by every script:

These three **structural** columns use fixed names (they are not configurable) — rename your source columns to match:

| Column | Type | Description |
|--------|------|-------------|
| `unit_id` | String | Unique identifier for each geographic unit|
| `time_period` | String (`YYYY-MM`) | Month identifier, e.g. `2022-07` |
| `parent_unit` | String | Parent unit name each row rolls up to |

Note: `unit_id` can be any stable, unique identifier for a geographic unit — it does not need to follow any national coding scheme. The only requirements are that it is unique per unit and consistent across all input files and time periods. (For an example of a national scheme, the India reference example derives `unit_id` from the LGD code system in the format `AA-BBB-CCCCC` — state, district, subdistrict; see [`contrib/india/example/`](../contrib/india/example/).)

In addition, each factor score requires its own input variables. The table below shows the default variables and the minimum viable set for each factor:

### Hazard

| Column | Description | Min. requirement |
|--------|-------------|-----------------|
| `inundation_intensity_mean_nonzero` | Mean flood inundation intensity | Any measure of flood water extent or depth |
| `inundation_intensity_sum` | Cumulative inundation intensity | Any cumulative flood exposure measure |
| `drainage_density` | Stream length per unit area | km/km² or equivalent |
| `mean_rain` | Mean rainfall in the unit | mm or consistent unit |
| `max_rain` | Maximum rainfall pixel value | mm or consistent unit |

**Minimum viable:** any 2 or more of the above. See [score_hazard.md](./score_hazard.md) for alternative data sources.

### Exposure

| Column | Description | Min. requirement |
|--------|-------------|-----------------|
| `total_population` | Total estimated population | Any population count |
| `total_households` | Total number of households | Any household count |

**Minimum viable:** 1 variable. See [score_exposure.md](./score_exposure.md) for alternative data sources.

### Vulnerability

Requires two groups of variables:

**Condition inputs** (structural characteristics):

| Column | Description |
|--------|-------------|
| `mean_sex_ratio` | Females per 1,000 males |
| `schools_count` | Schools per administrative unit |
| `health_centres_count` | Health centres per administrative unit |
| `rail_length` | Rail track length per administrative unit |
| `road_length` | Road length per administrative unit |
| `net_sown_area_ha` | Agricultural sown area |
| `electricity_access` | Electricity access score (0–1) |
| `piped_water_households_pct` | Percentage of households with piped water |
| `no_sanitation_households_pct` | Percentage of households without sanitation |
| `elderly_population` | Elderly population per administrative unit |
| `flood_protection_failures` | Failures of flood-protection structures per administrative unit |

**Damage outputs** (observed flood impacts):

| Column | Description |
|--------|-------------|
| `human_lives_lost` | Deaths per capita |
| `population_affected_total` | Affected population per capita |
| `crop_area` | Damaged crop area / total sown area |
| `flood_protection_damaged` | Damage to flood-protection structures per km² |
| `roads_damaged` | Road damage per km² |
| `bridges_damaged` | Bridge damage per km² |

> **If damage data is not available:** The DEA method used for vulnerability scoring requires observed damage data to function correctly. Without it, consider replacing the DEA with a simpler weighted index over the condition variables. See [score_vulnerability.md](./score_vulnerability.md) for detail.

See [score_vulnerability.md](./score_vulnerability.md) for alternative data sources.

### Government Response

| Column | Description | Min. requirement |
|--------|-------------|-----------------|
| `total_procurement_value` | Total value of all flood-related contracts awarded | Any measure of total disaster-related procurement |
| `disaster_fund_sanctions_value` | Value of disaster-fund sanctions | Disaster-fund disbursements or equivalent |
| `disaster_fund_procurement_value` | Value of scheme-specific contracts | Optional; can be omitted |

**Minimum viable:** 1 variable representing total government flood expenditure. See [score_government_response.md](./score_government_response.md) for alternative data sources including OCDS-format procurement data. (These generic column names are placeholders — the India example uses scheme-specific names such as `SDRF_sanctions_awarded_value`.)

### District ID Lookup

**`data/district_objectid.csv`**

Maps district names to the platform's geographic IDs. Required by the TOPSIS script for district-level aggregation. Must contain:

| Column | Description |
|--------|-------------|
| `parent_unit` | Parent-unit name matching the values in `MASTER_VARIABLES.csv` |
| `unit_id` | Platform-level ID for that parent unit |

---

## Step 2 — Configure the Project

Scaffold an editable config with `drsm init-config ./config`. This writes two
TOML files; you do not need to edit any Python to adapt the model — only the TOML.
The config describes *what* your data is and *how* to score it. *Where* files
live is not in the config — it is supplied at run time via `--data-dir` /
`--input-file` (see Step 3).

### `scores_config.toml`

Holds one section per factor.

**Structural columns are fixed, not configured.** Every stage requires three
columns in the master input, and their names are fixed — rename your source
columns to match rather than configuring them:

| Column | Meaning |
|--------|---------|
| `time_period` | Monthly time slice, `YYYY-MM` |
| `unit_id` | Stable unique id of the geographic unit being scored |
| `parent_unit` | The parent unit each row rolls up to in the TOPSIS step |

**`[hazard.*]`**

| Setting | Default | Change if... |
|---------|---------|-------------|
| `hazard.inputs.variables` | 5 rainfall/inundation columns | You have different or fewer hazard variables |
| `hazard.classification.quantile_thresholds` | `[0.35, 0.60, 0.80, 0.95]` | You want different classification boundaries |
| `hazard.classification.classes` | `[1, 2, 3, 4, 5]` | You want a different number of risk classes |

**`[exposure.*]`**

| Setting | Default | Change if... |
|---------|---------|-------------|
| `exposure.inputs.variables` | `total_population`, `total_households` | You have different population/household columns (min: 1) |
| `exposure.classification.classes` | `[1, 2, 3, 4, 5]` | You want different class labels |

**`[vulnerability.*]`**

| Setting | Default | Change if... |
|---------|---------|-------------|
| `vulnerability.inputs.condition_vars` | 11 infrastructure/demographic columns | You have different structural condition variables |
| `vulnerability.inputs.damage_vars` | 6 flood damage columns | You have different damage variables (or none — see note below) |
| `vulnerability.inputs.inverted_inputs` | 6 resilience variables | You change condition_vars — update which variables are inverted |
| `vulnerability.inputs.neg_inputs` | 3 negative-polarity variables | You change condition_vars |
| `vulnerability.normalisation.per_capita` | 2 variables ÷ `total_population` | Update denominators to match your data |
| `vulnerability.normalisation.per_area` | 11 variables ÷ `area_sqkm` | Update denominators to match your data |
| `vulnerability.classification.n_classes` | `5` | You want a different number of vulnerability classes |
| `vulnerability.classification.damage_threshold` | `0.0001` | You want to change the damage significance threshold |

> **If damage data is not available:** The DEA method requires observed damage data. Without it, consider replacing the DEA with a simpler weighted index over `vulnerability.inputs.condition_vars` only.

**`[govtresponse.*]`**

| Setting | Default | Change if... |
|---------|---------|-------------|
| `govtresponse.inputs.variables` | 3 generic procurement/fund columns | You have different expenditure columns (min: 1) |
| `govtresponse.fiscal_year.start_month` | `1` (January / calendar year) | Your geography uses a different fiscal year calendar (the India example uses `4`) |

### `topsis_config.toml`

| Setting | Default | Change if... |
|---------|---------|-------------|
| `weights.*` | hazard=4, exposure=1, vulnerability=2, response=2 | You want to re-weight factors based on local context or policy |
| `classification.n_bins` | `5` | You want a different number of output risk classes |
| `[indicators]` | Generic columns with aggregation rules (optional) | Add/remove rows to match the columns in your data (missing ones are ignored) |
| `[rounding]` | Per-column decimal precision (optional) | You want different output rounding |

The `[indicators]`, `[rounding]`, `[cumulative_vars]`, `[derivations]` and
`[renames]` sections are optional enrichment of the district-level output; omit
them and the core risk scores are still produced. The district lookup
(`district_objectid.csv`) and the output filenames are fixed names resolved
under `--data-dir`, not config settings.

Column references in this file are written in `snake_case`; the final output columns
are lowercased and hyphenated to `kebab-case` automatically.

---

## Step 3 — Run the Pipeline

After `drsm init-config ./config`, generate the synthetic sample (or supply your
own `MASTER_VARIABLES.csv` in the data directory) and run the pipeline:

```bash
drsm generate-sample-data        # writes data/MASTER_VARIABLES.csv + district lookup
drsm run                         # all four factors, then TOPSIS
```

`drsm run` resolves the config from `./config` and reads/writes under `./data` by
default. Override either with flags or environment variables:

| Flag | Environment variable | Default |
|------|----------------------|---------|
| `--config-dir DIR` | `RISK_MODEL_CONFIG_DIR` | `./config` |
| `--data-dir DIR` | `RISK_MODEL_DATA_DIR` | `./data` |
| `--input-file NAME` | `RISK_MODEL_INPUT_FILE` | `MASTER_VARIABLES.csv` |

For example, to run the bundled India reference example:

```bash
drsm run --config-dir contrib/india/example/config --data-dir contrib/india/example/data
```

The four factor steps are independent and can run individually in any order
(`drsm hazard`, `drsm exposure`, `drsm vulnerability`, `drsm govtresponse`); the
TOPSIS step (`drsm topsis`) must run after all four. `drsm run` chains all five.

---

## Step 4 — Validate Your Outputs

After running all scripts, the following files should be present in `data/`:

| File | What to check |
|------|--------------|
| `factor_scores_l1_flood-hazard.csv` | `flood-hazard` column present; values in range 1–5; all 5 classes represented |
| `factor_scores_l1_exposure.csv` | `exposure` column present; values in range 1–5 |
| `factor_scores_l1_vulnerability.csv` | `vulnerability` column present; values in range 1–5; `efficiency` column in range 0–1 |
| `factor_scores_l1_government-response.csv` | `government-response` column present; values in range 1–5 |
| `risk_score.csv` | `risk-score` and `topsis-score` columns present; no missing values |
| `risk_score_district.csv` | Contains both block-level and district-level rows |

The hazard script also saves a diagnostic plot (`data/hazard_distribution.png`) showing the class distribution — a roughly decreasing distribution (more low-risk units than high-risk) is expected.

If any factor score shows only 1–2 classes represented, it usually indicates that the input variable has very low variance for that geography or time period. Review the input data distribution for that factor.
