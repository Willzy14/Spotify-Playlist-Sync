import argparse
import json
import sys

from . import config
from . import state
from .folder_scanner import scan_all
from .matcher import classify_match, search_track
from .playlist_manager import (
    resolve_playlists,
    resort_playlist,
    sync_main_playlist,
    sync_top10_playlist,
)
from .spotify_client import get_client
from .top10_suggestions import generate_suggestions


def cmd_auth(_args: argparse.Namespace) -> None:
    print("Testing Spotify authentication...")
    sp = get_client()
    user = sp.current_user()
    print(f"Authenticated as: {user['display_name']} ({user['id']})")


def cmd_scan(_args: argparse.Namespace) -> None:
    print("Connecting to Spotify...")
    sp = get_client()
    print("Scanning project folders...")
    folders = scan_all(skip_processed=True)
    print(f"\n{len(folders)} new folders to process.\n")

    if not folders:
        print("Nothing new to scan.")
        return

    results = []
    matched = 0
    needs_review = 0
    no_match = 0

    for f in folders:
        matches = search_track(
            sp, f["artist"], f["track"], f["remixer"], f["label"]
        )
        best = matches[0] if matches else None
        classification = classify_match(best["confidence"]) if best else "no_match"

        if classification == "auto_approved":
            tag = "OK"
            matched += 1
        elif classification == "needs_review":
            tag = "??"
            needs_review += 1
        else:
            tag = "--"
            no_match += 1

        if best:
            print(
                f"  [{tag}]  {f['artist']} - {f['track']}"
                f"  =>  {best['spotify_artist']} - {best['spotify_name']}"
                f"  ({best['confidence']:.2f})"
            )
        else:
            print(f"  [{tag}]  {f['artist']} - {f['track']}  =>  no match")

        entry = {
            "folder_path": f["folder_path"],
            "folder_name": f["folder_name"],
            "source_type": f["source_type"],
            "parsed": {
                "artist": f["artist"],
                "track": f["track"],
                "remixer": f["remixer"],
                "label": f["label"],
            },
            "matches": matches,
            "status": classification,
        }
        results.append(entry)

        state.save_folder(
            f["folder_path"], f["folder_name"], f["source_type"],
            f["artist"], f["track"],
            best["spotify_id"] if best and classification != "no_match" else None,
            classification,
        )

    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.PENDING_REVIEW.write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    print(f"\nSummary: {matched} matched, {needs_review} need review, {no_match} no match")
    print(f"Review file: {config.PENDING_REVIEW}")


def cmd_review(_args: argparse.Namespace) -> None:
    if not config.PENDING_REVIEW.exists():
        print("No pending review file. Run 'scan' first.")
        return

    data = json.loads(config.PENDING_REVIEW.read_text(encoding="utf-8"))
    to_review = [e for e in data if e["status"] == "needs_review"]

    if not to_review:
        print("Nothing to review — all matches are auto-approved or no-match.")
        return

    print(f"\n{len(to_review)} tracks need review.\n")
    sp = get_client()

    for entry in to_review:
        p = entry["parsed"]
        print(f"\nFolder:  {entry['folder_name']}")
        print(f"Parsed:  {p['artist']} - {p['track']}")

        for i, m in enumerate(entry["matches"], 1):
            print(
                f"  Match #{i}: {m['spotify_artist']} - {m['spotify_name']}"
                f"  [confidence: {m['confidence']:.2f}]"
            )

        choices = [str(i) for i in range(1, len(entry["matches"]) + 1)]
        prompt = f"  [{'/'.join(choices)}] Accept  [s] Skip  [m] Manual search  [q] Quit: "
        choice = input(prompt).strip().lower()

        if choice == "q":
            break
        elif choice == "s":
            entry["status"] = "skipped"
            state.save_folder(
                entry["folder_path"], entry["folder_name"], entry["source_type"],
                p["artist"], p["track"], None, "skipped",
            )
        elif choice == "m":
            query = input("  Search query: ").strip()
            if query:
                results = sp.search(q=query, type="track", limit=5)
                items = results.get("tracks", {}).get("items", [])
                for i, item in enumerate(items, 1):
                    artists = ", ".join(a["name"] for a in item["artists"])
                    print(f"    {i}. {artists} - {item['name']}")
                pick = input("  Pick number (or s to skip): ").strip()
                if pick.isdigit() and 1 <= int(pick) <= len(items):
                    chosen = items[int(pick) - 1]
                    entry["status"] = "auto_approved"
                    entry["matches"] = [{
                        "spotify_id": chosen["id"],
                        "spotify_name": chosen["name"],
                        "spotify_artist": ", ".join(
                            a["name"] for a in chosen["artists"]
                        ),
                        "spotify_album": chosen["album"]["name"],
                        "popularity": chosen.get("popularity", 0),
                        "confidence": 1.0,
                    }]
                    state.save_folder(
                        entry["folder_path"], entry["folder_name"],
                        entry["source_type"], p["artist"], p["track"],
                        chosen["id"], "auto_approved",
                    )
        elif choice in choices:
            idx = int(choice) - 1
            entry["status"] = "auto_approved"
            m = entry["matches"][idx]
            state.save_folder(
                entry["folder_path"], entry["folder_name"], entry["source_type"],
                p["artist"], p["track"], m["spotify_id"], "auto_approved",
            )

    config.PENDING_REVIEW.write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )
    print("\nReview saved.")


def cmd_add(_args: argparse.Namespace) -> None:
    if not config.PENDING_REVIEW.exists():
        print("No pending review file. Run 'scan' first.")
        return

    data = json.loads(config.PENDING_REVIEW.read_text(encoding="utf-8"))
    approved = [e for e in data if e["status"] == "auto_approved" and e["matches"]]

    if not approved:
        print("No approved tracks to add.")
        return

    tracks_to_add = []
    for entry in approved:
        best = entry["matches"][0]
        tracks_to_add.append({
            "spotify_id": best["spotify_id"],
            "source_type": entry["source_type"],
            "popularity": best.get("popularity", 0),
        })

    print(f"\n{len(tracks_to_add)} tracks approved for adding.\n")
    print("Connecting to Spotify...")
    sp = get_client()

    print("Looking up playlists...")
    playlists = resolve_playlists(sp)

    total_added = 0
    for key in ["mastered", "mixed_mastered"]:
        if key not in playlists:
            continue
        count = sync_main_playlist(sp, key, playlists[key], tracks_to_add)
        print(f"  {config.PLAYLIST_NAMES[key]}: {count} tracks added")
        total_added += count

    for key in ["mastered_top10", "mixed_mastered_top10"]:
        if key not in playlists:
            continue
        count = sync_top10_playlist(sp, key, playlists[key])
        print(f"  {config.PLAYLIST_NAMES[key]}: rebuilt with {count} tracks")

    no_match_count = sum(1 for e in data if e["status"] == "no_match")
    state.log_run(len(data), len(approved), total_added, no_match_count)
    print(f"\nDone. {total_added} tracks added total.")


def cmd_sync(_args: argparse.Namespace) -> None:
    """Full automated sync: scan, match, add new tracks, re-sort by popularity."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("NIGHTLY SYNC")
    print("=" * 60)

    print("\n[1/5] Authenticating...")
    sp = get_client()
    user = sp.current_user()
    print(f"  Logged in as: {user['display_name']}")

    print("\n[2/5] Scanning project folders...")
    folders = scan_all(skip_processed=True)
    print(f"  {len(folders)} folders to process")

    print(f"\n[3/5] Searching Spotify for {len(folders)} tracks...")
    approved = []
    review_count = 0
    no_match_count = 0
    too_new_count = 0

    for i, f in enumerate(folders, 1):
        age = f.get("folder_age_days", 999)
        matches = search_track(
            sp, f["artist"], f["track"], f["remixer"], f["label"]
        )
        best = matches[0] if matches else None
        classification = classify_match(best["confidence"]) if best else "no_match"

        if classification == "no_match" and age < config.MIN_FOLDER_AGE_DAYS:
            status = "too_new"
            too_new_count += 1
        elif classification == "auto_approved":
            status = "auto_approved"
            approved.append({
                "spotify_id": best["spotify_id"],
                "source_type": f["source_type"],
                "folder": f,
                "match": best,
            })
        elif classification == "needs_review":
            status = "needs_review"
            review_count += 1
        else:
            status = "no_match"
            no_match_count += 1

        state.save_folder(
            f["folder_path"], f["folder_name"], f["source_type"],
            f["artist"], f["track"],
            best["spotify_id"] if best and classification != "no_match" else None,
            status,
        )

        if best and best["confidence"] > 0:
            print(
                f"  {i:>3}/{len(folders)}  "
                f"{f['artist']} - {f['track']}  =>  "
                f"{best['spotify_artist']} - {best['spotify_name']}  "
                f"({best['confidence']:.2f})  [{status}]"
            )

    print(f"\n  {len(approved)} approved, {review_count} review, "
          f"{no_match_count} no match, {too_new_count} too new")

    print("\n[4/5] Looking up playlists...")
    playlists = resolve_playlists(sp)

    total_added = 0
    for key in ["mastered", "mixed_mastered"]:
        if key not in playlists:
            continue
        tracks = [a for a in approved if a["source_type"] in config.PLAYLIST_SOURCES[key]]
        track_data = [{"spotify_id": t["spotify_id"], "source_type": t["source_type"]} for t in tracks]
        count = sync_main_playlist(sp, key, playlists[key], track_data)
        if count:
            print(f"  {config.PLAYLIST_NAMES[key]}: {count} new tracks added")
        total_added += count

    print("\n[5/5] Re-sorting playlists by current popularity...")
    for key in ["mastered", "mixed_mastered"]:
        if key not in playlists:
            continue
        count = resort_playlist(sp, playlists[key], key)
        print(f"  {config.PLAYLIST_NAMES[key]}: {count} tracks sorted")

    state.log_run(len(folders), len(approved), total_added, no_match_count)

    from datetime import datetime
    if datetime.now().weekday() == 0:  # Monday
        print("\n[WEEKLY] Generating Top 10 suggestions...")
        report = generate_suggestions(sp)
        if report:
            print("  Suggestions written to state dir")
        else:
            print("  No suggestions — curated lists match rankings")

    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print(f"  New tracks added: {total_added}")
    print(f"  Playlists re-sorted by popularity")
    print("=" * 60)


def cmd_status(_args: argparse.Namespace) -> None:
    stats = state.get_stats()
    print(f"\nFolders processed: {stats['total_folders']}")
    print(f"  Matched & added: {stats['matched']}")
    print(f"  No match:        {stats['no_match']}")
    print(f"  Pending review:  {stats['pending_review']}")
    print(f"Total tracks added: {stats['total_added']}")
    if stats["last_run"]:
        print(f"Last run: {stats['last_run']['run_at']}")


def cmd_rescan(_args: argparse.Namespace) -> None:
    confirm = input("Clear all state and rescan? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    state.clear_all()
    print("State cleared. Run 'scan' to rescan all folders.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="spotify-playlist-sync",
        description="Sync mastering/mixing projects to Spotify playlists",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("auth", help="Test Spotify authentication")
    sub.add_parser("scan", help="Scan folders and search Spotify")
    sub.add_parser("review", help="Review uncertain matches")
    sub.add_parser("add", help="Add approved tracks to playlists")
    sub.add_parser("sync", help="Full automated sync: scan, match, add, re-sort")
    sub.add_parser("status", help="Show sync statistics")
    sub.add_parser("rescan", help="Clear state and start fresh")

    args = parser.parse_args()
    commands = {
        "auth": cmd_auth,
        "scan": cmd_scan,
        "review": cmd_review,
        "add": cmd_add,
        "sync": cmd_sync,
        "status": cmd_status,
        "rescan": cmd_rescan,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
