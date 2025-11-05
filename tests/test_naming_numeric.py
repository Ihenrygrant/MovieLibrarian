from lib import naming

def test_long_numeric_strings_are_noisy_and_not_chosen():
    # direct noisy check
    assert naming.is_noisy_title("7087575040")
    assert naming.is_noisy_title("7,087,575,040")
    # chooser should not pick a long numeric TINFO as the title
    raw = '\n'.join([
        'TINFO:0,27,0,"7087575040"',
        'TINFO:0,30,0,"0:02:31"'
    ])
    chosen = naming.choose_title(raw, "", [], interactive=False)
    assert chosen == ""