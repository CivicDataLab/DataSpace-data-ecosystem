from disaster_risk_score_model.common import (
    EXPOSURE_COL,
    TIME_COLUMN,
    UNIT_ID_COLUMN,
    classify_std_intervals,
    load_master,
    merge_and_save,
    score_by_month,
)
from disaster_risk_score_model.config import load_config


def main(config_dir=None, data_dir=None, input_file=None):
    cfg = load_config("exposure", config_dir=config_dir)

    value_vars = cfg["inputs"]["variables"]
    classes = cfg["classification"]["classes"]

    master, data_path = load_master(data_dir, input_file)
    scored = score_by_month(
        master,
        value_vars,
        lambda d: classify_std_intervals(d, value_vars, classes, EXPOSURE_COL),
    )
    merge_and_save(
        master,
        scored,
        [TIME_COLUMN, UNIT_ID_COLUMN],
        [EXPOSURE_COL],
        data_path / cfg["output"]["file"],
    )
    print("Results saved successfully!")
