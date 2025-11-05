import subprocess
import hashlib
import re
from typing import List, Dict
from pathlib import Path

from lib import naming

MAKEMKV_PATH = r"C:\Program Files (x86)\MakeMKV\makemkvcon.exe"

def run_info(drive_index):
    """Return raw makemkv 'info' output for disc:{drive_index}."""
    try:
        r = subprocess.run(
            [MAKEMKV_PATH, "-r", "info", f"disc:{drive_index}"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        return r.stdout
    except Exception:
        return ""

def get_makemkv_drives():
    """Parse MakeMKV drive list from makemkv info disc:9999."""
    try:
        r = subprocess.run(
            [MAKEMKV_PATH, "-r", "info", "disc:9999"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
    except Exception:
        return []
    drives = []
    for line in r.stdout.splitlines():
        if not line.startswith("DRV:"):
            continue
        parts = line.split(",")
        try:
            index = int(parts[0].split(":")[1])
            flags = int(parts[1])
            if flags != 2:
                continue
            label = parts[4].strip('"')
            letter = parts[5].strip('"').rstrip(":")
            drives.append({"index": index, "label": label, "letter": letter})
        except Exception:
            continue
    return drives

def disc_signature(drive_index):
    """Hash TINFO lines to detect disc changes."""
    out = run_info(drive_index)
    lines = [l for l in out.splitlines() if l.startswith("TINFO")]
    return hashlib.sha1("".join(lines).encode("utf-8")).hexdigest() if lines else ""

def get_titles_info(drive_index: int, min_length_seconds: int = 600) -> List[Dict]:
    """Return list of parsed titles (id, title, duration, size, seconds).
    Each title dict includes:
      - id
      - raw (raw TINFO map)
      - title (best cleaned title from TINFO fields, may be empty)
      - duration (string)
      - seconds (int)
      - size (string)
    """
    out = run_info(drive_index)
    current = {}
    for line in out.splitlines():
        if not line.startswith("TINFO"):
            continue
        parts = line.split(",", 3)
        if len(parts) < 4:
            continue
        try:
            tid = int(parts[0].split(":", 1)[1])
            field = int(parts[1])
            val = parts[3].strip().strip('"')
        except Exception:
            continue
        current.setdefault(tid, {})[field] = val

    titles = []
    dur_re = re.compile(r'(?:(\d+):)?(\d{1,2}):(\d{2})')
    for tid, data in current.items():
        duration_str = data.get(9) or data.get(4) or data.get(3) or ""
        if not duration_str:
            for v in data.values():
                m = dur_re.search(v)
                if m:
                    duration_str = m.group(0)
                    break
        if not duration_str:
            continue
        m = dur_re.search(duration_str)
        if not m:
            continue
        try:
            h = int(m.group(1) or 0)
            mmin = int(m.group(2))
            s = int(m.group(3))
            seconds = h * 3600 + mmin * 60 + s
        except Exception:
            continue
        if seconds >= min_length_seconds:
            # pick best cleaned-per-title name from TINFO using naming helper
            human_title = naming.pick_title_name_from_tinfo(data)
            titles.append({
                "id": tid,
                "raw": data,
                "title": human_title,   # IMPORTANT: human-friendly per-title name (may be empty)
                "duration": duration_str,
                "seconds": seconds,
                "size": data.get(11, data.get(10, "")),
            })
    return sorted(titles, key=lambda x: x["seconds"], reverse=True)