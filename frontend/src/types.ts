export interface Project {
  id: string;
  name: string;
  topic_or_script: string;
  input_type: 'auto' | 'topic' | 'full_script';
  duration_preset: string;
  language: string;
  story_type: string;
  visual_style: string;
  global_visual_style?: string;
  creative_brief?: string;
  status: 'draft' | 'generating' | 'completed' | 'failed';
  current_stage: string;
  error_message?: string;
  active_job_id?: string;
  active_text_provider: string;
  active_image_provider: string;
  active_tts_provider: string;
  aspect_ratio: string;
  resolution: string;
  default_voice_id?: string;
  subtitle_settings_json?: string;
  bg_music_path?: string;
  bg_music_volume?: number;
  is_test_project?: boolean;
  created_at: string;
  updated_at: string;
}

export interface Script {
  id: number;
  project_id: string;
  text: string;
  is_user_provided: boolean;
  created_at: string;
}

export interface Character {
  id: number;
  project_id: string;
  name: string;
  age?: string;
  gender?: string;
  hair?: string;
  eyes?: string;
  clothes?: string;
  appearance: string;
  reference_image_path?: string;
  is_auto_generated: boolean;
}

export interface Location {
  id: number;
  project_id: string;
  name: string;
  description: string;
  reference_image_path?: string;
  is_auto_generated: boolean;
}

export interface Scene {
  id: number;
  project_id: string;
  scene_uuid: string;
  scene_order: number;
  narration: string;
  shot_type: string;
  camera_motion: string;
  transition: string;
  image_prompt?: string;
  enhanced_prompt?: string;
  duration_target: number;
  actual_duration?: number;
  audio_path?: string;
  image_path?: string;
  video_clip_path?: string;
  image_status: 'not_created' | 'queued' | 'running' | 'completed' | 'outdated' | 'error' | 'cancelled';
  tts_status: 'not_created' | 'queued' | 'running' | 'completed' | 'outdated' | 'error' | 'cancelled';
  clip_status: 'not_created' | 'queued' | 'running' | 'completed' | 'outdated' | 'error' | 'cancelled';
  scene_type: 'static' | 'motion' | 'animation';
  voice_id?: string;
  audio_offset_start?: number;
  audio_offset_end?: number;
  input_version: number;
  image_prompt_needs_review?: boolean;
  error_message?: string;
  status?: string; // legacy fallback
  character_ids_json?: string;
  location_id?: number;
}

export interface ImageVariation {
  id: number;
  scene_uuid: string;
  image_path: string;
  prompt_used?: string;
  seed?: number;
  is_active: boolean;
  created_at: string;
}

export interface ProviderSetting {
  id: number;
  provider_name: string;
  provider_type: 'text' | 'image' | 'tts' | 'video' | 'custom';
  is_enabled: boolean;
  model_id?: string;
  base_url?: string;
  endpoint?: string;
  voice_id?: string;
  extra_config_json?: string;
  has_api_key: boolean;
}

export interface Job {
  id: string;
  project_id: string;
  scene_id?: number;
  job_type: string;
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused' | 'cancelled' | 'interrupted';
  progress_pct: number;
  checkpoint_stage: string;
  current_step_description?: string;
  error_message?: string;
  cancelled_at?: string;
  interrupted?: boolean;
  created_at: string;
  updated_at: string;
}

export interface FFmpegStatus {
  ffmpeg_installed: boolean;
  ffprobe_installed: boolean;
  ffmpeg_path: string;
  ffprobe_path: string;
}
