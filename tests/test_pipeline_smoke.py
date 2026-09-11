"""End-to-end smoke test for the full risk-score pipeline.

Drives the installed CLI (`python -m disaster_risk_score_model`) inside a
temporary working directory: scaffolds a config, generates the synthetic
sample, runs the full pipeline, and asserts that the expected outputs are
produced with valid columns and value ranges.
"""

import os
import subprocess
import sys

import pandas as pd
import pytest


def _drsm(*args, cwd):
    env = {**os.environ, "MPLBACKEND": "Agg"}
    subprocess.run(
        [sys.executable, "-m", "disaster_risk_score_model", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    work = tmp_path_factory.mktemp("pipeline")
    _drsm("init-config", "config", cwd=work)
    _drsm("generate-sample-data", cwd=work)
    _drsm("run", cwd=work)
    return work / "data"


def _read(data_dir, name):
    return pd.read_csv(data_dir / name)


@pytest.mark.parametrize(
    ("filename", "column"),
    [
        ("factor_scores_l1_flood-hazard.csv", "flood-hazard"),
        ("factor_scores_l1_exposure.csv", "exposure"),
        ("factor_scores_l1_vulnerability.csv", "vulnerability"),
        ("factor_scores_l1_government-response.csv", "government-response"),
    ],
)
def test_factor_scores_in_range(data_dir, filename, column):
    df = _read(data_dir, filename)
    assert column in df.columns
    vals = df[column].dropna()
    assert len(vals) > 0
    assert vals.between(1, 5).all()


def test_vulnerability_efficiency_in_unit_interval(data_dir):
    df = _read(data_dir, "factor_scores_l1_vulnerability.csv")
    eff = df["efficiency"].dropna()
    assert eff.between(0, 1).all()


def test_block_risk_score(data_dir):
    rs = _read(data_dir, "risk_score.csv")
    # Columns are lower-cased / kebab-cased on write.
    assert "risk-score" in rs.columns
    assert "topsis-score" in rs.columns
    scores = rs["risk-score"].dropna()
    assert scores.between(1, 5).all()
    # The composite should exercise a real spread, not collapse to one class.
    assert scores.nunique() >= 3


def test_final_district_output(data_dir):
    final = _read(data_dir, "risk_score_district.csv")
    block = _read(data_dir, "risk_score.csv")
    # District-level rows are appended below the block-level rows.
    assert len(final) > len(block)
    # Every row carries a unit- or parent-level "unit-id" in one column;
    # no NaN split and no stray snake_case "unit_id" column.
    assert final["unit-id"].notna().all()
    assert "unit_id" not in final.columns
