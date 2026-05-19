# AI Context Brain - Spotify Playlist Sync

> **CRITICAL**: This is the living memory of this project. Read this FIRST at the start of every session.
> **Last Updated**: 2026-05-19

## Project Mission

Python CLI that automatically populates Sam's Spotify playlists with tracks he's mixed and mastered. Scans his Dropbox project folders, parses folder names for artist/track metadata, fuzzy-matches against Spotify, and adds tracks to playlists with popularity-based ordering. Runs nightly via Windows Task Scheduler.

## Tech Stack

- **Language**: Python 3.14
- **Key Libraries**: spotipy (Spotify API), python-dotenv, difflib (fuzzy matching)
- **Storage**: SQLite (state tracking at `~/.spotify-playlist-sync/state.db`)
- **Key Dependency**: `track-release-pipeline` (sibling project — provides `file_parser.parse_folder_name`)
- **Auth**: Spotify OAuth via spotipy (credentials from MCP server .env)
- **Automation**: Windows Task Scheduler, daily 8am via `sync.bat`

## Current Status

- **LIVE** on real Spotify playlists — nightly sync running since 2026-05-19
- Mastered By Sam Wills: 1,899 tracks, sorted by two-tier popularity
- Mixed & Mastered By Sam Wills: 396 tracks, sorted by two-tier popularity
- Top 10 playlists: hand-curated by Sam (not automated)
- Weekly Top 10 suggestions generated Mondays, fed to Wren's weekly brief via handshake system
- Re-linked track ID resolution working (fixes ~720 tracks with false popularity 0)
- Blocklist system active (`top10_blocklist.json`)

## Architecture Overview

```
Spotify-Playlist-Sync/
    pyproject.toml              # Package config, deps: spotipy, python-dotenv
    sync.bat                    # Task Scheduler entry point (gitignored)
    top10_blocklist.json        # Artist/track blocklist for Top 10 suggestions
    src/
        spotify_playlist_sync/
            __init__.py
            __main__.py         # Entry point: python -m spotify_playlist_sync
            cli.py              # CLI: scan, review, add, sync, status, rescan, auth
            config.py           # Paths, playlist names, env loading
            folder_scanner.py   # Walks source dirs, calls file_parser
            matcher.py          # Spotify search + fuzzy matching + scoring
            playlist_manager.py # Find/read/add/replace/resort playlist tracks
            spotify_client.py   # Spotipy OAuth wrapper
            state.py            # SQLite state management
            top10_suggestions.py # Weekly Top 10 swap suggestion engine
    Documentation/
        AI_CONTEXT.md           # This file
        TOOLBOX.md              # Module inventory
    .github/
        ai-activity-log.md     # Shared AI activity log
        copilot-instructions.md # Copilot-specific instructions
        memory.json             # Machine-readable project memory
```

## Key Files

| File | Purpose | When to Edit |
|------|---------|-------------|
| `config.py` | All paths, playlist names, env vars, thresholds | Adding new playlists or tuning parameters |
| `folder_scanner.py` | Scans Dropbox project dirs | Changing scan logic or source dirs |
| `matcher.py` | Spotify search + confidence scoring + version preference | Tuning match quality |
| `playlist_manager.py` | Playlist CRUD + two-tier sorting + re-linked ID resolution | Changing how tracks are added/ordered |
| `state.py` | SQLite state tracking | Adding new tracked data |
| `cli.py` | All CLI commands including `sync` (nightly) | Adding new commands |
| `top10_suggestions.py` | Weekly Top 10 suggestion engine | Adjusting scoring formula or output |
| `top10_blocklist.json` | Artists/tracks excluded from Top 10 suggestions | Sam wants to block someone |

## Design Rules

- **Folder parsing**: Reuses `track-release-pipeline`'s `file_parser.parse_folder_name` — never duplicate
- **Main playlist ordering**: Two-tier sort — recent (60 days) at top by popularity, older below by popularity
- **Top 10 playlists**: Hand-curated by Sam, NOT programmatic. Algorithm is suggestion-only
- **Top 10 scoring formula**: `track_pop * (1 + artist_pop/200) * (1 + sqrt(age_years))` — track popularity leads, artist is a bonus
- **Top 10 dedup**: One track per primary artist, one version per normalised title, cross-list dedup (mastered first, M&M excludes mastered picks)
- **Popularity**: Uses Spotify's 0-100 score, not stream counts
- **Re-linked tracks**: Fetch playlist tracks with `market='GB'` to resolve re-linked IDs, then fetch those IDs for real popularity
- **State**: SQLite at `~/.spotify-playlist-sync/state.db` — tracks processed folders and added tracks
- **Re-checking**: Only "added" and "parse_failed" folders are permanently skipped; "no_match" and "needs_review" are re-checked each run
- **Credentials**: Loaded from MCP server `.env` or local `.env`
- **Rate limiting**: 0.2s delay between Spotify search API calls
- **MIN_POPULARITY**: 5 — catches old recordings on new compilation albums

## Matching Rules (Domain Knowledge)

- **Release date filter**: Tracks released >365 days ago scored 0.0
- **Popularity filter**: Tracks with popularity <5 scored 0.0 — catches compilations
- **Folder age filter**: Folders created <30 days ago classified as "too_new" not "no_match"
- **Hard remixer filter**: If folder has named remixer, Spotify match MUST contain that remixer name
- **Version preference**: radio edit (100) > edit (80) > clean (70) > original (50) > club/vocal (40) > dub/instrumental (20) > extended (10)
- **Primary artist matching**: Compare folder artist against Spotify's FIRST-credited artist
- **ADM exclusion**: Folders containing "ADM" silently skipped
- **Confidence tiers**: >=0.7 auto_approved, 0.4-0.7 needs_review, <0.4 no_match

## How to Run

```bash
# Nightly automated sync (runs via Task Scheduler)
python -m spotify_playlist_sync sync

# Manual commands
python -m spotify_playlist_sync auth      # Test Spotify auth
python -m spotify_playlist_sync scan      # Scan folders + search Spotify
python -m spotify_playlist_sync review    # Review uncertain matches
python -m spotify_playlist_sync add       # Add approved tracks to playlists
python -m spotify_playlist_sync status    # Show sync statistics
python -m spotify_playlist_sync rescan    # Clear state and start fresh
```

## Playlists

| Key | Playlist Name | Spotify ID | Management |
|-----|--------------|------------|------------|
| `mastered` | Mastered By Sam Wills | `13j4DqrmZw0LlFQnQh7mwX` | Automated (nightly sync) |
| `mixed_mastered` | Mixed & Mastered By Sam Wills | `4w9RHBo73xiBxnFocT70SJ` | Automated (nightly sync) |
| `mastered_top10` | Mastered By Sam Wills Top 10 | `5rqpRN03GqlljkEd1JrN6u` | Hand-curated by Sam |
| `mixed_mastered_top10` | Mixed and Mastered by Sam Wills Top 10 | `52kCIv0TmRAyaFm1S9Uii1` | Hand-curated by Sam |

## Connections

- **Track-Release-Pipeline** — imports `file_parser.parse_folder_name` for folder name parsing
- **MCP Spotify Server** — shares Spotify OAuth credentials (same client ID/secret)
- **samwillsmixing.com** — playlists serve as portfolio/proof of work linked from website
- **Wren (Hermes)** — receives weekly Top 10 suggestions via handshake system for inclusion in weekly brief

## Recent Session History

### 2026-05-19 Session 3 (Latest)
**Focus**: Top 10 playlist scoring formula and strategy decision

**Completed**:
- Investigated why Navos "Believe Me", James Hype "Afraid", Dots Per Inch missing from Top 10
- Discovered Navos artist_pop=50 (too low for 60% artist weight), James Hype already in list via "More Than Friends", Dots Per Inch not in playlist at all
- Tested 3 formula options: current (tp×0.4 + ap×0.6), Option A (tp×0.7 + ap×0.3), Option B (tp × (1 + ap/200))
- Option B chosen — track popularity leads, artist is a small bonus
- Added cross-list dedup so tracks can't appear in both Top 10s
- **Key decision**: Top 10 playlists stay hand-curated by Sam, algorithm becomes suggestion engine only
- Built `top10_suggestions.py` module with Option B scoring
- Wired Monday suggestions into `cmd_sync`
- Created Wren handoff (Entry 016) to add suggestions to weekly brief cron
- Cleaned up all 3 test playlists
- Recorded current curated Top 10 contents in project memory

**Key Learnings**:
- Sam's hand-curated Top 10s are strategically better — they balance big names, underground cred, and legacy credits
- Algorithm clusters towards one type of track, can't capture sales/marketing nuance
- "I Was Lovin' You" (James Hype feat. Dots Per Inch) not in playlist — folders exist somewhere but not in standard source dirs

### 2026-05-19 Session 2
**Focus**: Go live on real playlists, two-tier sorting, re-linked track fix, Top 10 formula iteration

**Completed**:
- Fixed playlist name mismatches in config
- Added MIN_POPULARITY=5 filter (caught Sammy Davis Jr. false positive)
- Went live on real playlists (Mastered: 1,899 tracks, M&M: 396 tracks)
- Built `cmd_sync` for nightly automation
- Set up Windows Task Scheduler (daily 8am)
- Implemented two-tier playlist sorting (recent 60 days at top, older below)
- Fixed re-linked track ID resolution (~720 tracks with false popularity 0)
- Iterated Top 10 formula through 6 rounds with Sam's feedback
- Built blocklist system (`top10_blocklist.json`)

### 2026-05-19 Session 1
**Focus**: Full project build — modules, bootstrap, OAuth auth, matching refinement
**Completed**:
- Created project structure and all 8 core modules
- 5 rounds of matching refinement with domain-expert feedback
- Created Claude Testing playlist with 60 tracks
- OAuth auth confirmed working

## Key Decisions

- **Top 10 = human-curated**: Algorithm tested through 6+ iterations — Sam's hand-picked lists are better for sales because they balance commercial reach with scene credibility. Algorithm serves as weekly suggestion engine only.
- **Option B scoring**: `track_pop * (1 + artist_pop/200) * (1 + sqrt(age_years))` — rewards actual track performance, artist name is a small bonus not the primary signal
- **Cross-list dedup**: A track in the Mastered Top 10 can't also appear in Mixed & Mastered Top 10
- **Release age 365 days**: Sam clears project folders every January
- **Folder age 30 days**: Most tracks take at least a month from mastering to Spotify release
- **Re-linked resolution**: Must use `market='GB'` when fetching playlist tracks to get current IDs
- **MIN_POPULARITY 5**: Catches old recordings on new compilation albums (Sammy Davis Jr. on 2025 comp)

## Known Issues

- 3 folders fail to parse: `Hipp-E Strange Daze`, `Hipp-E Tunnels`, stray subfolder
- James Hype "I Was Lovin' You" feat. Dots Per Inch — folder exists somewhere but not in standard source dirs. Sam will address separately
- ~720 tracks were added before sync system existed — no `added_at` dates in state DB (default to 365 days for age calculations)

## Upcoming Work

- Sam to locate missing project folders (Navos, James Hype, Dots Per Inch etc.) for scanning
- Wren to wire Top 10 suggestions into weekly brief cron (handshake entry 016)
- Add project to Project Registry
