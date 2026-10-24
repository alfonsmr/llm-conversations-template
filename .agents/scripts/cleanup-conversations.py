#!/usr/bin/env python3
"""PreInvocation hook that syncs conversation subfolder names with UI titles and deletes orphaned folders."""

import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time

TRASH_RETENTION_SECONDS = 30 * 24 * 60 * 60  # 30 days


def move_to_trash(target_path: Path, trash_dir: Path, conv_id: str = "") -> Path | None:
    """Safely move a conversation folder into .trash/ and reset its mtime."""
    if not target_path.is_dir() or target_path.is_symlink():
        return None
    trash_dir.mkdir(parents=True, exist_ok=True)
    base_name = target_path.name
    dest = trash_dir / base_name
    # Avoid collisions if a folder with the same name is already in .trash/
    if dest.exists():
        suffix = f"{conv_id[:6]}_{int(time.time())}" if conv_id else str(int(time.time()))
        dest = trash_dir / f"{base_name}_{suffix}"
    shutil.move(str(target_path), str(dest))
    # Reset mtime to now so the 30-day countdown starts from deletion time
    os.utime(dest, None)
    return dest


def cleanup_trash(trash_dir: Path, max_age_seconds: int = TRASH_RETENTION_SECONDS) -> list[str]:
    """Permanently delete folders in .trash/ older than max_age_seconds."""
    if not trash_dir.is_dir() or trash_dir.is_symlink():
        return []
    now = time.time()
    purged: list[str] = []
    resolved_trash = trash_dir.resolve()
    for item in trash_dir.iterdir():
        try:
            # Never follow symlinks and verify item is a direct child of .trash/
            if item.is_symlink() or not item.is_dir():
                continue
            if item.resolve().parent != resolved_trash:
                continue
            age = now - item.stat().st_mtime
            if age > max_age_seconds:
                shutil.rmtree(item, ignore_errors=True)
                purged.append(item.name)
        except Exception:
            continue
    return purged


def slugify(title: str) -> str:
    """Convert a conversation UI title into a clean kebab-case folder name."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(slug) > 60:
        slug = slug[:60].rsplit("-", 1)[0] or slug[:60].strip("-")
    return slug


def normalize_subfolder(subfolder: str) -> str:
    """Normalize a subfolder value by stripping any leading 'conversations/' prefix and slashes."""
    if not isinstance(subfolder, str):
        return ""
    cleaned = subfolder.strip().strip("/")
    if cleaned.startswith("conversations/"):
        cleaned = cleaned[len("conversations/"):].strip("/")
    return cleaned


def load_conversation_titles(db_path: Path) -> dict[str, str]:
    """Read conversation_id -> title mappings from Antigravity's SQLite database."""
    if not db_path.is_file() or not os.access(db_path, os.R_OK):
        return {}
    try:
        uri = f"file:{db_path.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=2.0) as conn:
            cursor = conn.execute(
                "SELECT conversation_id, title FROM conversation_summaries WHERE title != ''"
            )
            return {row[0]: row[1] for row in cursor.fetchall() if row[0] and row[1]}
    except Exception:
        return {}


def is_safe_child(conversations_dir: Path, subfolder: str) -> Path | None:
    """Return resolved path if subfolder is a safe direct child of conversations_dir."""
    subfolder = normalize_subfolder(subfolder)
    if not subfolder:
        return None
    if "/" in subfolder or "\\" in subfolder or subfolder in (".", ".."):
        return None
    target = (conversations_dir / subfolder).resolve()
    if target.parent != conversations_dir.resolve():
        return None
    return target


def main() -> None:
    try:
        raw_input = sys.stdin.read()
        payload = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        payload = {}

    ephemeral_notes: list[str] = []
    user_visible_events: list[str] = []

    try:
        workspace_root = Path(__file__).resolve().parent.parent.parent
        conversations_dir = workspace_root / "conversations"
        trash_dir = workspace_root / ".trash"
        conversations_file = workspace_root / ".conversations.json"

        artifact_dir = payload.get("artifactDirectoryPath", "")
        if artifact_dir:
            brain_dir = Path(artifact_dir).resolve().parent
        else:
            brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"

        app_data_dir = brain_dir.parent
        db_path = app_data_dir / "conversation_summaries.db"
        titles = load_conversation_titles(db_path)

        current_conv_id = payload.get("conversationId", "")
        current_title = titles.get(current_conv_id, "")

        mappings: dict[str, str] = {}
        if conversations_file.is_file():
            loaded = json.loads(conversations_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                mappings = {k: normalize_subfolder(v) for k, v in loaded.items()}

        updated = False
        brain_accessible = brain_dir.is_dir() and os.access(brain_dir, os.R_OK)

        for conv_id, subfolder in list(mappings.items()):
            if not conv_id:
                continue

            # 1. Check if conversation was deleted -> move to .trash/
            if conv_id != current_conv_id and brain_accessible:
                conv_brain_path = brain_dir / conv_id
                if not conv_brain_path.exists():
                    target_path = is_safe_child(conversations_dir, subfolder)
                    if target_path and target_path.is_dir():
                        trashed_path = move_to_trash(target_path, trash_dir, conv_id)
                        if trashed_path:
                            user_visible_events.append(
                                f"Moved orphaned folder `conversations/{subfolder}/` to `.trash/{trashed_path.name}/` (conversation `{conv_id}` was deleted)."
                            )
                    del mappings[conv_id]
                    updated = True
                    continue

            # 2. Check if conversation was renamed in the UI
            ui_title = titles.get(conv_id, "").strip()
            if ui_title:
                desired_slug = slugify(ui_title)
                if desired_slug and desired_slug != subfolder:
                    conversations_dir.mkdir(parents=True, exist_ok=True)
                    old_path = is_safe_child(conversations_dir, subfolder)
                    new_path = is_safe_child(conversations_dir, desired_slug)

                    if new_path is not None:
                        if new_path.exists() and desired_slug in mappings.values():
                            desired_slug = f"{desired_slug}-{conv_id[:6]}"
                            new_path = is_safe_child(conversations_dir, desired_slug)

                    if new_path is not None:
                        if old_path and old_path.is_dir() and not new_path.exists():
                            old_path.rename(new_path)
                        mappings[conv_id] = desired_slug
                        updated = True
                        user_visible_events.append(
                            f"Renamed folder `conversations/{subfolder}/` -> `conversations/{desired_slug}/` (to match conversation title \"{ui_title}\")."
                        )

        # Purge .trash/ folders older than 30 days
        purged_folders = cleanup_trash(trash_dir)
        for folder_name in purged_folders:
            user_visible_events.append(
                f"Permanently deleted `.trash/{folder_name}/` (exceeded 30-day retention)."
            )

        if updated:
            conversations_file.write_text(
                json.dumps(mappings, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        if user_visible_events:
            events_str = " ".join(user_visible_events)
            ephemeral_notes.append(
                f"FOLDER_EVENT (MUST ANNOUNCE TO USER AT START OF RESPONSE): {events_str}"
            )

        if current_conv_id:
            assigned_folder = mappings.get(current_conv_id, "")
            if assigned_folder:
                ephemeral_notes.append(
                    f"Active workspace subfolder for this conversation ({current_conv_id}): 'conversations/{assigned_folder}'."
                )
            elif current_title:
                suggested = slugify(current_title)
                ephemeral_notes.append(
                    f"Current UI conversation title is '{current_title}'. If creating a subfolder for this conversation, create 'conversations/{suggested}' (and record '{suggested}' in .conversations.json)."
                )
    except Exception:
        pass

    if ephemeral_notes:
        print(
            json.dumps(
                {
                    "injectSteps": [
                        {"ephemeralMessage": " ".join(ephemeral_notes)}
                    ]
                }
            )
        )
    else:
        print("{}")


if __name__ == "__main__":
    main()
