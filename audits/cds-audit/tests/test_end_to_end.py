import json

from cds_audit.cli import main


def _run(tmp_path, snapshot, *extra):
    out = tmp_path / "out"
    code = main(["run", "--offline", "--cache", str(snapshot), "--out", str(out), "--workers", "1", *extra])
    assert code == 0
    return out, json.loads((out / "audit.json").read_text())


def test_light_run_writes_all_reports(tmp_path, snapshot):
    out, data = _run(tmp_path, snapshot)
    for f in ("report.html", "summary.md", "scores.csv", "issues.csv", "audit.json"):
        assert (out / f).stat().st_size > 0
    assert len(data["datasets"]) == 8
    by_title = {d["title"]: d for d in data["datasets"]}
    assert by_title["Daily rainfall for Bihar districts (2000–2020)"]["grade"] == "Good"
    assert by_title["Annual report on anganwadi centres"]["grade"] == "Poor"
    # sorted weakest first
    scores = [d["score"] for d in data["datasets"]]
    assert scores == sorted(scores)
    html = (out / "report.html").read_text()
    assert "Annual report on anganwadi centres" in html and "<\\/" not in html.split("const D =")[0]


def test_failing_check_caps_grade(tmp_path, snapshot):
    _, data = _run(tmp_path, snapshot)
    for d in data["datasets"]:
        if any(c["status"] == "fail" for c in d["checks"]):
            assert d["grade"] != "Good", d["title"]


def test_deep_run_adds_byte_level_findings(tmp_path, snapshot):
    _, data = _run(tmp_path, snapshot, "--deep")
    by_title = {d["title"]: d for d in data["datasets"]}
    lit = {c["check_id"]: c for c in by_title["Literacy by district in Assam, Census 2011"]["checks"]}
    assert lit["2.2_encoding"]["status"] == "fail"
    geo = {c["check_id"]: c for c in by_title["GUWAHATI WARD BOUNDARIES"]["checks"]}
    assert any("WGS84" in i for i in geo["2.1_file_format"]["issues"])


def test_fail_under_exit_code(tmp_path, snapshot):
    code = main(["run", "--offline", "--cache", str(snapshot), "--out", str(tmp_path / "o"),
                 "--workers", "1", "--fail-under", "99"])
    assert code == 1
