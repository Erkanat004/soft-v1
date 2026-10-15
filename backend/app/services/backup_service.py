"""Consistent local library archives; API credentials remain in Windows keyring."""
import json
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, UTC
from pathlib import Path

from app.config import BACKUPS_DIR, DB_PATH, PROJECTS_DIR
from app.database import SessionLocal
from app.models import Job, Project


def create_library_archive() -> Path:
    with SessionLocal() as db:
        if db.query(Job.id).filter(Job.status.in_(("pending", "running"))).first():
            raise ValueError("Дождитесь завершения текущей задачи перед созданием копии.")
        project_ids = [project_id for (project_id,) in db.query(Project.id).all()]

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = None
    snapshot_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="storyforge-db-", suffix=".sqlite3", dir=BACKUPS_DIR, delete=False) as snapshot:
            snapshot_path = Path(snapshot.name)
        with closing(sqlite3.connect(DB_PATH)) as source, closing(sqlite3.connect(snapshot_path)) as destination:
            source.backup(destination)

        with tempfile.NamedTemporaryFile(prefix="storyforge-export-", suffix=".zip", dir=BACKUPS_DIR, delete=False) as archive:
            archive_path = Path(archive.name)
        with zipfile.ZipFile(archive_path, "w", allowZip64=True) as output:
            output.writestr("manifest.json", json.dumps({
                "format": "storyforge-library", "version": 1,
                "created_at_utc": datetime.now(UTC).isoformat(),
                "project_count": len(project_ids), "api_keys_included": False,
                "projects_root": str(PROJECTS_DIR),
                "external_media_included": False,
            }, ensure_ascii=False), compress_type=zipfile.ZIP_DEFLATED)
            output.write(snapshot_path, "database.sqlite3", compress_type=zipfile.ZIP_DEFLATED)
            for project_id in project_ids:
                candidate = PROJECTS_DIR / project_id
                directory = candidate.resolve()
                if candidate.is_symlink() or not directory.is_relative_to(PROJECTS_DIR) or not directory.is_dir():
                    continue
                for path in directory.rglob("*"):
                    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(directory):
                        continue
                    output.write(path, (Path("projects") / project_id / path.relative_to(directory)).as_posix(),
                                 compress_type=zipfile.ZIP_STORED)
        return archive_path
    except BaseException:
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)
        raise
    finally:
        if snapshot_path is not None:
            snapshot_path.unlink(missing_ok=True)
