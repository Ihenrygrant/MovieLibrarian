from lib import naming

def test_html_like_title_is_stripped_and_considered_noisy():
    bad = '<b>Title information</b><br>'
    cleaned = naming.clean_title_string(bad)
    assert cleaned == "" or cleaned.lower().startswith("title") is False
    assert naming.is_noisy_title(bad)

def test_underscored_markup_like_string_is_noisy():
    bad = '_b_Title information__b__br_'
    assert naming.is_noisy_title(bad)
    assert naming.clean_title_string(bad) == ""