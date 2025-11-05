import urllib.parse
import json
from io import StringIO
from lib import naming, omdb_client

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
        # basic parsing, respond to search (s=) and lookup (i= or t=)
        qs = urllib.parse.urlparse(url).query
        params = urllib.parse.parse_qs(qs)
        if "s" in params:
            payload = {"Search": [{"Title": "Armageddon", "Year": "1998", "imdbID": "tt0123456"}], "Response": "True"}
            return FakeResp(json.dumps(payload))
        if "t" in params or "i" in params:
            payload = {"Title": "Armageddon", "Year": "1998", "imdbID": "tt0123456", "Response": "True"}
            return FakeResp(json.dumps(payload))
        return FakeResp(json.dumps({"Response": "False"}))
    return fake_urlopen

def test_pick_cinfo_then_resolve(monkeypatch):
    # simulate CINFO typo "ARMAGEDN" and ensure OMDb resolver suggests "Armageddon"
    raw = '\n'.join([
        'CINFO:2,0,"ARMAGEDN"',
        'TINFO:0,27,0,"A1_t00.mkv"',
        'TINFO:0,30,0,"22 chapter(s) , 7087.6 MB (A1)"',
    ])
    # chooser should pick CINFO first (even if misspelled)
    cinfo_choice = naming.pick_cinfo_title(raw)
    assert cinfo_choice == "ARMAGEDN"
    # monkeypatch urlopen and resolve via OMDb client
    fake = _fake_urlopen_factory()
    monkeypatch.setattr(omdb_client.urllib.request, "urlopen", fake)
    title, year, imdbid, score = omdb_client.resolve_title_via_omdb(cinfo_choice, api_key="FAKE", interactive=False, threshold=0.5)
    assert title == "Armageddon"
    assert year == "1998"
    assert imdbid == "tt0123456"
    assert score >= 0.5

def test_pick_title_name_from_tinfo_prefers_human():
    data = {
        27: 'A1_t00.mkv',
        30: '22 chapter(s) , 7087.6 MB (A1)',
        2: 'ARMAGEDN'
    }
    # per-title picker should avoid 'A1_t00' and return nothing (per-title), cinfo should be used for disc
    per_title = naming.pick_title_name_from_tinfo(data)
    assert per_title == ""
    cinfo_sim = 'CINFO:2,0,"ARMAGEDN"'
    assert naming.pick_cinfo_title(cinfo_sim) == "ARMAGEDN"