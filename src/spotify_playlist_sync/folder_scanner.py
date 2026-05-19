from datetime import datetime, timezone
from pathlib import Path

from track_release_pipeline.file_parser import parse_folder_name

from . import config
from . import state


def _folder_created_at(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_ctime, tz=timezone.utc)


def _folder_age_days(path: Path) -> int:
    return (datetime.now(timezone.utc) - _folder_created_at(path)).days


def scan_all(skip_processed: bool = True) -> list[dict]:
    """Scan all source directories and return parsed folder metadata.

    Each result dict has: folder_path, folder_name, source_type,
    artist, track, remixer, label, folder_age_days.
    """
    results = []
    for source_type, source_dir in config.SOURCE_DIRS.items():
        if not source_dir.exists():
            print(f"  [WARN] Source dir not found: {source_dir}")
            continue
        folders = sorted(
            p for p in source_dir.iterdir() if p.is_dir()
        )
        print(f"  Scanning {source_dir.name}... {len(folders)} folders")
        for folder in folders:
            folder_path = str(folder)
            if skip_processed and state.is_folder_processed(folder_path):
                continue
            parsed = parse_folder_name(folder_path)
            if parsed is None:
                print(f"  [SKIP] Could not parse: {folder.name}")
                state.save_folder(
                    folder_path, folder.name, source_type,
                    None, None, None, "parse_failed",
                )
                continue
            results.append({
                "folder_path": folder_path,
                "folder_name": folder.name,
                "source_type": source_type,
                "artist": parsed["artist"],
                "track": parsed["track"],
                "remixer": parsed.get("remixer"),
                "label": parsed.get("label"),
                "folder_age_days": _folder_age_days(folder),
            })
    return results
