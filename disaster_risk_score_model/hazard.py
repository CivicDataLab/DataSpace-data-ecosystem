import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from disaster_risk_score_model.common import (
    HAZARD_CLASS_COL,
    HAZARD_FLOAT_COL,
    TIME_COLUMN,
    UNIT_ID_COLUMN,
    load_master,
    merge_and_save,
    score_by_month,
)
from disaster_risk_score_model.config import load_config

# The model fixes the hazard scale at five classes (see classify_std_intervals
# in common.py, which makes the same assumption).
EXPECTED_HAZARD_CLASSES = 5


def calculate_hazard_scores(df, cfg):
    hazard_vars = cfg["inputs"]["variables"]

    transformed = pd.DataFrame()
    for var in hazard_vars:
        transformed[var] = np.log1p(df[var])
        mean = transformed[var].mean()
        std = transformed[var].std()
        transformed[var] = (transformed[var] - mean) / std

    df[HAZARD_FLOAT_COL] = transformed[hazard_vars].mean(axis=1)

    thresholds = [df[HAZARD_FLOAT_COL].quantile(q) for q in cfg["classification"]["quantile_thresholds"]]

    conditions = [df[HAZARD_FLOAT_COL] <= thresholds[0]]
    conditions.extend(
        (df[HAZARD_FLOAT_COL] > thresholds[i]) & (df[HAZARD_FLOAT_COL] <= thresholds[i + 1])
        for i in range(len(thresholds) - 1)
    )
    conditions.append(df[HAZARD_FLOAT_COL] > thresholds[-1])

    df[HAZARD_CLASS_COL] = np.select(conditions, cfg["classification"]["classes"], default=1)

    time_col = TIME_COLUMN
    object_id_col = UNIT_ID_COLUMN
    return df[[time_col, object_id_col, HAZARD_CLASS_COL, HAZARD_FLOAT_COL]]


def plot_hazard_distribution(df, cfg, output_path=None):
    figsize = cfg["plot"]["figsize"]

    _fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

    sns.countplot(data=df, x=HAZARD_CLASS_COL, ax=ax1, color="steelblue")
    ax1.set_title("Distribution of Flood Hazard Classes", pad=15)
    ax1.set_xlabel("Hazard Class")
    ax1.set_ylabel("Count")
    for p in ax1.patches:
        ax1.annotate(
            f"{int(p.get_height()):,}",
            (p.get_x() + p.get_width() / 2.0, p.get_height()),
            ha="center",
            va="bottom",
            fontsize=10,
        )

    sns.boxplot(data=df, x=HAZARD_CLASS_COL, y=HAZARD_FLOAT_COL, ax=ax2, color="lightblue")
    ax2.set_title("Distribution of Float Values by Hazard Class", pad=15)
    ax2.set_xlabel("Hazard Class")
    ax2.set_ylabel("Standardized Hazard Score")

    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=cfg["plot"]["dpi"], bbox_inches="tight")
        print(f"\nPlot saved to: {output_path}")


def validate_hazard_distribution(df):
    dist = df[HAZARD_CLASS_COL].value_counts().sort_index()
    total = len(df)

    print("\nHazard Distribution Validation:")
    print("-" * 40)
    for class_num in range(1, EXPECTED_HAZARD_CLASSES + 1):
        count = dist.get(class_num, 0)
        print(f"Class {class_num}: {count:,} ({count / total * 100:.1f}%)")

    checks = {
        "All classes present": len(dist) == EXPECTED_HAZARD_CLASSES,
        "Class range valid": df[HAZARD_CLASS_COL].between(1, EXPECTED_HAZARD_CLASSES).all(),
        "Decreasing trend": dist.iloc[0] > dist.iloc[-1],
        "No missing values": df[HAZARD_CLASS_COL].notna().all(),
    }

    print("\nValidation Checks:")
    print("-" * 40)
    for check, result in checks.items():
        print(f"{check}: {'✓' if result else '✗'}")

    return all(checks.values())


def print_variable_statistics(df, hazard_vars):
    print("\nVariable Statistics:")
    print("-" * 40)
    for var in hazard_vars:
        stats = df[var].describe()
        print(f"\n{var}:")
        print(f"  Mean: {stats['mean']:.2f}  Std: {stats['std']:.2f}")
        print(f"  Min:  {stats['min']:.2f}  Max: {stats['max']:.2f}")
        print(f"  Skew: {df[var].skew():.2f}")


def main(config_dir=None, data_dir=None, input_file=None):
    cfg = load_config("hazard", config_dir=config_dir)

    hazard_vars = cfg["inputs"]["variables"]

    master, data_path = load_master(data_dir, input_file)

    print_variable_statistics(master, hazard_vars)

    scored = score_by_month(
        master,
        hazard_vars,
        lambda d: calculate_hazard_scores(d, cfg),
    )
    master = merge_and_save(
        master,
        scored,
        [TIME_COLUMN, UNIT_ID_COLUMN],
        [HAZARD_CLASS_COL, HAZARD_FLOAT_COL],
        data_path / cfg["output"]["file"],
    )

    is_valid = validate_hazard_distribution(master)
    if is_valid:
        print("\nHazard distribution passes all validation checks!")
    else:
        print("\nWarning: Some validation checks failed. Please review the distribution.")

    plot_hazard_distribution(
        master,
        cfg,
        data_path / cfg["output"]["plot_file"],
    )

    print("\nResults saved successfully!")
