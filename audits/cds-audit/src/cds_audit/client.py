"""Talk to the CivicDataSpace backend and normalise responses into DatasetInfo objects.

Endpoints (from CivicDataLab/DataSpaceBackend and DataSpaceFrontend):
  GET  {base}/api/search/dataset/?page=&size=&sort=recent     -> {"results": [...], "total": N}
  POST {base}/api/graphql  getDataset / datasetResources        -> full metadata, schema, preview
  GET  {base}/api/download/resource/{id}                        -> raw file (only with --deep)

Every raw response is written to a cache directory so an audit can be re-run offline
(`--offline`) and so the tests can run against recorded fixtures.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import requests

from .models import DatasetInfo, ResourceInfo

log = logging.getLogger(__name__)

DATASET_QUERY = """
query auditDataset($datasetId: UUID!) {
  getDataset(datasetId: $datasetId) {
    id title description created modified license isIndividualDataset
    tags { value }
    user { fullName }
    organization { name }
    sectors { name }
    geographies { name type }
    formats
    metadata { metadataItem { label dataType } value }
  }
}
"""

RESOURCES_QUERY = """
query auditResources($datasetId: UUID!) {
  datasetResources(datasetId: $datasetId) {
    id name description type
    fileDetails { format size %FILE% }
    schema { fieldName format description }
    previewData { columns rows }
  }
}
"""


class OfflineMiss(Exception):
    """Raised in offline mode when a response is not in the cache."""


class DataSpaceClient:
    def __init__(self, api_cfg: Dict[str, Any], cache_dir: Optional[str] = None, offline: bool = False):
        self.cfg = api_cfg
        self.base = api_cfg["base_url"].rstrip("/")
        self.cache = Path(cache_dir) if cache_dir else None
        self.offline = offline
        if self.cache:
            (self.cache / "files").mkdir(parents=True, exist_ok=True)
        if offline and not self.cache:
            raise ValueError("--offline needs --cache pointing at a previous snapshot")
        self.session = requests.Session()
        self.session.headers["User-Agent"] = api_cfg.get("user_agent", "cds-audit")
        self._file_query_supported = True

    # ------------------------------------------------------------ plumbing
    def _cache_path(self, key: str) -> Optional[Path]:
        if not self.cache:
            return None
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
        return self.cache / f"{safe}.json"

    def _cached(self, key: str) -> Optional[Any]:
        p = self._cache_path(key)
        if p and p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        if self.offline:
            raise OfflineMiss(key)
        return None

    def _store(self, key: str, payload: Any) -> None:
        p = self._cache_path(key)
        if p:
            p.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    def _request(self, method: str, url: str, **kw: Any) -> requests.Response:
        last: Optional[Exception] = None
        for attempt in range(self.cfg.get("max_retries", 3)):
            try:
                resp = self.session.request(method, url, timeout=self.cfg.get("timeout_seconds", 30), **kw)
                if resp.status_code in (429, 502, 503, 504):
                    raise requests.HTTPError(f"{resp.status_code} from {url}", response=resp)
                time.sleep(self.cfg.get("pause_between_requests", 0.25))
                return resp
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                last = e
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Request failed after retries: {url}: {last}")

    def graphql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        url = self.base + self.cfg["graphql_path"]
        resp = self._request("POST", url, json={"query": query, "variables": variables})
        try:
            return resp.json()
        except ValueError:
            raise RuntimeError(f"GraphQL returned non-JSON (HTTP {resp.status_code}) from {url}")

    # ------------------------------------------------------------- search
    def iter_search(self, max_datasets: Optional[int] = None, extra_params: Optional[Dict[str, str]] = None
                    ) -> Iterator[Dict[str, Any]]:
        size = int(self.cfg.get("page_size", 36))
        page, seen = 1, 0
        while True:
            params = {"page": page, "size": size, "sort": self.cfg.get("sort", "recent")}
            params.update(extra_params or {})
            key = "search_" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
            data = self._cached(key)
            if data is None:
                resp = self._request("GET", self.base + self.cfg["search_path"], params=params)
                if resp.status_code != 200:
                    raise RuntimeError(f"Search failed: HTTP {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                self._store(key, data)
            results = data.get("results", []) if isinstance(data, dict) else []
            total = data.get("total", 0) if isinstance(data, dict) else 0
            for r in results:
                yield r
                seen += 1
                if max_datasets and seen >= max_datasets:
                    return
            if not results or seen >= total:
                return
            page += 1

    # ------------------------------------------------------------ details
    def dataset_detail(self, dataset_id: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        key = f"dataset_{dataset_id}"
        data = self._cached(key)
        if data is None:
            data = self.graphql(DATASET_QUERY, {"datasetId": dataset_id})
            self._store(key, data)
        errs = [e.get("message", str(e)) for e in data.get("errors") or []]
        return (data.get("data") or {}).get("getDataset"), errs

    def dataset_resources(self, dataset_id: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        key = f"resources_{dataset_id}"
        data = self._cached(key)
        if data is None:
            q = RESOURCES_QUERY.replace("%FILE%", "file { name }" if self._file_query_supported else "")
            data = self.graphql(q, {"datasetId": dataset_id})
            if data.get("errors") and self._file_query_supported and any(
                    "file" in (e.get("message") or "").lower() for e in data["errors"]):
                log.info("Backend rejected fileDetails.file; retrying without file names")
                self._file_query_supported = False
                data = self.graphql(RESOURCES_QUERY.replace("%FILE%", ""), {"datasetId": dataset_id})
            self._store(key, data)
        errs = [e.get("message", str(e)) for e in data.get("errors") or []]
        return (data.get("data") or {}).get("datasetResources") or [], errs

    def download_resource(self, resource_id: str, max_bytes: int) -> Tuple[Optional[bytes], str, str]:
        """Return (bytes | None, filename, note). Note explains a skip."""
        meta_p = self.cache / "files" / f"{resource_id}.meta.json" if self.cache else None
        bin_p = self.cache / "files" / f"{resource_id}.bin" if self.cache else None
        if meta_p and meta_p.exists():
            meta = json.loads(meta_p.read_text())
            blob = bin_p.read_bytes() if bin_p and bin_p.exists() else None
            return blob, meta.get("filename", ""), meta.get("note", "")
        if self.offline:
            return None, "", "not in offline snapshot"
        url = self.base + self.cfg["download_path"].format(resource_id=resource_id)
        try:
            resp = self.session.get(url, stream=True, timeout=self.cfg.get("timeout_seconds", 30))
        except requests.RequestException as e:
            return None, "", f"download failed: {e}"
        filename = ""
        cd = resp.headers.get("Content-Disposition", "")
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
        if m:
            filename = requests.utils.unquote(m.group(1))
        note, blob = "", None
        if resp.status_code != 200:
            note = f"HTTP {resp.status_code}"
        elif int(resp.headers.get("Content-Length") or 0) > max_bytes:
            note = f"skipped: larger than {max_bytes // 1_000_000} MB"
        else:
            buf = bytearray()
            for chunk in resp.iter_content(65536):
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    note = f"truncated at {max_bytes // 1_000_000} MB"
                    break
            blob = bytes(buf)
        resp.close()
        if meta_p:
            meta_p.write_text(json.dumps({"filename": filename, "note": note}))
            if blob is not None and bin_p:
                bin_p.write_bytes(blob)
        time.sleep(self.cfg.get("pause_between_requests", 0.25))
        return blob, filename, note

    def check_link(self, url: str) -> int:
        """HTTP status of a URL (599 on connection failure). Cached."""
        key = "link_" + hashlib.sha1(url.encode()).hexdigest()[:16]
        cached = self._cached_quiet(key)
        if cached is not None:
            return int(cached)
        if self.offline:
            return 0
        try:
            r = self.session.head(url, allow_redirects=True, timeout=10)
            if r.status_code in (403, 405, 501):
                r = self.session.get(url, allow_redirects=True, timeout=10, stream=True)
                r.close()
            status = r.status_code
        except requests.RequestException:
            status = 599
        self._store(key, status)
        return status

    def _cached_quiet(self, key: str) -> Optional[Any]:
        p = self._cache_path(key)
        if p and p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None


# ------------------------------------------------------------- normalise
def _names(items: Any, key: str = "name") -> List[str]:
    out = []
    for it in items or []:
        if isinstance(it, str):
            out.append(it)
        elif isinstance(it, dict) and it.get(key):
            out.append(str(it[key]))
    return out


def normalise(search_hit: Dict[str, Any], detail: Optional[Dict[str, Any]],
              resources: List[Dict[str, Any]], errors: List[str]) -> DatasetInfo:
    """Merge the search hit (always present) with GraphQL detail (richer, may be missing)."""
    d = detail or {}
    hit = search_hit or {}
    org = d.get("organization") or hit.get("organization") or {}
    user = d.get("user") or hit.get("user") or {}

    if d.get("metadata") is not None:
        metadata = [{"label": (m.get("metadataItem") or {}).get("label", ""),
                     "data_type": (m.get("metadataItem") or {}).get("dataType", ""),
                     "value": m.get("value")} for m in d["metadata"]]
    else:
        metadata = [{"label": (m.get("metadata_item") or {}).get("label", ""), "data_type": "",
                     "value": m.get("value")} for m in hit.get("metadata") or []]

    if d.get("geographies") is not None:
        geos = [{"name": g.get("name"), "type": g.get("type")} for g in d["geographies"]]
    else:
        geos = [{"name": g, "type": ""} for g in _names(hit.get("geographies"))]

    ds = DatasetInfo(
        id=str(d.get("id") or hit.get("id")),
        title=d.get("title") or hit.get("title") or "",
        description=d.get("description") or hit.get("description") or "",
        slug=hit.get("slug", ""),
        created=d.get("created") or hit.get("created") or "",
        modified=d.get("modified") or hit.get("modified") or "",
        license=d.get("license") or "",
        organization=(org or {}).get("name") or "",
        user=(user or {}).get("fullName") or (user or {}).get("name") or "",
        is_individual=bool(d.get("isIndividualDataset", hit.get("is_individual_dataset", False))),
        tags=_names(d.get("tags"), "value") if d.get("tags") is not None else _names(hit.get("tags")),
        sectors=_names(d.get("sectors")) if d.get("sectors") is not None else _names(hit.get("sectors")),
        geographies=geos,
        formats=list(d.get("formats") or hit.get("formats") or []),
        metadata=metadata,
        dataset_type=hit.get("dataset_type", "DATA"),
        fetch_errors=list(errors),
    )
    if ds.is_individual and not ds.organization:
        ds.organization = ""
    for r in resources or []:
        fd = r.get("fileDetails") or {}
        prev = r.get("previewData") or {}
        ds.resources.append(ResourceInfo(
            id=str(r.get("id")),
            name=r.get("name") or "",
            description=r.get("description") or "",
            format=(fd.get("format") or "").upper(),
            file_name=((fd.get("file") or {}).get("name") if isinstance(fd.get("file"), dict) else fd.get("file")) or "",
            size=fd.get("size"),
            columns=[{"name": s.get("fieldName"), "type": s.get("format"), "description": s.get("description")}
                     for s in r.get("schema") or []],
            preview_columns=list(prev.get("columns") or []),
            preview_rows=[list(x) if isinstance(x, (list, tuple)) else list((x or {}).values())
                          for x in prev.get("rows") or []],
        ))
    return ds
