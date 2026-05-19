import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _find_dropbox_root() -> Path:
    candidates = [
        Path(r"C:\Users\Carillon\Wired Masters Dropbox\Sam Wills"),
        Path(r"F:\Wired Masters Dropbox\Sam Wills"),
        Path("/Users/samuelwills/Wired Masters Dropbox/Sam Wills"),
    ]
    for c in candidates:
        if c.exists():
            return c
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "Sam Wills" and "Wired Masters Dropbox" in str(parent):
            return parent
    print("ERROR: Could not find Wired Masters Dropbox root", file=sys.stderr)
    sys.exit(1)


DROPBOX_ROOT = _find_dropbox_root()

_MCP_ENV = (
    DROPBOX_ROOT / "Claude Code Brain" / "mcp-servers"
    / "mcp-claude-spotify" / ".env"
)
_LOCAL_ENV = Path(__file__).resolve().parents[2] / ".env"

if _LOCAL_ENV.exists():
    load_dotenv(_LOCAL_ENV)
elif _MCP_ENV.exists():
    load_dotenv(_MCP_ENV)

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_SCOPES = (
    "playlist-modify-public "
    "playlist-modify-private "
    "playlist-read-private"
)

SOURCE_DIRS = {
    "mastered": DROPBOX_ROOT / "1. Stereo Masters",
    "mixed_finished": DROPBOX_ROOT / "2.1. Finished Stem Mixes",
}

PLAYLIST_NAMES = {
    "mastered": "Mastered By Sam Wills",
    "mixed_mastered": "Mixed and Mastered by Sam Wills",
    "mastered_top10": "Mastered by Sam Wills Top 10",
    "mixed_mastered_top10": "Mixed and Mastered by Sam Wills Top 10",
}

PLAYLIST_SOURCES = {
    "mastered": ["mastered", "mixed_finished"],
    "mixed_mastered": ["mixed_finished"],
    "mastered_top10": ["mastered", "mixed_finished"],
    "mixed_mastered_top10": ["mixed_finished"],
}

STATE_DIR = Path.home() / ".spotify-playlist-sync"
STATE_DB = STATE_DIR / "state.db"
TOKEN_CACHE = STATE_DIR / ".cache"
PENDING_REVIEW = STATE_DIR / "pending_review.json"

TOP_10_WINDOW_DAYS = 365
NEW_TRACK_WINDOW_DAYS = 60
SEARCH_DELAY = 0.2

MAX_RELEASE_AGE_DAYS = 365
MIN_FOLDER_AGE_DAYS = 30
MIN_POPULARITY = 5
