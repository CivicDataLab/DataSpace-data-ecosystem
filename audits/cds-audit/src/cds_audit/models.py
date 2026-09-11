"""Plain data structures shared across the auditor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

PASS = "pass"
WARN = "warn"
FAIL = "fail"
NA = "na"


@dataclass
class CheckResult:
    """Outcome of one guideline check for one dataset."""

    check_id: str            # e.g. "1.1_title"
    guideline: str           # e.g. "1.1 Dataset Title"
    score: Optional[float]   # 0..1, None when not applicable
    issues: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    weight: float = 0.0

    @property
    def status(self) -> str:
        if self.score is None:
            return NA
        if self.score >= 0.999:
            return PASS
        if self.score >= 0.5:
            return WARN
        return FAIL

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status
        return d


@dataclass
class ResourceInfo:
    """A single file attached to a dataset, normalised from the GraphQL payload."""

    id: str
    name: str = ""
    description: str = ""
    format: str = ""
    file_name: str = ""
    size: Optional[float] = None
    columns: List[Dict[str, Any]] = field(default_factory=list)   # [{name, type, description}]
    preview_columns: List[str] = field(default_factory=list)
    preview_rows: List[List[Any]] = field(default_factory=list)
    # Filled in by deep inspection (file download)
    raw_bytes_checked: bool = False
    encoding_ok: Optional[bool] = None
    has_bom: bool = False
    file_header: List[str] = field(default_factory=list)
    file_rows: List[List[Any]] = field(default_factory=list)
    geojson: Optional[Dict[str, Any]] = None
    shapefile_has_prj: Optional[bool] = None
    inspect_error: str = ""

    def column_names(self) -> List[str]:
        if self.file_header:
            return list(self.file_header)
        if self.columns:
            return [c.get("name", "") for c in self.columns]
        return list(self.preview_columns)

    def sample(self) -> "tuple[list[str], list[list[Any]]]":
        """Best available (header, rows): full file sample if downloaded, else API preview."""
        if self.file_rows and self.file_header:
            return self.file_header, self.file_rows
        if self.preview_rows and self.preview_columns:
            return self.preview_columns, self.preview_rows
        return self.column_names(), []


@dataclass
class DatasetInfo:
    """A dataset normalised from search + GraphQL responses."""

    id: str
    title: str = ""
    description: str = ""
    slug: str = ""
    created: str = ""
    modified: str = ""
    license: str = ""
    organization: str = ""
    user: str = ""
    is_individual: bool = False
    tags: List[str] = field(default_factory=list)
    sectors: List[str] = field(default_factory=list)
    geographies: List[Dict[str, Any]] = field(default_factory=list)   # [{name, type}]
    formats: List[str] = field(default_factory=list)
    metadata: List[Dict[str, Any]] = field(default_factory=list)      # [{label, data_type, value}]
    resources: List[ResourceInfo] = field(default_factory=list)
    dataset_type: str = "DATA"
    fetch_errors: List[str] = field(default_factory=list)

    @property
    def publisher(self) -> str:
        return self.organization or self.user

    def url(self, public_site: str) -> str:
        return f"{public_site.rstrip('/')}/datasets/{self.id}"


@dataclass
class DatasetAudit:
    dataset: DatasetInfo
    checks: List[CheckResult]
    score: float
    grade: str
    metadata_score: Optional[float]
    data_score: Optional[float]

    def top_fixes(self, n: int = 5) -> List[str]:
        """Highest-impact fixes: failing checks with the largest weighted shortfall first."""
        ranked = sorted(
            (c for c in self.checks if c.score is not None and c.score < 0.999),
            key=lambda c: -(c.weight * (1 - c.score)),
        )
        # Round-robin: the best fix from each check first (by impact), then second-best, …
        queues = [[f"[{c.guideline.split(' ')[0]}] {fx}" for fx in (c.fixes or c.issues[:1])] for c in ranked]
        out: List[str] = []
        depth = 0
        while len(out) < n and any(len(q) > depth for q in queues):
            for q in queues:
                if len(q) > depth:
                    out.append(q[depth])
                    if len(out) >= n:
                        break
            depth += 1
        return out
