import os
from pathlib import Path

from dotenv import load_dotenv

_MCP_ENV = Path(
    r"F:\Wired Masters Dropbox\Sam Wills"
    r"\Claude Code Brain\mcp-servers\mcp-claude-spotify\.env"
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

DROPBOX_ROOT = Path(r"F:\Wired Masters Dropbox\Sam Wills")

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
