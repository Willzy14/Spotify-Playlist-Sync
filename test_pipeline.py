"""End-to-end pipeline test using a disposable "Claude Testing" playlist."""

import json
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from spotify_playlist_sync import config
from spotify_playlist_sync.folder_scanner import scan_all
from spotify_playlist_sync.matcher import classify_match, search_track
from spotify_playlist_sync.spotify_client import get_client, get_playlist_track_ids
from spotify_playlist_sync.state import clear_all as clear_state

TEST_PLAYLIST_NAME = "Claude Testing"
MAX_FOLDERS = 0  # 0 = no limit


def find_or_create_playlist(sp, name):
    user_id = sp.current_user()["id"]
    offset = 0
    while True:
        batch = sp.current_user_playlists(limit=50, offset=offset)
        for pl in batch["items"]:
            if pl["name"] == name:
                print(f"  Found existing playlist: {name} ({pl['id']})")
                return pl["id"]
        if batch["next"] is None:
            break
        offset += 50
    pl = sp.user_playlist_create(user_id, name, public=False,
                                  description="Temporary test playlist — safe to delete")
    print(f"  Created playlist: {name} ({pl['id']})")
    return pl["id"]


def main():
    print("=" * 60)
    print("PIPELINE TEST — Claude Testing Playlist")
    print(f"  Release age filter: >{config.MAX_RELEASE_AGE_DAYS} days = rejected")
    print(f"  Folder age filter: <{config.MIN_FOLDER_AGE_DAYS} days = too new")
    print("=" * 60)

    # Step 1: Auth
    print("\n[1/5] Authenticating...")
    sp = get_client()
    user = sp.current_user()
    print(f"  Logged in as: {user['display_name']}")

    # Step 2: Create/find test playlist
    print("\n[2/5] Setting up test playlist...")
    playlist_id = find_or_create_playlist(sp, TEST_PLAYLIST_NAME)

    # Step 3: Scan folders (subset)
    print(f"\n[3/5] Scanning folders (max {MAX_FOLDERS})...")
    clear_state()
    all_folders = scan_all(skip_processed=False)
    folders = all_folders[:MAX_FOLDERS] if MAX_FOLDERS else all_folders
    print(f"  {len(all_folders)} total folders found, processing {'all' if not MAX_FOLDERS else len(folders)}")

    # Step 4: Match against Spotify
    print(f"\n[4/5] Searching Spotify for {len(folders)} tracks...")
    approved = []
    review = []
    no_match = []
    too_new = []

    for i, f in enumerate(folders, 1):
        age = f.get("folder_age_days", 999)

        matches = search_track(sp, f["artist"], f["track"], f["remixer"], f["label"])
        best = matches[0] if matches else None
        classification = classify_match(best["confidence"]) if best else "no_match"

        if classification == "no_match" and age < config.MIN_FOLDER_AGE_DAYS:
            tag = "NW"
            too_new.append(f)
        elif classification == "auto_approved":
            tag = "OK"
            approved.append({"folder": f, "match": best})
        elif classification == "needs_review":
            tag = "??"
            review.append({"folder": f, "match": best})
        else:
            tag = "--"
            no_match.append(f)

        age_str = f"{age}d" if age < 100 else ""
        if best:
            print(
                f"  [{tag}] {i:>2}/{len(folders)}  "
                f"{f['artist']} - {f['track']}  =>  "
                f"{best['spotify_artist']} - {best['spotify_name']}  "
                f"({best['confidence']:.2f})"
                f"{'  [folder ' + age_str + ' old]' if age_str else ''}"
            )
        else:
            print(
                f"  [{tag}] {i:>2}/{len(folders)}  "
                f"{f['artist']} - {f['track']}  =>  no match"
                f"{'  [folder ' + age_str + ' old]' if age_str else ''}"
            )

    print(f"\n  Results: {len(approved)} auto-approved, {len(review)} need review, "
          f"{len(no_match)} no match, {len(too_new)} too new to expect")

    # Step 5: Add approved tracks to test playlist
    if not approved:
        print("\n[5/5] No approved tracks to add. Done.")
        return

    track_ids = [a["match"]["spotify_id"] for a in approved]
    existing = get_playlist_track_ids(sp, playlist_id)
    new_ids = [tid for tid in track_ids if tid not in existing]

    print(f"\n[5/5] Adding {len(new_ids)} tracks to '{TEST_PLAYLIST_NAME}'...")
    if new_ids:
        pops = {}
        for i in range(0, len(new_ids), 50):
            batch = new_ids[i:i + 50]
            tracks = sp.tracks(batch)
            for t in tracks["tracks"]:
                if t:
                    pops[t["id"]] = t.get("popularity", 0)
        new_ids.sort(key=lambda tid: pops.get(tid, 0), reverse=True)

        for i in range(0, len(new_ids), 100):
            batch = new_ids[i:i + 100]
            sp.playlist_add_items(playlist_id, batch, position=0)
        print(f"  Added {len(new_ids)} tracks (sorted by popularity, most popular first)")
    else:
        print("  All tracks already in playlist.")

    # Summary
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print(f"  Playlist: {TEST_PLAYLIST_NAME}")
    print(f"  Tracks added: {len(new_ids)}")
    print(f"  Auto-approved: {len(approved)}")
    print(f"  Needs review: {len(review)}")
    print(f"  No match: {len(no_match)}")
    print(f"  Too new: {len(too_new)}")
    if approved:
        print("\n  Top matches by popularity:")
        sorted_approved = sorted(approved, key=lambda a: a["match"]["popularity"], reverse=True)
        for a in sorted_approved[:10]:
            m = a["match"]
            print(f"    {m['popularity']:>3}  {m['spotify_artist']} - {m['spotify_name']}")
    if review:
        print("\n  Uncertain matches (would need review):")
        for r in review[:5]:
            m = r["match"]
            f = r["folder"]
            print(f"    {f['artist']} - {f['track']}  =>  {m['spotify_artist']} - {m['spotify_name']}  ({m['confidence']:.2f})")
    if no_match:
        print("\n  No match found:")
        for f in no_match[:5]:
            print(f"    {f['artist']} - {f['track']}")
    if too_new:
        print("\n  Too new to expect on Spotify yet:")
        for f in too_new[:5]:
            print(f"    {f['artist']} - {f['track']}  (folder {f['folder_age_days']}d old)")


if __name__ == "__main__":
    main()
