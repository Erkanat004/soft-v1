import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    topic_or_script = Column(Text, nullable=False)
    input_type = Column(String, default="auto")  # topic | full_script | auto
    duration_preset = Column(String, default="40")  # 10, 20, 30, 40, 60, auto
    language = Column(String, default="English")  # English, Russian, Custom, Auto
    story_type = Column(String, default="Horror")  # Horror, Mystery, Reddit, Crime, etc.
    visual_style = Column(String, default="Cinematic")  # Cinematic, Realistic, Dark, Illustration, Auto
    global_visual_style = Column(Text, nullable=True)
    status = Column(String, default="draft")  # draft, generating, completed, failed
    current_stage = Column(String, default="idle")  # idle, script, bibles, scenes, tts, images, render, completed, failed
    error_message = Column(Text, nullable=True)
    active_job_id = Column(String, nullable=True)
    active_text_provider = Column(String, default="gemini")
    active_image_provider = Column(String, default="gemini_image")
    active_tts_provider = Column(String, default="elevenlabs")
    aspect_ratio = Column(String, default="16:9")
    resolution = Column(String, default="1920x1080")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    script = relationship("Script", uselist=False, back_populates="project", cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan", order_by="Scene.scene_order")
    characters = relationship("Character", back_populates="project", cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="project", cascade="all, delete-orphan")

class Script(Base):
    __tablename__ = "scripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    text = Column(Text, nullable=False)
    is_user_provided = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

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
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    scene_order = Column(Integer, nullable=False)
    narration = Column(Text, nullable=False)
    shot_type = Column(String, default="Medium Shot")  # Establishing, Wide, Medium, Close-Up, POV, Low Angle, etc.
    camera_motion = Column(String, default="random_cinematic")
    transition = Column(String, default="crossfade")
    image_prompt = Column(Text, nullable=True)
    enhanced_prompt = Column(Text, nullable=True)
    duration_target = Column(Float, default=15.0)
    actual_duration = Column(Float, nullable=True)
    audio_path = Column(String, nullable=True)
    image_path = Column(String, nullable=True)
    video_clip_path = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, tts_done, image_done, clip_done, failed
    character_ids_json = Column(Text, default="[]")
    location_id = Column(Integer, nullable=True)

    project = relationship("Project", back_populates="scenes")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    job_type = Column(String, nullable=False)  # auto_pipeline, generate_images, generate_tts, render
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending, running, completed, failed, paused, cancelled
    progress_pct = Column(Float, default=0.0)
    checkpoint_stage = Column(String, default="idle")
    current_step_description = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

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
