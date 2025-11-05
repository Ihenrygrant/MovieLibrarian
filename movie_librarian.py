import os
import re
import subprocess
import time
import threading
import itertools
import sys
import winsound
import hashlib
import json
import urllib.request
import urllib.parse
from lib import makemkv, naming, omdb_client, fs_utils
from pathlib import Path

# try to use tomllib (py3.11+) or toml package; fall back to json if neither available
try:
    import tomllib as _toml_reader  # type: ignore
    _have_toml_writer = False
except Exception:
    _toml_reader = None
try:
    import toml  # type: ignore
    _have_toml_writer = True
except Exception:
    if _toml_reader is None:
        _toml_reader = None
    _have_toml_writer = False

# keyring is optional (used to store secrets like OMDB_API_KEY)
try:
    import keyring  # type: ignore
except Exception:
    keyring = None

def default_config():
    return {
        "MAKEMKV_PATH": r"C:\Program Files (x86)\MakeMKV\makemkvcon.exe",
        "SAVE_DIR": r"E:\Video",
        "WAIT_SECONDS": 5,
        "MIN_LENGTH_SECONDS": 600,
        "OMDB_API_KEY": "",
        "OMDB_INTERACTIVE": True,
        "LOG_FILE": "movie_librarian.log",
    }

def get_config_dir() -> Path:
    # allow override via env var
    cfg_env = os.getenv("MOVIE_LIBRARIAN_CONFIG_DIR")
    if cfg_env:
        return Path(cfg_env)
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "MovieLibrarian"
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "MovieLibrarian"
    return Path.home() / ".config" / "MovieLibrarian"

def _parse_legacy_env_file(p: Path) -> dict:
    """Parse simple KEY=VAL legacy config (config.txt / .env style)."""
    out = {}
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out

def _read_toml(path: Path) -> dict:
    try:
        if _toml_reader:
            return _toml_reader.loads(path.read_bytes().decode("utf-8"))
        elif _have_toml_writer:
            return toml.load(path)
    except Exception:
        pass
    return {}

def _write_toml(path: Path, data: dict):
    try:
        if _have_toml_writer:
            path.write_text(toml.dumps(data), encoding="utf-8")
        else:
            # fallback to JSON if toml writer not available
            path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    except Exception:
        pass

def load_config(path: str | None = None) -> dict:
    cfg = default_config()
    cfg_dir = get_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    user_path = Path(path) if path else cfg_dir / "config.toml"

    # migrate legacy project-local files (project root)
    project_root = Path(__file__).parent
    legacy_toml = project_root / "config.toml"
    legacy_json = project_root / "config.json"
    legacy_txt = project_root / "config.txt"

    # migrate config.toml first
    if legacy_toml.exists() and not user_path.exists():
        try:
            user_path.write_bytes(legacy_toml.read_bytes())
        except Exception:
            pass

    # migrate legacy json
    if legacy_json.exists() and not user_path.exists():
        try:
            user_path.write_text(legacy_json.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass

    # migrate simple KEY=VAL config.txt into toml
    if legacy_txt.exists() and not user_path.exists():
        parsed = _parse_legacy_env_file(legacy_txt)
        if parsed:
            # map common legacy keys into expected config keys
            mapping = {}
            if "OMDB_API_KEY" in parsed:
                mapping["OMDB_API_KEY"] = parsed["OMDB_API_KEY"]
            # write the migrated config
            try:
                _write_toml(user_path, {**default_config(), **mapping})
            except Exception:
                pass

    # read user config (toml preferred)
    if user_path.exists():
        data = _read_toml(user_path)
        if isinstance(data, dict):
            cfg.update(data)

    # write template if missing
    if not user_path.exists():
        try:
            _write_toml(user_path, cfg)
        except Exception:
            pass

    # environment overrides
    env_map = {
        "MAKEMKV_PATH": ["MOVIE_LIBRARIAN_MAKEMKV_PATH"],
        "SAVE_DIR": ["MOVIE_LIBRARIAN_SAVE_DIR"],
        "WAIT_SECONDS": ["MOVIE_LIBRARIAN_WAIT_SECONDS"],
        "MIN_LENGTH_SECONDS": ["MOVIE_LIBRARIAN_MIN_LENGTH_SECONDS"],
        "OMDB_API_KEY": ["MOVIE_LIBRARIAN_OMDB_API_KEY", "OMDB_API_KEY"],
        "OMDB_INTERACTIVE": ["MOVIE_LIBRARIAN_OMDB_INTERACTIVE"],
        "LOG_FILE": ["MOVIE_LIBRARIAN_LOG_FILE"],
    }
    for key, vars_ in env_map.items():
        for v in vars_:
            val = os.getenv(v)
            if val is not None:
                if isinstance(cfg.get(key), bool):
                    cfg[key] = val.lower() in ("1", "true", "yes", "on")
                elif isinstance(cfg.get(key), int):
                    try:
                        cfg[key] = int(val)
                    except Exception:
                        pass
                else:
                    cfg[key] = val
                break

    # keyring override for OMDB_API_KEY (preferred for production secrets)
    if keyring:
        try:
            kr = keyring.get_password("MovieLibrarian", "omdb_api_key")
            if kr:
                cfg["OMDB_API_KEY"] = kr
        except Exception:
            pass

    return cfg

# load once at module import
CONFIG = load_config()

# re-export config values to module-level names used in the code
MAKEMKV_PATH = CONFIG.get("MAKEMKV_PATH")
SAVE_DIR = CONFIG.get("SAVE_DIR")
WAIT_SECONDS = int(CONFIG.get("WAIT_SECONDS", 5))
MIN_LENGTH_SECONDS = int(CONFIG.get("MIN_LENGTH_SECONDS", 600))
OMDB_API_KEY = CONFIG.get("OMDB_API_KEY", "") or ""
OMDB_INTERACTIVE = bool(CONFIG.get("OMDB_INTERACTIVE", True))
LOG_FILE = os.path.join(os.path.dirname(__file__), CONFIG.get("LOG_FILE", "movie_librarian.log"))

# set up logging using configured log file
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("movie_librarian")

# re-export or local aliases for convenience
get_makemkv_drives = makemkv.get_makemkv_drives
disc_signature = makemkv.disc_signature
get_titles_info = makemkv.get_titles_info
safe_filename = naming.safe_filename
clean_title_string = naming.clean_title_string
is_hardware_label = naming.is_hardware_label

def choose_title(first, raw_label, titles, interactive=OMDB_INTERACTIVE):
    """
    Wrapper that accepts either:
      - first = makemkv drive index (int) -> will call makemkv.run_info(index)
      - first = raw_info_text (str) -> will use it directly
    Forwards the interactive flag to naming.choose_title.
    """
    try:
        # treat integers (or numeric strings) as drive indices
        if isinstance(first, int):
            raw_info_text = makemkv.run_info(first)
        else:
            raw_info_text = first or ""
    except Exception:
        raw_info_text = first or ""
    return naming.choose_title(raw_info_text, raw_label, titles, interactive=interactive)
 
lookup_omdb_year = lambda title: omdb_client.lookup_omdb_year(title, OMDB_API_KEY, interactive=OMDB_INTERACTIVE)
next_available_filename = fs_utils.next_available_filename

# === Utility functions ===

def play_chime(frequency=880, duration=500):
    """Simple beep notification."""
    try:
        winsound.Beep(frequency, duration)
    except Exception:
        pass


# small wrapper: per-disc rip/resolve logic moved to lib.ripper.rip_longest_titles
from lib.ripper import rip_longest_titles

# === Main program ===

def main():
    logger.info("=== Starting movie librarian ===")
    print("Welcome to the Movie Librarian!")

    # OMDb API key is loaded at module import from config (see top-level load_config).
    if OMDB_API_KEY:
        logger.info("OMDb API key configured (will use OMDb lookups).")
    else:
        logger.info("No OMDb API key configured; OMDb lookups disabled.")

    # don't exit here — the main loop below will poll and retry when no drives are found
    logger.debug("Entering main polling loop (will retry when no drives found).")

    # Immediate one-shot scan so discs already in tray are picked up right away.
    try:
        initial_drives = get_makemkv_drives()
        logger.debug("initial get_makemkv_drives() -> %s", initial_drives)
        # If we found drives, handle them once immediately before entering the polling loop.
        if initial_drives:
            for d in initial_drives:
                try:
                    logger.debug("Processing drive from initial scan: %s", d)
                    rip_longest_titles(d)
                except Exception:
                    logger.exception("error processing initial drive %s", d)
    except Exception:
        logger.exception("initial get_makemkv_drives() probe failed")
    # keep state between iterations
    last_seen_labels = {}
    last_seen_hashes = {}

    try:
        while True:
            # refresh drives each loop so disc swaps are detected
            drives = get_makemkv_drives()
            logger.debug("found drives: %s", drives)

            if not drives:
                logger.warning("⚠️ No valid MakeMKV drives found.")
                # sleep briefly and try again (non-blocking continuous loop)
                time.sleep(5)
                continue

            for d in drives:
                try:
                    # ...existing per-drive handling ...
                    rip_count, folder_name = rip_longest_titles(d)
                    # ...any post-rip bookkeeping...
                except Exception:
                    logger.exception("error processing drive %s", d)
                    # continue to next drive rather than exit
                    continue

            # main loop delay between scans
            time.sleep(WAIT_SECONDS)

    except KeyboardInterrupt:
        logger.info("Interrupted by user; exiting.")
    except Exception:
        logger.exception("unexpected error in main loop")

if __name__ == "__main__":
    import argparse
    import getpass

    parser = argparse.ArgumentParser(prog="movie_librarian", description="Movie Librarian utility")
    parser.add_argument("--set-omdb-key", nargs="?", const=True,
                        help="Store OMDb API key. Use no value to be prompted, or pass the key directly.")
    parser.add_argument("--show-config", action="store_true", help="Print resolved configuration and exit.")
    args = parser.parse_args()

    if args.show_config:
        # print effective config (do not print raw key from keyring)
        cfg_copy = dict(CONFIG)
        if keyring:
            try:
                kr = keyring.get_password("MovieLibrarian", "omdb_api_key")
                cfg_copy["OMDB_API_KEY"] = "<stored in keyring>" if kr else cfg_copy.get("OMDB_API_KEY", "")
            except Exception:
                pass
        else:
            cfg_copy["OMDB_API_KEY"] = "<from config file>" if cfg_copy.get("OMDB_API_KEY") else ""
        print(json.dumps(cfg_copy, indent=2))
        sys.exit(0)

    if args.set_omdb_key is not None:
        if args.set_omdb_key is True:
            key_val = getpass.getpass("Enter OMDb API key (input hidden): ").strip()
        else:
            key_val = str(args.set_omdb_key).strip()

        if not key_val:
            print("No key provided, aborting.")
            sys.exit(1)

        # prefer keyring
        if keyring:
            try:
                keyring.set_password("MovieLibrarian", "omdb_api_key", key_val)
                print("OMDb API key saved to OS keyring (MovieLibrarian / omdb_api_key).")
                sys.exit(0)
            except Exception as e:
                print(f"Warning: keyring save failed: {e} — falling back to config file.")

        # fallback: write to user's config.toml
        cfg_path = get_config_dir() / "config.toml"
        current = _read_toml(cfg_path) or default_config()
        current["OMDB_API_KEY"] = key_val
        _write_toml(cfg_path, current)
        print(f"OMDb API key written to {cfg_path}")
        sys.exit(0)

    # no CLI action — run main loop
    main()
