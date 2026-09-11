from cds_audit.checks import metadata as m
from cds_audit.models import DatasetInfo


def ds(**kw):
    base = dict(id="x", title="Daily rainfall for Bihar districts (2000–2020)",
                description=("This dataset provides daily rainfall for districts of Bihar from 2000 to 2020. "
                             "It was compiled by the Example Climate Institute. It is intended to support flood planning."),
                organization="Example Climate Institute", tags=["Rainfall"], sectors=["Climate Action"],
                geographies=[{"name": "Bihar"}], license="CC_BY_4_0_ATTRIBUTION",
                metadata=[{"label": "Date of Creation", "data_type": "DATE", "value": "2021-03-15"},
                          {"label": "Source Website", "data_type": "URL", "value": "https://example.org/rain"}])
    base.update(kw)
    return DatasetInfo(**base)


def test_good_dataset_passes_all_metadata(rules):
    d = ds()
    for fn in m.ALL_METADATA_CHECKS:
        res = fn(d, rules) if fn is not m.check_source_website else fn(d, rules, None)
        assert res.status == "pass", (res.check_id, res.issues)


def test_title_rules(rules):
    r = m.check_title(ds(title="State Revenue & Receipts"), rules)
    assert any("special characters" in i for i in r.issues)
    assert any("time period" in i for i in r.issues)
    r = m.check_title(ds(title="NFHS-5 indicators for districts 2019"), rules)
    assert any("abbreviations" in i and "NFHS" in i for i in r.issues)
    r = m.check_title(ds(title="x" * 70 + " 2020"), rules)
    assert any("characters (limit 60)" in i for i in r.issues)


def test_all_caps_title_is_a_casing_issue_not_abbreviations(rules):
    r = m.check_title(ds(title="GUWAHATI WARD BOUNDARIES 2022"), rules)
    assert any("sentence case" in i for i in r.issues)
    assert not any("abbreviations" in i for i in r.issues)


def test_description_needs_named_source_not_just_the_word_government(rules):
    text = ("Revenue receipts include tax and non-tax revenues. Together they form the total receipts of "
            "the government.")
    r = m.check_description(ds(description=text, organization="Budget Lab"), rules)
    assert any("who collected" in i for i in r.issues)
    r = m.check_description(ds(description="Figures for Assam in 2011. Data from the Census of India."), rules)
    assert not any("who collected" in i for i in r.issues)


def test_description_sentence_bounds(rules):
    assert any("only 1 sentence" in i for i in m.check_description(ds(description="Pending cases."), rules).issues)
    long = " ".join(f"Sentence number {i} about Bihar in 2020." for i in range(8))
    assert any("runs to" in i for i in m.check_description(ds(description=long), rules).issues)


def test_government_source_needs_godl(rules):
    meta = [{"label": "Source Website", "data_type": "URL", "value": "https://finance.assam.gov.in/budget"}]
    r = m.check_license(ds(metadata=meta), rules)
    assert r.status == "warn" and "platform default" in r.issues[0]
    r = m.check_license(ds(metadata=meta, license="GOVERNMENT_OPEN_DATA_LICENSE"), rules)
    assert r.status == "pass"


def test_date_of_creation_iso(rules):
    bad = [{"label": "Date of Creation", "data_type": "DATE", "value": "15/04/2024"}]
    assert m.check_date_of_creation(ds(metadata=bad), rules).status == "warn"
    assert m.check_date_of_creation(ds(metadata=[]), rules).status == "fail"


def test_source_website(rules):
    bad = [{"label": "Source Website", "data_type": "URL", "value": "example.org"}]
    assert m.check_source_website(ds(metadata=bad), rules).status == "warn"
    ok = [{"label": "Source Website", "data_type": "URL", "value": "https://example.org"}]
    assert m.check_source_website(ds(metadata=ok), rules, {"https://example.org": 404}).status == "warn"


def test_geography_mismatch_with_title(rules):
    r = m.check_geography(ds(title="Health indicators for Uttar Pradesh 2021", geographies=[{"name": "India"}]), rules)
    assert r.status == "warn" and "Uttar Pradesh" in r.issues[0]


def test_individual_publisher_and_tags(rules):
    assert m.check_publisher(ds(organization="", user="A. Person"), rules).status == "warn"
    assert m.check_tags(ds(tags=[]), rules).status == "fail"
    assert m.check_tags(ds(tags=["Climate Action"], sectors=["Climate Action"]), rules).status == "warn"
