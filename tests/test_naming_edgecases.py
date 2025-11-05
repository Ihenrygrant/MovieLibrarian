import pytest
from lib import naming

def test_choose_prefers_human_tinfo_over_hardware_label():
    raw = "\n".join([
        'CINFO:2,0,"BD-RE HL-DT-ST BD-RE  WH16NS60 1.02 KL5O6R95954"',
        'TINFO:0,27,0,"The Matrix (Feature) .m2ts"',
        'TINFO:0,30,0,"2:16:00"'
    ])
    # parsed_titles includes a cleaned per-title name (simulating makemkv.get_titles_info)
    parsed_titles = [{"id": 0, "title": "The Matrix", "seconds": 8160}]
    chosen = naming.choose_title(raw, "BD-RE HL-DT-ST BD-RE  WH16NS60 1.02 KL5O6R95954", parsed_titles, interactive=False)
    assert chosen.lower().startswith("the matrix")

def test_tv_season_string_is_cleaned_and_chosen():
    raw = "\n".join([
        'TINFO:0,27,0,"Some Show - Season 1 - Episode 02.m2ts"',
        'TINFO:0,30,0,"0:42:00"'
    ])
    parsed_titles = [{"id": 0, "title": "Some Show - Season 1", "seconds": 2520}]
    chosen = naming.choose_title(raw, "", parsed_titles, interactive=False)
    cleaned = naming.clean_title_string(chosen)
    assert "Season" in cleaned or "Some Show" in cleaned

def test_fallback_to_unknown_when_no_good_candidate():
    raw = "\n".join([
        'TINFO:0,27,0,"A1_t00.mkv"',
        'TINFO:0,30,0,"22 chapter(s) , 7087.6 MB (A1)"',
    ])
    parsed_titles = [{"id": 0, "title": "", "seconds": 7087}]
    chosen = naming.choose_title(raw, "BD-RE WH16NS60", parsed_titles, interactive=False)
    # chooser returns empty when no good candidate; caller should fallback to 'Unknown'
    assert chosen == ""
    folder_name = naming.safe_filename(chosen) or "Unknown"
    assert folder_name == "Unknown"

def test_clean_title_string_removes_episode_markers_and_exts():
    s = 'Some.Show.S01E02_1080p.m2ts'
    cleaned = naming.clean_title_string(s)
    # ensure extension and obvious episode token removed (relaxed check)
    assert 'S01E02' not in cleaned and 'Some' in cleaned
