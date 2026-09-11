"""Section 2 of the guidelines: data standardisation checks.

These run on whatever evidence is available for each resource:
  * the schema the platform inferred (column names + types)          — always
  * the API preview rows (up to ~1,000 rows from the indexed table)   — always, if preview is enabled
  * the raw file (bytes, header, full sample)                         — only with --deep
Checks that have no evidence to work with return score=None ("na") so they do not
penalise the dataset; the report shows which checks were not assessable.
"""

from __future__ import annotations

import re
from collections import Counter
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..models import CheckResult, DatasetInfo, ResourceInfo
from ..textutils import has_year, tokenize_identifier, truncate

Rules = Dict[str, Any]

_NUM_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_FORMATTED_NUM_RE = re.compile(
    r"^(?:(?:rs\.?|inr|₹|\$|€|£)\s?[+-]?\d[\d,]*(\.\d+)?"      # currency prefix
    r"|[+-]?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?"                     # 1,234 / 1,23,456
    r"|[+-]?\d+(?:\.\d+)?\s?%)$",                               # 12.5%
    re.I,
)
_DECIMAL_COMMA_RE = re.compile(r"^[+-]?\d+,\d{1,2}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")
_NON_ISO_DATE_RE = re.compile(
    r"^(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"                        # 12/01/2020, 1-2-20
    r"|\d{4}/\d{1,2}/\d{1,2}"                                   # 2020/01/12
    r"|\d{1,2}[ -](jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[ -,]*\d{2,4}"
    r"|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[ -]\d{1,2},?[ -]\d{2,4}"
    r"|\d{8})$",
    re.I,
)
_DATE_NAME_RE = re.compile(r"(date|_dt$|^dt_|timestamp|datetime|_on$|created_at|updated_at)", re.I)
_MOJIBAKE_RE = re.compile(r"(Ã.|â€|Â.|\ufffd)")
_BOOL_SETS = {
    "true_false": {"true", "false"},
    "zero_one": {"0", "1"},
    "yes_no": {"yes", "no"},
    "y_n": {"y", "n"},
    "t_f": {"t", "f"},
}


# ------------------------------------------------------------------ helpers
def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v != v:  # NaN
        return ""
    return str(v).strip()


def _as_number(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if v != v else float(v)
    t = _s(v)
    if _NUM_RE.match(t):
        try:
            return float(t)
        except ValueError:
            return None
    return None


def _columns(header: List[str], rows: List[List[Any]]) -> Dict[str, List[Any]]:
    cols: Dict[str, List[Any]] = {h: [] for h in header}
    for r in rows:
        for i, h in enumerate(header):
            cols[h].append(r[i] if i < len(r) else None)
    return cols


def _schema_type(res: ResourceInfo, col: str) -> str:
    for c in res.columns:
        if c.get("name") == col:
            return (c.get("type") or "").upper()
    return ""


_AUTO_DESC_RE = re.compile(r"^description of column\b", re.I)


def _schema_desc(res: ResourceInfo, col: str) -> str:
    """Column description, ignoring the platform's auto-generated 'Description of column X'."""
    for c in res.columns:
        if c.get("name") == col:
            d = (c.get("description") or "").strip()
            return "" if _AUTO_DESC_RE.match(d) else d
    return ""


def _is_numeric_col(res: ResourceInfo, col: str, values: List[Any], accepted_missing: set) -> bool:
    """Numeric by schema, or >=90% of non-missing values parse as (possibly badly formatted) numbers."""
    st = _schema_type(res, col)
    if st in ("NUMBER", "INTEGER"):
        return True
    if st in ("STRING", "DATE", "BOOLEAN"):
        pass  # still infer: a STRING column full of "1,234" is a numeric column stored badly
    vals = [v for v in values if _s(v) not in accepted_missing]
    if not vals:
        return False
    parsed = sum(1 for v in vals if _as_number(v) is not None or _FORMATTED_NUM_RE.match(_s(v)))
    return parsed / len(vals) >= 0.9


def _na(check_id: str, guideline: str, why: str, rules: Optional[Rules] = None, deep_helps: bool = False) -> CheckResult:
    if deep_helps and rules is not None and not rules.get("runtime", {}).get("deep"):
        why += " Run with --deep to assess from the raw file."
    return CheckResult(check_id=check_id, guideline=guideline, score=None, evidence={"not_assessed": why})


def _aggregate(check_id: str, guideline: str, per_res: List[Tuple[ResourceInfo, float, List[str], List[str]]],
               why_na: str, rules: Optional[Rules] = None, deep_helps: bool = False, **evidence: Any) -> CheckResult:
    """Combine per-resource scores (mean) into one dataset-level result."""
    if not per_res:
        return _na(check_id, guideline, why_na, rules, deep_helps)
    res = CheckResult(check_id=check_id, guideline=guideline, score=round(mean(p[1] for p in per_res), 3))
    multi = len(per_res) > 1
    seen_fix = set()
    for r, sc, issues, fixes in per_res:
        prefix = f"[{truncate(r.name or r.file_name or r.id, 40)}] " if multi else ""
        res.issues.extend(prefix + i for i in issues)
        for f in fixes:
            if f not in seen_fix:
                seen_fix.add(f)
                res.fixes.append(f)
    res.evidence.update(evidence)
    res.evidence["resources_assessed"] = len(per_res)
    return res


def _fmt(res: ResourceInfo) -> str:
    f = (res.format or "").upper().lstrip(".")
    if not f and res.file_name and "." in res.file_name:
        f = res.file_name.rsplit(".", 1)[-1].upper()
    return {"SHAPEFILE": "SHP"}.get(f, f)


# ------------------------------------------------------------ 2.1 Format
def check_file_format(ds: DatasetInfo, rules: Rules) -> CheckResult:
    cfg = rules["formats"]
    gid, gname = "2.1_file_format", "2.1 File Format"
    if not ds.resources:
        return CheckResult(gid, gname, 0.0, ["Dataset has no data files."], ["Upload the data as CSV/JSON/GeoJSON/Parquet."])
    open_f = {f.upper() for f in cfg["open"]}
    prop = {f.upper() for f in cfg["proprietary_tabular"]}
    geo = {f.upper() for f in cfg["geospatial"]}
    nmr = {f.upper() for f in cfg["not_machine_readable"]}
    formats = [_fmt(r) for r in ds.resources]
    has_csv = "CSV" in formats
    per: List[Tuple[ResourceInfo, float, List[str], List[str]]] = []
    for r, f in zip(ds.resources, formats):
        issues, fixes, sc = [], [], 1.0
        if f in prop:
            if not has_csv:
                sc = 0.3
                issues.append(f"{f} file with no CSV version.")
                fixes.append("Add a CSV version alongside every Excel file.")
        elif f in nmr:
            sc = 0.2
            issues.append(f"{f} is not a machine-readable data format.")
            fixes.append("Publish the underlying data as CSV/JSON (keep the PDF only as supporting documentation).")
        elif f == "":
            sc = 0.5
            issues.append("File format is not recorded.")
            fixes.append("Set the file format on the resource.")
        elif f not in open_f and f not in geo:
            sc = 0.5
            issues.append(f"{f} is not one of the recommended open formats.")
            fixes.append("Convert to CSV, JSON, GeoJSON or Parquet.")
        if f == "KML":
            sc = min(sc, 0.6)
            issues.append("Geospatial data in KML; guideline asks for GeoJSON or Shapefile.")
            fixes.append("Provide geospatial layers as GeoJSON (EPSG:4326) or Shapefile.")
        if f in geo | {"GEOJSON"} or r.shapefile_has_prj is not None:
            crs_issue = _crs_issue(r, ds)
            if crs_issue:
                sc = min(sc, 0.6)
                issues.append(crs_issue)
                fixes.append("State the spatial reference system; use WGS84 (EPSG:4326).")
        per.append((r, sc, issues, fixes))
    return _aggregate(gid, gname, per, "", formats=formats)


def _crs_issue(r: ResourceInfo, ds: DatasetInfo) -> str:
    gj = r.geojson
    if gj:
        crs = (((gj.get("crs") or {}).get("properties") or {}).get("name") or "")
        if crs and not re.search(r"(4326|CRS84|WGS ?84)", crs, re.I):
            return f"GeoJSON declares CRS '{crs}', not WGS84 (EPSG:4326)."
        coords = list(_iter_coords(gj))[:5000]
        if coords and any(abs(x) > 180 or abs(y) > 90 for x, y in coords):
            return "Coordinates fall outside longitude/latitude range — data looks projected, not EPSG:4326."
        return ""
    if r.shapefile_has_prj is not None:
        return "" if r.shapefile_has_prj else "Shapefile has no .prj file — spatial reference system not stated."
    if _fmt(r) in ("SHP", "ZIP"):
        text = " ".join([ds.description or "", r.description or ""])
        if not re.search(r"(epsg|wgs ?84|crs|projection|spatial reference|utm)", text, re.I):
            return "Spatial reference system is not stated in the description."
    return ""


def _iter_coords(obj: Any) -> Iterable[Tuple[float, float]]:
    if isinstance(obj, dict):
        if "coordinates" in obj:
            yield from _iter_coords(obj["coordinates"])
        for key in ("features", "geometry", "geometries"):
            if key in obj:
                yield from _iter_coords(obj[key])
    elif isinstance(obj, list):
        if len(obj) >= 2 and all(isinstance(v, (int, float)) for v in obj[:2]):
            yield float(obj[0]), float(obj[1])
        else:
            for o in obj:
                yield from _iter_coords(o)


# ---------------------------------------------------------- 2.2 Encoding
def check_encoding(ds: DatasetInfo, rules: Rules) -> CheckResult:
    gid, gname = "2.2_encoding", "2.2 Encoding and Character Sets"
    per = []
    for r in ds.resources:
        header, rows = r.sample()
        strings = [h for h in header] + [_s(v) for row in rows[:2000] for v in row if isinstance(v, str)]
        mojibake = [s for s in strings if _MOJIBAKE_RE.search(s)]
        dec_comma = [s for s in strings if _DECIMAL_COMMA_RE.match(s)]
        issues, fixes = [], []
        if r.raw_bytes_checked:
            sc = 1.0
            if r.encoding_ok is False:
                sc = 0.0
                issues.append("File is not valid UTF-8.")
                fixes.append("Re-save the file as UTF-8.")
            elif r.has_bom:
                sc = 0.9
                issues.append("File starts with a UTF-8 byte-order mark (BOM).")
                fixes.append("Save as UTF-8 without BOM so the first column name is clean.")
        elif mojibake:
            sc = 0.2
        else:
            sc = None  # no byte-level evidence
        if mojibake:
            sc = min(sc if sc is not None else 1.0, 0.2)
            issues.append(f"Garbled characters suggest a non-UTF-8 source, e.g. '{truncate(mojibake[0], 30)}'.")
            fixes.append("Re-export the source file as UTF-8.")
        if dec_comma and len(dec_comma) >= 3:
            sc = min(sc if sc is not None else 1.0, 0.6)
            issues.append(f"Decimal commas found (e.g. '{dec_comma[0]}') — locale-specific number format.")
            fixes.append("Use '.' as the decimal separator throughout.")
        if sc is not None:
            per.append((r, sc, issues, fixes))
    return _aggregate(gid, gname, per, "No text-based data file to check byte-level encoding.", rules, True)


# ---------------------------------------------------- 2.3 Column naming
_SNAKE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
_CAMEL = re.compile(r"^[a-z][a-z0-9]*([A-Z][a-z0-9]*)+$")


def column_convention(name: str) -> str:
    if _SNAKE.match(name):
        return "snake_or_single" if "_" not in name else "snake"
    if _CAMEL.match(name):
        return "camel"
    return "other"


def check_column_naming(ds: DatasetInfo, rules: Rules) -> CheckResult:
    cfg = rules["columns"]
    gid, gname = "2.3_column_naming", "2.3 Column Naming"
    amb_patterns = [re.compile(p, re.I) for p in cfg["ambiguous_patterns"]]
    amb_allow = {a.lower() for a in cfg.get("ambiguous_allowlist", [])}
    per = []
    for r in ds.resources:
        names = [n for n in r.column_names() if n is not None]
        if not names:
            continue
        conv = Counter(column_convention(n) for n in names)
        issues, fixes = [], []
        bad_chars = [n for n in names if re.search(r"[^A-Za-z0-9_]", n)]
        ambiguous = [n for n in names if n.lower() not in amb_allow and any(p.match(n.strip()) for p in amb_patterns)]
        too_long = [n for n in names if len(n) > cfg["max_length"]]
        dupes = [n for n, c in Counter(n.lower() for n in names).items() if c > 1]
        has_snake, has_camel = conv["snake"] > 0, conv["camel"] > 0
        consistent = not (has_snake and has_camel) and conv["other"] == 0

        good = [n for n in names if n not in bad_chars and n not in ambiguous and n not in too_long]
        sc = 0.6 * (len(good) / len(names)) + 0.4 * (1.0 if consistent else 0.0)
        if dupes:
            sc = min(sc, 0.4)
            issues.append(f"Duplicate column names: {', '.join(dupes[:4])}")
            fixes.append("Make every column name unique.")
        if bad_chars:
            issues.append(f"{len(bad_chars)}/{len(names)} columns contain spaces or special characters, e.g. '{truncate(bad_chars[0], 40)}'.")
            fixes.append("Rename columns to snake_case (lowercase, words joined with underscores).")
        if has_snake and has_camel:
            issues.append(f"Mixes snake_case and camelCase, e.g. '{next(n for n in names if column_convention(n) == 'camel')}'.")
            fixes.append("Use one convention (snake_case recommended) for every column.")
        elif not consistent and not bad_chars:
            issues.append(f"Mixed naming conventions: {dict(conv)}")
            fixes.append("Use one convention (snake_case recommended) for every column.")
        if ambiguous:
            issues.append(f"Ambiguous column names: {', '.join(ambiguous[:5])}")
            fixes.append("Give every column a descriptive name (e.g. district_name, temp_max_c).")
        if too_long:
            issues.append(f"{len(too_long)} column names exceed {cfg['max_length']} characters.")
            fixes.append("Shorten long column names; move detail to the column description.")
        per.append((r, round(sc, 3), issues, fixes))
    return _aggregate(gid, gname, per, "No column information available (non-tabular files or schema missing).", rules, True)


# ------------------------------------------------------- 2.4 Data types
def check_data_types(ds: DatasetInfo, rules: Rules) -> CheckResult:
    gid, gname = "2.4_data_types", "2.4 Data Types"
    accepted = set(rules["missing_values"]["accepted"])
    per = []
    for r in ds.resources:
        header, rows = r.sample()
        if not rows:
            continue
        cols = _columns(header, rows)
        issues, fixes = [], []
        assessed, bad = 0, 0
        for col, values in cols.items():
            vals = [_s(v) for v in values if _s(v) not in accepted]
            if not vals:
                continue
            assessed += 1
            col_bad = False
            # Dates
            is_date_col = _schema_type(r, col) == "DATE" or bool(_DATE_NAME_RE.search(col or ""))
            non_iso = [v for v in vals if _NON_ISO_DATE_RE.match(v)]
            if is_date_col or len(non_iso) / len(vals) > 0.5:
                bad_dates = [v for v in vals if not _ISO_DATE_RE.match(v)]
                if bad_dates and (is_date_col or non_iso):
                    if len(bad_dates) / len(vals) > 0.05:
                        col_bad = True
                        issues.append(f"'{col}': dates not in ISO 8601, e.g. '{bad_dates[0]}'.")
                        fixes.append("Format dates as YYYY-MM-DD (timestamps as YYYY-MM-DD hh:mm:ss UTC).")
            # Formatted numbers stored as text
            fmt_nums = [v for v in vals if _FORMATTED_NUM_RE.match(v)]
            if fmt_nums and len(fmt_nums) / len(vals) > 0.05:
                col_bad = True
                issues.append(f"'{col}': numbers carry commas/currency/% symbols, e.g. '{fmt_nums[0]}'.")
                fixes.append("Store numbers as raw values — no thousands separators, currency or % signs.")
            # Booleans
            low = {v.lower() for v in vals}
            if 1 < len(low) <= 4:
                styles = [k for k, sset in _BOOL_SETS.items() if low & sset]
                if low <= set().union(*_BOOL_SETS.values()) and styles and not (low <= {"0", "1"}):
                    if len(styles) > 1 or styles[0] in ("yes_no", "y_n", "t_f"):
                        col_bad = True
                        issues.append(f"'{col}': boolean values as {sorted(low)}.")
                        fixes.append("Represent booleans as 0/1 or True/False, consistently.")
            # Decimal precision drift in numeric columns
            nums = [v for v in vals if _NUM_RE.match(v) and "." in v]
            if len(nums) >= 20:
                places = Counter(len(v.split(".")[1]) for v in nums if "e" not in v.lower())
                if len(places) > 3 and max(places) > 4:
                    issues.append(f"'{col}': inconsistent decimal places ({min(places)}–{max(places)}).")
                    fixes.append("Round numeric columns to a standard number of decimal places.")
                    bad += 0.5
            bad += 1 if col_bad else 0
        if not assessed:
            continue
        per.append((r, round(max(0.0, 1 - bad / assessed), 3), issues[:6], fixes))
    return _aggregate(gid, gname, per, "No row sample available for this dataset.", rules, True)


# ------------------------------------------------------------- 2.5 Units
def check_units(ds: DatasetInfo, rules: Rules) -> CheckResult:
    cfg = rules["units"]
    gid, gname = "2.5_units", "2.5 Units of Measurement"
    unit_tokens = {t.lower() for t in cfg["unit_tokens"]}
    non_si = {t.lower() for t in cfg["non_si_tokens"]}
    placeholder_any = False
    id_res = [re.compile(p, re.I) for p in cfg["identifier_patterns"]]
    accepted = set(rules["missing_values"]["accepted"]) | set(rules["missing_values"]["placeholder_strings"])
    per = []
    for r in ds.resources:
        header, rows = r.sample()
        names = header or r.column_names()
        if not names:
            continue
        cols = _columns(names, rows) if rows else {n: [] for n in names}
        measures = []
        for n in names:
            snake = "_".join(tokenize_identifier(n))
            if any(p.search(snake) for p in id_res):
                continue
            if rows:
                if _is_numeric_col(r, n, cols.get(n, []), accepted):
                    measures.append(n)
            elif _schema_type(r, n) in ("NUMBER", "INTEGER"):
                measures.append(n)
        if not measures:
            continue
        documented, non_si_cols = [], []
        res_text = (r.description or "").lower()
        units_in_res_desc = bool(re.search(r"\b(unit|units|measured in|in (mm|km|°c|celsius|inr|rs|lakh|crore|hectare|percent))\b", res_text))
        for n in measures:
            toks = set(tokenize_identifier(n))
            desc = _schema_desc(r, n).lower()
            if toks & non_si or any(t in desc for t in non_si):
                non_si_cols.append(n)
            if toks & unit_tokens or "%" in n or re.search(r"\b(unit|in [a-z°%]+|%|₹|mm|km|kg|°c)\b", desc):
                documented.append(n)
        described = [n for n in measures if _schema_desc(r, n)]
        frac = len(documented) / len(measures)
        if units_in_res_desc:
            frac = max(frac, 0.8)
        issues, fixes = [], []
        if frac < 0.999:
            undocumented = [m for m in measures if m not in documented]
            issues.append(f"{len(undocumented)}/{len(measures)} measurement columns have no documented unit, e.g. {', '.join(undocumented[:4])}.")
            fixes.append("Document the unit of every measurement column (name suffix like _mm / _inr_crore, or column description).")
        if non_si_cols:
            frac = min(frac, 0.3)
            issues.append(f"Non-SI units in: {', '.join(non_si_cols[:4])}.")
            fixes.append("Convert to SI units (°C, mm, m/s, hPa, hectares).")
        placeholder_desc = bool(r.columns) and not described
        if placeholder_desc and frac < 0.999:
            issues.append("Column descriptions are still the platform's auto-generated placeholders.")
            fixes.append("Fill in column descriptions on the resource schema, including units.")
        per.append((r, round(frac, 3), issues, fixes))
        placeholder_any = placeholder_any or placeholder_desc
    return _aggregate(gid, gname, per, "No numeric measurement columns identified.",
                      placeholder_column_descriptions=placeholder_any)


# ----------------------------------------------------- 2.6 Missing values
def check_missing_values(ds: DatasetInfo, rules: Rules) -> CheckResult:
    cfg = rules["missing_values"]
    gid, gname = "2.6_missing_values", "2.6 Missing Values"
    accepted = set(cfg["accepted"])
    sentinels = {float(x) for x in cfg["sentinel_numbers"]}
    placeholders = set(cfg["placeholder_strings"])
    per = []
    for r in ds.resources:
        header, rows = r.sample()
        if not rows:
            continue
        cols = _columns(header, rows)
        issues, fixes = [], []
        sentinel_cols, placeholder_cols, mixed_cols = [], [], []
        for col, values in cols.items():
            svals = [_s(v) for v in values]
            nums = [_as_number(v) for v in values]
            numeric_share = sum(1 for n in nums if n is not None) / max(len(values), 1)
            if numeric_share > 0.5:
                hits = [n for n in nums if n is not None and n in sentinels]
                # a sentinel is suspicious when it repeats and sits far from the column's other values
                if hits and (len(hits) >= 2 or len(values) < 20):
                    others = [n for n in nums if n is not None and n not in sentinels]
                    if not others or all(abs(h) > 10 * (max(abs(o) for o in others) or 1) or h < 0 <= min(others) for h in hits):
                        sentinel_cols.append((col, hits[0]))
            ph = [v for v in svals if v in placeholders]
            if ph:
                placeholder_cols.append((col, ph[0]))
            kinds = {("blank" if v == "" else v.lower()) for v in svals if v in accepted or v in placeholders}
            if len(kinds) > 1:
                mixed_cols.append(col)
        sc = 1.0
        if sentinel_cols:
            sc -= 0.5
            c, v = sentinel_cols[0]
            issues.append(f"Placeholder number {v:g} used for missing data in '{c}'" + (f" (+{len(sentinel_cols)-1} more columns)" if len(sentinel_cols) > 1 else "") + ".")
            fixes.append("Replace -999-style placeholders with blank/NULL (or document them explicitly).")
        if placeholder_cols:
            sc -= 0.3
            c, v = placeholder_cols[0]
            issues.append(f"Non-standard missing marker '{v}' in '{c}'" + (f" (+{len(placeholder_cols)-1} more columns)" if len(placeholder_cols) > 1 else "") + ".")
            fixes.append("Use blank cells, NULL or NaN for missing values — not 'NA', '-', 'nil'.")
        if mixed_cols:
            sc -= 0.2
            issues.append(f"Mixed missing-value markers within columns: {', '.join(mixed_cols[:4])}.")
            fixes.append("Use a single missing-value representation across the dataset.")
        per.append((r, round(max(sc, 0.0), 3), issues, fixes))
    return _aggregate(gid, gname, per, "No row sample available for this dataset.", rules, True)


# ------------------------------------------------------ 2.7 Data quality
def check_data_quality(ds: DatasetInfo, rules: Rules) -> CheckResult:
    cfg = rules["quality"]
    gid, gname = "2.7_data_quality", "2.7 Data Quality Checks"
    pct_re = re.compile(cfg["percent_name_pattern"], re.I)
    temp_re = re.compile(cfg["temperature_name_pattern"], re.I)
    cnt_re = re.compile(cfg["count_name_pattern"], re.I)
    lat_re = re.compile(cfg["latitude_name_pattern"], re.I)
    lon_re = re.compile(cfg["longitude_name_pattern"], re.I)
    tlo, thi = cfg["temperature_range_c"]
    sentinels = {float(x) for x in rules["missing_values"]["sentinel_numbers"]}
    per = []
    for r in ds.resources:
        header, rows = r.sample()
        issues, fixes = [], []
        sc = 1.0
        assessed = False
        if rows:
            assessed = True
            keys = [tuple(_s(v) for v in row) for row in rows]
            dup = len(keys) - len(set(keys))
            if dup:
                share = dup / len(keys)
                sc -= min(0.4, 0.1 + share)
                issues.append(f"{dup} duplicate rows in {len(keys)} sampled ({share:.1%}).")
                fixes.append("Remove duplicate records.")
            cols = _columns(header, rows)
            range_bad = []
            for col, values in cols.items():
                nums = [n for n in (_as_number(v) for v in values) if n is not None and n not in sentinels]
                if not nums:
                    continue
                snake = "_".join(tokenize_identifier(col)) + ("_%" if "%" in (col or "") else "")
                if pct_re.search(snake) and any(n < 0 or n > 100 for n in nums):
                    range_bad.append(f"'{col}' has percentages outside 0–100 (e.g. {next(n for n in nums if n < 0 or n > 100):g})")
                if temp_re.search(snake) and any(n < tlo or n > thi for n in nums):
                    range_bad.append(f"'{col}' has implausible temperatures (e.g. {next(n for n in nums if n < tlo or n > thi):g})")
                if cnt_re.search(snake) and any(n < 0 for n in nums):
                    range_bad.append(f"'{col}' has negative counts")
                if lat_re.match(snake) and any(abs(n) > 90 for n in nums):
                    range_bad.append(f"'{col}' has latitudes outside ±90")
                if lon_re.match(snake) and any(abs(n) > 180 for n in nums):
                    range_bad.append(f"'{col}' has longitudes outside ±180")
            if range_bad:
                sc -= min(0.5, 0.2 * len(range_bad))
                issues.extend(range_bad[:4])
                fixes.append("Validate numeric ranges (percentages 0–100, plausible temperatures, non-negative counts).")
        if r.geojson is not None:
            assessed = True
            geo_issues = validate_geojson(r.geojson)
            if geo_issues:
                sc -= 0.6
                issues.extend(geo_issues[:3])
                fixes.append("Fix invalid geometries (closed rings, valid coordinates, no self-intersections).")
        if assessed:
            per.append((r, round(max(sc, 0.0), 3), issues, fixes))
    return _aggregate(gid, gname, per, "No row sample or geometry available for this dataset.", rules, True)


def validate_geojson(gj: Dict[str, Any]) -> List[str]:
    """Structural checks, plus shapely's is_valid when shapely is installed."""
    issues: List[str] = []
    feats = gj.get("features") if gj.get("type") == "FeatureCollection" else [gj]
    if not isinstance(feats, list):
        return ["GeoJSON has no 'features' array."]
    try:
        from shapely.geometry import shape  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        shape = None
    null_geom, open_rings, invalid = 0, 0, 0
    for f in feats:
        geom = f.get("geometry") if isinstance(f, dict) and f.get("type") == "Feature" else f
        if not geom:
            null_geom += 1
            continue
        if geom.get("type") in ("Polygon", "MultiPolygon"):
            polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom.get("coordinates", [])
            for poly in polys:
                for ring in poly or []:
                    if len(ring) < 4 or ring[0] != ring[-1]:
                        open_rings += 1
        if shape is not None:
            try:
                if not shape(geom).is_valid:
                    invalid += 1
            except Exception:
                invalid += 1
    if null_geom:
        issues.append(f"{null_geom} features have no geometry.")
    if open_rings:
        issues.append(f"{open_rings} polygon rings are not closed.")
    if invalid:
        issues.append(f"{invalid} geometries are invalid (self-intersections or bad topology).")
    return issues


# ------------------------------------------------------- 2.8 File naming
_DJANGO_SUFFIX = re.compile(r"_[A-Za-z0-9]{7}(?=\.[A-Za-z0-9]+$)")


def clean_file_name(name: str) -> str:
    """Strip the storage path and Django's 7-char collision suffix."""
    base = (name or "").replace("\\", "/").split("/")[-1]
    return _DJANGO_SUFFIX.sub("", base)


def check_file_naming(ds: DatasetInfo, rules: Rules) -> CheckResult:
    gid, gname = "2.8_file_naming", "2.8 File Naming"
    pattern = re.compile(rules["file_naming"]["pattern"])
    per = []
    for r in ds.resources:
        name = clean_file_name(r.file_name)
        if not name:
            continue
        stem, _, ext = name.rpartition(".")
        issues, fixes = [], []
        subs = {
            "lowercase_snake": bool(re.match(r"^[a-z0-9]+(_[a-z0-9.]+)*$", stem)),
            "time_period": has_year(stem),
            "version": bool(re.search(r"_v\d+(\.\d+)*$", stem)),
            "extension_matches_format": bool(ext) and (not r.format or ext.lower() == r.format.lower()
                                                       or {ext.lower(), r.format.lower()} <= {"xls", "xlsx"}
                                                       or {ext.lower(), r.format.lower()} <= {"shp", "zip", "shapefile"}),
        }
        if pattern.match(name) and all(subs.values()):
            per.append((r, 1.0, [], []))
            continue
        missing = [k for k, v in subs.items() if not v]
        human = {"lowercase_snake": "not lowercase snake_case", "time_period": "no time period",
                 "version": "no _v{version} suffix", "extension_matches_format": "extension does not match format"}
        issues.append(f"'{truncate(name, 60)}' — " + ", ".join(human[m] for m in missing) + ".")
        fixes.append("Rename files as {theme}_{region}_{time_period}_v{version}.{format}, e.g. climate_bihar_precipitation_2000_2020_v1.0.csv.")
        per.append((r, round(sum(subs.values()) / len(subs), 3), issues, fixes))
    return _aggregate(gid, gname, per, "File names not exposed by the API.")


ALL_DATA_CHECKS = [
    check_file_format,
    check_encoding,
    check_column_naming,
    check_data_types,
    check_units,
    check_missing_values,
    check_data_quality,
    check_file_naming,
]
