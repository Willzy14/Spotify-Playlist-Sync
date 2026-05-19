"""Generate weekly Top 10 swap suggestions by comparing curated playlists against rising tracks."""
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import spotipy

from . import config
from . import state
from .playlist_manager import _resolve_playlist_tracks, get_popularity


SUGGESTIONS_DIR = config.STATE_DIR / "suggestions"
BLOCKLIST_PATH = Path(__file__).resolve().parents[2] / "top10_blocklist.json"

TOP10_PLAYLIST_IDS = {
    "mastered": "5rqpRN03GqlljkEd1JrN6u",
    "mixed_mastered": "52kCIv0TmRAyaFm1S9Uii1",
}

MAIN_PLAYLIST_IDS = {
    "mastered": "13j4DqrmZw0LlFQnQh7mwX",
    "mixed_mastered": "4w9RHBo73xiBxnFocT70SJ",
}


def _load_blocklist() -> tuple[set[str], set[str]]:
    if BLOCKLIST_PATH.exists():
        data = json.loads(BLOCKLIST_PATH.read_text(encoding="utf-8"))
        artists = {a.lower() for a in data.get("blocked_artists", [])}
        tracks = set(data.get("blocked_tracks", []))
        return artists, tracks
    return set(), set()


def _norm_title(name: str) -> str:
    return re.sub(
        r"\s*[-\(].*?(remix|mix|edit|version|radio|extended|dub|instrumental|vip|rework|bootleg).*",
        "", name, flags=re.IGNORECASE,
    ).strip().lower()


def _score_all_tracks(
    sp: spotipy.Spotify,
    playlist_id: str,
    playlist_key: str,
    exclude_ids: set[str] | None = None,
) -> list[dict]:
    if exclude_ids is None:
        exclude_ids = set()

    blocked_artists, blocked_tracks = _load_blocklist()
    track_ids = _resolve_playlist_tracks(sp, playlist_id)
    added_dates = state.get_track_added_dates(playlist_key)

    all_tracks = []
    for i in range(0, len(track_ids), 50):
        batch = track_ids[i : i + 50]
        result = sp.tracks(batch)
        for t in result["tracks"]:
            if t:
                all_tracks.append(t)

    artist_ids = set()
    for t in all_tracks:
        for a in t["artists"]:
            artist_ids.add(a["id"])

    artist_pop = {}
    aid_list = list(artist_ids)
    for i in range(0, len(aid_list), 50):
        batch = aid_list[i : i + 50]
        result = sp.artists(batch)
        for a in result["artists"]:
            if a:
                artist_pop[a["id"]] = a["popularity"]

    now = datetime.now(timezone.utc)
    scored = []
    for t in all_tracks:
        tid = t["id"]
        if tid in blocked_tracks or tid in exclude_ids:
            continue
        primary = t["artists"][0]["name"]
        if primary.lower() in blocked_artists:
            continue

        tp = t["popularity"]
        ap = max((artist_pop.get(a["id"], 0) for a in t["artists"]), default=0)
        added_str = added_dates.get(tid)
        age_days = (now - datetime.fromisoformat(added_str)).days if added_str else 365
        age_years = age_days / 365.0

        score = tp * (1 + ap / 200) * (1 + math.sqrt(age_years))

        scored.append({
            "id": tid,
            "name": t["name"],
            "artist": primary,
            "all_artists": ", ".join(a["name"] for a in t["artists"]),
            "tp": tp,
            "ap": ap,
            "score": score,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    seen_a, seen_t = set(), set()
    deduped = []
    for s in scored:
        ak = s["artist"].lower()
        tk = _norm_title(s["name"])
        if ak in seen_a or tk in seen_t:
            continue
        seen_a.add(ak)
        seen_t.add(tk)
        deduped.append(s)

    return deduped


def generate_suggestions(sp: spotipy.Spotify) -> str | None:
    """Compare curated Top 10s against algorithmic rankings. Returns report text."""
    lines = []
    lines.append(f"# Top 10 Playlist Suggestions — {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    mastered_top10_ids = set()
    has_suggestions = False

    for key, label in [("mastered", "Mastered"), ("mixed_mastered", "Mixed & Mastered")]:
        top10_pid = TOP10_PLAYLIST_IDS.get(key)
        main_pid = MAIN_PLAYLIST_IDS.get(key)
        if not top10_pid or not main_pid:
            continue

        curated_ids = _resolve_playlist_tracks(sp, top10_pid)
        curated_tracks = {}
        if curated_ids:
            result = sp.tracks(curated_ids)
            for t in result["tracks"]:
                if t:
                    curated_tracks[t["id"]] = {
                        "name": t["name"],
                        "artist": ", ".join(a["name"] for a in t["artists"]),
                        "pop": t["popularity"],
                    }

        exclude = mastered_top10_ids if key == "mixed_mastered" else None
        ranked = _score_all_tracks(sp, main_pid, key, exclude_ids=exclude)

        if key == "mastered":
            mastered_top10_ids = {s["id"] for s in ranked[:10]}

        lines.append(f"## {label} By Sam Wills Top 10")
        lines.append("")

        candidates = [s for s in ranked[:20] if s["id"] not in curated_ids]
        if not candidates:
            lines.append("No changes suggested — your curated list aligns with the rankings.")
            lines.append("")
            continue

        has_suggestions = True

        weakest = None
        weakest_score = float("inf")
        for cid, ct in curated_tracks.items():
            for s in ranked:
                if s["id"] == cid:
                    if s["score"] < weakest_score:
                        weakest_score = s["score"]
                        weakest = {**ct, "id": cid, "score": s["score"]}
                    break

        lines.append("**Rising tracks not in your Top 10:**")
        lines.append("")
        for s in candidates[:5]:
            lines.append(
                f"- {s['all_artists']} — {s['name']} "
                f"(pop={s['tp']}, artist={s['ap']}, score={s['score']:.0f})"
            )
        lines.append("")

        if weakest:
            lines.append(
                f"**Lowest-scoring track in your current Top 10:** "
                f"{weakest['artist']} — {weakest['name']} "
                f"(pop={weakest['pop']}, score={weakest['score']:.0f})"
            )
            lines.append("")

    if not has_suggestions:
        return None

    report = "\n".join(lines)

    SUGGESTIONS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = SUGGESTIONS_DIR / "latest_suggestions.md"
    report_path.write_text(report, encoding="utf-8")

    return report
