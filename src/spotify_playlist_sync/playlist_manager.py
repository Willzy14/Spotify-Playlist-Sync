from datetime import datetime, timezone

import spotipy

from . import config
from . import state
from .spotify_client import find_playlist_id, get_playlist_track_ids


def resolve_playlists(sp: spotipy.Spotify) -> dict[str, str]:
    """Look up all four playlist IDs by name. Returns {key: playlist_id}."""
    resolved = {}
    for key, name in config.PLAYLIST_NAMES.items():
        pid = find_playlist_id(sp, name)
        if pid:
            resolved[key] = pid
            print(f"  Found: {name} ({pid})")
        else:
            print(f"  [WARN] Playlist not found: {name}")
    return resolved


def add_tracks_to_top(
    sp: spotipy.Spotify,
    playlist_id: str,
    track_ids: list[str],
) -> int:
    """Insert tracks at position 0 (top). Returns count added."""
    if not track_ids:
        return 0
    existing = get_playlist_track_ids(sp, playlist_id)
    new_ids = [tid for tid in track_ids if tid not in existing]
    if not new_ids:
        return 0
    for i in range(0, len(new_ids), 100):
        batch = new_ids[i : i + 100]
        sp.playlist_add_items(playlist_id, batch, position=0)
    return len(new_ids)


def replace_playlist(
    sp: spotipy.Spotify,
    playlist_id: str,
    track_ids: list[str],
) -> None:
    """Replace entire playlist contents with the given track IDs."""
    sp.playlist_replace_items(playlist_id, [])
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i : i + 100]
        sp.playlist_add_items(playlist_id, batch)


def get_popularity(sp: spotipy.Spotify, track_ids: list[str]) -> dict[str, int]:
    """Fetch popularity scores for a list of track IDs."""
    pop: dict[str, int] = {}
    for i in range(0, len(track_ids), 50):
        batch = track_ids[i : i + 50]
        tracks = sp.tracks(batch)
        for t in tracks["tracks"]:
            if t:
                pop[t["id"]] = t.get("popularity", 0)
    return pop


def sync_main_playlist(
    sp: spotipy.Spotify,
    playlist_key: str,
    playlist_id: str,
    approved_tracks: list[dict],
) -> int:
    """Add new tracks to a main playlist, most popular first."""
    source_types = config.PLAYLIST_SOURCES[playlist_key]
    relevant = [
        t for t in approved_tracks
        if t["source_type"] in source_types
    ]
    if not relevant:
        return 0

    track_ids = [t["spotify_id"] for t in relevant]
    existing = get_playlist_track_ids(sp, playlist_id)
    new_ids = [tid for tid in track_ids if tid not in existing]
    if not new_ids:
        return 0

    pop = get_popularity(sp, new_ids)
    new_ids.sort(key=lambda tid: pop.get(tid, 0), reverse=True)

    for i in range(0, len(new_ids), 100):
        batch = new_ids[i : i + 100]
        sp.playlist_add_items(playlist_id, batch, position=0)

    for tid in new_ids:
        state.record_track_added(tid, playlist_key)

    return len(new_ids)


def _resolve_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> list[str]:
    """Get all track IDs from a playlist, resolving re-linked tracks to current IDs."""
    ids: list[str] = []
    offset = 0
    while True:
        batch = sp.playlist_tracks(playlist_id, limit=100, offset=offset, market="GB")
        for item in batch["items"]:
            track = item.get("track")
            if track and track.get("id"):
                ids.append(track["id"])
        if batch["next"] is None:
            return ids
        offset += 100


def resort_playlist(
    sp: spotipy.Spotify, playlist_id: str, playlist_key: str,
) -> int:
    """Re-sort playlist in two tiers: recent (60 days) then older, both by popularity."""
    track_ids = _resolve_playlist_tracks(sp, playlist_id)
    if not track_ids:
        return 0

    pop = get_popularity(sp, track_ids)
    added_dates = state.get_track_added_dates(playlist_key)
    now = datetime.now(timezone.utc)
    cutoff_days = config.RECENT_TIER_DAYS

    recent = []
    older = []
    for tid in track_ids:
        added_str = added_dates.get(tid)
        if added_str:
            added_dt = datetime.fromisoformat(added_str)
            age_days = (now - added_dt).days
            if age_days <= cutoff_days:
                recent.append(tid)
            else:
                older.append(tid)
        else:
            older.append(tid)

    recent.sort(key=lambda tid: pop.get(tid, 0), reverse=True)
    older.sort(key=lambda tid: pop.get(tid, 0), reverse=True)

    replace_playlist(sp, playlist_id, recent + older)
    return len(track_ids)


def sync_top10_playlist(
    sp: spotipy.Spotify,
    playlist_key: str,
    playlist_id: str,
) -> int:
    """Rebuild a Top 10 playlist from tracks added in the last 12 months."""
    added = state.get_added_tracks(
        playlist_key.replace("_top10", ""),
        since_days=config.TOP_10_WINDOW_DAYS,
    )
    if not added:
        return 0

    track_ids = [a["spotify_id"] for a in added]
    pop = get_popularity(sp, track_ids)
    ranked = sorted(track_ids, key=lambda tid: pop.get(tid, 0), reverse=True)[:10]

    replace_playlist(sp, playlist_id, ranked)
    return len(ranked)
