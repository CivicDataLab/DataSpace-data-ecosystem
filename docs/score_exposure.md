# Exposure Score — Methodology

**Command:** `drsm exposure` (module `disaster_risk_score_model.exposure`)
**Config:** `scores_config.toml` → `[exposure.*]`
**Input:** `<data-dir>/MASTER_VARIABLES.csv`
**Output:** `<data-dir>/factor_scores_l1_exposure.csv`
**Output column added:** `exposure` (integer 1–5)

---

## Purpose

The Exposure score classifies each geographic unit for each month on a 1–5 scale representing the size of the population and household base exposed to flood risk. Units with larger populations and more households are considered more exposed, regardless of the physical flood conditions (which are captured in the Hazard score).

**Score interpretation:** 1 = Very Low exposure, 5 = Very High exposure.

---

## Methodology Overview

```mermaid
flowchart TD
    A([MASTER_VARIABLES.csv]) --> B

    subgraph PerMonth["Processed independently per month"]
        B[Extract exposure variables\nfor that month] --> C

        C[MinMax scaling\nper variable, within month\n0–1 range] --> D

        D[Sum scaled variables\n→ composite exposure score] --> E

        E[Compute month mean μ\nand std deviation σ] --> F

        F{Std-dev threshold bands\nμ, μ+σ, μ+2σ, μ+3σ} --> G

        G[Assign class 1–5]
    end

    G --> H[Concatenate all months]
    H --> I[Merge back to master]
    I --> J[factor_scores_l1_exposure.csv\nexposure column]
```

---

## Step-by-Step Computation

### Step 1 — MinMax Scaling (per month)

Each exposure variable is scaled to [0, 1] within the current month's data:

```
scaled[var] = (raw[var] − min(raw[var])) / (max(raw[var]) − min(raw[var]))
```

Scaling is applied **independently per month**, so each month's distribution is self-normalised.

### Step 2 — Composite Score

The scaled variables are summed to produce a composite exposure index:

```
composite = sum(scaled[var₁], scaled[var₂], ..., scaled[varₙ])
```

### Step 3 — Standard Deviation Classification

The composite score is classified using the month's mean (μ) and standard deviation (σ):

| Class | Condition |
|-------|-----------|
| 1 (Very Low) | composite ≤ μ |
| 2 (Low) | μ < composite ≤ μ + σ |
| 3 (Medium) | μ + σ < composite ≤ μ + 2σ |
| 4 (High) | μ + 2σ < composite ≤ μ + 3σ |
| 5 (Very High) | composite > μ + 3σ |

---

## Input Variable Requirements

| Column | Description | Minimum Requirement |
|--------|-------------|---------------------|
| `total_population` | Total estimated population in the unit | Any population count (census, modelled) |
| `total_households` | Total number of households in the unit | Any household count |

**Minimum viable configuration:** 1 variable is sufficient; the model works with any combination of population-type measures.

### Adapting to Different Data Sources

| Variable | Alternative sources acceptable |
|----------|-------------------------------|
| `total_population` | WorldPop, GPWv4, census block statistics, GHSL population grid, LandScan |
| `total_households` | National census household tables, Antyodaya survey HHD counts, proxy derived from population / average household size |

**Note on normalisation:** Because MinMax scaling is applied per month and the classification uses relative std-dev bands, the absolute units of the input variables do not matter — only the relative spatial distribution within a month.

---

## Output Schema

**File:** `factor_scores_l1_exposure.csv`

Contains all columns from `MASTER_VARIABLES.csv` plus:

| Column | Type | Description |
|--------|------|-------------|
| `exposure` | Integer (1–5) | Exposure class; 1 = Very Low, 5 = Very High |
