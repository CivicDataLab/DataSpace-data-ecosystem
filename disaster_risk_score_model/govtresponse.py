from disaster_risk_score_model.common import (
    FINANCIAL_YEAR_COL,
    GOVTRESPONSE_COL,
    TIME_COLUMN,
    UNIT_ID_COLUMN,
    classify_std_intervals,
    load_master,
    merge_and_save,
    score_by_month,
)
from disaster_risk_score_model.config import load_config


def get_financial_year(time_period, start_month):
    year = int(time_period.split("-")[0])
    month = int(time_period.split("-")[1])
    if month >= start_month:
        return f"{year}-{year + 1}"
    return f"{year - 1}-{year}"


def main(config_dir=None, data_dir=None, input_file=None):
    cfg = load_config("govtresponse", config_dir=config_dir)

    value_vars = cfg["inputs"]["variables"]
    start_month = cfg["fiscal_year"]["start_month"]
    classes = cfg["classification"]["classes"]

    master, data_path = load_master(data_dir, input_file)

    master[FINANCIAL_YEAR_COL] = master[TIME_COLUMN].apply(lambda x: get_financial_year(x, start_month))

    # Accumulate spending within each fiscal year before scoring.
    for var in value_vars:
        master[var] = master.groupby([UNIT_ID_COLUMN, FINANCIAL_YEAR_COL])[var].cumsum()

    scored = score_by_month(
        master,
        value_vars,
        lambda d: classify_std_intervals(d, value_vars, classes, GOVTRESPONSE_COL),
    )
    merge_and_save(
        master,
        scored,
        [TIME_COLUMN, UNIT_ID_COLUMN],
        [GOVTRESPONSE_COL],
        data_path / cfg["output"]["file"],
    )
    print("Results saved successfully!")
