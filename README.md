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
