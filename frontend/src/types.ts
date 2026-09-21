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
  status: 'draft' | 'generating' | 'completed' | 'failed';
  current_stage: string;
  error_message?: string;
  active_job_id?: string;
  active_text_provider: string;
  active_image_provider: string;
  active_tts_provider: string;
  aspect_ratio: string;
  resolution: string;
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
  status: 'pending' | 'tts_done' | 'image_done' | 'clip_done' | 'failed';
  character_ids_json: string;
  location_id?: number;
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
  job_type: string;
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'paused' | 'cancelled';
  progress_pct: number;
  checkpoint_stage: string;
  current_step_description?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface FFmpegStatus {
  ffmpeg_installed: boolean;
  ffprobe_installed: boolean;
  ffmpeg_path: string;
  ffprobe_path: string;
}
