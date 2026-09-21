import axios from 'axios';
import { Project, Script, Scene, Character, Location, ProviderSetting, Job, FFmpegStatus } from './types';

const API_BASE = '/api';

export const api = {
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
    active_text_provider?: string;
    active_image_provider?: string;
    active_tts_provider?: string;
  }): Promise<Project> => {
    const res = await axios.post(`${API_BASE}/projects`, payload);
    return res.data;
  },
  updateProject: async (id: string, payload: Partial<Project>): Promise<Project> => {
    const res = await axios.patch(`${API_BASE}/projects/${id}`, payload);
    return res.data;
  },
  deleteProject: async (id: string): Promise<void> => {
    await axios.delete(`${API_BASE}/projects/${id}`);
  },
  clearAllProjects: async (): Promise<void> => {
    await axios.delete(`${API_BASE}/projects`);
  },
  triggerAutoPipeline: async (id: string): Promise<Job> => {
    const res = await axios.post(`${API_BASE}/projects/${id}/generate`);
    return res.data;
  },

  // Script
  getScript: async (projectId: string): Promise<Script> => {
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

  // Storyboard Scenes
  listScenes: async (projectId: string): Promise<Scene[]> => {
    const res = await axios.get(`${API_BASE}/projects/${projectId}/scenes`);
    return res.data;
  },
  updateScene: async (projectId: string, sceneId: number, payload: Partial<Scene>): Promise<Scene> => {
    const res = await axios.patch(`${API_BASE}/projects/${projectId}/scenes/${sceneId}`, payload);
    return res.data;
  },
  regenerateSceneImage: async (projectId: string, sceneId: number): Promise<Scene> => {
    const res = await axios.post(`${API_BASE}/projects/${projectId}/scenes/${sceneId}/regenerate_image`);
    return res.data;
  },
  regenerateSceneTTS: async (projectId: string, sceneId: number): Promise<Scene> => {
    const res = await axios.post(`${API_BASE}/projects/${projectId}/scenes/${sceneId}/regenerate_tts`);
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
    const res = await axios.get(`${API_BASE}/jobs/${jobId}`);
    return res.data;
  },
  retryFailedTasks: async (jobId: string): Promise<Job> => {
    const res = await axios.post(`${API_BASE}/jobs/${jobId}/retry_failed`);
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

  // Render & Export
  startRender: async (projectId: string): Promise<{ status: string; output_path: string }> => {
    const res = await axios.post(`${API_BASE}/projects/${projectId}/render`);
    return res.data;
  }
};
