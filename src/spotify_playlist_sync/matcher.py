import re
import time
from difflib import SequenceMatcher

import spotipy

from . import config

_ADM_RE = re.compile(r"\s+ADM'?S?\s*$", re.IGNORECASE)
_FEAT_RE = re.compile(
    r"\s*(feat\.?|ft\.?|featuring)\s+", re.IGNORECASE
)
_JOINER_RE = re.compile(r"\s*[,&x]\s*", re.IGNORECASE)


def _normalise(text: str) -> str:
    text = _ADM_RE.sub("", text)
    text = _FEAT_RE.sub(" ", text)
    text = _JOINER_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalise(a), _normalise(b)).ratio()


def search_track(
    sp: spotipy.Spotify,
    artist: str,
    track: str,
    remixer: str | None = None,
    label: str | None = None,
) -> list[dict]:
    """Search Spotify for a track and return scored matches."""
    track_clean = _ADM_RE.sub("", track).strip()
    candidates: list[dict] = []

    queries = [
        f'track:"{track_clean}" artist:"{artist}"',
        f"{artist} {track_clean}",
    ]
    if remixer:
        queries.insert(1, f'track:"{track_clean}" artist:"{remixer}"')

    seen_ids: set[str] = set()
    for q in queries:
        time.sleep(config.SEARCH_DELAY)
        try:
            results = sp.search(q=q, type="track", limit=10)
        except Exception as e:
            print(f"  [ERR] Spotify search failed: {e}")
            continue
        for item in results.get("tracks", {}).get("items", []):
            tid = item["id"]
            if tid in seen_ids:
                continue
            seen_ids.add(tid)
            sp_artists = ", ".join(a["name"] for a in item["artists"])
            sp_track = item["name"]
            score = _score_match(
                artist, track_clean, remixer, label,
                sp_artists, sp_track, item,
            )
            candidates.append({
                "spotify_id": tid,
                "spotify_name": sp_track,
                "spotify_artist": sp_artists,
                "spotify_album": item["album"]["name"],
                "popularity": item.get("popularity", 0),
                "confidence": round(score, 3),
            })
        if candidates:
            break

    if not candidates:
        for sub_track in _split_multi_track(track_clean):
            if sub_track == track_clean:
                continue
            sub_results = search_track(sp, artist, sub_track, remixer, label)
            candidates.extend(sub_results)

    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    return candidates[:5]


def _score_match(
    folder_artist: str,
    folder_track: str,
    folder_remixer: str | None,
    folder_label: str | None,
    sp_artists: str,
    sp_track: str,
    sp_item: dict,
) -> float:
    artist_sim = _similarity(folder_artist, sp_artists)
    track_sim = _similarity(folder_track, sp_track)
    score = (artist_sim * 0.45) + (track_sim * 0.45)

    if folder_remixer and sp_track:
        if folder_remixer.lower() in sp_track.lower():
            score += 0.05
        remix_artists = " ".join(a["name"] for a in sp_item["artists"])
        if folder_remixer.lower() in remix_artists.lower():
            score += 0.05

    return min(score, 1.0)


def _split_multi_track(track: str) -> list[str]:
    """Split compound track titles like 'Track A & Track B'."""
    parts = re.split(r"\s*[&,]\s*", track)
    if len(parts) > 1:
        return [p.strip() for p in parts if p.strip()]
    return [track]


def classify_match(confidence: float) -> str:
    if confidence >= 0.7:
        return "auto_approved"
    if confidence >= 0.4:
        return "needs_review"
    return "no_match"
