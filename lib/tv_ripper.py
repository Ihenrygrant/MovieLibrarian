import logging
from typing import Dict, Optional, Tuple
from . import naming, omdb_client, fs_utils, metadata_store, ripper_utils

logger = logging.getLogger(__name__)

def find_or_create_set(drive: Dict, tmdb_client=None, expected_discs: Optional[int]=None) -> str:
    """
    Determine or create a manifest set id for a TV multi-disc release.
    Uses naming.pick_cinfo_title / drive label to infer show title (season optional).
    Returns set_id (string).
    """
    raw_info = drive.get("run_info", "") or ""
    label = (drive.get("label") or "").strip()
    drive_letter = (drive.get("letter") or "").strip()

    inferred = naming.pick_cinfo_title(raw_info) or label or drive_letter or "untitled"
    show_title = inferred
    season = None
    # optional: try to parse "S01" or "Season 1" from label/raw_info (omitted, implement as needed)

    # attempt to find existing manifest with normalized title+season
    normalized = ripper_utils.normalize_title(show_title)
    for mid in metadata_store.list_manifests():
        if mid.startswith(normalized):
            logger.debug("found existing manifest %s for %s", mid, normalized)
            return mid

    # no existing manifest => create new
    set_id = ripper_utils.make_set_id(show_title, season)
    manifest = {
        "set_id": set_id,
        "show_title": show_title,
        "season": season,
        "created_at": None,
        "discs": {},
        "expected_discs": expected_discs or None
    }
    metadata_store.save_manifest(set_id, manifest)
    logger.debug("created manifest %s", set_id)
    return set_id

def rip_disc_into_set(set_id: str, drive: Dict, ripper_fn=None) -> Tuple[bool, dict]:
    """
    Rip a disc and update manifest. ripper_fn is a callable that actually performs the rip
    and returns a list of output filenames and episode mapping.
    Returns (success, manifest_fragment) for the caller to persist/act on.
    """
    manifest = metadata_store.load_manifest(set_id)
    disc_hash = drive.get("signature") or drive.get("index")
    disc_id = f"disc-{disc_hash}"
    if disc_id in manifest["discs"] and manifest["discs"][disc_id].get("ripped"):
        logger.debug("disc %s already ripped for set %s", disc_id, set_id)
        return True, manifest["discs"][disc_id]

    # delegate actual ripping if provided (keeps this function testable)
    ripped_files = []
    episode_map = []
    if ripper_fn:
        ripped_files, episode_map = ripper_fn(drive)

    manifest["discs"][disc_id] = {
        "disc_index": drive.get("index"),
        "label": drive.get("label"),
        "makemkv_info_hash": drive.get("info_hash"),
        "ripped": bool(ripped_files),
        "ripped_files": ripped_files,
        "episode_map": episode_map
    }
    metadata_store.save_manifest(set_id, manifest)
    return True, manifest["discs"][disc_id]