from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

# --- Project Schemas ---

class ProjectCreate(BaseModel):
    name: str = "Untitled Story Project"
    topic_or_script: str
    input_type: str = "auto"  # auto | topic | full_script
    duration_preset: str = "40"  # auto, 10, 20, 30, 40, 60
    language: str = "English"
    story_type: str = "Horror"
    visual_style: str = "Cinematic"
    creative_brief: Optional[str] = Field(default=None, max_length=4000)
    active_text_provider: Optional[str] = "gemini"
    active_image_provider: Optional[str] = "gemini_image"
    active_tts_provider: Optional[str] = "elevenlabs"
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    resolution: Literal["1080p", "720p"] = "1080p"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    language: Optional[str] = None
    story_type: Optional[str] = None
    visual_style: Optional[str] = None
    global_visual_style: Optional[str] = None
    creative_brief: Optional[str] = Field(default=None, max_length=4000)
    active_text_provider: Optional[str] = None
    active_image_provider: Optional[str] = None
    active_tts_provider: Optional[str] = None
    aspect_ratio: Optional[Literal["16:9", "9:16", "1:1"]] = None
    resolution: Optional[Literal["1080p", "720p"]] = None
    default_voice_id: Optional[str] = None
    subtitle_settings_json: Optional[str] = None
    bg_music_path: Optional[str] = None
    bg_music_volume: Optional[float] = None

class ProjectResponse(BaseModel):
    id: str
    name: str
    topic_or_script: str
    input_type: str
    duration_preset: str
    language: str
    story_type: str
    visual_style: str
    global_visual_style: Optional[str] = None
    creative_brief: Optional[str] = None
    status: str
    current_stage: str
    error_message: Optional[str] = None
    active_job_id: Optional[str] = None
    active_text_provider: str
    active_image_provider: str
    active_tts_provider: str
    aspect_ratio: str
    resolution: str
    is_test_project: Optional[bool] = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Script Schemas ---

class ScriptCreate(BaseModel):
    text: str
    is_user_provided: bool = False

class ScriptResponse(BaseModel):
    id: int
    project_id: str
    text: str
    is_user_provided: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Character & Location Schemas ---

class CharacterBase(BaseModel):
    name: str
    age: Optional[str] = None
    gender: Optional[str] = None
    hair: Optional[str] = None
    eyes: Optional[str] = None
    clothes: Optional[str] = None
    appearance: str

class CharacterCreate(CharacterBase):
    pass

class CharacterResponse(CharacterBase):
    id: int
    project_id: str
    reference_image_path: Optional[str] = None
    is_auto_generated: bool

    model_config = ConfigDict(from_attributes=True)

class LocationBase(BaseModel):
    name: str
    description: str

class LocationCreate(LocationBase):
    pass

class LocationResponse(LocationBase):
    id: int
    project_id: str
    reference_image_path: Optional[str] = None
    is_auto_generated: bool

    model_config = ConfigDict(from_attributes=True)

# --- Scene Schemas ---

class SceneResponse(BaseModel):
    id: int
    project_id: str
    scene_uuid: Optional[str] = None
    scene_order: int
    narration: str
    shot_type: str
    camera_motion: str
    transition: str
    image_prompt: Optional[str] = None
    enhanced_prompt: Optional[str] = None
    duration_target: float
    actual_duration: Optional[float] = None
    audio_path: Optional[str] = None
    audio_offset_start: float = 0.0
    audio_offset_end: float = 0.0
    image_path: Optional[str] = None
    video_clip_path: Optional[str] = None
    status: str
    image_status: Optional[str] = "not_created"
    tts_status: Optional[str] = "not_created"
    clip_status: Optional[str] = "not_created"
    scene_type: Optional[str] = "motion"
    voice_id: Optional[str] = None
    input_version: int = 1
    image_prompt_needs_review: bool = False
    error_message: Optional[str] = None
    character_ids_json: str
    location_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class SceneUpdate(BaseModel):
    narration: Optional[str] = None
    shot_type: Optional[str] = None
    camera_motion: Optional[str] = None
    transition: Optional[str] = None
    image_prompt: Optional[str] = None

# --- Provider Setting Schemas ---

class ProviderSettingBase(BaseModel):
    provider_name: str
    provider_type: str  # text, image, tts, video, custom
    is_enabled: bool = True
    model_id: Optional[str] = None
    base_url: Optional[str] = None
    endpoint: Optional[str] = None
    voice_id: Optional[str] = None
    extra_config_json: Optional[str] = "{}"
    api_key: Optional[str] = None  # Key is accepted on input, but NEVER stored in DB or returned

class ProviderSettingCreate(ProviderSettingBase):
    remember_key: bool = True

class ProviderSettingResponse(BaseModel):
    id: int
    provider_name: str
    provider_type: str
    is_enabled: bool
    model_id: Optional[str] = None
    base_url: Optional[str] = None
    endpoint: Optional[str] = None
    voice_id: Optional[str] = None
    extra_config_json: Optional[str] = "{}"
    has_api_key: bool = False  # Tells frontend key is set without revealing secret string

    model_config = ConfigDict(from_attributes=True)

# --- Job & Progress Schemas ---

class JobResponse(BaseModel):
    id: str
    project_id: str
    job_type: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    status: str
    progress_pct: float
    checkpoint_stage: str
    current_step_description: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
