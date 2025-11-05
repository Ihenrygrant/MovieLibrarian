import json
from io import StringIO
import urllib.parse
from lib import omdb_client

def _fake_urlopen_factory():
    # returns a fake urlopen that responds to OMDb 's=' and 'i=' queries
    def fake_urlopen(url, timeout=8):
        q = urllib.parse.urlparse(url).query
        params = urllib.parse.parse_qs(q)
        if 's' in params:
            # search response
            payload = {"Search": [{"Title": "Armageddon", "Year": "1998", "imdbID": "tt0123456"}], "Response": "True"}
            return StringIO(json.dumps(payload))
        if 'i' in params or 't' in params:
            # full record response
            payload = {"Title": "Armageddon", "Year": "1998", "imdbID": "tt0123456", "Response": "True"}
            return StringIO(json.dumps(payload))
        return StringIO(json.dumps({"Response": "False"}))
    return fake_urlopen

def test_resolve_title_via_omdb_fuzzy(monkeypatch):
    fake = _fake_urlopen_factory()
    monkeypatch.setattr(omdb_client.urllib.request, "urlopen", fake)
    title, year, imdbid, score = omdb_client.resolve_title_via_omdb("ARMAGEDN", api_key="FAKE", interactive=False, threshold=0.6)
    assert title == "Armageddon"
    assert year == "1998"
    assert imdbid == "tt0123456"
    assert score > 0.6