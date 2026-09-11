"""Unit tests for shared helpers in ``common``."""

import pandas as pd
import pytest

from disaster_risk_score_model.common import (
    PARENT_UNIT_COLUMN,
    REQUIRED_COLUMNS,
    TIME_COLUMN,
    UNIT_ID_COLUMN,
    load_master,
    require_columns,
)


def test_require_columns_passes_when_all_present():
    df = pd.DataFrame(columns=[*REQUIRED_COLUMNS, "extra"])
    # Should not raise.
    require_columns(df, REQUIRED_COLUMNS, "test frame")


def test_require_columns_names_missing_column():
    df = pd.DataFrame(columns=[TIME_COLUMN, UNIT_ID_COLUMN])  # missing parent_unit
    with pytest.raises(ValueError, match=PARENT_UNIT_COLUMN):
        require_columns(df, REQUIRED_COLUMNS, "test frame")


def test_load_master_fails_fast_on_missing_structural_column(tmp_path):
    # A master input lacking a required structural column must fail with a clear error.
    (tmp_path / "MASTER_VARIABLES.csv").write_text(f"{TIME_COLUMN},{UNIT_ID_COLUMN}\n2022-07,R01-D01-S01\n")
    with pytest.raises(ValueError, match=PARENT_UNIT_COLUMN):
        load_master(data_dir=str(tmp_path))
