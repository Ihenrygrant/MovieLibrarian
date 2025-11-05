import json
import urllib.parse
from io import StringIO
from lib import omdb_client

def _fake_urlopen_factory():
    class FakeResp:
        def __init__(self, text):
            self._buf = StringIO(text)
        def __enter__(self):
            return self._buf
        def __exit__(self, exc_type, exc, tb):
            try:
                self._buf.close()
            except Exception:
                pass

    def fake_urlopen(url, timeout=8):
        q = urllib.parse.urlparse(url).query
        params = urllib.parse.parse_qs(q)
        # exact title lookup (t=) for 'ARMAGEDN' -> return no exact match
        if params.get("t") and params.get("t")[0].lower() == "armagedn":
            return FakeResp(json.dumps({"Response": "False", "Error": "Movie not found!"}))
        # permissive search: return both a short "Arma" and the full "Armageddon"
        if params.get("s"):
            payload = {
                "Search": [
                    {"Title": "Arma", "Year": "2017", "imdbID": "tt7007728"},
                    {"Title": "Armageddon", "Year": "1998", "imdbID": "tt0123456"},
                ],
                "Response": "True",
            }
            return FakeResp(json.dumps(payload))
        # id lookup for Armageddon
        if params.get("i") and params.get("i")[0] == "tt0123456":
            payload = {"Title": "Armageddon", "Year": "1998", "imdbID": "tt0123456", "Response": "True"}
            return FakeResp(json.dumps(payload))
        # id lookup for Arma
        if params.get("i") and params.get("i")[0] == "tt7007728":
            payload = {"Title": "Arma", "Year": "2017", "imdbID": "tt7007728", "Response": "True"}
            return FakeResp(json.dumps(payload))
        return FakeResp(json.dumps({"Response": "False"}))
    return fake_urlopen

def test_resolve_truncated_label_prefers_full_title(monkeypatch):
    fake = _fake_urlopen_factory()
    monkeypatch.setattr(omdb_client.urllib.request, "urlopen", fake)
    title, year, imdbid, score = omdb_client.resolve_title_via_omdb("ARMAGEDN", api_key="FAKE", interactive=False, threshold=0.4)
    assert title == "Armageddon"
    assert year == "1998"
    assert imdbid == "tt0123456"
    assert score >= 0.4