import logging
from typing import Dict, Optional, Tuple
from . import naming, omdb_client, fs_utils, metadata_store, ripper_utils

logger = logging.getLogger(__name__)

def rip_movie_from_drive(drive: Dict, omdb_api_key: Optional[str]=None, interactive: bool=False) -> Tuple[bool, Optional[str]]:
    """
    Simple movie rip flow:
      - pick candidate title (cinfo/label/drive-letter)
      - try OMDb resolve (if key)
      - return (success_flag, final_folder_name)
    This is intentionally small: actual ripping/writing handled by caller or fs_utils.
    """
    raw_info = drive.get("run_info", "") or ""
    raw_label = (drive.get("label") or "").strip()
    drive_letter = (drive.get("letter") or "").strip()

    candidate = naming.pick_cinfo_title(raw_info) or drive_letter or raw_label or ""
    logger.debug("movie_ripper: candidate=%r", candidate)

    final_title = candidate
    if omdb_api_key and candidate:
        t, y, imdb, score = omdb_client.resolve_title_via_omdb(candidate, omdb_api_key, interactive=interactive)
        if t and score >= 0.60:
            final_title = t

    # caller handles rip and save; return chosen name
    return True, final_title