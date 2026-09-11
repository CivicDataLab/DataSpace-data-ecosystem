# SPDX-License-Identifier: MIT
#
# Data Envelopment Analysis (DEA) routines using open-source LP solvers.
#
# Refactored for compatibility with the Digital Public Goods Alliance (DPGA)
# Standard. The original implementation depended on Gurobi (proprietary,
# commercial-licensed), which precludes the project from meeting DPG
# Indicator 4 (Platform Independence). This module replaces that dependency
# with PuLP and its bundled CBC solver, both OSI-approved open source.
#
# Original algorithmic structure adapted from:
#   https://github.com/wurmen/DEA

"""
Data Envelopment Analysis (DEA) using open-source LP solvers.

Public API
----------
CRS                Solve the input-oriented, constant-returns-to-scale DEA
                   model (multiplier/primal form).

``CRS`` returns a ``pandas.DataFrame`` with columns ``['DMU', 'efficiency']``.
Efficiency lies in ``(0, 1]``, where ``1.0`` denotes a fully efficient unit.

Only the input-oriented CRS multiplier model is implemented, as it is the
single model used by the risk-scoring pipeline (see ``scripts/vulnerability.py``).

Intended use and limitations
----------------------------
This module computes DEA efficiency scores from numeric input/output
tables. It is intended as a component of a larger risk-modelling
pipeline and **should not** be used as the sole basis for decisions
that affect individuals or households. DMU identifiers are expected to
be non-personal (e.g. administrative unit codes); do not feed personal
identifiers into this routine.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd
from pulp import (
    PULP_CBC_CMD,
    LpMaximize,
    LpProblem,
    LpStatus,
    LpStatusOptimal,
    LpVariable,
    lpSum,
    value,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# Type aliases for clarity
DMUData = dict[str, list[float]]


# ---------------------------------------------------------------------------
# Solver helpers
# ---------------------------------------------------------------------------

# A single CBC solver instance is reused across LPs. ``msg=False`` silences
# the underlying CBC chatter; use the module logger for any reporting.
_CBC = PULP_CBC_CMD(msg=False)


def _solve_or_raise(prob: LpProblem, dmu: str) -> float:
    """Solve ``prob`` and return its objective value, or raise."""
    status = prob.solve(_CBC)
    if status != LpStatusOptimal:
        raise RuntimeError(
            f"LP for DMU {dmu!r} terminated with status {LpStatus[status]!r}; cannot report efficiency."
        )
    obj = value(prob.objective)
    if obj is None:
        return 0.0
    return float(obj)


def _validate_shapes(dmus: Sequence[str], x: DMUData, y: DMUData) -> tuple[int, int]:
    """Check that all DMUs share a consistent input/output dimensionality."""
    if not dmus:
        raise ValueError("No DMUs supplied.")
    n_in = len(x[dmus[0]])
    n_out = len(y[dmus[0]])
    for k in dmus:
        if len(x[k]) != n_in:
            raise ValueError(f"DMU {k!r} has {len(x[k])} inputs, expected {n_in}.")
        if len(y[k]) != n_out:
            raise ValueError(f"DMU {k!r} has {len(y[k])} outputs, expected {n_out}.")
    return n_in, n_out


def _result_frame(rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["DMU", "efficiency"])


# ---------------------------------------------------------------------------
# CRS (Charnes-Cooper-Rhodes) model
# ---------------------------------------------------------------------------


def CRS(  # noqa: N802 - keep historical capitalisation for API compatibility
    DMU: Sequence[str], X: DMUData, Y: DMUData
) -> pd.DataFrame:
    """
    Input-oriented CRS DEA, multiplier (primal) form.

    Parameters
    ----------
    DMU : Sequence[str]
        Ordered DMU identifiers.
    X, Y : DMUData
        Input and output dictionaries keyed by DMU.

    Returns
    -------
    pandas.DataFrame
        Columns ``['DMU', 'efficiency']``; efficiency in ``(0, 1]``.

    """
    n_in, n_out = _validate_shapes(DMU, X, Y)
    rows: list[tuple[str, float]] = []
    for r in DMU:
        prob = LpProblem(f"CRS_in_primal_{r}", LpMaximize)
        v = [LpVariable(f"v_{i}", lowBound=0) for i in range(n_in)]
        u = [LpVariable(f"u_{j}", lowBound=0) for j in range(n_out)]
        prob += lpSum(u[j] * Y[r][j] for j in range(n_out))
        prob += lpSum(v[i] * X[r][i] for i in range(n_in)) == 1
        for k in DMU:
            prob += lpSum(u[j] * Y[k][j] for j in range(n_out)) - lpSum(v[i] * X[k][i] for i in range(n_in)) <= 0
        rows.append((r, _solve_or_raise(prob, r)))
    return _result_frame(rows)


__all__ = ["CRS"]
