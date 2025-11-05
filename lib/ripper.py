import logging
import time
from typing import Tuple, Optional

from . import naming, omdb_client, fs_utils

logger = logging.getLogger(__name__)

def _drive_letter_probe(drive_letter: str, api_key: str, interactive: bool) -> Tuple[Optional[str], Optional[str], float]:
    """
    Try the raw drive-letter/label token with OMDb (raw and underscore->space variants).
    Returns (title, year, score) or (None, None, 0.0).
    """
    if not api_key or not drive_letter:
        return None, None, 0.0

    try:
        logger.debug("OMDb: trying direct lookup for drive-letter token: %r", drive_letter)
        t, y, i, s = omdb_client.resolve_title_via_omdb(drive_letter, api_key, interactive=interactive)
        if t:
            return t, y, s or 1.0
        norm = drive_letter.replace("_", " ").strip()
        if norm and norm != drive_letter:
            logger.debug("OMDb: trying normalized drive-letter token: %r", norm)
            t2, y2, i2, s2 = omdb_client.resolve_title_via_omdb(norm, api_key, interactive=interactive)
            if t2:
                return t2, y2, s2 or 1.0
    except Exception:
        logger.exception("drive-letter OMDb probe failed for %r", drive_letter)
    return None, None, 0.0

def rip_longest_titles(drive: dict,
                       omdb_api_key: Optional[str],
                       omdb_interactive: bool,
                       wait_seconds: int) -> Tuple[int, Optional[str]]:
    """
    Encapsulate the previous long rip/resolve flow for a detected drive.

    Returns (rip_count_estimate, chosen_folder_name_or_None).
    This function mirrors the behavior previously embedded in movie_librarian.py:
      - build disc candidates (CINFO -> drive letter -> drive label)
      - try OMDb probes (drive-letter-first)
      - score and possibly prompt user (interactive)
      - return the final folder name to use (or None)
    """
    # minimal defensive checks
    if not isinstance(drive, dict):
        logger.debug("rip_longest_titles: invalid drive object %r", drive)
        return 0, None

    drive_index = drive.get("index")
    raw_label = (drive.get("label") or "").strip()
    drive_letter = (drive.get("letter") or "").strip()

    # read makemkv run_info if available in drive dict (some code paths put raw run_info there)
    raw_info = drive.get("run_info", "")  # fallback; caller may populate
    logger.debug("rip_longest_titles: drive_index=%s drive_letter=%r raw_label=%r", drive_index, drive_letter, raw_label)

    # Candidate selection: prefer CINFO-extracted title, then drive letter, then drive label
    cinfo_candidate = naming.pick_cinfo_title(raw_info) or ""
    if drive_letter and not naming.is_noisy_title(drive_letter):
        disc_candidate = drive_letter
        used_candidate_source = "drive_letter"
    elif cinfo_candidate:
        disc_candidate = cinfo_candidate
        used_candidate_source = "cinfo"
    elif raw_label and not naming.is_noisy_title(raw_label):
        disc_candidate = raw_label
        used_candidate_source = "drive_label"
    else:
        disc_candidate = ""
        used_candidate_source = "none"
    logger.debug("disc_candidate=%r (source=%s)", disc_candidate, used_candidate_source)

    suggested_omdb_title = None
    suggested_omdb_year = None
    suggested_omdb_score = 0.0

    # Try drive-letter probe first (ensure OMDb sees raw underscored token)
    if omdb_api_key and drive_letter:
        t, y, s = _drive_letter_probe(drive_letter, omdb_api_key, omdb_interactive)
        if t:
            suggested_omdb_title, suggested_omdb_year, suggested_omdb_score = t, y or "", s or 1.0
            logger.debug("OMDb: found match for drive-letter %r -> %r (%r) score=%r", drive_letter, suggested_omdb_title, suggested_omdb_year, suggested_omdb_score)

    # If no drive-letter OMDb suggestion, try disc_candidate (CINFO/label) via OMDb
    if not suggested_omdb_title and disc_candidate and omdb_api_key:
        logger.debug("attempting OMDb resolve for disc candidate: %r (threshold=0.60)", disc_candidate)
        t, y, i, s = omdb_client.resolve_title_via_omdb(disc_candidate, omdb_api_key, interactive=omdb_interactive, threshold=0.60)
        if t:
            suggested_omdb_title, suggested_omdb_year, suggested_omdb_score = t, y or "", s or 1.0
            logger.debug("OMDb suggestion: %r %r (score=%r)", suggested_omdb_title, suggested_omdb_year, suggested_omdb_score)

    # determine final folder name source (preserve previous heuristics)
    folder_name_src = ""
    if suggested_omdb_title:
        # prefer OMDb suggestion when high confidence
        if suggested_omdb_score >= 0.60:
            folder_name_src = suggested_omdb_title
        else:
            # fall back to disc_candidate if OMDb is weak
            folder_name_src = disc_candidate or suggested_omdb_title
    else:
        folder_name_src = disc_candidate or raw_label or None

    # Return a small tuple; the caller (main loop) handles user prompting / rips
    # rip_count estimate left as 0 for caller to calculate (keeps this function testable)
    return 0, folder_name_src