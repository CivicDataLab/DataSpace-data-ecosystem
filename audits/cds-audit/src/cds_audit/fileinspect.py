"""Parse downloaded resource files into a header + row sample for the data checks."""

from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from typing import Any, Dict, List

from .models import ResourceInfo

log = logging.getLogger(__name__)


def inspect_bytes(res: ResourceInfo, blob: bytes, filename: str, rules: Dict[str, Any]) -> None:
    """Populate encoding and sample fields on `res` from raw file bytes (in place)."""
    sample_rows = int(rules["deep"]["sample_rows"])
    if filename and not res.file_name:
        res.file_name = filename
    fmt = (res.format or (filename.rsplit(".", 1)[-1] if "." in filename else "")).upper()
    res.raw_bytes_checked = True

    text_formats = {"CSV", "TSV", "JSON", "GEOJSON", "TXT", "XML"}
    if fmt in text_formats:
        res.has_bom = blob.startswith(b"\xef\xbb\xbf")
        try:
            text = blob.decode("utf-8-sig")
            res.encoding_ok = True
        except UnicodeDecodeError:
            res.encoding_ok = False
            text = blob.decode("latin-1")  # keep going so other checks still run
    else:
        res.encoding_ok = None  # binary formats: encoding is internal to the format

    try:
        if fmt in ("CSV", "TSV", "TXT"):
            _read_delimited(res, text, sample_rows, "\t" if fmt == "TSV" else None)
        elif fmt in ("JSON", "GEOJSON"):
            _read_json(res, text, sample_rows)
        elif fmt in ("XLSX", "XLS"):
            _read_excel(res, blob, sample_rows)
        elif fmt == "PARQUET":
            _read_parquet(res, blob, sample_rows)
        elif fmt in ("ZIP", "SHP"):
            _read_zip(res, blob)
    except Exception as e:  # never let one bad file stop the audit
        res.inspect_error = f"{type(e).__name__}: {e}"
        log.warning("Could not parse %s (%s): %s", res.id, fmt, e)


def _read_delimited(res: ResourceInfo, text: str, limit: int, delimiter: Any = None) -> None:
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows: List[List[str]] = []
    header: List[str] = []
    for i, row in enumerate(reader):
        if i == 0:
            header = row
            continue
        if i > limit:
            break
        rows.append(row)
    res.file_header, res.file_rows = header, rows


def _read_json(res: ResourceInfo, text: str, limit: int) -> None:
    obj = json.loads(text)
    if isinstance(obj, dict) and obj.get("type") in ("FeatureCollection", "Feature"):
        res.geojson = obj
        feats = obj.get("features") or [obj]
        records = [(f.get("properties") or {}) for f in feats[:limit] if isinstance(f, dict)]
    elif isinstance(obj, list):
        records = [r for r in obj[:limit] if isinstance(r, dict)]
    elif isinstance(obj, dict):
        # {"data": [...]} style wrappers
        lists = [v for v in obj.values() if isinstance(v, list) and v and isinstance(v[0], dict)]
        records = lists[0][:limit] if lists else []
    else:
        records = []
    header: List[str] = []
    for r in records:
        for k in r:
            if k not in header:
                header.append(k)
    res.file_header = header
    res.file_rows = [[r.get(h) for h in header] for r in records]


def _read_excel(res: ResourceInfo, blob: bytes, limit: int) -> None:
    try:
        import openpyxl  # type: ignore
    except ImportError:
        res.inspect_error = "openpyxl not installed; Excel contents not inspected"
        return
    wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i > limit:
            break
        rows.append(["" if v is None else v for v in row])
    if rows:
        res.file_header = [str(h) if h != "" else "" for h in rows[0]]
        res.file_rows = rows[1:]


def _read_parquet(res: ResourceInfo, blob: bytes, limit: int) -> None:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ImportError:
        res.inspect_error = "pyarrow not installed; Parquet contents not inspected"
        return
    table = pq.read_table(io.BytesIO(blob))
    res.file_header = list(table.column_names)
    res.file_rows = [list(r.values()) for r in table.slice(0, limit).to_pylist()]


def _read_zip(res: ResourceInfo, blob: bytes) -> None:
    """For zipped shapefiles, record whether a .prj (projection) file is present."""
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = [n.lower() for n in zf.namelist()]
    if any(n.endswith(".shp") for n in names):
        res.shapefile_has_prj = any(n.endswith(".prj") for n in names)
