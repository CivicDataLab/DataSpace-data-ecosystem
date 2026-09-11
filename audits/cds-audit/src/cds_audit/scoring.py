"""Run all checks on a dataset and turn them into a weighted score and grade."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .checks import ALL_DATA_CHECKS, ALL_METADATA_CHECKS
from .checks.metadata import check_source_website
from .models import CheckResult, DatasetAudit, DatasetInfo

Rules = Dict[str, Any]


def _weighted(checks: List[CheckResult]) -> Optional[float]:
    applicable = [c for c in checks if c.score is not None and c.weight > 0]
    total = sum(c.weight for c in applicable)
    if not total:
        return None
    return round(100 * sum(c.weight * c.score for c in applicable) / total, 1)


def grade_for(score: float, rules: Rules, has_fail: bool = False) -> str:
    bands = rules["grades"]
    label = next((b["label"] for b in bands if score >= b["min"]), bands[-1]["label"])
    cap = rules.get("grade_cap_on_fail")
    if has_fail and cap:
        order = [b["label"] for b in bands]
        if cap in order and order.index(label) < order.index(cap):
            label = cap
    return label


def audit_dataset(ds: DatasetInfo, rules: Rules, link_status: Optional[Dict[str, int]] = None) -> DatasetAudit:
    weights = rules["weights"]
    checks: List[CheckResult] = []
    for fn in ALL_METADATA_CHECKS:
        if fn is check_source_website:
            res = fn(ds, rules, link_status)
        else:
            res = fn(ds, rules)
        checks.append(res)
    for fn in ALL_DATA_CHECKS:
        checks.append(fn(ds, rules))
    for c in checks:
        c.weight = float(weights.get(c.check_id, 0))

    meta = [c for c in checks if c.check_id.startswith("1.")]
    data = [c for c in checks if c.check_id.startswith("2.")]
    score = _weighted(checks) or 0.0
    return DatasetAudit(
        dataset=ds,
        checks=checks,
        score=score,
        grade=grade_for(score, rules, any(c.status == "fail" for c in checks)),
        metadata_score=_weighted(meta),
        data_score=_weighted(data),
    )
