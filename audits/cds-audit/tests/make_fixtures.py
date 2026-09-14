"""Build a SYNTHETIC API snapshot for tests and the demo report.

None of this is real CivicDataSpace data. Each dataset is invented to exercise specific
guideline checks. Response shapes mirror the real backend:
  search   -> api/views/search_dataset.py  (DatasetDocumentSerializer)
  GraphQL  -> getDataset / datasetResources (api/schema, api/types)

Run:  python tests/make_fixtures.py   (writes tests/fixtures/snapshot/)
"""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

OUT = Path(__file__).parent / "fixtures" / "snapshot"


def md(label, dtype, value):
    return {"metadataItem": {"label": label, "dataType": dtype}, "value": value}


def csv_bytes(header, rows, encoding="utf-8", bom=False):
    lines = [",".join(header)] + [",".join(str(v) for v in r) for r in rows]
    blob = ("\n".join(lines) + "\n").encode(encoding)
    return (b"\xef\xbb\xbf" + blob) if bom else blob


def xlsx_bytes(header, rows):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------- datasets
DATASETS = []

# 1. A dataset that follows the guidelines closely
rain_rows = [[f"2020-01-{d:02d}", dist, round(1.5 * d + i, 1), round(14 + d * 0.3, 1)]
             for d in range(1, 21) for i, dist in enumerate(["Patna", "Gaya", "Purnia"])]
DATASETS.append(dict(
    id="11111111-1111-4111-8111-111111111111",
    title="Daily rainfall for Bihar districts (2000–2020)",
    description=("This dataset provides daily rainfall and minimum temperature for all districts of Bihar "
                 "from 2000 to 2020. It was compiled by the Example Climate Institute from gridded station "
                 "records. It is intended to support flood risk assessment and agricultural planning."),
    license="CC_BY_4_0_ATTRIBUTION", org="Example Climate Institute",
    tags=["Rainfall", "Temperature", "Flood risk"], sectors=["Climate Action"],
    geos=[{"name": "Bihar", "type": "STATE"}],
    metadata=[md("Date of Creation", "DATE", "2021-03-15"),
              md("Source Website", "URL", "https://climate-institute.example.org/rainfall")],
    resources=[dict(id="aaaaaaaa-0001-4000-8000-000000000001", name="Daily rainfall",
                    description="Rainfall in mm, temperature in °C.", format="CSV",
                    file="resources/climate_bihar_rainfall_2000_2020_v1.0.csv",
                    schema=[("date", "DATE"), ("district_name", "STRING"), ("rainfall_mm", "NUMBER"),
                            ("temp_min_c", "NUMBER")],
                    header=["date", "district_name", "rainfall_mm", "temp_min_c"], rows=rain_rows,
                    blob=csv_bytes(["date", "district_name", "rainfall_mm", "temp_min_c"], rain_rows))],
))

# 2. Government source left on the platform-default licence; "&" in title; generic description
DATASETS.append(dict(
    id="22222222-2222-4222-8222-222222222222",
    title="State Revenue & Receipts 2018-26",
    description=("Revenue receipts include tax and non-tax revenues. Capital receipts include borrowings "
                 "and loan recoveries. Together they form the total receipts of the government."),
    license="CC_BY_4_0_ATTRIBUTION", org="Example Budget Lab",
    tags=["Public Finance"], sectors=["Public Finance"], geos=[{"name": "Assam", "type": "STATE"}],
    metadata=[md("Date of Creation", "DATE", "15/04/2024"),
              md("Source Website", "URL", "https://finance.assam.gov.in/budget")],
    resources=[dict(id="aaaaaaaa-0002-4000-8000-000000000002", name="Receipts", description="", format="CSV",
                    file="resources/Revenue Receipts Final.csv",
                    schema=[("Year", "STRING"), ("Head of Account", "STRING"), ("Amount (Rs. Crore)", "STRING")],
                    header=["Year", "Head of Account", "Amount (Rs. Crore)"],
                    rows=[["2018-19", "Tax revenue", "1,23,456"], ["2019-20", "Tax revenue", "1,31,002"],
                          ["2020-21", "Non-tax revenue", "12,440"], ["2021-22", "Non-tax revenue", "NA"]])],
))

# 3. PDF only, no tags, geography or source
DATASETS.append(dict(
    id="33333333-3333-4333-8333-333333333333",
    title="Annual report on anganwadi centres",
    description="Annual report on anganwadi centres.",
    license="CC_BY_4_0_ATTRIBUTION", org="Example Child Rights Trust",
    tags=[], sectors=["Child Rights"], geos=[], metadata=[],
    resources=[dict(id="aaaaaaaa-0003-4000-8000-000000000003", name="Report", description="", format="PDF",
                    file="resources/report.pdf", schema=[], header=[], rows=[])],
))

# 4. Excel with no CSV twin; messy columns, dates, numbers and missing values
x_header = ["District Name", "Date of Survey", "Households Surveyed", "Toilet Coverage %", "Has Piped Water"]
x_rows = [["Kamrup", "12/03/2021", "1,204", 87.5, "Yes"], ["Nagaon", "13/03/2021", "980", 112.0, "No"],
          ["Cachar", "14/03/2021", -999, 64.2, "Yes"], ["Dhubri", "N/A", "1,110", -999, "No"]]
DATASETS.append(dict(
    id="44444444-4444-4444-8444-444444444444",
    title="Sanitation survey — Assam districts 2021",
    description=("Household sanitation survey across districts of Assam in 2021. Data collected by field "
                 "surveyors of the Example WASH Collective."),
    license="CC_BY_SA_4_0_ATTRIBUTION_SHARE_ALIKE", org="Example WASH Collective",
    tags=["Sanitation", "Water"], sectors=["Urban Development"], geos=[{"name": "Assam", "type": "STATE"}],
    metadata=[md("Date of Creation", "DATE", "2021-06-01"), md("Source Website", "URL", "wash-collective.example")],
    resources=[dict(id="aaaaaaaa-0004-4000-8000-000000000004", name="Survey", description="", format="XLSX",
                    file="resources/Sanitation Survey.xlsx",
                    schema=[(h, "STRING") for h in x_header], header=x_header, rows=x_rows,
                    blob=xlsx_bytes(x_header, x_rows))],
))

# 5. Individual publisher, one-line description, no creation date, no source link
DATASETS.append(dict(
    id="55555555-5555-4555-8555-555555555555",
    title="court cases pending",
    description="Pending cases by court.",
    license="OPEN_DATABASE_LICENSE", org=None, user="A. Researcher",
    tags=["Law and Justice", "Courts", "Court"], sectors=["Law and Justice"], geos=[{"name": "India", "type": "COUNTRY"}],
    metadata=[],
    resources=[dict(id="aaaaaaaa-0005-4000-8000-000000000005", name="Cases", description="", format="CSV",
                    file="resources/cases_v2_aB3xYz1.csv",
                    schema=[("courtName", "STRING"), ("pendingCases", "INTEGER"), ("col1", "STRING")],
                    header=["courtName", "pendingCases", "col1"],
                    rows=[["High Court A", 1200, "x"], ["High Court B", 900, "y"], ["High Court A", 1200, "x"]])],
))

# 6. GeoJSON in a projected CRS, ALL-CAPS title
gj = {"type": "FeatureCollection",
      "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32645"}},
      "features": [{"type": "Feature", "properties": {"ward_no": 1, "ward_name": "Ward 1"},
                    "geometry": {"type": "Polygon", "coordinates": [[[500000, 2800000], [501000, 2800000],
                                                                      [501000, 2801000], [500000, 2800000]]]}},
                   {"type": "Feature", "properties": {"ward_no": 2, "ward_name": "Ward 2"},
                    "geometry": {"type": "Polygon", "coordinates": [[[501000, 2800000], [502000, 2800000],
                                                                      [502000, 2801000]]]}}]}
DATASETS.append(dict(
    id="66666666-6666-4666-8666-666666666666",
    title="GUWAHATI WARD BOUNDARIES",
    description=("Ward boundaries for Guwahati city. Digitised by the Example Urban Observatory from municipal "
                 "maps in 2022. Useful for ward-level planning and service mapping."),
    license="OPEN_DATA_COMMONS_BY_ATTRIBUTION", org="Example Urban Observatory",
    tags=["Boundaries", "Wards"], sectors=["Urban Development"], geos=[{"name": "Assam", "type": "STATE"}],
    metadata=[md("Date of Creation", "DATE", "2022-08-30"),
              md("Source Website", "URL", "https://urban-observatory.example.org/wards")],
    resources=[dict(id="aaaaaaaa-0006-4000-8000-000000000006", name="Wards", description="", format="GEOJSON",
                    file="resources/guwahati_wards.geojson", schema=[], header=[], rows=[],
                    blob=json.dumps(gj).encode())],
))

# 7. Mixed conventions, duplicates, out-of-range percentages, Latin-1 file
m_header = ["district_name", "literacyRate", "female_literacy_pct", "Population 2011"]
m_rows = [["Barpetá", 63.8, 58.1, 1693622], ["Barpetá", 63.8, 58.1, 1693622], ["Dhemaji", 72.1, 104.3, 686133]]
DATASETS.append(dict(
    id="77777777-7777-4777-8777-777777777777",
    title="Literacy by district in Assam, Census 2011",
    description=("District-wise literacy rates for Assam from the Census of India 2011. Figures are decadal "
                 "census counts compiled by the Example Education Forum. The data helps track gender gaps "
                 "in literacy."),
    license="GOVERNMENT_OPEN_DATA_LICENSE", org="Example Education Forum",
    tags=["Literacy", "Census"], sectors=["Gender"], geos=[{"name": "Assam", "type": "STATE"}],
    metadata=[md("Date of Creation", "DATE", "2013-04-30"), md("Source Website", "URL", "https://censusindia.gov.in")],
    resources=[dict(id="aaaaaaaa-0007-4000-8000-000000000007", name="Literacy", description="", format="CSV",
                    file="resources/literacy_assam_2011_v1.csv",
                    schema=[("district_name", "STRING"), ("literacyRate", "NUMBER"),
                            ("female_literacy_pct", "NUMBER"), ("Population 2011", "INTEGER")],
                    header=m_header, rows=m_rows, blob=csv_bytes(m_header, m_rows, encoding="latin-1"))],
))

# 8. Long title with abbreviations; description runs long
DATASETS.append(dict(
    id="88888888-8888-4888-8888-888888888888",
    title="NFHS-5 district fact sheet indicators on maternal and child health for Uttar Pradesh",
    description=" ".join([
        "This dataset contains district fact sheet indicators from the National Family Health Survey round 5.",
        "It covers maternal health, child nutrition and immunisation.",
        "Indicators are reported for every district of Uttar Pradesh.",
        "The survey was conducted in 2019–21 by the Example Health Ministry.",
        "Values are percentages of the relevant population.",
        "The data can be used to prioritise district health interventions.",
        "Survey rounds are released roughly every five years."]),
    license="GOVERNMENT_OPEN_DATA_LICENSE", org="Example Health Data Lab",
    tags=["Maternal health", "Nutrition"], sectors=["Gender", "Child Rights"],
    geos=[{"name": "India", "type": "COUNTRY"}],
    metadata=[md("Date of Creation", "DATE", "2022-05-06"), md("Source Website", "URL", "https://rchiips.org/nfhs")],
    resources=[dict(id="aaaaaaaa-0008-4000-8000-000000000008", name="Indicators", description="", format="CSV",
                    file="resources/health_up_nfhs5_2019_2021_v1.0.csv",
                    schema=[("district_name", "STRING"), ("institutional_births_pct", "NUMBER"),
                            ("stunted_children", "NUMBER"), ("anaemic_women", "NUMBER")],
                    header=["district_name", "institutional_births_pct", "stunted_children", "anaemic_women"],
                    rows=[["Agra", 85.2, 38.1, 50.4], ["Lucknow", 90.1, 32.0, 47.9], ["Varanasi", 88.7, 36.4, None]])],
))


def build() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "files").mkdir(parents=True)
    results = []
    for d in DATASETS:
        org = {"name": d["org"], "logo": ""} if d.get("org") else None
        user = {"fullName": d["user"]} if d.get("user") else None
        results.append({
            "id": d["id"], "title": d["title"], "description": d["description"],
            "slug": d["title"].lower().replace(" ", "-"), "created": "2025-01-01T00:00:00Z",
            "modified": "2026-09-01T00:00:00Z", "status": "PUBLISHED", "dataset_type": "DATA",
            "metadata": [{"metadata_item": {"label": m["metadataItem"]["label"]}, "value": m["value"]}
                         for m in d["metadata"]],
            "tags": d["tags"], "sectors": d["sectors"], "formats": [r["format"] for r in d["resources"]],
            "catalogs": [], "geographies": [g["name"] for g in d["geos"]], "has_charts": False,
            "download_count": 0, "is_individual_dataset": bool(user),
            "organization": org, "user": {"name": d["user"], "bio": "", "profile_picture": ""} if user else None,
        })
        detail = {"data": {"getDataset": {
            "id": d["id"], "title": d["title"], "description": d["description"],
            "created": "2025-01-01T00:00:00Z", "modified": "2026-09-01T00:00:00Z",
            "license": d["license"], "isIndividualDataset": bool(user),
            "tags": [{"value": t} for t in d["tags"]], "user": user, "organization": org,
            "sectors": [{"name": s} for s in d["sectors"]], "geographies": d["geos"],
            "formats": [r["format"] for r in d["resources"]], "metadata": d["metadata"],
        }}}
        resources = []
        for r in d["resources"]:
            resources.append({
                "id": r["id"], "name": r["name"], "description": r["description"], "type": "FILE",
                "fileDetails": {"format": r["format"], "size": 1000.0, "file": {"name": r["file"]}},
                "schema": [{"fieldName": n, "format": t, "description": f"Description of column {n}"}
                           for n, t in r["schema"]],
                "previewData": {"columns": r["header"], "rows": [["" if v is None else v for v in row] for row in r["rows"]]},
            })
            meta = {"filename": r["file"].split("/")[-1], "note": ""}
            if r.get("blob") is None:
                meta["note"] = "no file in fixture"
            else:
                (OUT / "files" / f"{r['id']}.bin").write_bytes(r["blob"])
            (OUT / "files" / f"{r['id']}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (OUT / f"dataset_{d['id']}.json").write_text(
            json.dumps(detail, indent=1, ensure_ascii=False), encoding="utf-8")
        (OUT / f"resources_{d['id']}.json").write_text(
            json.dumps({"data": {"datasetResources": resources}}, indent=1, ensure_ascii=False), encoding="utf-8")
    search = {"results": results, "total": len(results), "aggregations": {}}
    (OUT / "search_page-1_size-36_sort-recent.json").write_text(
        json.dumps(search, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "README.md").write_text(
        "SYNTHETIC fixture data for tests. Not real CivicDataSpace datasets.\n", encoding="utf-8")
    print(f"Wrote {len(DATASETS)} synthetic datasets to {OUT}")


if __name__ == "__main__":
    build()
