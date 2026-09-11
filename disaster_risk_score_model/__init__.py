"""
Intelligent Data Solution for Disaster Risk Reduction (IDS-DRR).

A configurable, geography-neutral pipeline that computes flood risk scores from
publicly available data. See the ``drsm`` command-line interface (or
``python -m disaster_risk_score_model``) for usage.
"""

from disaster_risk_score_model.config import load_config

__version__ = "0.1.0"

__all__ = ["__version__", "load_config"]
