"""Orchestrate: search -> details -> (optional) downloads -> checks -> scores."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from .client import DataSpaceClient, OfflineMiss, normalise
from .checks.metadata import _source_urls
from .fileinspect import inspect_bytes
from .models import DatasetAudit, DatasetInfo
from .scoring import audit_dataset

log = logging.getLogger(__name__)


def collect_dataset(client: DataSpaceClient, hit: Dict[str, Any], rules: Dict[str, Any],
                    deep: bool = False) -> DatasetInfo:
    ds_id = str(hit.get("id"))
    errors: List[str] = []
    detail, resources = None, []
    try:
        detail, errs = client.dataset_detail(ds_id)
        errors += errs
    except OfflineMiss:
        errors.append("dataset detail not in offline snapshot")
    except Exception as e:  # keep going with the search-hit data
        errors.append(f"dataset detail failed: {e}")
    try:
        resources, errs = client.dataset_resources(ds_id)
        errors += errs
    except OfflineMiss:
        errors.append("resources not in offline snapshot")
    except Exception as e:
        errors.append(f"resources failed: {e}")
    ds = normalise(hit, detail, resources, errors)

    if deep:
        max_bytes = int(rules["deep"]["max_file_mb"] * 1_000_000)
        for r in ds.resources:
            blob, filename, note = client.download_resource(r.id, max_bytes)
            if blob:
                inspect_bytes(r, blob, filename, rules)
            else:
                if filename and not r.file_name:
                    r.file_name = filename
                r.inspect_error = note
    return ds


def run_audit(client: DataSpaceClient, rules: Dict[str, Any], max_datasets: Optional[int] = None,
              deep: bool = False, check_links: bool = False, workers: int = 4,
              progress: Optional[Callable[[int, str], None]] = None,
              search_params: Optional[Dict[str, str]] = None) -> List[DatasetAudit]:
    rules = {**rules, "runtime": {"deep": deep}}
    hits = list(client.iter_search(max_datasets=max_datasets, extra_params=search_params))
    log.info("Found %d datasets", len(hits))

    def work(hit: Dict[str, Any]) -> DatasetAudit:
        ds = collect_dataset(client, hit, rules, deep=deep)
        link_status = None
        if check_links:
            link_status = {u: client.check_link(u) for u in _source_urls(ds)[:1]}
        audit = audit_dataset(ds, rules, link_status)
        if progress:
            progress(len(hits), ds.title)
        return audit

    if workers <= 1:
        audits = [work(h) for h in hits]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            audits = list(pool.map(work, hits))
    return sorted(audits, key=lambda a: a.score)
