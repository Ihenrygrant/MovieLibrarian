import json
from pathlib import Path
from typing import Dict
from . import ripper_utils

MANIFEST_DIR = ripper_utils.MANIFEST_DIR


def save_manifest(set_id: str, data: Dict):
    """
    Persist manifest data for a given set_id atomically.
    """
    ripper_utils.ensure_manifest_dir()
    dst = MANIFEST_DIR / (set_id + ".json")
    ripper_utils.save_json_atomic(dst, data)


def load_manifest(set_id: str) -> Dict:
    """
    Load a manifest; raises FileNotFoundError if missing.
    """
    dst = MANIFEST_DIR / (set_id + ".json")
    return ripper_utils.load_json(dst)


def list_manifests():
    return list(ripper_utils.list_manifest_ids())