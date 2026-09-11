import json

from cds_audit.checks import data as d
from cds_audit.fileinspect import inspect_bytes
from cds_audit.models import DatasetInfo, ResourceInfo


def one(res, **kw):
    return DatasetInfo(id="x", resources=[res], **kw)


def res(header, rows, fmt="CSV", file_name="theme_region_2020_v1.csv", types=None):
    types = types or {}
    return ResourceInfo(id="r1", name="r", format=fmt, file_name=file_name,
                        columns=[{"name": h, "type": types.get(h, "STRING"), "description": f"Description of column {h}"}
                                 for h in header],
                        preview_columns=header, preview_rows=rows)


def test_file_format(rules):
    assert d.check_file_format(DatasetInfo(id="x"), rules).status == "fail"
    assert d.check_file_format(one(res([], [], fmt="PDF")), rules).status == "fail"
    assert d.check_file_format(one(res([], [], fmt="XLSX")), rules).status == "fail"
    both = DatasetInfo(id="x", resources=[res([], [], fmt="XLSX"), res([], [], fmt="CSV")])
    assert d.check_file_format(both, rules).status == "pass"


def test_column_naming(rules):
    assert d.check_column_naming(one(res(["district_name", "temp_max_c"], [])), rules).status == "pass"
    r = d.check_column_naming(one(res(["District Name", "col1"], [])), rules)
    assert r.status == "fail" and any("spaces" in i for i in r.issues)
    r = d.check_column_naming(one(res(["district_name", "literacyRate"], [])), rules)
    assert any("Mixes snake_case and camelCase" in i for i in r.issues)


def test_data_types(rules):
    rows = [["12/03/2021", "1,204", "Yes"], ["13/03/2021", "980", "No"], ["14/03/2021", "1,110", "Yes"]]
    r = d.check_data_types(one(res(["survey_date", "households", "piped_water"], rows)), rules)
    text = " ".join(r.issues)
    assert "ISO 8601" in text and "commas" in text and "boolean" in text
    good = [["2021-03-12", 1204, 1], ["2021-03-13", 980, 0]]
    assert d.check_data_types(one(res(["survey_date", "households", "piped_water"], good)), rules).status == "pass"


def test_units(rules):
    rows = [[1.0, 2.0, 3.0]]
    r = d.check_units(one(res(["rainfall_mm", "temp_c", "pct_urban"], rows)), rules)
    assert r.status == "pass"
    r = d.check_units(one(res(["district_code", "stunted_children", "rainfall_inches"], [[1, 2.0, 3.0]])), rules)
    assert r.status == "fail" and any("Non-SI" in i for i in r.issues)


def test_missing_values(rules):
    rows = [[10.0, "NA"], [-999, "x1"], [12.0, "x2"], [-999, "-"]]
    r = d.check_missing_values(one(res(["value_mm", "label"], rows)), rules)
    text = " ".join(r.issues)
    assert "-999" in text and "Non-standard missing marker" in text
    assert d.check_missing_values(one(res(["value_mm"], [[1.0], [""], [2.0]])), rules).status == "pass"


def test_quality(rules):
    rows = [["a", 50.0], ["a", 50.0], ["b", 104.0]]
    r = d.check_data_quality(one(res(["district_name", "literacy_pct"], rows)), rules)
    text = " ".join(r.issues)
    assert "duplicate" in text and "0–100" in text


def test_sentinels_not_double_counted_as_range_errors(rules):
    rows = [["a", 50.0], ["b", -999], ["c", -999], ["d", 40.0]]
    r = d.check_data_quality(one(res(["district_name", "literacy_pct"], rows)), rules)
    assert r.status == "pass"


def test_file_naming(rules):
    assert d.check_file_naming(one(res([], [], file_name="resources/climate_bihar_precipitation_2000_2020_v1.0.csv")), rules).status == "pass"
    r = d.check_file_naming(one(res([], [], file_name="resources/Revenue Receipts Final.csv")), rules)
    assert r.status == "fail"
    # Django's 7-character collision suffix is ignored
    assert d.clean_file_name("resources/cases_2020_v2_aB3xYz1.csv") == "cases_2020_v2.csv"


def test_deep_inspection_encoding_and_crs(rules):
    r = ResourceInfo(id="r", format="CSV")
    inspect_bytes(r, "name,value\nBarpetá,1\n".encode("latin-1"), "x.csv", rules)
    assert r.encoding_ok is False
    assert d.check_encoding(one(r), rules).status == "fail"

    gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"id": 1},
          "geometry": {"type": "Polygon", "coordinates": [[[500000, 2800000], [501000, 2800000], [501000, 2801000]]]}}]}
    g = ResourceInfo(id="g", format="GEOJSON")
    inspect_bytes(g, json.dumps(gj).encode(), "wards.geojson", rules)
    fmt = d.check_file_format(one(g), rules)
    assert any("projected" in i for i in fmt.issues)
    assert any("not closed" in i for i in d.check_data_quality(one(g), rules).issues)


def test_not_assessable_checks_mention_deep_only_in_light_mode(rules):
    pdf = one(res([], [], fmt="PDF"))
    light = d.check_encoding(pdf, rules)
    assert light.score is None and "--deep" in light.evidence["not_assessed"]
    deep = d.check_encoding(pdf, {**rules, "runtime": {"deep": True}})
    assert "--deep" not in deep.evidence["not_assessed"]
