# Toolbox — Spotify Playlist Sync

## Module Inventory

### config.py
- **Path**: `src/spotify_playlist_sync/config.py`
- **Purpose**: Central configuration — env loading, source paths, playlist names, constants
- **Key Exports**: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SOURCE_DIRS`, `PLAYLIST_NAMES`, `PLAYLIST_SOURCES`, `STATE_DB`, `TOKEN_CACHE`
- **Dependencies**: `python-dotenv`

### spotify_client.py
- **Path**: `src/spotify_playlist_sync/spotify_client.py`
- **Purpose**: Spotipy OAuth wrapper and playlist utility functions
- **Key Exports**: `get_client()`, `find_playlist_id()`, `get_playlist_track_ids()`
- **Dependencies**: `spotipy`, `config`

### state.py
- **Path**: `src/spotify_playlist_sync/state.py`
- **Purpose**: SQLite state management — tracks processed folders, added tracks, run history
- **Key Exports**: `is_folder_processed()`, `save_folder()`, `record_track_added()`, `get_added_tracks()`, `log_run()`, `get_stats()`, `clear_all()`
- **Dependencies**: `config` (for DB path)
- **Tables**: `processed_folders`, `added_tracks`, `run_log`

### folder_scanner.py
- **Path**: `src/spotify_playlist_sync/folder_scanner.py`
- **Purpose**: Walks source directories and parses folder names into track metadata
- **Key Exports**: `scan_all(skip_processed=True)`
- **Dependencies**: `track_release_pipeline.file_parser`, `config`, `state`

### matcher.py
- **Path**: `src/spotify_playlist_sync/matcher.py`
- **Purpose**: Spotify search with fuzzy matching and confidence scoring
- **Key Exports**: `search_track()`, `classify_match()`
- **Dependencies**: `spotipy`, `config`, `difflib`
- **Match Tiers**: auto_approved (>=0.7), needs_review (0.4-0.7), no_match (<0.4)

### playlist_manager.py
- **Path**: `src/spotify_playlist_sync/playlist_manager.py`
- **Purpose**: Playlist CRUD — find by name, read tracks, add at top, replace, popularity sorting
- **Key Exports**: `resolve_playlists()`, `add_tracks_to_top()`, `replace_playlist()`, `get_popularity()`, `sync_main_playlist()`, `sync_top10_playlist()`
- **Dependencies**: `spotipy`, `config`, `state`, `spotify_client`

### cli.py
- **Path**: `src/spotify_playlist_sync/cli.py`
- **Purpose**: CLI entry point with argparse — all user-facing commands
- **Key Exports**: `main()`, `cmd_auth()`, `cmd_scan()`, `cmd_review()`, `cmd_add()`, `cmd_status()`, `cmd_rescan()`
- **Dependencies**: All other modules
- **Commands**: `auth`, `scan`, `review`, `add`, `status`, `rescan`

## External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `spotipy` | >=2.24.0 | Spotify Web API wrapper |
| `python-dotenv` | >=1.0.0 | Load .env files |
| `track-release-pipeline` | 0.1.0 (editable) | Folder name parser (`file_parser.parse_folder_name`) |
