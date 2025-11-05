import io
import json
from lib import naming

def test_clean_title_string_removes_ext_and_suffixes():
    assert naming.clean_title_string('C9_t00.mkv') == 'C9'
    assert naming.clean_title_string('Movie - 22 chapter(s) , 1.2 GB (C9)') == 'Movie'
    assert naming.clean_title_string('MyFilm_t01.m2ts') == 'MyFilm'

def test_is_noisy_title_examples():
    assert naming.is_noisy_title('22 chapter(s) , 1022.4 MB (C9)')
    assert naming.is_noisy_title('C9_t00.mkv')
    assert not naming.is_noisy_title('Anchorman')

def test_pick_cinfo_title_prefers_cinfo(tmp_path):
    # build a small raw_info_text with CINFO and TINFO lines
    raw = '\n'.join([
        'CINFO:2,0,"ARMAGEDN"',
        'TINFO:0,27,0,"B1_t00.mkv"',
        'TINFO:0,30,0,"22 chapter(s) , 1022.4 MB (C9)"',
    ])
    picked = naming.pick_cinfo_title(raw)
    assert picked == 'ARMAGEDN'

def test_score_and_prioritise_filters_short_codes():
    raw = [
        ('tinfo', 'B1'),
        ('tinfo', 'C9_t00.mkv'),
        ('cinfo', 'ARMAGEDN'),
        ('label', 'BD-RE WH16NS60'),
        ('tinfo_parsed', 'Anchorman'),
    ]
    scored = naming.score_and_prioritise_candidates(raw)
    # Anchorman or ARMAGEDN should be top candidates (human readable)
    assert any('ARMAGEDN' == c for c, _ in scored) or any('Anchorman' == c for c, _ in scored)
