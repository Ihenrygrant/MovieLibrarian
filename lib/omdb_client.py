import json
import urllib.request
import urllib.parse
import re
import time
import logging
from typing import Tuple, Optional
import difflib
import csv
import io
import re

logger = logging.getLogger(__name__)

# try to use rapidfuzz for better fuzzy matching; fall back to difflib
try:
    from rapidfuzz import fuzz  # type: ignore
    _have_rapidfuzz = True
except Exception:
    fuzz = None
    _have_rapidfuzz = False

_OMDB_BASE = "http://www.omdbapi.com/"

# small new constant: below 'threshold' we will still return a suggestion if score >= SUGGEST_THRESHOLD
SUGGEST_THRESHOLD = 0.35

def _urlopen_json(url: str, timeout: int = 8) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.load(resp)

def _search_omdb(search_term: str, api_key: str):
    qs = {"apikey": api_key, "s": search_term, "type": "movie"}
    url = _OMDB_BASE + "?" + urllib.parse.urlencode(qs)
    try:
        return _urlopen_json(url)
    except Exception:
        return {}

def _get_omdb_by_id(imdb_id: str, api_key: str):
    qs = {"apikey": api_key, "i": imdb_id, "plot": "short"}
    url = _OMDB_BASE + "?" + urllib.parse.urlencode(qs)
    try:
        return _urlopen_json(url)
    except Exception:
        return {}

def _get_omdb_by_title(title: str, api_key: str):
    qs = {"apikey": api_key, "t": title, "type": "movie", "plot": "short"}
    url = _OMDB_BASE + "?" + urllib.parse.urlencode(qs)
    try:
        return _urlopen_json(url)
    except Exception:
        return {}

def _score_string(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if _have_rapidfuzz and fuzz is not None:
        return float(fuzz.token_set_ratio(a, b)) / 100.0
    else:
        return float(difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio())

def _looks_noisy_for_omdb(q: str) -> bool:
    if not q:
        return True
    qlow = q.lower()
    # hardware-like labels
    if re.search(r'\b(bd-?re|bdrom|hl-dt-st|wh\d+|dvd|usb|matshita|lite-on|plextor)\b', qlow):
        return True
    # chapter lists or parenthetical numeric lists
    if re.search(r'\(?\d+(?:,\d+)*\)?(?:[,\s]*\d+-\d+)+', q):
        return True
    # long numeric/hash strings
    if re.fullmatch(r'^[\d,\s]{5,}$', q.strip()):
        return True
    # markup artifacts
    if '<' in q or '>' in q:
        return True
    return False

def resolve_title_via_omdb(query: str, api_key: str, interactive: bool = False, threshold: float = 0.6):
    """
    Try straightforward exact lookups for obvious candidates first:
      - If the input looks like a DRV/CINFO CSV line, parse fields and try each field (raw and underscore->space)
      - If query contains underscored tokens, try the raw underscore form and the normalized form as exact lookups
    Falls back to existing broader search/prefix/fuzzy logic if no exact hits.
    """
    if not query or not api_key:
        return None, None, None, 0.0

    def _safe_lookup_title(title):
        try:
            return _get_omdb_by_title(title, api_key)  # existing helper in file
        except Exception as exc:
            logger.debug("OMDb exact lookup failed for %r: %s", title, exc)
            return {}

    # quick helper to try a candidate string as an exact OMDb title
    def _try_exact(cand):
        if not cand or len(re.sub(r'[^A-Za-z0-9]', '', cand)) < 2:
            return None
        logger.debug("OMDb: exact lookup attempt for candidate: %r", cand)
        res = _safe_lookup_title(cand)
        if res and res.get("Response", "False") == "True":
            return (res.get("Title"), res.get("Year"), res.get("imdbID"))
        return None

    # 1) If query is a delimited/drv/cinfo line, parse CSV fields and try them directly (raw + normalized)
    if ("," in query) or ('"' in query) or re.match(r'^\s*(DRV|CINFO|TINFO)\b', query, flags=re.IGNORECASE):
        logger.debug("OMDb: parsing input as CSV-like and trying exact-title lookups for fields")
        fields = []
        try:
            for row in csv.reader(io.StringIO(query)):
                for f in row:
                    if f:
                        fields.append(str(f).strip().strip('"'))
        except Exception:
            fields = re.findall(r'"([^"]+)"', query) or [p.strip() for p in re.split(r'\s*,\s*', query) if p.strip()]

        tried = set()
        for f in fields:
            if not f or f.lower() in tried:
                continue
            tried.add(f.lower())
            # ignore obvious non-title tokens quickly
            if re.fullmatch(r'\s*(?:DRV|CINFO|TINFO)[:\s]*\d+\s*', f, flags=re.IGNORECASE):
                continue
            if re.fullmatch(r'\s*[A-Za-z]:?\s*', f):  # drive letters like G:
                continue

            # Try raw field first (including underscored form if present)
            res = _try_exact(f)
            if res:
                logger.debug("OMDb exact match via CSV field (raw): %r", f)
                return res[0], res[1], res[2], 1.0

            # Try normalized variant: underscores -> spaces
            norm = f.replace('_', ' ').strip()
            if norm.lower() not in tried:
                tried.add(norm.lower())
                res = _try_exact(norm)
                if res:
                    logger.debug("OMDb exact match via CSV field (normalized): %r", norm)
                    return res[0], res[1], res[2], 1.0

    # 2) If the whole query contains underscores, try the raw underscore form and space-normalized form
    if "_" in query:
        logger.debug("OMDb: input contains underscores, trying underscore variants")
        cand_raw = query.strip().strip('"')
        cand_norm = cand_raw.replace('_', ' ').strip()
        for cand in (cand_raw, cand_norm):
            res = _try_exact(cand)
            if res:
                logger.debug("OMDb exact match from underscore-variant: %r", cand)
                return res[0], res[1], res[2], 1.0

    # 1) try exact title lookup
    logger.debug("OMDb: exact lookup: %r", query)
    exact = _safe_url(_get_omdb_by_title, query, api_key)
    if exact.get("Response", "False") == "True":
        logger.debug("OMDb exact match -> %r (%r)", exact.get("Title"), exact.get("Year"))
        return exact.get("Title"), exact.get("Year"), exact.get("imdbID"), 1.0

    candidates = []

    def run_search_and_collect(term):
        logger.debug("OMDb: search s=%r", term)
        res = _safe_url(_search_omdb, term, api_key)
        if res and res.get("Response") == "True":
            for item in res.get("Search", []):
                candidates.append(item)
            logger.debug("OMDb: search %r returned %d items", term, len(res.get("Search", [])))
        else:
            logger.debug("OMDb: search %r returned no items", term)

    # 2) full-search
    run_search_and_collect(query)

    # 3) progressive prefix searches (bounded)
    clean_q = re.sub(r'\s+', '', query)
    L = len(clean_q)
    for l in range(max(4, L), max(3, L - 6) - 1, -1):
        prefix = clean_q[:l]
        if prefix and len(prefix) >= 4:
            run_search_and_collect(prefix)

    # 4) token searches
    q_tokens = [t for t in re.findall(r'\w+', query) if len(t) >= 4]
    for token in q_tokens[:3]:
        run_search_and_collect(token)

    # dedupe
    uniq = {}
    for c in candidates:
        # use imdbID when present, otherwise synthetic key "Title|Year"
        title = c.get("Title", "")
        year = c.get("Year", "")
        iid = c.get("imdbID") or f"{title}|{year}"
        if iid not in uniq:
            uniq[iid] = c

    if not uniq:
        logger.debug("OMDb: no candidates collected for query %r", query)
        return None, None, None, 0.0

    # scoring
    best = (None, 0.0, None)  # (imdbID, score, (title,year))
    q_alnum = re.sub(r'[^A-Za-z0-9]', '', query).lower()
    q_tokens_set = set(re.findall(r'\w+', query.lower()))
    logger.debug("OMDb: scoring %d candidates for %r", len(uniq), query)

    def _is_subsequence(small: str, big: str) -> bool:
        """Return True if all chars in `small` appear in `big` in order (case-insensitive)."""
        si = re.sub(r'[^A-Za-z0-9]', '', small).lower()
        bi = re.sub(r'[^A-Za-z0-9]', '', big).lower()
        if not si or not bi:
            return False
        i = 0
        for ch in bi:
            if ch == si[i]:
                i += 1
                if i >= len(si):
                    return True
        return False

    for iid, meta in sorted(uniq.items()):  # deterministic order
        title = meta.get("Title", "")
        year = meta.get("Year", "")
        base = _score_string(query, title)
        t_tokens = set(re.findall(r'\w+', title.lower()))
        token_overlap = 0.0
        if q_tokens_set or t_tokens:
            token_overlap = len(q_tokens_set & t_tokens) / max(1, len(q_tokens_set | t_tokens))
        t_alnum = re.sub(r'[^A-Za-z0-9]', '', title).lower()
        length_factor = min(1.0, len(t_alnum) / max(1, len(q_alnum))) if q_alnum else 1.0

        # subsequence boost: if the query characters appear in order inside the full title,
        # it's a strong signal that the disc label is a shortened/truncated form.
        subseq_bonus = 0.0
        if _is_subsequence(query, title):
            subseq_bonus = 0.25

        # combined score (weights tuned to prefer token overlap/length and subsequence matches)
        final_score = (base * 0.50) + (token_overlap * 0.25) + (length_factor * 0.10) + subseq_bonus
        final_score = max(0.0, min(1.0, final_score))
        logger.debug("OMDb candidate: %r (%s) base=%.3f tokov=%.3f lenf=%.3f subseq=%.2f final=%.3f", title, iid, base, token_overlap, length_factor, subseq_bonus, final_score)

        # deterministic tie-breaker: prefer longer title on equal score
        prev_title_len = len(best[2][0]) if best[2] else 0
        if final_score > best[1] or (final_score == best[1] and len(title) > prev_title_len):
            best = (iid, final_score, (title, year))

    logger.debug("OMDb: best candidate %r score=%.3f", best[2], best[1])

    # If high-enough, fetch details
    if best[0] and best[1] >= threshold:
        imdb_id = best[0]
        if "|" in imdb_id and not imdb_id.startswith("tt"):
            meta = uniq[imdb_id]
            return meta.get("Title"), meta.get("Year"), None, best[1]
        details = _safe_url(_get_omdb_by_id, imdb_id, api_key)
        if details.get("Response") == "True":
            return details.get("Title"), details.get("Year"), details.get("imdbID"), best[1]
        else:
            meta = uniq.get(imdb_id)
            return meta.get("Title"), meta.get("Year"), meta.get("imdbID"), best[1]

    # If below threshold but still a plausible suggestion, return it with its score so caller can prompt the user.
    if best[0] and best[1] >= SUGGEST_THRESHOLD:
        logger.debug("OMDb: returning low-confidence suggestion %r score=%.3f", best[2], best[1])
        imdb_id = best[0]
        meta = uniq.get(imdb_id)
        # try details if possible
        if imdb_id.startswith("tt"):
            details = _safe_url(_get_omdb_by_id, imdb_id, api_key)
            if details.get("Response") == "True":
                return details.get("Title"), details.get("Year"), details.get("imdbID"), best[1]
        return meta.get("Title"), meta.get("Year"), meta.get("imdbID"), best[1]

    logger.debug("OMDb: no candidate passed any threshold for %r", query)
    return None, None, None, 0.0

def _safe_url(json_fn, *args, retries: int = 2, backoff: float = 0.25):
    """
    Call a JSON-returning helper with retries and exponential backoff.
    Returns the function's result on success or an empty dict on repeated failure.
    """
    for attempt in range(retries + 1):
        try:
            return json_fn(*args)
        except Exception as exc:
            logger.debug("OMDb request failed (attempt %d/%d): %s", attempt + 1, retries + 1, exc)
            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
            else:
                return {}