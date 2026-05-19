import spotipy
from spotipy.oauth2 import SpotifyOAuth

from . import config


def get_client() -> spotipy.Spotify:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    auth = SpotifyOAuth(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=config.SPOTIFY_REDIRECT_URI,
        scope=config.SPOTIFY_SCOPES,
        cache_path=str(config.TOKEN_CACHE),
    )
    return spotipy.Spotify(auth_manager=auth)


def find_playlist_id(sp: spotipy.Spotify, name: str) -> str | None:
    """Find a playlist by exact name among the current user's playlists."""
    offset = 0
    while True:
        batch = sp.current_user_playlists(limit=50, offset=offset)
        for pl in batch["items"]:
            if pl["name"] == name:
                return pl["id"]
        if batch["next"] is None:
            return None
        offset += 50


def get_playlist_track_ids(sp: spotipy.Spotify, playlist_id: str) -> set[str]:
    """Return all track IDs currently in a playlist."""
    ids: set[str] = set()
    offset = 0
    while True:
        batch = sp.playlist_tracks(playlist_id, limit=100, offset=offset)
        for item in batch["items"]:
            track = item.get("track")
            if track and track.get("id"):
                ids.add(track["id"])
        if batch["next"] is None:
            return ids
        offset += 100
