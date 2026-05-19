import sqlite3
from datetime import datetime, timezone

from . import config


def _connect() -> sqlite3.Connection:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.STATE_DB))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    _init_tables(conn)
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS processed_folders (
            folder_path   TEXT PRIMARY KEY,
            folder_name   TEXT NOT NULL,
            source_type   TEXT NOT NULL,
            parsed_artist TEXT,
            parsed_track  TEXT,
            spotify_id    TEXT,
            status        TEXT NOT NULL DEFAULT 'pending',
            processed_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS added_tracks (
            spotify_id    TEXT NOT NULL,
            playlist_key  TEXT NOT NULL,
            added_at      TEXT NOT NULL,
            PRIMARY KEY (spotify_id, playlist_key)
        );

        CREATE TABLE IF NOT EXISTS run_log (
            run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at          TEXT NOT NULL,
            folders_scanned INTEGER DEFAULT 0,
            matched         INTEGER DEFAULT 0,
            added           INTEGER DEFAULT 0,
            skipped         INTEGER DEFAULT 0
        );
    """)


def is_folder_processed(folder_path: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT status FROM processed_folders WHERE folder_path = ?",
            (folder_path,),
        ).fetchone()
        if row is None:
            return False
        return row["status"] in ("added", "parse_failed")


def save_folder(
    folder_path: str,
    folder_name: str,
    source_type: str,
    parsed_artist: str | None,
    parsed_track: str | None,
    spotify_id: str | None,
    status: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO processed_folders
               (folder_path, folder_name, source_type, parsed_artist,
                parsed_track, spotify_id, status, processed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (folder_path, folder_name, source_type,
             parsed_artist, parsed_track, spotify_id, status, now),
        )


def record_track_added(spotify_id: str, playlist_key: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO added_tracks
               (spotify_id, playlist_key, added_at) VALUES (?, ?, ?)""",
            (spotify_id, playlist_key, now),
        )


def get_added_tracks(playlist_key: str, since_days: int | None = None) -> list[dict]:
    with _connect() as conn:
        if since_days is not None:
            rows = conn.execute(
                """SELECT spotify_id, added_at FROM added_tracks
                   WHERE playlist_key = ?
                   AND added_at >= datetime('now', ?)""",
                (playlist_key, f"-{since_days} days"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT spotify_id, added_at FROM added_tracks WHERE playlist_key = ?",
                (playlist_key,),
            ).fetchall()
        return [dict(r) for r in rows]


def log_run(folders_scanned: int, matched: int, added: int, skipped: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO run_log (run_at, folders_scanned, matched, added, skipped)
               VALUES (?, ?, ?, ?, ?)""",
            (now, folders_scanned, matched, added, skipped),
        )


def get_stats() -> dict:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM processed_folders").fetchone()[0]
        matched = conn.execute(
            "SELECT COUNT(*) FROM processed_folders WHERE status = 'added'"
        ).fetchone()[0]
        no_match = conn.execute(
            "SELECT COUNT(*) FROM processed_folders WHERE status = 'no_match'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM processed_folders WHERE status = 'pending_review'"
        ).fetchone()[0]
        added = conn.execute("SELECT COUNT(*) FROM added_tracks").fetchone()[0]
        last_run = conn.execute(
            "SELECT * FROM run_log ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
        return {
            "total_folders": total,
            "matched": matched,
            "no_match": no_match,
            "pending_review": pending,
            "total_added": added,
            "last_run": dict(last_run) if last_run else None,
        }


def clear_all() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM processed_folders")
        conn.execute("DELETE FROM added_tracks")
        conn.execute("DELETE FROM run_log")
