import React, { useEffect, useState } from 'react';
import { api, apiErrorMessage, LocalPreflight } from '../api';
import { FFmpegStatus, Job, ProviderSetting } from '../types';
import { Activity, Terminal, CheckCircle2, XCircle, AlertTriangle, ShieldCheck, RefreshCw, Bug, ShieldAlert } from 'lucide-react';

export const DiagnosticsPage: React.FC = () => {
  const [ffmpeg, setFFmpeg] = useState<FFmpegStatus | null>(null);
  const [providers, setProviders] = useState<ProviderSetting[]>([]);
  const [simulatedError, setSimulatedError] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [backingUp, setBackingUp] = useState(false);
  const [preflight, setPreflight] = useState<LocalPreflight | null>(null);
  const [checkingPreflight, setCheckingPreflight] = useState(false);

  const handlePreflight = async () => {
    setCheckingPreflight(true);
    try { setPreflight(await api.getLocalPreflight()); }
    catch (error) { alert(apiErrorMessage(error, 'Локальная проверка не завершилась.')); }
    finally { setCheckingPreflight(false); }
  };

  const handleDownloadBackup = async () => {
    setBackingUp(true);
    try {
      const archive = await api.downloadBackup();
      const url = URL.createObjectURL(archive);
      const link = document.createElement('a');
      link.href = url;
      link.download = `storyforge-backup-${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (error) { alert(apiErrorMessage(error, 'Не удалось создать резервную копию.')); }
    finally { setBackingUp(false); }
  };

  const loadDiagnostics = async () => {
    setLoading(true);
    try {
      const [ff, provs, errState] = await Promise.all([
        api.getFFmpegStatus(),
        api.getProviders(),
        api.getSimulatedApiError()
      ]);
      setFFmpeg(ff);
      setProviders(provs);
      setSimulatedError(errState.simulated_error);
    } catch (err) {
      console.error("Failed to load diagnostics:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDiagnostics();
  }, []);

  const handleSetSimulatedError = async (code: number | null) => {
    try {
      const res = await api.simulateApiError(code);
      setSimulatedError(res.simulated_error);
    } catch (err) {
      console.error("Failed to simulate API error:", err);
      alert("Не удалось установить симуляцию ошибки.");
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-6 space-y-8">
      {/* Header */}
      <div className="border-b border-slate-800 pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Activity className="w-6 h-6 text-indigo-400" />
            <span>Диагностика и Система</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Проверка статуса бинарных файлов FFmpeg/FFprobe, активных фоновых задач и статуса подключений API.
          </p>
        </div>

        <button
          onClick={loadDiagnostics}
          className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl flex items-center gap-2 border border-slate-700"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Обновить</span>
        </button>
      </div>

      {/* Error Simulation Panel */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900 p-5 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-bold">Проверка перед работой</h3>
          <p className="text-xs text-slate-400 mt-1">Проверяет только этот компьютер; ключи не отправляются провайдерам.</p></div>
          <button disabled={checkingPreflight} onClick={handlePreflight} className="rounded-xl bg-slate-700 px-4 py-2 text-sm font-semibold disabled:opacity-50">{checkingPreflight ? 'Проверка…' : 'Проверить локально'}</button></div>
        {preflight && <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
          <p>FFmpeg / FFprobe: {preflight.ffmpeg_ready && preflight.ffprobe_ready ? 'готовы' : 'не найдены'}</p>
          <p>Папка проектов: {preflight.storage_ready ? 'доступна для записи' : 'нет доступа'}</p>
          <p>Голос Windows: {preflight.windows_voice_ready ? 'готов' : 'недоступен'}</p>
          <p>Свободно на диске: {preflight.free_disk_gb} ГБ</p>
          <p>Ключ для генерации текста: {preflight.text_key_configured ? 'указан' : 'не указан'}</p>
          <p className="text-slate-400">Внешних AI-запросов: 0</p>
        </div>}
      </div>

      <div className="rounded-2xl border border-indigo-800/60 bg-indigo-950/30 p-5 flex flex-wrap items-center justify-between gap-4">
        <div><h3 className="font-bold text-indigo-200">Резервная копия проектов</h3>
          <p className="text-xs text-slate-400 mt-1">База и медиа в ZIP; API-ключи не включаются. Во время генерации копия недоступна.</p></div>
        <button onClick={handleDownloadBackup} disabled={backingUp} className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold disabled:opacity-50">
          {backingUp ? 'Создаётся архив…' : 'Скачать копию'}
        </button>
      </div>

      {import.meta.env.DEV && import.meta.env.VITE_ENABLE_DEV_TOOLS === '1' && <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
            <Bug className="w-4 h-4 text-amber-400" />
            <span>Симуляция Ошибок API (Тестирование устойчивости и перезапуска)</span>
          </h3>
          {simulatedError ? (
            <span className="px-2.5 py-1 rounded bg-red-950 text-red-300 border border-red-800 text-xs font-bold animate-pulse flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
              <span>Активна ошибка HTTP {simulatedError}</span>
            </span>
          ) : (
            <span className="px-2.5 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 text-xs font-bold flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Нормальный режим (Ошибки отключены)</span>
            </span>
          )}
        </div>

        <p className="text-xs text-slate-400">
          Используйте эти кнопки для проверки обработки частично упавших сцен, баннеров ошибок и повторных попыток генерации для одной сцены.
        </p>

        <div className="flex flex-wrap gap-2 pt-2">
          <button
            onClick={() => handleSetSimulatedError(401)}
            className={`px-3 py-2 text-xs font-bold rounded-xl border transition-all ${simulatedError === 401 ? 'bg-red-900 text-white border-red-600 shadow-lg' : 'bg-slate-950 text-slate-300 border-slate-800 hover:bg-slate-800'}`}
          >
            401 Unauthorized (Неверный API Ключ)
          </button>

          <button
            onClick={() => handleSetSimulatedError(408)}
            className={`px-3 py-2 text-xs font-bold rounded-xl border transition-all ${simulatedError === 408 ? 'bg-amber-900 text-white border-amber-600 shadow-lg' : 'bg-slate-950 text-slate-300 border-slate-800 hover:bg-slate-800'}`}
          >
            408 Timeout (Таймаут запроса)
          </button>

          <button
            onClick={() => handleSetSimulatedError(429)}
            className={`px-3 py-2 text-xs font-bold rounded-xl border transition-all ${simulatedError === 429 ? 'bg-purple-900 text-white border-purple-600 shadow-lg' : 'bg-slate-950 text-slate-300 border-slate-800 hover:bg-slate-800'}`}
          >
            429 Rate Limit (Лимит запросов)
          </button>

          <button
            onClick={() => handleSetSimulatedError(500)}
            className={`px-3 py-2 text-xs font-bold rounded-xl border transition-all ${simulatedError === 500 ? 'bg-rose-900 text-white border-rose-600 shadow-lg' : 'bg-slate-950 text-slate-300 border-slate-800 hover:bg-slate-800'}`}
          >
            500 Internal Error
          </button>

          <button
            onClick={() => handleSetSimulatedError(null)}
            className={`px-3.5 py-2 text-xs font-bold rounded-xl border transition-all ${simulatedError === null ? 'bg-emerald-950 text-emerald-300 border-emerald-800' : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700'}`}
          >
            Сбросить симуляцию (ОК)
          </button>
        </div>
            </div>}

            {/* FFmpeg Detection Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
          <Terminal className="w-4 h-4 text-indigo-400" />
          <span>Статус мультимедийного движка (FFmpeg / FFprobe)</span>
        </h3>

        {ffmpeg ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className={`p-4 rounded-xl border flex items-start justify-between ${ffmpeg.ffmpeg_installed ? 'bg-emerald-950/40 border-emerald-800/80 text-emerald-300' : 'bg-red-950/40 border-red-800/80 text-red-300'}`}>
              <div>
                <div className="font-bold text-sm flex items-center gap-2">
                  {ffmpeg.ffmpeg_installed ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
                  <span>FFmpeg Executable</span>
                </div>
                <div className="mt-2 font-mono text-[11px] opacity-80 break-all">{ffmpeg.ffmpeg_path || "Не найден"}</div>
              </div>
            </div>

            <div className={`p-4 rounded-xl border flex items-start justify-between ${ffmpeg.ffprobe_installed ? 'bg-emerald-950/40 border-emerald-800/80 text-emerald-300' : 'bg-red-950/40 border-red-800/80 text-red-300'}`}>
              <div>
                <div className="font-bold text-sm flex items-center gap-2">
                  {ffmpeg.ffprobe_installed ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
                  <span>FFprobe Executable</span>
                </div>
                <div className="mt-2 font-mono text-[11px] opacity-80 break-all">{ffmpeg.ffprobe_path || "Не найден"}</div>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-slate-500 text-xs">Загрузка информации о бинарных файлах...</div>
        )}
      </div>

      {/* Providers API Keys & Test Connections */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-indigo-400" />
          <span>Подключенные Провайдеры API</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {providers.map(p => (
            <div key={p.provider_name} className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between">
              <div>
                <div className="font-bold text-xs text-white capitalize">{p.provider_name}</div>
                <div className="text-[10px] text-slate-400">{p.provider_type.toUpperCase()} • {p.model_id || 'default'}</div>
              </div>
              <span className={`px-2 py-0.5 text-[10px] font-bold rounded border ${p.has_api_key ? 'bg-emerald-950 text-emerald-400 border-emerald-800' : 'bg-slate-900 text-slate-500 border-slate-800'}`}>
                {p.has_api_key ? 'Ключ добавлен' : 'Без ключа'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
