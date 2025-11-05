from lib import naming

def test_duration_strings_are_noisy():
    assert naming.is_noisy_title("2:30:15")
    assert naming.is_noisy_title("0:42:00")
    assert naming.is_noisy_title("42:00")

def test_choose_skips_duration_in_parsed_titles_and_uses_cinfo():
    raw = 'CINFO:2,0,"ARMAGEDN"\n'
    parsed_titles = [{"id": 0, "title": "2:30:15", "seconds": 9000}]
    # parsed title is a duration and should be skipped; chooser should fall back to CINFO
    chosen = naming.choose_title(raw, "", parsed_titles, interactive=False)
    assert chosen == "ARMAGEDN"

def test_choose_returns_empty_when_only_duration_and_hw_label_present():
    raw = ''
    parsed_titles = [{"id": 0, "title": "2:30:15", "seconds": 9000}]
    # no CINFO and parsed title is noisy -> chooser returns empty (caller should fallback to "Unknown")
    chosen = naming.choose_title(raw, "BD-RE WH16NS60", parsed_titles, interactive=False)
    assert chosen == ""