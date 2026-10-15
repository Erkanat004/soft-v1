import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Job, Project } from '../types';
import { api, apiErrorMessage } from '../api';
import { CheckCircle2, Clock, Loader2, AlertCircle, RefreshCw, X, StopCircle } from 'lucide-react';

interface AutoProgressOverlayProps {
  project: Project;
  jobId?: string;
  onClose: () => void;
  onComplete: (job: Job) => void;
}

const STAGES = [
  { id: 'script', label: '1. Анализ темы и подготовка сценария' },
  { id: 'scenes', label: '2. Разбивка на сцены и промпты' },
  { id: 'tts', label: '3. Озвучка диалогов / диктора' },
  { id: 'duration_sync', label: '4. Пробинг длительности FFprobe' },
  { id: 'images', label: '5. Очередь генерации картинок' },
  { id: 'render', label: '6. Финальный рендер FFmpeg MP4' }
];

export const AutoProgressOverlay: React.FC<AutoProgressOverlayProps> = ({
  project,
  jobId,
  onClose,
  onComplete
}) => {
  const [job, setJob] = useState<Job | null>(null);
  const [pollError, setPollError] = useState('');
  const completeRef = useRef(onComplete);
  completeRef.current = onComplete;

  useEffect(() => {
    if (!jobId) return;

    let stopped = false;
    let failures = 0;
    let timer: ReturnType<typeof setTimeout>;
    setJob(null);
    setPollError('');
    const poll = async () => {
      let delay = 2000;
      try {
        const data = await api.getJobStatus(jobId);
        if (stopped) return;
        setJob(data);
        setPollError('');
        failures = 0;
        if (data.status === 'completed') {
          completeRef.current(data);
          return;
        } else if (['failed', 'cancelled', 'interrupted'].includes(data.status)) {
          return;
        }
      } catch (err) {
        if (stopped) return;
        if (axios.isAxiosError(err) && [404, 410].includes(err.response?.status || 0)) {
          setPollError('Задача больше не существует. Закройте окно и обновите проект.');
          return;
        }
        setPollError(apiErrorMessage(err));
        delay = Math.min(30000, 2000 * 2 ** Math.min(++failures, 4));
      }
      if (!stopped) timer = setTimeout(poll, delay);
    };
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [jobId]);

  const handleCancelJob = async () => {
    if (!jobId) return;
    try {
      await api.cancelJob(jobId);
      onClose();
    } catch (err) {
      setPollError(apiErrorMessage(err, 'Не удалось отменить задачу'));
    }
  };

  const currentStage = job?.checkpoint_stage || project.current_stage;
  const progressPct = job?.progress_pct || 0;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-6">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-6 relative overflow-hidden">
        
        {/* Background Ambient Glow */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <Loader2 className="w-5 h-5 text-indigo-400 animate-spin" />
              <span>Фоновый процесс генерации</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">Проект: <span className="text-slate-200">{project.name}</span></p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-semibold">
            <span className="text-indigo-400">{job?.current_step_description || 'Обработка шагов пайплайна...'}</span>
            <span className="text-slate-300">{progressPct}%</span>
          </div>
          <div className="w-full h-3 bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800">
            <div
              className="h-full bg-gradient-to-r from-indigo-600 to-purple-500 rounded-full transition-all duration-500 shadow-md shadow-indigo-900/50"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {/* Stage Checklist */}
        <div className="space-y-2.5 bg-slate-950 rounded-xl p-4 border border-slate-800">
          {STAGES.map((s, idx) => {
            const isFinished = progressPct >= ((idx + 1) * 16.6);
            const isCurrent = currentStage === s.id;

            return (
              <div key={s.id} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  {isFinished ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : isCurrent ? (
                    <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                  ) : (
                    <Clock className="w-4 h-4 text-slate-600" />
                  )}
                  <span className={isFinished ? 'text-slate-200 font-medium' : isCurrent ? 'text-indigo-300 font-semibold' : 'text-slate-500'}>
                    {s.label}
                  </span>
                </div>

                {isCurrent && (
                  <span className="text-xs font-semibold text-indigo-400 bg-indigo-950/80 px-2 py-0.5 rounded border border-indigo-800/40 animate-pulse">
                    В ПРОЦЕССЕ
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {(pollError || job?.error_message || job?.status === 'interrupted') && (
          <p role="alert" className="text-sm text-amber-300">
            {pollError || job?.error_message || 'Задача прервана перезапуском сервера. Запустите её повторно.'}
          </p>
        )}
        {/* Footer Actions */}
        <div className="flex justify-between items-center pt-2">
          <button
            onClick={handleCancelJob}
            className="px-3.5 py-2 bg-red-950/60 hover:bg-red-900 text-red-300 text-xs font-semibold rounded-xl flex items-center gap-1.5 border border-red-800"
          >
            <StopCircle className="w-4 h-4 text-red-400" />
            <span>Отменить задачу</span>
          </button>

          {job?.status === 'completed' ? (
            <button
              onClick={() => job && onComplete(job)}
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl shadow-lg shadow-emerald-900/30 transition-all"
            >
              Смотреть готовое видео
            </button>
          ) : (
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-xl transition-colors"
            >
              Свернуть в фон
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
