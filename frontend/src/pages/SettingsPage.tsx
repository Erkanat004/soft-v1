import React, { useEffect, useState } from 'react';
import { ProviderSetting, FFmpegStatus } from '../types';
import { api } from '../api';
import { Key, Server, Plus, CheckCircle2, AlertCircle, ShieldCheck, Cpu } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [providers, setProviders] = useState<ProviderSetting[]>([]);
  const [ffmpegStatus, setFFmpegStatus] = useState<FFmpegStatus | null>(null);
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});
  const [rememberKeyMap, setRememberKeyMap] = useState<Record<string, boolean>>({});
  const [showAddModal, setShowAddModal] = useState(false);
  
  // Custom Provider Form State
  const [customName, setCustomName] = useState('');
  const [customType, setCustomType] = useState<'text' | 'image' | 'tts'>('text');
  const [customBaseUrl, setCustomBaseUrl] = useState('');
  const [customModelId, setCustomModelId] = useState('');
  const [customApiKey, setCustomApiKey] = useState('');

  const loadSettings = async () => {
    try {
      const pData = await api.getProviders();
      setProviders(pData);

      const fData = await api.getFFmpegStatus();
      setFFmpegStatus(fData);
    } catch (err) {
      console.error("Failed to load settings:", err);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleSaveProvider = async (p: ProviderSetting) => {
    try {
      const apiKey = keyInputs[p.provider_name];
      const remember = rememberKeyMap[p.provider_name] ?? true;

      await api.saveProvider({
        provider_name: p.provider_name,
        provider_type: p.provider_type,
        is_enabled: p.is_enabled,
        model_id: p.model_id,
        base_url: p.base_url,
        endpoint: p.endpoint,
        voice_id: p.voice_id,
        extra_config_json: p.extra_config_json,
        api_key: apiKey !== undefined ? apiKey : undefined,
        remember_key: remember
      });

      alert(`Saved settings for ${p.provider_name}`);
      loadSettings();
    } catch (err) {
      console.error("Save error:", err);
      alert("Failed to save provider settings.");
    }
  };

  const handleTestConnection = async (name: string) => {
    try {
      const res = await api.testProvider(name);
      if (res.connected) {
        alert(`✅ ${name} connection successful!`);
      } else {
        alert(`❌ ${name} connection failed: ${res.error || 'Check API Key'}`);
      }
    } catch (err) {
      alert(`Connection test error for ${name}`);
    }
  };

  const handleAddCustomProvider = async () => {
    if (!customName.trim() || !customBaseUrl.trim()) return;

    try {
      await api.saveProvider({
        provider_name: customName.trim().toLowerCase(),
        provider_type: customType,
        is_enabled: true,
        model_id: customModelId || 'default',
        base_url: customBaseUrl.trim(),
        api_key: customApiKey.trim() || undefined,
        remember_key: true
      });

      setShowAddModal(false);
      setCustomName('');
      setCustomBaseUrl('');
      setCustomModelId('');
      setCustomApiKey('');
      loadSettings();
    } catch (err) {
      alert("Failed to add custom provider.");
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-6 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-dark-700 pb-5">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Key className="w-6 h-6 text-purple-400" />
            <span>API Providers & Credentials</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            API keys are saved in Windows Credential Manager via Keyring. Keys are never stored in SQLite database, project files, or Git.
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded-xl text-xs flex items-center gap-2 shadow-lg shadow-purple-900/30 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>+ Add Provider</span>
        </button>
      </div>

      {/* FFmpeg Detection Card */}
      <div className="bg-dark-800 border border-dark-700 rounded-2xl p-5 flex items-center justify-between shadow-md">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-cyan-950/60 border border-cyan-800/50 text-cyan-400 flex items-center justify-center">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">Local FFmpeg & FFprobe Status</h4>
            <p className="text-xs text-slate-400">Required for camera motion filters, audio probing, and local MP4 render.</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 ${
            ffmpegStatus?.ffmpeg_installed ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40' : 'bg-red-950/60 text-red-400 border border-red-800/40'
          }`}>
            {ffmpegStatus?.ffmpeg_installed ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
            <span>FFmpeg: {ffmpegStatus?.ffmpeg_installed ? 'Detected' : 'Missing'}</span>
          </div>

          <div className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 ${
            ffmpegStatus?.ffprobe_installed ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/40' : 'bg-red-950/60 text-red-400 border border-red-800/40'
          }`}>
            {ffmpegStatus?.ffprobe_installed ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
            <span>FFprobe: {ffmpegStatus?.ffprobe_installed ? 'Detected' : 'Missing'}</span>
          </div>
        </div>
      </div>

      {/* Provider List Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {providers.map(p => (
          <div key={p.id} className="bg-dark-800 border border-dark-700 rounded-2xl p-5 space-y-4 shadow-xl">
            {/* Title & Enable Switch */}
            <div className="flex items-center justify-between border-b border-dark-700/60 pb-3">
              <div className="flex items-center gap-2.5">
                <Server className="w-4 h-4 text-purple-400" />
                <h3 className="font-bold text-sm text-white capitalize">{p.provider_name}</h3>
                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-dark-700 text-slate-400">
                  {p.provider_type}
                </span>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-xs text-slate-400">Enabled</span>
                <input
                  type="checkbox"
                  checked={p.is_enabled}
                  onChange={(e) => {
                    const updated = { ...p, is_enabled: e.target.checked };
                    setProviders(providers.map(pr => pr.id === p.id ? updated : pr));
                  }}
                  className="rounded border-dark-600 bg-dark-900 text-purple-600 focus:ring-purple-500"
                />
              </label>
            </div>

            {/* Fields */}
            <div className="space-y-3">
              {(p.provider_name === 'local_cards' || p.provider_name === 'windows_tts') && (
                <p className="text-xs text-amber-300">
                  {p.provider_name === 'local_cards'
                    ? 'Локальные карточки по описанию сцены: бесплатно, без AI-иллюстраций и без ключа.'
                    : 'Озвучка установленными голосами Windows: бесплатно и без ключа.'}
                </p>
              )}
              {/* API Key Input */}
              {p.provider_name !== 'local_cards' && p.provider_name !== 'windows_tts' && <div className="space-y-1">
                <div className="flex justify-between items-center text-xs text-slate-400">
                  <span className="flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                    <span>API Key</span>
                  </span>
                  {p.has_api_key && <span className="text-[10px] text-emerald-400 font-semibold">✓ KEY STORED SECURELY</span>}
                </div>
                <input
                  type="password"
                  placeholder={p.has_api_key ? "••••••••••••••••••••" : "Enter API key"}
                  value={keyInputs[p.provider_name] ?? ''}
                  onChange={(e) => setKeyInputs({ ...keyInputs, [p.provider_name]: e.target.value })}
                  className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-purple-500"
                />
              </div>}

              {/* Editable Model ID */}
              {p.provider_name.startsWith('gemini') && (
                <p className="text-xs text-slate-400">
                  Если прежняя модель недоступна, укажите <strong>auto</strong> и нажмите Save.
                  Доступная модель будет определяться через API; квоты провайдера сохраняются.
                </p>
              )}
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Model ID</label>
                <input
                  type="text"
                  value={p.model_id || ''}
                  onChange={(e) => {
                    const updated = { ...p, model_id: e.target.value };
                    setProviders(providers.map(pr => pr.id === p.id ? updated : pr));
                  }}
                  placeholder={p.provider_name.startsWith('gemini') ? 'auto — доступная модель Gemini' : 'Model ID'}
                  className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-purple-500"
                />
              </div>

              {/* Base URL (if custom or OpenAI compatible) */}
              {(p.base_url !== undefined || p.provider_type === 'custom') && (
                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Base URL</label>
                  <input
                    type="text"
                    value={p.base_url || ''}
                    onChange={(e) => {
                      const updated = { ...p, base_url: e.target.value };
                      setProviders(providers.map(pr => pr.id === p.id ? updated : pr));
                    }}
                    placeholder="https://api.openai.com/v1"
                    className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-purple-500"
                  />
                </div>
              )}

              {/* Voice ID (for TTS) */}
              {p.provider_type === 'tts' && (
                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Voice ID</label>
                  <input
                    type="text"
                    value={p.voice_id || ''}
                    onChange={(e) => {
                      const updated = { ...p, voice_id: e.target.value };
                      setProviders(providers.map(pr => pr.id === p.id ? updated : pr));
                    }}
                    placeholder="ElevenLabs Voice ID or OpenAI voice (e.g. onyx)"
                    className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2 text-xs font-mono text-slate-100 focus:outline-none focus:border-purple-500"
                  />
                </div>
              )}

              {/* Remember Key Checkbox */}
              {p.provider_name !== 'local_cards' && p.provider_name !== 'windows_tts' && <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id={`rem_${p.provider_name}`}
                  checked={rememberKeyMap[p.provider_name] ?? true}
                  onChange={(e) => setRememberKeyMap({ ...rememberKeyMap, [p.provider_name]: e.target.checked })}
                  className="rounded border-dark-600 bg-dark-900 text-purple-600"
                />
                <label htmlFor={`rem_${p.provider_name}`} className="text-xs text-slate-400">
                  Remember API Key in Windows Credential Manager
                </label>
              </div>}
            </div>

            {/* Card Footer Actions */}
            <div className="flex justify-between items-center pt-2 border-t border-dark-700/60">
              <button
                onClick={() => handleTestConnection(p.provider_name)}
                className="px-3 py-1.5 bg-dark-700 hover:bg-dark-600 text-slate-300 font-medium text-xs rounded-lg transition-colors"
              >
                Test Connection
              </button>

              <button
                onClick={() => handleSaveProvider(p)}
                className="px-4 py-1.5 bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs rounded-lg shadow-md transition-all"
              >
                Save
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add Custom Provider Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-dark-800 border border-dark-700 rounded-2xl p-6 max-w-md w-full space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Plus className="w-5 h-5 text-purple-400" />
              <span>Add Custom AI Provider</span>
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400">Provider Name</label>
                <input
                  type="text"
                  placeholder="e.g. my_custom_llm"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400">Provider Type</label>
                <select
                  value={customType}
                  onChange={(e) => setCustomType(e.target.value as any)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                >
                  <option value="text">Text Generation</option>
                  <option value="image">Image Generation</option>
                  <option value="tts">TTS Voice</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-slate-400">Base URL</label>
                <input
                  type="text"
                  placeholder="http://localhost:11434/v1 or https://custom-api.com"
                  value={customBaseUrl}
                  onChange={(e) => setCustomBaseUrl(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400">Model ID</label>
                <input
                  type="text"
                  placeholder="llama3, custom-model"
                  value={customModelId}
                  onChange={(e) => setCustomModelId(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400">API Key (Optional)</label>
                <input
                  type="password"
                  placeholder="Secret key if required"
                  value={customApiKey}
                  onChange={(e) => setCustomApiKey(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2 text-xs text-slate-100"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-3">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-slate-300 font-medium text-xs rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={handleAddCustomProvider}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs rounded-xl"
              >
                Add Provider
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
