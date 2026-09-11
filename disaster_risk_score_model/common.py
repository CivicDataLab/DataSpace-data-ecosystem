"""
Shared helpers for the factor-scoring modules.

Collects the boilerplate that the per-factor modules (hazard, exposure,
vulnerability, government-response) otherwise repeat: silencing warnings,
reading the master variables CSV, the per-month scoring loop, and merging
scores back before writing the output CSV. Also holds the mean±std interval
classifier shared by exposure and government-response.
"""

import warnings

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tqdm import tqdm

from disaster_risk_score_model.config import resolve_data_dir, resolve_input_file

warnings.filterwarnings("ignore")

# Output column names produced by the factor modules and consumed by topsis.py.
# These are a fixed internal contract between those modules, NOT a geography
# knob: changing one here means changing it in the producing factor module and
# every consumer in TOPSIS together. They are deliberately not configurable,
# since nothing about a geography's input data depends on them. Display columns
# are kebab-cased on final write in TOPSIS.
HAZARD_CLASS_COL = "flood-hazard"
HAZARD_FLOAT_COL = "flood-hazard-float"
EXPOSURE_COL = "exposure"
VULNERABILITY_COL = "vulnerability"
EFFICIENCY_COL = "efficiency"
DAMAGE_SCORE_COL = "damage_score"
GOVTRESPONSE_COL = "government-response"
FINANCIAL_YEAR_COL = "financial_year"

# Required structural columns in the master input. These names are FIXED, not
# configurable: every geography must use them verbatim so the data dictionary,
# configs, and outputs stay consistent (see CONTRIBUTING naming conventions).
# - time_period: the time slice (monthly, ISO 8601 "YYYY-MM").
# - unit_id:     stable unique id of the geographic unit being scored.
# - parent_unit: the parent unit each row rolls up to in the TOPSIS step.
TIME_COLUMN = "time_period"
UNIT_ID_COLUMN = "unit_id"
PARENT_UNIT_COLUMN = "parent_unit"
REQUIRED_COLUMNS = (TIME_COLUMN, UNIT_ID_COLUMN, PARENT_UNIT_COLUMN)

# Fixed filenames for the TOPSIS district lookup (an input written by
# generate-sample-data) and the two TOPSIS outputs. Like the column names above,
# these are an internal pipeline contract and are not configurable; only their
# containing directory varies, via the resolved data dir.
DISTRICT_LOOKUP_FILE = "district_objectid.csv"
RISK_SCORE_FILE = "risk_score.csv"
DISTRICT_RISK_FILE = "risk_score_district.csv"


def require_columns(df, columns, source):
    """Raise a clear ``ValueError`` if any of ``columns`` is absent from ``df``."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"{source} is missing required column(s): {', '.join(missing)}. "
            f"Inputs must use the fixed structural column names "
            f"{TIME_COLUMN!r}, {UNIT_ID_COLUMN!r}, {PARENT_UNIT_COLUMN!r}."
        )


def load_master(data_dir=None, input_file=None):
    """
    Read the master variables CSV; return (df, data_dir).

    The returned ``data_dir`` is the resolved data directory, where callers
    write their output CSV. Fails fast if the input lacks a required structural
    column (``time_period``, ``unit_id``, ``parent_unit``).
    """
    data_path = resolve_data_dir(data_dir)
    input_path = data_path / resolve_input_file(input_file)
    df = pd.read_csv(input_path)
    require_columns(df, REQUIRED_COLUMNS, f"master input {input_path}")
    return df, data_path


def score_by_month(master, value_vars, fn):
    """Apply ``fn`` to each month's [value_vars + keys] slice and concat results."""
    results = []
    for month in tqdm(master[TIME_COLUMN].unique()):
        month_data = master[master[TIME_COLUMN] == month][[*value_vars, TIME_COLUMN, UNIT_ID_COLUMN]].copy()
        results.append(fn(month_data))
    return pd.concat(results)


def merge_and_save(master, scored, keys, cols, out_path):
    """Merge selected ``cols`` from ``scored`` back onto ``master`` and write CSV."""
    merged = master.merge(scored[keys + cols], on=keys)
    merged.to_csv(out_path, index=False)
    return merged


def classify_std_intervals(df, value_vars, classes, out_col):
    """
    MinMaxScaler -> row sum -> mean±std interval bins.

    Shared by exposure and government-response. Assumes ``len(classes) == 5``,
    matching the existing model.
    """
    df = df.copy()
    df[value_vars] = MinMaxScaler().fit_transform(df[value_vars])
    s = df[value_vars].sum(axis=1)
    mean, std = s.mean(), s.std()
    conditions = [
        s <= mean,
        (s > mean) & (s <= mean + std),
        (s > mean + std) & (s <= mean + 2 * std),
        (s > mean + 2 * std) & (s <= mean + 3 * std),
        s > mean + 3 * std,
    ]
    df[out_col] = np.select(conditions, classes)
    return df
