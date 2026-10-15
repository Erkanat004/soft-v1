"""Restore a StoryForge archive to a NEW data directory; never overwrite data."""
import argparse
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath

MAX_UNCOMPRESSED_BYTES = 50 * 1024 ** 3
PATH_COLUMNS = {
    "projects": ("bg_music_path",),
    "scenes": ("audio_path", "image_path", "video_clip_path"),
    "characters": ("reference_image_path",),
    "locations": ("reference_image_path",),
    "image_variations": ("image_path",),
}


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (not path.is_absolute() and ".." not in path.parts and
            (name in {"manifest.json", "database.sqlite3"} or
             (len(path.parts) >= 3 and path.parts[0] == "projects" and
              path.parts[1].startswith("proj_") and all(path.parts))))


def _rewrite_media_paths(database: Path, old_root: str, new_root: Path) -> None:
    old_prefix = os.path.normpath(old_root).rstrip("\\/") + os.sep
    with closing(sqlite3.connect(database)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("База данных в архиве повреждена.")
        for table, columns in PATH_COLUMNS.items():
            for column in columns:
                for row_id, value in connection.execute(f"SELECT rowid, {column} FROM {table} WHERE {column} IS NOT NULL").fetchall():
                    original = os.path.normpath(str(value))
                    if not os.path.normcase(original).startswith(os.path.normcase(old_prefix)):
                        continue
                    relative = original[len(old_prefix):]
                    result = (new_root / relative).resolve()
                    if not result.is_relative_to(new_root.resolve()):
                        raise ValueError("В архиве найден опасный путь к медиафайлу.")
                    connection.execute(f"UPDATE {table} SET {column}=? WHERE rowid=?", (str(result), row_id))
        connection.commit()


def restore_archive(archive: Path, target: Path) -> Path:
    archive, target = archive.resolve(), target.resolve()
    if not archive.is_file():
        raise ValueError("Архив не найден.")
    if target.exists() or target == Path(target.anchor) or target == Path.home().resolve():
        raise ValueError("Укажите новую, ещё не существующую папку данных.")
    parent = target.parent
    if not parent.is_dir():
        raise ValueError("Родительская папка назначения не существует.")

    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        names = {item.filename for item in entries}
        if not {"manifest.json", "database.sqlite3"}.issubset(names):
            raise ValueError("Это не полная резервная копия StoryForge.")
        total_size = sum(item.file_size for item in entries)
        if len(entries) > 100000 or total_size > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Архив слишком большой.")
        if total_size > shutil.disk_usage(parent).free:
            raise ValueError("Недостаточно свободного места для восстановления.")
        if source.getinfo("manifest.json").file_size > 1024 * 1024:
            raise ValueError("Некорректный манифест резервной копии.")
        manifest = json.loads(source.read("manifest.json"))
        if manifest.get("format") != "storyforge-library" or manifest.get("version") != 1:
            raise ValueError("Версия резервной копии не поддерживается.")
        old_root = manifest.get("projects_root")
        if not isinstance(old_root, str) or not old_root:
            raise ValueError("В архиве не указан исходный путь проектов.")
        for item in entries:
            mode = item.external_attr >> 16
            if not _safe_member(item.filename) or stat.S_IFMT(mode) == stat.S_IFLNK:
                raise ValueError("В архиве найден недопустимый путь или ссылка.")

        stage = Path(tempfile.mkdtemp(prefix=".storyforge-restore-", dir=parent)).resolve()
        try:
            for item in entries:
                if item.is_dir() or item.filename == "manifest.json":
                    continue
                relative = Path("storyforge.db") if item.filename == "database.sqlite3" else Path(*PurePosixPath(item.filename).parts)
                destination = (stage / relative).resolve()
                if not destination.is_relative_to(stage):
                    raise ValueError("В архиве найден опасный путь.")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as reader, destination.open("xb") as writer:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
            _rewrite_media_paths(stage / "storyforge.db", old_root, stage / "projects")
            # Paths in the DB must point to the final directory, not staging.
            _rewrite_media_paths(stage / "storyforge.db", str(stage / "projects"), target / "projects")
            os.replace(stage, target)
        except BaseException:
            if stage.is_relative_to(parent.resolve()):
                shutil.rmtree(stage, ignore_errors=True)
            raise
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore StoryForge to a NEW directory")
    parser.add_argument("archive", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    restored = restore_archive(args.archive, args.target)
    print(f"Restored to {restored}. Start StoryForge with STORYFORGE_DATA_DIR set to this directory.")
