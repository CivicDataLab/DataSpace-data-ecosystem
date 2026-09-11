from cds_audit.client import DataSpaceClient, normalise


class FakeResp:
    def __init__(self, payload, status=200, headers=None):
        self._p, self.status_code, self.headers, self.text = payload, status, headers or {}, ""

    def json(self):
        return self._p


class FakeSession:
    def __init__(self, handler):
        self.handler, self.headers, self.calls = handler, {}, []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return self.handler(method, url, kw)


def test_search_paginates_until_total(rules):
    def handler(method, url, kw):
        page = kw["params"]["page"]
        results = [{"id": f"{page}-{i}", "title": "t"} for i in range(2 if page < 3 else 1)]
        return FakeResp({"results": results, "total": 5})
    c = DataSpaceClient({**rules["api"], "page_size": 2, "pause_between_requests": 0})
    c.session = FakeSession(handler)
    ids = [h["id"] for h in c.iter_search()]
    assert ids == ["1-0", "1-1", "2-0", "2-1", "3-0"]


def test_resources_query_falls_back_without_file_field(rules):
    def handler(method, url, kw):
        q = kw["json"]["query"]
        if "file { name }" in q:
            return FakeResp({"errors": [{"message": "Cannot query field 'file' on type 'TypeFileDetails'"}]})
        return FakeResp({"data": {"datasetResources": [{"id": "r1", "fileDetails": {"format": "csv"}}]}})
    c = DataSpaceClient({**rules["api"], "pause_between_requests": 0})
    c.session = FakeSession(handler)
    res, errs = c.dataset_resources("abc")
    assert res[0]["id"] == "r1" and not errs


def test_normalise_falls_back_to_search_hit_when_graphql_missing():
    hit = {"id": "d1", "title": "T", "description": "D", "tags": ["a"], "sectors": ["Gender"],
           "geographies": ["Assam"], "organization": {"name": "Org"},
           "metadata": [{"metadata_item": {"label": "Source Website"}, "value": "https://x.org"}]}
    ds = normalise(hit, None, [], ["detail failed"])
    assert ds.organization == "Org" and ds.geographies[0]["name"] == "Assam"
    assert ds.metadata[0]["label"] == "Source Website" and ds.fetch_errors == ["detail failed"]
