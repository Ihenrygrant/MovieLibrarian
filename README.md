# Movie Librarian

Purpose
- Automate ripping and cataloging of discs using MakeMKV and OMDb.
- Detect discs inserted in optical drives, extract candidate titles from MakeMKV output, consult OMDb for metadata, and save ripped content into a structured video folder.

MovieLibrarian is a automated tooling for the handling of ripping discs from optical drives and catalogue the files. In order for Plex to detect the exact title in the library, it will require the files to be named and dated properly. Due to the ambiguous nature of how movie and tv show discs are handled by companies, there is not a single or reliable heuristic to grab the title, year, or other various metadata from the disc itselfs. The tool will attempt a fuzzy search against the OMDB API against any potental title candidates to gain confidence in a match. Anything with a low enough confidence will prompt the user for proper naming.

What it does
- Polls MakeMKV for attached drives and disc metadata.
- Extracts candidate titles from MakeMKV DRV/CINFO output and drive labels.
- Queries OMDb (exact and fuzzy) to resolve title/year/imdbID.
- Prompts the user for confirmation when confidence is low (interactive mode).
- Rips selected titles with MakeMKV and stores files in a configurable output folder.
- Includes utilities for filename cleanup and filesystem operations.

Planned Features
- Support TV show ripping
- Handle multiple optical drives
- Add a GUI for a better user experience
- Add support for trimming saved ripped files

TODOs
- Add TV show ripping support
- Add multi-language support (needed for TV show support (KDRAMAs))
- Add support for multiple disc reads (needed for TV show support)
- Add disambiguation logic and prompts for film titles matching multiple years (i.e. The Thing (1951), The Thing (1982), and The Thing (2011))
- Create a thread per optical drive
- Denylist certain strings such as optical drive hardware names (per user systems)


Requirements

System
- Windows (tested); MakeMKV (makemkvcon) must be installed and accessible.
- Administrative privileges may be required for makemkvcon in some environments.

Python
- Python 3.11+ recommended (tomllib used when available).
- A virtual environment is strongly recommended.

Python packages
- requests
- pytest (for running tests)
- toml (only required on Python < 3.11)
- rapidfuzz (optional, for improved fuzzy matching; falls back to difflib)
- (development) flake8, vulture (optional static analysis)

OMDb
- OMDb API key (get one at https://www.omdbapi.com/). Place in configuration or environment variable used by the app.

MakeMKV
- makemkvcon executable path must be configured or discoverable on PATH.

Quickstart (Windows PowerShell)
1. Create and activate a venv:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

2. Install dependencies:
   pip install requests pytest rapidfuzz toml

3. Configure:
   - Ensure `makemkvcon.exe` is installed and reachable.
   - Set your OMDb API key (env or config file).

4. Run the app:
   py movie_librarian.py

5. Run tests:
   py -m pytest -q

Configuration notes
- The script looks for MakeMKV output and drive labels to build candidate titles.
- OMDb lookups are used to confirm/normalize titles; the workflow prefers exact/underscored tokens when present.
- If you change behavior (e.g., OMDb-first vs local extraction), update tests under `tests/` to reflect the new contract.

Development / Maintenance
- Use `vulture` to locate dead code before removing functions.
- Update unit tests when refactoring title-extraction behavior (mock `lib.omdb_client.resolve_title_via_omdb` for integration tests).
- Keep `makemkvcon` path and OMDb key documented for each deployment.

License & Contribution
- Add your project's license and contribution guidelines as appropriate.

## Configuration / configurable values

The app reads configuration from config.toml (or env vars); defaults are provided by the program.

- MAKEMKV_PATH
  - Path to makemkvcon executable (default: C:\Program Files (x86)\MakeMKV\makemkvcon.exe)
  - Env override: MOVIE_LIBRARIAN_MAKEMKV_PATH

- SAVE_DIR
  - Base folder for movie rips (default: E:\Video)
  - Env override: MOVIE_LIBRARIAN_SAVE_DIR

- TV_SAVE_DIR
  - Base folder for TV rips (default: E:\Video\TV)
  - If not set, defaults to SAVE_DIR\TV

- WAIT_SECONDS
  - Poll loop delay between scans (seconds). Default: 5
  - Env override: MOVIE_LIBRARIAN_WAIT_SECONDS

- MIN_LENGTH_SECONDS
  - Minimum title length to consider a title (seconds). Default: 600

- OMDB_API_KEY
  - OMDb API key (string). Prefer storing with keyring in production.
  - Env override: MOVIE_LIBRARIAN_OMDB_API_KEY or OMDB_API_KEY

- OMDB_INTERACTIVE
  - Whether to prompt user for low-confidence suggestions (true/false). Default: true
  - Env override: MOVIE_LIBRARIAN_OMDB_INTERACTIVE

- LOG_FILE
  - Path/name of the log file (default: movie_librarian.log in code dir)

CLI flags:
- --mode {movie,tv}  — run in movie or tv mode (default: movie)
- --non-interactive   — disable user prompts

Config location:
- Default per-user config directory (Windows => %APPDATA%\MovieLibrarian\config.toml)
- Override with MOVIE_LIBRARIAN_CONFIG_DIR

## TV / Multi-disc notes

- TV rips use TV_SAVE_DIR by default; manifests are stored in `manifests/`.
- Multi-disc sets are grouped into a persistent manifest so you can stop/restart between discs.
- Episode-to-file mapping requires a metadata source (TMDb/TVDB) for per-episode data; OMDb is used as a fallback for simple titles.
