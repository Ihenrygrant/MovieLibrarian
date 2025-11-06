import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    script = Path(__file__).with_name("movie_librarian.py")
    cmd = [sys.executable, str(script), "--mode", "tv"] + sys.argv[1:]
    subprocess.run(cmd)