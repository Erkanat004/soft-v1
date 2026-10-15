import datetime
import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now() -> datetime.datetime:
    """Return naive UTC for compatibility with existing SQLite DateTime rows."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    topic_or_script = Column(Text, nullable=False)
    input_type = Column(String, default="auto")  # topic | full_script | auto
    duration_preset = Column(String, default="30")  # 10, 20, 30, 40, 60, 90, auto
    language = Column(String, default="English")  # English, Russian, Custom, Auto
    story_type = Column(String, default="Horror")  # Horror, Mystery, Reddit, Crime, etc.
    visual_style = Column(String, default="Cinematic")  # Cinematic, Realistic, Dark, Illustration, Auto
    global_visual_style = Column(Text, nullable=True)
    creative_brief = Column(Text, nullable=True)
    status = Column(String, default="draft")  # draft, generating, completed, failed
    current_stage = Column(String, default="idle")  # idle, script, bibles, scenes, tts, images, render, completed, failed
    error_message = Column(Text, nullable=True)
    active_job_id = Column(String, nullable=True)
    active_text_provider = Column(String, default="gemini")
    active_image_provider = Column(String, default="gemini_image")
    active_tts_provider = Column(String, default="elevenlabs")
    aspect_ratio = Column(String, default="16:9")  # 16:9 | 9:16 | 1:1
    resolution = Column(String, default="1080p")  # 1080p | 720p (legacy WxH values are also supported)
    default_voice_id = Column(String, nullable=True)
    subtitle_settings_json = Column(Text, nullable=True)
    bg_music_path = Column(String, nullable=True)
    bg_music_volume = Column(Float, default=0.08)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    is_test_project = Column(Boolean, default=False)

    script = relationship("Script", uselist=False, back_populates="project", cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan", order_by="Scene.scene_order")
    characters = relationship("Character", back_populates="project", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="project", cascade="all, delete-orphan")
    image_variations = relationship("ImageVariation", back_populates="project", cascade="all, delete-orphan")

class Script(Base):
    __tablename__ = "scripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    text = Column(Text, nullable=False)
    is_user_provided = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    project = relationship("Project", back_populates="script")

class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    age = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    hair = Column(String, nullable=True)
    eyes = Column(String, nullable=True)
    clothes = Column(String, nullable=True)
    appearance = Column(Text, nullable=False)
    reference_image_path = Column(String, nullable=True)
    is_auto_generated = Column(Boolean, default=True)

    project = relationship("Project", back_populates="characters")

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    reference_image_path = Column(String, nullable=True)
    is_auto_generated = Column(Boolean, default=True)

    project = relationship("Project", back_populates="locations")

class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_uuid = Column(String, default=lambda: uuid.uuid4().hex, index=True, nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    scene_order = Column(Integer, nullable=False)
    narration = Column(Text, nullable=False)
    shot_type = Column(String, default="Medium Shot")  # Establishing, Wide, Medium, Close-Up, POV, Low Angle, etc.
    camera_motion = Column(String, default="slow_zoom_in")  # static, slow_zoom_in, slow_zoom_out, pan_left, pan_right, etc.
    scene_type = Column(String, default="motion")  # static | motion | animation
    transition = Column(String, default="crossfade")
    image_prompt = Column(Text, nullable=True)
    enhanced_prompt = Column(Text, nullable=True)
    duration_target = Column(Float, default=15.0)
    actual_duration = Column(Float, nullable=True)
    audio_path = Column(String, nullable=True)
    audio_offset_start = Column(Float, default=0.0)
    audio_offset_end = Column(Float, default=0.0)
    image_path = Column(String, nullable=True)
    video_clip_path = Column(String, nullable=True)
    voice_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # Legacy field preserved for backward compat
    image_status = Column(String, default="not_created")  # not_created, queued, running, completed, outdated, error, cancelled
    tts_status = Column(String, default="not_created")    # not_created, queued, running, completed, outdated, error, cancelled
    clip_status = Column(String, default="not_created")   # not_created, queued, running, completed, outdated, error, cancelled
    image_prompt_needs_review = Column(Boolean, default=False)
    input_version = Column(Integer, default=1)
    character_ids_json = Column(Text, default="[]")
    location_id = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    project = relationship("Project", back_populates="scenes")

class ImageVariation(Base):
    __tablename__ = "image_variations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scene_uuid = Column(String, index=True, nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    image_path = Column(String, nullable=False)
    prompt_used = Column(Text, nullable=True)
    seed = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    project = relationship("Project", back_populates="image_variations")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    job_type = Column(String, nullable=False)  # auto_pipeline, generate_images, generate_tts, render, scene_task
    scene_id = Column(String, nullable=True)
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending, running, completed, failed, paused, cancelled, interrupted
    progress_pct = Column(Float, default=0.0)
    checkpoint_stage = Column(String, default="idle")
    current_step_description = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    interrupted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

class ProviderSetting(Base):
    __tablename__ = "provider_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_name = Column(String, unique=True, nullable=False)  # e.g., gemini, openai, elevenlabs, custom_1
    provider_type = Column(String, nullable=False)  # text, image, tts, video, custom
    is_enabled = Column(Boolean, default=True)
    model_id = Column(String, nullable=True)
    base_url = Column(String, nullable=True)
    endpoint = Column(String, nullable=True)
    voice_id = Column(String, nullable=True)
    extra_config_json = Column(Text, default="{}")
