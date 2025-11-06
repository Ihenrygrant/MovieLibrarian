import json
import os
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

MANIFEST_DIR = Path("manifests")


def ensure_manifest_dir() -> Path:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    return MANIFEST_DIR


def save_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    """
    Write JSON to a tmp file and atomically replace the destination.
    """
    ensure_manifest_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    # ensure parent exists
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def list_manifest_ids() -> Iterable[str]:
    ensure_manifest_dir()
    return [p.stem for p in MANIFEST_DIR.glob("*.json")]


def make_set_id(title: str, season: Optional[int] = None) -> str:
    """
    Create a reasonably unique set id from title, optional season, timestamp and short uuid.
    """
    n = normalize_title(title)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    if season is not None:
        return f"{n}-s{int(season):02d}-{ts}-{uuid.uuid4().hex[:6]}"
    return f"{n}-{ts}-{uuid.uuid4().hex[:6]}"


def normalize_title(s: str) -> str:
    """
    Normalize a title into a filesystem/manifest friendly id: lowercase, alnum + dashes.
    """
    s = (s or "").strip()
    # remove punctuation except word/space/hyphen/underscore
    s = re.sub(r"[^\w\s-]", "", s, flags=re.U)
    s = re.sub(r"[\s_-]+", "-", s).strip("-").lower()
    return s or "untitled"