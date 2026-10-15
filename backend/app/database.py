import uuid
import sqlite3
from contextlib import closing
from datetime import datetime, UTC
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL, DB_PATH, BACKUPS_DIR

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def backup_database_before_migration():
    """One recoverable SQLite snapshot before upgrading an existing database."""
    if not DB_PATH.is_file() or DB_PATH.stat().st_size == 0:
        return None
    with closing(sqlite3.connect(DB_PATH)) as source:
        tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "projects" not in tables or source.execute("PRAGMA user_version").fetchone()[0] >= 1:
            return None
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        destination = BACKUPS_DIR / f"before-schema-v1-{datetime.now(UTC):%Y%m%d-%H%M%S-%f}.sqlite3"
        try:
            with closing(sqlite3.connect(destination)) as target:
                source.backup(target)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return destination

def run_db_migrations():
    """
    Safely migrates existing SQLite tables by adding any missing columns without data loss.
    """
    with engine.connect() as conn:
        # Check projects table columns
        res = conn.execute(text("PRAGMA table_info(projects)")).fetchall()
        p_cols = {row[1] for row in res} if res else set()

        if p_cols:
            if "active_job_id" not in p_cols:
                conn.execute(text("ALTER TABLE projects ADD COLUMN active_job_id VARCHAR"))
            if "default_voice_id" not in p_cols:
                conn.execute(text("ALTER TABLE projects ADD COLUMN default_voice_id VARCHAR"))
            if "subtitle_settings_json" not in p_cols:
                conn.execute(text("ALTER TABLE projects ADD COLUMN subtitle_settings_json TEXT"))
            if "bg_music_path" not in p_cols:
                conn.execute(text("ALTER TABLE projects ADD COLUMN bg_music_path VARCHAR"))
            if "bg_music_volume" not in p_cols:
                conn.execute(text("ALTER TABLE projects ADD COLUMN bg_music_volume FLOAT DEFAULT 0.08"))
            if "is_test_project" not in p_cols:
                conn.execute(text("ALTER TABLE projects ADD COLUMN is_test_project BOOLEAN DEFAULT 0"))
            if "creative_brief" not in p_cols:
                conn.execute(text("ALTER TABLE projects ADD COLUMN creative_brief TEXT"))

        # Check scenes table columns
        res_sc = conn.execute(text("PRAGMA table_info(scenes)")).fetchall()
        sc_cols = {row[1] for row in res_sc} if res_sc else set()

        if sc_cols:
            if "scene_uuid" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN scene_uuid VARCHAR"))
            if "image_status" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN image_status VARCHAR DEFAULT 'not_created'"))
            if "tts_status" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN tts_status VARCHAR DEFAULT 'not_created'"))
            if "clip_status" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN clip_status VARCHAR DEFAULT 'not_created'"))
            if "scene_type" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN scene_type VARCHAR DEFAULT 'motion'"))
            if "voice_id" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN voice_id VARCHAR"))
            if "audio_offset_start" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN audio_offset_start FLOAT DEFAULT 0.0"))
            if "audio_offset_end" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN audio_offset_end FLOAT DEFAULT 0.0"))
            if "image_prompt_needs_review" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN image_prompt_needs_review BOOLEAN DEFAULT 0"))
            if "input_version" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN input_version INTEGER DEFAULT 1"))
            if "error_message" not in sc_cols:
                conn.execute(text("ALTER TABLE scenes ADD COLUMN error_message TEXT"))

        # Check jobs table columns
        res_j = conn.execute(text("PRAGMA table_info(jobs)")).fetchall()
        j_cols = {row[1] for row in res_j} if res_j else set()
        if j_cols:
            if "cancelled_at" not in j_cols:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN cancelled_at DATETIME"))
            if "interrupted" not in j_cols:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN interrupted BOOLEAN DEFAULT 0"))
            if "scene_id" not in j_cols:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN scene_id VARCHAR"))

        conn.execute(text("PRAGMA user_version=1"))
        conn.commit()

    # Assign UUIDs to any scenes missing scene_uuid
    with SessionLocal() as db:
        from app.models import Scene
        scenes_without_uuid = db.query(Scene).filter((Scene.scene_uuid == None) | (Scene.scene_uuid == "")).all()
        for sc in scenes_without_uuid:
            sc.scene_uuid = uuid.uuid4().hex
        if scenes_without_uuid:
            db.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
