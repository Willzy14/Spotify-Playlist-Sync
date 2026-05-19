# AI Context Brain - Spotify Playlist Sync

> **CRITICAL**: This is the living memory of this project. Read this FIRST at the start of every session.
> **Last Updated**: 2026-05-19

## Project Mission

Python CLI that automatically populates Sam's Spotify playlists with tracks he's mixed and mastered. Scans his Dropbox project folders, parses folder names for artist/track metadata, fuzzy-matches against Spotify, and adds tracks to four playlists with popularity-based ordering.

## Tech Stack

- **Language**: Python 3.14
- **Key Libraries**: spotipy (Spotify API), python-dotenv, difflib (fuzzy matching)
- **Storage**: SQLite (state tracking at `~/.spotify-playlist-sync/state.db`)
- **Key Dependency**: `track-release-pipeline` (sibling project — provides `file_parser.parse_folder_name`)
- **Auth**: Spotify OAuth via spotipy (credentials from MCP server .env)

## Current Status

- All core modules built and working
- Folder scanner tested — 231 of 234 folders parse successfully
- OAuth auth complete — token cached
- Scan/review/add flow not yet tested end-to-end with Spotify
- Playlist manager and Top 10 logic built but untested

## Architecture Overview

```
Spotify-Playlist-Sync/
    pyproject.toml              # Package config, deps: spotipy, python-dotenv
    test_scan.py                # Quick test script for folder scanner
    src/
        spotify_playlist_sync/
            __init__.py
            __main__.py         # Entry point: python -m spotify_playlist_sync
            cli.py              # CLI: scan, review, add, status, rescan, auth
            config.py           # Paths, playlist names, env loading
            folder_scanner.py   # Walks source dirs, calls file_parser
            matcher.py          # Spotify search + fuzzy matching + scoring
            playlist_manager.py # Find/read/add/replace playlist tracks
            spotify_client.py   # Spotipy OAuth wrapper
            state.py            # SQLite state management
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
| `config.py` | All paths, playlist names, env vars | Adding new playlists or source dirs |
| `folder_scanner.py` | Scans Dropbox project dirs | Changing scan logic or source dirs |
| `matcher.py` | Spotify search + confidence scoring | Tuning match quality |
| `playlist_manager.py` | Playlist CRUD + ordering logic | Changing how tracks are added/ordered |
| `state.py` | SQLite state tracking | Adding new tracked data |
| `cli.py` | All CLI commands | Adding new commands |

## Design Rules

- **Folder parsing**: Reuses `track-release-pipeline`'s `file_parser.parse_folder_name` — never duplicate
- **Playlist ordering**: Main playlists = insert new at top (most popular first). Top 10 = fully replaced
- **Popularity**: Uses Spotify's 0-100 score, not stream counts
- **State**: SQLite at `~/.spotify-playlist-sync/state.db` — tracks processed folders and added tracks
- **Credentials**: Loaded from MCP server `.env` at `Claude Code Brain/mcp-servers/mcp-claude-spotify/.env`
- **Rate limiting**: 0.2s delay between Spotify search API calls

## How to Run

```bash
# First time — authenticate with Spotify (opens browser)
python -m spotify_playlist_sync auth

# Scan folders and search Spotify
python -m spotify_playlist_sync scan

# Review uncertain matches interactively
python -m spotify_playlist_sync review

# Add approved tracks to playlists
python -m spotify_playlist_sync add

# Check stats
python -m spotify_playlist_sync status

# Clear state and start fresh
python -m spotify_playlist_sync rescan
```

## Four Playlists

| Key | Playlist Name | Source Folders | Behaviour |
|-----|--------------|---------------|-----------|
| `mastered` | Mastered By Sam Wills | Stereo Masters + Finished Mixes | New at top, popular first |
| `mixed_mastered` | Mixed and Mastered by Sam Wills | Finished Mixes only | New at top, popular first |
| `mastered_top10` | Mastered by Sam Wills Top 10 | Stereo Masters + Finished Mixes | Top 10 by popularity, 12-month rolling |
| `mixed_mastered_top10` | Mixed and Mastered by Sam Wills Top 10 | Finished Mixes only | Top 10 by popularity, 12-month rolling |

## Connections

- **Track-Release-Pipeline** — imports `file_parser.parse_folder_name` for folder name parsing
- **MCP Spotify Server** — shares Spotify OAuth credentials (same client ID/secret)
- **samwillsmixing.com** — playlists serve as portfolio/proof of work linked from website

## Recent Session History

### 2026-05-19 (Latest Session)
**Focus**: Full project build — modules, bootstrap, OAuth auth
**Completed**:
- Created project structure and pyproject.toml
- Built all 8 modules: config, spotify_client, state, folder_scanner, matcher, playlist_manager, cli, __main__
- Tested folder scanner — 231/234 folders parse correctly
- Installed dependencies (spotipy, python-dotenv, track-release-pipeline editable)
- Created all context files: AI_CONTEXT.md, TOOLBOX.md, memory.json, copilot-instructions.md, !SKILLS.md
- Initialized git repo with GitHub remote
- Fixed Spotify credentials in .env (client ID had "YOU" prefix, secret had "Y" prefix)
- Added `http://127.0.0.1:8888/callback` redirect URI to Spotify Developer Dashboard
- Completed OAuth flow — token cached at `~/.spotify-playlist-sync/.cache`
- Auth confirmed working: `python -m spotify_playlist_sync auth` → "Authenticated as: Sam Wills"

**Key Learnings**:
- The MCP Spotify .env had corrupted credentials (extra chars prepended) — now fixed
- spotipy can't open browser from Claude Code's shell — use manual auth flow (get URL, paste redirect)
- Auth codes expire fast — need to exchange within seconds of receiving

## Known Issues

- 3 folders fail to parse: `Hipp-E Strange Daze`, `Hipp-E Tunnels` (no artist-track separator), stray `2. Ongoing Stem Mixes` subfolder
- Multi-track folders (e.g. `Artist - Track A & Track B`) split logic not yet tested

## Upcoming Work

- Test full scan → review → add flow against Spotify
- Verify tracks appear in correct playlists with correct ordering
- Test Top 10 playlist rebuild with popularity sorting
- Add to Project Registry
