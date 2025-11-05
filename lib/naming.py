import re
import sys
import html as _html
import csv
import io
import re
from typing import Optional, List, Tuple

CANDIDATE_TINFO_PRIORITY = [27, 49, 30, 3]  # per-title field priority (exclude fid 2 which often mirrors CINFO)

def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", (name or ""))

def is_hardware_label(name: str) -> bool:
    if not name:
        return False
    # treat very long labels as hardware-like
    if len(name) > 40:
        return True
    # match common hardware/drive tokens even when embedded (e.g. WH16NS60, BDRE123)
    pattern = r'(bd-?re|bd-r|bdrom|hl-dt-st|wh\d+[a-z0-9]*|dvd|usb|matshita|lite-on|plextor)'
    return bool(re.search(pattern, name, flags=re.IGNORECASE))

def clean_title_string(s: str) -> str:
    if not s:
        return ""
    s = s.strip().strip('"')

    # strip HTML tags and decode HTML entities early
    s = re.sub(r'<[^>]+>', ' ', s)
    s = _html.unescape(s)

    # normalize separators early so subsequent token regexes match reliably
    s = re.sub(r'[._]+', ' ', s)
    s = s.replace('_', ' ')
    s = s.strip()

    # remove obvious standalone markup tokens that appear from naive replacements
    s = re.sub(r'\b(?:b|br|i|span|div)\b', ' ', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+', ' ', s).strip()

    # if the cleaned string is clearly just markup/labels (e.g. "Title information"), treat as empty
    low = s.lower()
    if not s or 'title information' in low or 'source information' in low:
        return ""

    # remove common file extensions (both ".mkv" and trailing " mkv" forms)
    s = re.sub(r'(?i)\.(mkv|m2ts|mpls|iso)\s*$', '', s)
    s = re.sub(r'(?i)\s+(mkv|m2ts|mpls|iso)\s*$', '', s)

    # remove per-title markers like " t00"
    s = re.sub(r'\b[tT]\d{1,3}\b', '', s)

    # remove episode tokens like S01E02 or s01e02
    s = re.sub(r'\b[Ss]\d{1,2}[Ee]\d{1,2}\b', '', s)

    # remove common resolution/codec tokens
    s = re.sub(r'\b(?:\d{3,4}p|720p|1080p|2160p|HD|SD|x264|x265|HEVC)\b', '', s, flags=re.IGNORECASE)

    # drop any trailing suffix like " - extra info"
    s = re.split(r'\s+-\s+', s, maxsplit=1)[0]

    # collapse repeated punctuation/underscores and whitespace
    s = re.sub(r'[_\-]{2,}', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()

    # remove leading/trailing leftover punctuation
    s = s.strip(' _-')

    # final safety: if result looks like markup tokens only, return empty
    if re.fullmatch(r'^(?:b|br|i|span|div)(?:\s+(?:b|br|i|span|div))*$', s, flags=re.IGNORECASE):
        return ""

    return s

def is_noisy_title(s: str) -> bool:
    if not s:
        return True
    low = s.lower()

    # treat raw DRV/CINFO/TINFO tokens (e.g. "DRV:0", "CINFO:1", "TINFO:0") as noisy
    if re.fullmatch(r'\s*(?:DRV|CINFO|TINFO)[:\s]*\d+\s*', s, flags=re.IGNORECASE):
        return True

    # time-like strings (e.g. "2:30:15" or "0:42:00") are not titles
    if re.fullmatch(r'\d{1,2}:\d{2}(?::\d{2})?', s.strip()):
        return True

    # long numeric values (file sizes, hashes, offsets) are noisy — but allow 4-digit years like 1998
    if re.fullmatch(r'^[\d,\s]{5,}$', s.strip()):
        return True

    # chapter / chapter-list patterns (e.g. "(1,3),5-20,21-35,(36,38),40") are noisy
    if re.search(r'\bchapter\b', low) or re.search(r'\(?\d+(?:,\d+)*\)?(?:[,\s]*\d+-\d+)+', s):
        return True
    # punctuation-heavy numeric lists (parentheses + commas + dashes) are noisy
    if re.fullmatch(r'^[\d\(\)\-,\s]+$', s.strip()):
        return True

    # HTML or fenced markup artifacts are noisy
    if '<' in s or '>' in s or '&lt;' in low or '&gt;' in low:
        return True
    if 'title information' in low or 'source information' in low:
        return True

    # obvious noise markers
    if "chapter" in low or "chapter(s)" in low or "gb" in low or "mb" in low:
        return True
    if re.search(r'\b\d+\s*chapter', low):
        return True
    if re.search(r'\b\d+(\.\d+)?\s*(gb|mb)\b', low):
        return True
    if re.search(r'\.(mkv|m2ts|mpls|iso)$', s, re.IGNORECASE):
        return True
    # short cryptic labels like "C9_t00" or alphanumeric codes
    if re.match(r'^[A-Z0-9_\-]{1,6}$', s, re.IGNORECASE) and '_' in s:
        return True
    # single-letter or purely numeric values are noisy
    if re.fullmatch(r'^[\dA-Za-z]{1,3}$', s):
        return True
    # hardware-like labels also considered noisy for naming
    if is_hardware_label(s):
        return True
    return False

def pick_title_name_from_tinfo(data: dict) -> str:
    """Pick best title string from a TINFO (per-title fields) dict."""
    for fid in CANDIDATE_TINFO_PRIORITY:
        v = data.get(fid)
        if not v:
            continue
        cand = clean_title_string(v)
        if cand and not is_noisy_title(cand):
            return cand
    # fallback: any non-noisy cleaned value, but skip CINFO-like fields (e.g. fid==2)
    skip_fields = {2}
    for fid, v in data.items():
        if fid in skip_fields:
            continue
        cand = clean_title_string(v)
        # ensure we skip time/duration-like strings even if cleaned
        if cand and not is_noisy_title(cand):
            return cand
    # last resort return empty
    return ""

def gather_raw_title_candidates(raw_info_text: str, drive_label: Optional[str] = None, parsed_titles: Optional[List[dict]] = None) -> List[Tuple[str, str]]:
    cands = []
    if drive_label:
        cands.append(("label", drive_label))
    for line in (raw_info_text or "").splitlines():
        if line.startswith("CINFO"):
            parts = line.split(",", 2)
            if len(parts) >= 3:
                v = parts[2].strip().strip('"')
                if v:
                    cands.append(("cinfo", v))
        elif line.startswith("TINFO"):
            parts = line.split(",", 3)
            if len(parts) >= 4:
                v = parts[3].strip().strip('"')
                if v:
                    cands.append(("tinfo", v))
    if parsed_titles:
        for t in parsed_titles:
            if t.get("title"):
                cands.append(("tinfo_parsed", t["title"]))
    return cands

def score_and_prioritise_candidates(cands: List[Tuple[str, str]]) -> List[Tuple[str, int]]:
    seen = {}
    for src, val in cands:
        cand = clean_title_string(val)
        if not cand or is_noisy_title(cand):
            continue
        key = cand.strip()
        score = 0
        if src == "cinfo":
            score += 40
        elif src == "label":
            score += 8
        elif src == "tinfo_parsed":
            score += 12
        elif src == "tinfo":
            score += 4
        else:
            score += 1
        if len(key) >= 4:
            score += 2
        # slight boost for mixed-case human-like strings
        if re.search(r'[a-z][A-Z]|[A-Z][a-z]', val or ""):
            score += 1
        seen[key] = seen.get(key, 0) + score
    return sorted([(k, v) for k, v in seen.items()], key=lambda x: x[1], reverse=True)

def pick_cinfo_title(raw_info: str) -> str:
    """
    Extract a probable disc-level title from MakeMKV raw_info lines (DRV/CINFO).
    - Parse raw_info with csv.reader so quoted fields are respected.
    - Prefer quoted/CSV fields that contain underscores and letters (REMEMBER_THE_TITANS).
    - Normalize underscored tokens -> Title Case; preserve single-word ALLCAPS tokens.
    - Ignore trivial tokens like DRV/CINFO/TINFO and drive letters.
    """
    if not raw_info:
        return ""

    def _alpha_count(s: str) -> int:
        return len(re.sub(r'[^A-Za-z]', '', s or ""))

    def _is_drive_letter_field(s: str) -> bool:
        return bool(re.fullmatch(r'\s*[A-Za-z]:?\s*', s))

    # Parse as CSV so quoted fields are extracted correctly
    fields = []
    try:
        for row in csv.reader(io.StringIO(raw_info)):
            for f in row:
                if f is not None:
                    fields.append(str(f).strip())
    except Exception:
        # fallback: quoted-field capture
        fields = re.findall(r'"([^"]+)"', raw_info)

    # 1) Prefer underscored tokens in parsed fields (most reliable for your DRV example).
    for f in fields:
        if not f:
            continue
        if _is_drive_letter_field(f):
            continue
        if _alpha_count(f) < 3:
            continue
        if '_' in f and re.search(r'[A-Za-z]', f):
            candidate = f.replace('_', ' ').strip()
            candidate = ' '.join(w.title() if w.isupper() else w for w in candidate.split())
            cand = clean_title_string(candidate)
            if cand and not is_noisy_title(cand):
                return cand

    # 2) Second pass: single-word ALLCAPS (preserve ALL CAPS) or other reasonable textual fields
    for f in fields:
        if not f:
            continue
        # skip trivial internal tokens
        if re.fullmatch(r'\s*(?:DRV|CINFO|TINFO)[:\s]*\d+\s*', f, flags=re.IGNORECASE):
            continue
        if _is_drive_letter_field(f):
            continue
        if _alpha_count(f) < 3:
            continue

        token = f.strip()
        # preserve single-word ALLCAPS (e.g. ARMAGEDN)
        if re.fullmatch(r'[A-Z0-9]{3,}', token):
            cand = clean_title_string(token)
            if cand and not is_noisy_title(cand):
                # prefer returning original ALLCAPS if cleaning downcased it
                if cand.lower() == token.lower():
                    return token
                return cand

        # otherwise normalize underscores/spaces and titlecase words that are all upper
        parts = token.replace('_', ' ').split()
        candidate = ' '.join(w.title() if w.isupper() else w for w in parts)
        cand = clean_title_string(candidate)
        if cand and not is_noisy_title(cand):
            return cand

    return ""

def choose_title(raw_info_text: str, drive_label: str, parsed_titles: List[dict], interactive: bool = True) -> str:
    # Prefer parsed per-title human names (from makemkv parsing) first
    if parsed_titles:
        # parsed_titles expected sorted by duration; pick longest human-friendly title
        for t in sorted(parsed_titles, key=lambda x: x.get("seconds", 0), reverse=True):
            ttitle = t.get("title") or ""
            t_clean = clean_title_string(ttitle)
            if t_clean and not is_noisy_title(t_clean):
                return t_clean

    # Next, prefer a clean non-hardware CINFO disc title
    cinfo_choice = pick_cinfo_title(raw_info_text)
    if cinfo_choice:
        return cinfo_choice

    # Otherwise build candidate list, score and choose — but filter out hardware-like candidates
    cands = gather_raw_title_candidates(raw_info_text, drive_label, parsed_titles)
    scored = score_and_prioritise_candidates(cands)

    # filter out hardware labels in scored results
    filtered = [(c, s) for c, s in scored if not is_hardware_label(c)]
    if not filtered:
        return ""

    if len(filtered) == 1 or (len(filtered) > 1 and filtered[0][1] >= filtered[1][1] + 8):
        return filtered[0][0]

    if interactive and sys.stdin and sys.stdin.isatty():
        print("\nAmbiguous disc title candidates:")
        for i, (cand, s) in enumerate(filtered[:6], start=1):
            print(f"  {i}) {cand}  (score {s})")
        print("  0) None of the above / use fallback")
        try:
            choice = input("Choose correct disc title number (0 to skip): ").strip()
            if choice.isdigit():
                idx = int(choice)
                if idx == 0:
                    return ""
                if 1 <= idx <= min(6, len(filtered)):
                    return filtered[idx - 1][0]
        except Exception:
            pass

    return filtered[0][0]