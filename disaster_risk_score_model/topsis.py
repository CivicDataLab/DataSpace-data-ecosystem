import numpy as np
import pandas as pd

from disaster_risk_score_model.common import (
    DISTRICT_LOOKUP_FILE,
    DISTRICT_RISK_FILE,
    EFFICIENCY_COL,
    EXPOSURE_COL,
    FINANCIAL_YEAR_COL,
    GOVTRESPONSE_COL,
    HAZARD_CLASS_COL,
    HAZARD_FLOAT_COL,
    PARENT_UNIT_COLUMN,
    REQUIRED_COLUMNS,
    RISK_SCORE_FILE,
    TIME_COLUMN,
    UNIT_ID_COLUMN,
    VULNERABILITY_COL,
    require_columns,
)
from disaster_risk_score_model.config import load_config, resolve_data_dir

# Each factor's output column paired with its weight key in [weights]. One ordered
# source of truth so the evaluation-matrix columns and the weight vector cannot
# drift out of alignment.
FACTOR_WEIGHTS = [
    (HAZARD_CLASS_COL, "flood_hazard"),
    (EXPOSURE_COL, "exposure"),
    (VULNERABILITY_COL, "vulnerability"),
    (GOVTRESPONSE_COL, "government_response"),
]


def topsis(evaluation_matrix, weight_matrix):
    """
    Score alternatives by TOPSIS closeness to the worst condition.

    Given an m-alternatives x n-criteria evaluation matrix and criteria weights,
    returns the closeness of each alternative to the worst condition, used as the
    composite score by the risk-score pipeline. All criteria are benefit criteria
    (higher is better), so the best condition is the column max and the worst is
    the column min.
    """
    evaluation_matrix = np.array(evaluation_matrix, dtype="float")

    weights = np.array(weight_matrix, dtype="float")
    weights = weights / weights.sum()

    # Normalise column-wise (L2 norm), then weight.
    normalized = evaluation_matrix / np.sqrt((evaluation_matrix**2).sum(axis=0))
    weighted = normalized * weights

    # L2 distance of each alternative to the best and worst conditions.
    best_distance = np.sqrt(((weighted - weighted.max(axis=0)) ** 2).sum(axis=1))
    worst_distance = np.sqrt(((weighted - weighted.min(axis=0)) ** 2).sum(axis=1))

    with np.errstate(all="ignore"):
        return worst_distance / (worst_distance + best_distance)


def _kebab(col):
    return col.lower().replace("_", "-").replace(" ", "-")


def _parent_unit_factor_score(topsis_df, col, dist_ids, n_bins, labels, parent_col, time_col):
    dist = topsis_df.groupby([parent_col, time_col])[col].mean().reset_index()
    dist[col] = pd.cut(dist[col], bins=n_bins, precision=0, labels=labels)
    return dist.merge(dist_ids, on=parent_col)


def apply_rounding_rules(df, rules):
    for column, decimals in rules.items():
        if column in df.columns:
            df[column] = df[column].round(decimals)
    return df


def main(config_dir=None, data_dir=None):
    cfg = load_config("topsis", config_dir=config_dir)

    # The block-level result has its column names kebab-cased (see below), so the
    # parent-unit aggregation step keys on the kebab-cased forms of these columns.
    time_out = _kebab(TIME_COLUMN)
    parent_out = _kebab(PARENT_UNIT_COLUMN)

    factor_cols = [col for col, _ in FACTOR_WEIGHTS]
    weights = [cfg["weights"][weight_key] for _, weight_key in FACTOR_WEIGHTS]
    n_bins = cfg["classification"]["n_bins"]
    # The enrichment sections are optional; a minimal config may omit them and
    # still produce the core risk scores.
    cumulative_vars = cfg.get("cumulative_vars", {}).get("variables", [])
    # Config keys are written in snake_case (one spelling per file); the output
    # columns they refer to are kebab-cased, so kebab the keys here to match.
    aggregation_rules = {_kebab(k): v for k, v in cfg.get("indicators", {}).items()}
    indicators = list(aggregation_rules.keys())
    rounding_rules = {_kebab(k): v for k, v in cfg.get("rounding", {}).items()}

    data_dir = resolve_data_dir(data_dir)

    factor_files = sorted(data_dir.glob("factor_scores_l1*.csv"))

    # Extra per-unit columns to carry through from the factor files (only those
    # actually present are kept), used downstream for display/diagnostics.
    additional_columns = [FINANCIAL_YEAR_COL, EFFICIENCY_COL, HAZARD_FLOAT_COL]

    merged_df = pd.read_csv(factor_files[0])
    for path in factor_files[1:]:
        df = pd.read_csv(path)
        selected = [c for c in factor_cols if c in df.columns]
        selected_extra = [c for c in additional_columns if c in df.columns]
        df = df[[*selected, UNIT_ID_COLUMN, TIME_COLUMN, *selected_extra]]
        merged_df = merged_df.merge(df, on=[UNIT_ID_COLUMN, TIME_COLUMN], how="inner", suffixes=("", "_drop"))
        merged_df = merged_df.loc[:, ~merged_df.columns.str.endswith("_drop")]

    require_columns(merged_df, REQUIRED_COLUMNS, "factor score CSVs")

    merged_df = merged_df.sort_values(by=[UNIT_ID_COLUMN, FINANCIAL_YEAR_COL, TIME_COLUMN])

    for var in cumulative_vars:
        if var in merged_df.columns:
            merged_df[var + "_fy_cumsum"] = merged_df.groupby([UNIT_ID_COLUMN, FINANCIAL_YEAR_COL])[var].cumsum()

    dist_ids = pd.read_csv(data_dir / DISTRICT_LOOKUP_FILE)
    # Match the kebab-case naming applied to the block-level result below, so the
    # parent-unit lookup id lands in the same column as the block-level unit id
    # rather than a separate snake_case column after the final concat.
    dist_ids.columns = [_kebab(c) for c in dist_ids.columns]
    compositescorelabels = [str(i) for i in range(1, n_bins + 1)]

    df_months = []
    for month in merged_df[TIME_COLUMN].unique():
        df_month = merged_df[merged_df[TIME_COLUMN] == month]
        evaluation_matrix = np.array(df_month[factor_cols].values)

        df_month = df_month.copy()
        df_month["topsis_score"] = topsis(evaluation_matrix, weights)
        df_month = df_month.sort_values(by="topsis_score", ascending=False)

        compscore = pd.cut(
            df_month["topsis_score"],
            bins=n_bins,
            precision=0,
            labels=list(range(1, n_bins + 1)),
        )
        df_month["risk-score"] = compscore
        df_months.append(df_month)

    topsis_result = pd.concat(df_months)
    topsis_result.columns = [_kebab(col) for col in topsis_result.columns]

    topsis_result.to_csv(data_dir / RISK_SCORE_FILE, index=False)

    dist_vul = _parent_unit_factor_score(
        topsis_result,
        VULNERABILITY_COL,
        dist_ids,
        n_bins,
        compositescorelabels,
        parent_out,
        time_out,
    )
    dist_exp = _parent_unit_factor_score(
        topsis_result,
        EXPOSURE_COL,
        dist_ids,
        n_bins,
        compositescorelabels,
        parent_out,
        time_out,
    )
    dist_govt = _parent_unit_factor_score(
        topsis_result,
        GOVTRESPONSE_COL,
        dist_ids,
        n_bins,
        compositescorelabels,
        parent_out,
        time_out,
    )
    dist_haz = _parent_unit_factor_score(
        topsis_result,
        HAZARD_CLASS_COL,
        dist_ids,
        n_bins,
        compositescorelabels,
        parent_out,
        time_out,
    )

    topsis_result["risk-score"] = topsis_result["risk-score"].astype(int)
    dist_risk = topsis_result.groupby([parent_out, time_out])["risk-score"].mean().reset_index()
    dist_risk["risk-score"] = pd.cut(dist_risk["risk-score"], bins=n_bins, precision=0, labels=compositescorelabels)
    dist_risk = dist_risk.merge(dist_ids, on=parent_out)

    present_indicators = [c for c in indicators if c in topsis_result.columns]
    present_agg_rules = {k: v for k, v in aggregation_rules.items() if k in topsis_result.columns}

    dist_indicators = topsis_result.groupby([parent_out, time_out]).agg(present_agg_rules).reset_index()

    dist = pd.concat(
        [
            dist_vul.set_index([parent_out, time_out]),
            dist_exp.set_index([parent_out, time_out])[EXPOSURE_COL],
            dist_govt.set_index([parent_out, time_out])[GOVTRESPONSE_COL],
            dist_haz.set_index([parent_out, time_out])[HAZARD_CLASS_COL],
            dist_risk.set_index([parent_out, time_out])["risk-score"],
            dist_indicators.set_index([parent_out, time_out])[present_indicators],
        ],
        axis=1,
    ).reset_index()

    final = pd.concat([topsis_result, dist], ignore_index=True)

    final = apply_rounding_rules(final, rounding_rules)

    # Optional, config-driven post-processing (see the [derivations] and [renames]
    # sections of the TOPSIS config). All of this is optional: a geography that
    # omits those sections — as the generic config does — is unaffected. Config
    # keys are written in snake_case and kebab-cased here to match the output
    # columns. This keeps any geography-specific display logic in that geography's
    # own config rather than hardcoded in the shared pipeline.
    derivations = cfg.get("derivations", {})
    # Scale a column in place by a constant factor (e.g. fraction -> percentage).
    for raw_column, factor in derivations.get("scale", {}).items():
        column = _kebab(raw_column)
        if column in final.columns:
            final[column] = final[column] * factor
    # Create a new column as the row-wise sum of components, only when all are present.
    for new_column, raw_components in derivations.get("sum", {}).items():
        components = [_kebab(c) for c in raw_components]
        if all(c in final.columns for c in components):
            final[_kebab(new_column)] = final[components].sum(axis=1)

    # Optional column renames; missing columns are ignored.
    final = final.rename(
        columns={_kebab(k): _kebab(v) for k, v in cfg.get("renames", {}).items()},
    )

    final.to_csv(data_dir / DISTRICT_RISK_FILE, index=False)
    print("Risk score computation complete.")
