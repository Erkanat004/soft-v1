import axios from 'axios';
import { Project, Script, Scene, Character, Location, ProviderSetting, Job, FFmpegStatus } from './types';

export interface ReferenceAnalysis {
  duration_seconds: number;
  width: number;
  height: number;
  analyzed_seconds: number;
  detected_cuts: number;
  cuts_per_minute: number;
  pace: string;
  cut_times: number[];
  cut_detection_available: boolean;
}

export interface NicheAnalysis {
  sample_size: number;
  median_views_per_day: number;
  ranked_videos: { title: string; views: number; age_days: number; views_per_day: number; relative_to_median: number | null }[];
}

export interface LocalPreflight {
  ffmpeg_ready: boolean;
  ffprobe_ready: boolean;
  storage_ready: boolean;
  windows_voice_ready: boolean;
  free_disk_gb: number;
  text_key_configured: boolean;
  external_api_calls_made: boolean;
}

const API_BASE = '/api';

export function apiErrorMessage(error: unknown, fallback = 'Не удалось выполнить действие'): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (!error.response) return 'Нет связи с сервером. Проверьте, запущен ли backend.';
  }
  return fallback;
}

export const api = {
  downloadBackup: async (): Promise<Blob> => {
    const response = await axios.post(`${API_BASE}/backup/export`, {}, { responseType: 'blob', timeout: 300000 });
    return response.data;
  },
  getLocalPreflight: async (): Promise<LocalPreflight> => {
    const response = await axios.get(`${API_BASE}/settings/preflight`, { timeout: 30000 });
    return response.data;
  },
  analyzeReference: async (file: File): Promise<ReferenceAnalysis> => {
    const form = new FormData();
    form.append('file', file);
    const response = await axios.post(`${API_BASE}/research/reference-video`, form, { timeout: 150000 });
    return response.data;
  },
  analyzeNiche: async (videos: { title: string; views: number; age_days: number }[]): Promise<NicheAnalysis> => {
    const response = await axios.post(`${API_BASE}/research/niche`, { videos });
    return response.data;
  },
  // Projects
  listProjects: async (): Promise<Project[]> => {
    const res = await axios.get(`${API_BASE}/projects`);
    return res.data;
  },
  getProject: async (id: string): Promise<Project> => {
    const res = await axios.get(`${API_BASE}/projects/${id}`);
    return res.data;
  },
  createProject: async (payload: {
    name?: string;
    topic_or_script: string;
    input_type?: string;
    duration_preset?: string;
    language?: string;
    story_type?: string;
    visual_style?: string;
    creative_brief?: string;
    active_text_provider?: string;
    active_image_provider?: string;
    active_tts_provider?: string;
    aspect_ratio?: string;
    resolution?: string;
  }): Promise<Project> => {
    const res = await axios.post(`${API_BASE}/projects`, payload);
    return res.data;
  },
  createTestProject: async (): Promise<Project> => {
    const res = await axios.post(`${API_BASE}/projects/create-test`);
    return res.data;
  },
  updateProject: async (id: string, payload: Partial<Project>): Promise<Project> => {
    const res = await axios.patch(`${API_BASE}/projects/${id}`, payload);
    return res.data;
  },
  deleteProject: async (id: string): Promise<void> => {
    await axios.delete(`${API_BASE}/projects/${id}`);
  },
  clearAllProjects: async (): Promise<{ media_cleanup_warnings?: string[] }> => {
    const res = await axios.delete(`${API_BASE}/projects`);
    return res.data;
  },
  triggerAutoRemaining: async (id: string): Promise<Job> => {
    const res = await axios.post(`${API_BASE}/projects/${id}/auto-remaining`);
    return res.data;
  },
  triggerBatchTTS: async (id: string): Promise<Job> => {
    const res = await axios.post(`${API_BASE}/projects/${id}/batch-tts`);
    return res.data;
  },
  triggerBatchImages: async (id: string): Promise<Job> => {
    const res = await axios.post(`${API_BASE}/projects/${id}/batch-images`);
    return res.data;
  },
  triggerBatchClips: async (id: string): Promise<Job> => {
    const res = await axios.post(`${API_BASE}/projects/${id}/batch-clips`);
    return res.data;
  },
  exportProject: async (id: string): Promise<{ message: string; video_path: string }> => {
    const res = await axios.post(`${API_BASE}/projects/${id}/export`);
    return res.data;
  },
  getRenderStatus: async (id: string): Promise<{ exists: boolean; current: boolean }> => {
    const res = await axios.get(`${API_BASE}/projects/${id}/render/status`);
    return res.data;
  },

  // Script
  getScript: async (projectId: string): Promise<Script | null> => {
    const res = await axios.get(`${API_BASE}/projects/${projectId}/script`);
    return res.data;
  },
  updateScript: async (projectId: string, text: string): Promise<Script> => {
    const res = await axios.put(`${API_BASE}/projects/${projectId}/script`, { text, is_user_provided: true });
    return res.data;
  },
  enhanceScript: async (projectId: string, instruction: string): Promise<Script> => {
    const res = await axios.post(`${API_BASE}/projects/${projectId}/script/enhance?instruction=${encodeURIComponent(instruction)}`);
    return res.data;
  },
  decomposeScenes: async (projectId: string): Promise<Scene[]> => {
    const res = await axios.post(`${API_BASE}/projects/${projectId}/script/decompose`);
    return res.data;
  },

  // Storyboard Scenes CRUD & Media
  listScenes: async (projectId: string): Promise<Scene[]> => {
    const res = await axios.get(`${API_BASE}/projects/${projectId}/scenes`);
    return res.data;
  },
  addScene: async (projectId: string, narration: string, insertAfterUuid?: string): Promise<Scene> => {
    const res = await axios.post(`${API_BASE}/projects/${projectId}/scenes`, {
      narration,
      insert_after_uuid: insertAfterUuid
    });
    return res.data;
  },
  patchScene: async (sceneUuid: string, payload: Partial<Scene>): Promise<Scene> => {
    const res = await axios.patch(`${API_BASE}/scenes/${sceneUuid}`, payload);
    return res.data;
  },
  deleteScene: async (sceneUuid: string): Promise<void> => {
    await axios.delete(`${API_BASE}/scenes/${sceneUuid}`);
  },
  splitScene: async (sceneUuid: string, splitIndex?: number, splitText?: string): Promise<Scene[]> => {
    const res = await axios.post(`${API_BASE}/scenes/${sceneUuid}/split`, { split_index: splitIndex, split_text: splitText });
    return res.data;
  },
  mergeScenes: async (firstUuid: string, secondUuid: string): Promise<Scene> => {
    const res = await axios.post(`${API_BASE}/scenes/merge`, {
      first_scene_uuid: firstUuid,
      second_scene_uuid: secondUuid
    });
    return res.data;
  },
  reorderScenes: async (projectId: string, sceneUuids: string[]): Promise<Scene[]> => {
    const res = await axios.post(`${API_BASE}/projects/${projectId}/scenes/reorder`, { scene_uuids: sceneUuids });
    return res.data;
  },
  generateSceneImage: async (sceneUuid: string): Promise<Scene> => {
    const res = await axios.post(`${API_BASE}/scenes/${sceneUuid}/generate-image`);
    return res.data;
  },
  generateSceneTTS: async (sceneUuid: string): Promise<Scene> => {
    const res = await axios.post(`${API_BASE}/scenes/${sceneUuid}/generate-tts`);
    return res.data;
  },
  renderSceneClip: async (sceneUuid: string): Promise<Scene> => {
    const res = await axios.post(`${API_BASE}/scenes/${sceneUuid}/render-clip`);
    return res.data;
  },
  uploadSceneImage: async (sceneUuid: string, file: File): Promise<Scene> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await axios.post(`${API_BASE}/scenes/${sceneUuid}/upload-image`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },
  uploadSceneAudio: async (sceneUuid: string, file: File): Promise<Scene> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await axios.post(`${API_BASE}/scenes/${sceneUuid}/upload-audio`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return res.data;
  },

  // Characters & Locations
  listCharacters: async (projectId: string): Promise<Character[]> => {
    const res = await axios.get(`${API_BASE}/projects/${projectId}/characters`);
    return res.data;
  },
  listLocations: async (projectId: string): Promise<Location[]> => {
    const res = await axios.get(`${API_BASE}/projects/${projectId}/locations`);
    return res.data;
  },

  // Jobs
  getJobStatus: async (jobId: string): Promise<Job> => {
    const res = await axios.get(`${API_BASE}/jobs/${jobId}`, { timeout: 10000 });
    return res.data;
  },
  cancelJob: async (jobId: string): Promise<{ message: string }> => {
    const res = await axios.post(`${API_BASE}/jobs/${jobId}/cancel`);
    return res.data;
  },

  // Settings & Providers
  getProviders: async (): Promise<ProviderSetting[]> => {
    const res = await axios.get(`${API_BASE}/settings/providers`);
    return res.data;
  },
  saveProvider: async (payload: {
    provider_name: string;
    provider_type: string;
    is_enabled: boolean;
    model_id?: string;
    base_url?: string;
    endpoint?: string;
    voice_id?: string;
    extra_config_json?: string;
    api_key?: string;
    remember_key?: boolean;
  }): Promise<ProviderSetting> => {
    const res = await axios.post(`${API_BASE}/settings/providers`, payload);
    return res.data;
  },
  testProvider: async (providerName: string): Promise<{ connected: boolean; status: string; error?: string }> => {
    const res = await axios.post(`${API_BASE}/settings/providers/${providerName}/test`);
    return res.data;
  },
  getFFmpegStatus: async (): Promise<FFmpegStatus> => {
    const res = await axios.get(`${API_BASE}/settings/ffmpeg`);
    return res.data;
  },
  simulateApiError: async (errorCode: number | null): Promise<{ status: string; simulated_error: number | null }> => {
    const res = await axios.post(`${API_BASE}/settings/simulate-error`, { error_code: errorCode });
    return res.data;
  },
  getSimulatedApiError: async (): Promise<{ simulated_error: number | null }> => {
    const res = await axios.get(`${API_BASE}/settings/simulate-error`);
    return res.data;
  }
};
