import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher

import spotipy

from . import config

_ADM_RE = re.compile(r"\s+ADM'?S?\s*$", re.IGNORECASE)
_FEAT_RE = re.compile(
    r"\s*(feat\.?|ft\.?|featuring)\s+", re.IGNORECASE
)
_JOINER_RE = re.compile(r"\s*[,&x]\s*", re.IGNORECASE)

_VERSION_WORDS = re.compile(
    r"\b(remix|mix|edit|rework|dub|bootleg|refix|version|re-?edit)\b",
    re.IGNORECASE,
)
_GENERIC_VERSIONS = {
    "extended", "original", "club", "radio", "vip", "instrumental",
    "vocal", "stripped", "acoustic", "short", "long", "clean", "dirty",
}


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

    remixer_name = _extract_remixer_name(remixer) if remixer else None

    queries = []
    if remixer_name:
        queries.append(f"{artist} {track_clean} {remixer_name}")
        queries.append(f'track:"{track_clean}" artist:"{remixer_name}"')
    queries.append(f'track:"{track_clean}" artist:"{artist}"')
    queries.append(f"{artist} {track_clean}")

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
            version_label, version_pref = _detect_version(sp_track)
            candidates.append({
                "spotify_id": tid,
                "spotify_name": sp_track,
                "spotify_artist": sp_artists,
                "spotify_album": item["album"]["name"],
                "popularity": item.get("popularity", 0),
                "confidence": round(score, 3),
                "version": version_label,
                "version_pref": version_pref,
            })
        if candidates:
            break

    if not candidates:
        for sub_track in _split_multi_track(track_clean):
            if sub_track == track_clean:
                continue
            sub_results = search_track(sp, artist, sub_track, remixer, label)
            candidates.extend(sub_results)

    candidates.sort(key=lambda c: (c["confidence"], c["version_pref"]), reverse=True)
    return candidates[:5]


def _parse_release_date(album: dict) -> datetime | None:
    raw = album.get("release_date", "")
    precision = album.get("release_date_precision", "day")
    try:
        if precision == "day":
            return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        elif precision == "month":
            return datetime.strptime(raw, "%Y-%m").replace(tzinfo=timezone.utc)
        elif precision == "year":
            return datetime.strptime(raw, "%Y").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    return None


def _release_too_old(sp_item: dict) -> bool:
    released = _parse_release_date(sp_item.get("album", {}))
    if released is None:
        return False
    age_days = (datetime.now(timezone.utc) - released).days
    return age_days > config.MAX_RELEASE_AGE_DAYS


def _extract_remixer_name(remixer: str) -> str | None:
    """Extract the artist name from a remixer string like 'Butch Remix'.

    Returns None if it's a generic version (Extended Mix, Original, etc.)
    rather than a named remixer.
    """
    name = _VERSION_WORDS.sub("", remixer).strip()
    name = re.sub(r"\s+", " ", name).strip(" -")
    if not name or name.lower() in _GENERIC_VERSIONS:
        return None
    return name


_ARRANGEMENT_SUFFIX_RE = re.compile(
    r"\s*[-–—]\s+("
    r"extended\s*mix|radio\s*edit|original\s*mix|club\s*mix|"
    r"dub\s*mix|instrumental|vocal\s*mix|vip\s*mix|"
    r"stripped|acoustic|short\s*edit|clean|dirty|"
    r"edit|dub"
    r")\s*$",
    re.IGNORECASE,
)

_REMIX_SUFFIX_RE = re.compile(
    r"\s*[-–—]\s+.*?(remix|rework|bootleg|refix|re-?edit)\s*$",
    re.IGNORECASE,
)

_VERSION_PREFERENCE = {
    "radio edit": 100,
    "radio mix": 100,
    "edit": 80,
    "short edit": 80,
    "clean": 70,
    "original mix": 50,
    "original": 50,
    "club mix": 40,
    "vocal mix": 40,
    "dub mix": 20,
    "dub": 20,
    "instrumental": 20,
    "stripped": 20,
    "acoustic": 20,
    "extended mix": 10,
    "extended": 10,
    "vip mix": 10,
}


def _remixer_present(remixer_name: str, sp_track: str, sp_item: dict) -> bool:
    """Check if the remixer name appears in the Spotify track title or artist credits."""
    target = remixer_name.lower()
    if target in sp_track.lower():
        return True
    for a in sp_item.get("artists", []):
        if target in a["name"].lower():
            return True
    return False


def _strip_version_suffix(sp_track: str) -> str:
    """Remove arrangement suffixes (Extended Mix, Radio Edit, etc.) and remix suffixes."""
    cleaned = _ARRANGEMENT_SUFFIX_RE.sub("", sp_track)
    cleaned = _REMIX_SUFFIX_RE.sub("", cleaned)
    return cleaned.strip()


def _detect_version(sp_track: str) -> tuple[str | None, int]:
    """Detect the arrangement version and return (version_label, preference_score)."""
    m = _ARRANGEMENT_SUFFIX_RE.search(sp_track)
    if m:
        version = m.group(1).strip().lower()
        return version, _VERSION_PREFERENCE.get(version, 30)
    if not _REMIX_SUFFIX_RE.search(sp_track):
        return None, 50
    return None, 30


def _artist_similarity(folder_artist: str, sp_item: dict) -> float:
    """Score artist match using primary Spotify artist, not the full credit string."""
    sp_artists_list = sp_item.get("artists", [])
    if not sp_artists_list:
        return 0.0

    primary = sp_artists_list[0]["name"]
    primary_sim = _similarity(folder_artist, primary)

    full_credits = ", ".join(a["name"] for a in sp_artists_list)
    full_sim = _similarity(folder_artist, full_credits)

    return max(primary_sim, full_sim * 0.7)


def _score_match(
    folder_artist: str,
    folder_track: str,
    folder_remixer: str | None,
    folder_label: str | None,
    sp_artists: str,
    sp_track: str,
    sp_item: dict,
) -> float:
    if _release_too_old(sp_item):
        return 0.0

    remixer_name = _extract_remixer_name(folder_remixer) if folder_remixer else None
    if remixer_name and not _remixer_present(remixer_name, sp_track, sp_item):
        return 0.0

    sp_track_clean = _strip_version_suffix(sp_track)
    artist_sim = _artist_similarity(folder_artist, sp_item)

    if remixer_name:
        track_sim = _similarity(folder_track, sp_track_clean)
        score = (artist_sim * 0.40) + (track_sim * 0.40) + 0.20
    else:
        track_sim = _similarity(folder_track, sp_track_clean)
        score = (artist_sim * 0.45) + (track_sim * 0.45)

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
