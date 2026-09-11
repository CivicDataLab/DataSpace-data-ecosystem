"""Tests for the open-source Data Envelopment Analysis (DEA) implementation.

These exercise the textbook 5-DMU / 2-input / 1-output example for the
input-oriented CRS multiplier model — the single model used by the pipeline.
"""

import pytest

from disaster_risk_score_model import dea

# CBC LP precision is ~1e-4 in the worst case; 1e-3 is a safe, generous
# threshold for these comparisons.
TOL = 1e-3

DMUS = ["A", "B", "C", "D", "E"]
X = {"A": [4.0, 3.0], "B": [7.0, 3.0], "C": [8.0, 1.0], "D": [4.0, 2.0], "E": [2.0, 4.0]}
Y = {"A": [1.0], "B": [1.0], "C": [1.0], "D": [1.0], "E": [1.0]}


def test_efficiencies_in_unit_interval():
    for v in dea.CRS(DMUS, X, Y)["efficiency"]:
        assert 0 <= v <= 1 + TOL


def test_at_least_one_efficient_dmu():
    # The CRS frontier is always non-empty: at least one DMU scores 1.0.
    effs = dea.CRS(DMUS, X, Y)["efficiency"]
    assert max(effs) == pytest.approx(1.0, abs=TOL)


def test_all_zero_output_dmu_is_inefficient():
    # A DMU with all-zero outputs is legitimately fully inefficient (efficiency 0)
    # and must not raise (regression test for empty-objective handling).
    dmus = ["A", "B"]
    x = {"A": [1.0], "B": [1.0]}
    y = {"A": [1.0], "B": [0.0]}
    res = dea.CRS(dmus, x, y)
    eff = dict(zip(res["DMU"], res["efficiency"], strict=True))
    assert eff["B"] == pytest.approx(0.0, abs=TOL)
