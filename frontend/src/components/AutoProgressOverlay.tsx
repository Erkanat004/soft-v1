import React, { useEffect, useState } from 'react';
import { Job, Project } from '../types';
import { api } from '../api';
import { CheckCircle2, Clock, Loader2, AlertCircle, RefreshCw, X } from 'lucide-react';

interface AutoProgressOverlayProps {
  project: Project;
  jobId?: string;
  onClose: () => void;
  onComplete: () => void;
}

const STAGES = [
  { id: 'script', label: '1. Script & Bible Generation' },
  { id: 'scenes', label: '2. Scene Splitting & Prompts' },
  { id: 'tts', label: '3. TTS Voiceover Generation' },
  { id: 'duration_sync', label: '4. FFprobe Duration Sync' },
  { id: 'images', label: '5. Image Generation Queue' },
  { id: 'render', label: '6. FFmpeg MP4 Render' }
];

export const AutoProgressOverlay: React.FC<AutoProgressOverlayProps> = ({
  project,
  jobId,
  onClose,
  onComplete
}) => {
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const interval = setInterval(async () => {
      try {
        const data = await api.getJobStatus(jobId);
        setJob(data);

        if (data.status === 'completed') {
          clearInterval(interval);
          onComplete();
        } else if (data.status === 'failed') {
          clearInterval(interval);
        }
      } catch (err) {
        console.error("Polling job status error:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId]);

  const handleRetryFailed = async () => {
    if (!jobId) return;
    try {
      const updated = await api.retryFailedTasks(jobId);
      setJob(updated);
    } catch (err) {
      console.error("Retry failed error:", err);
    }
  };

  const currentStage = job?.checkpoint_stage || project.current_stage;
  const progressPct = job?.progress_pct || 0;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-6">
      <div className="bg-dark-800 border border-dark-700 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-6 relative overflow-hidden">
        
        {/* Background Ambient Glow */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-purple-600/20 rounded-full blur-3xl pointer-events-none" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-dark-700 pb-4">
          <div>
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <Loader2 className="w-5 h-5 text-purple-400 animate-spin" />
              <span>Auto Pipeline Processing</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">Project: <span className="text-slate-200">{project.name}</span></p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-dark-700 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-semibold">
            <span className="text-purple-400">{job?.current_step_description || 'Processing pipeline steps...'}</span>
            <span className="text-slate-300">{progressPct}%</span>
          </div>
          <div className="w-full h-3 bg-dark-900 rounded-full overflow-hidden p-0.5 border border-dark-700">
            <div
              className="h-full bg-gradient-to-r from-purple-600 to-indigo-500 rounded-full transition-all duration-500 shadow-md shadow-purple-900/50"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {/* Stage Checklist */}
        <div className="space-y-2.5 bg-dark-900/60 rounded-xl p-4 border border-dark-700/60">
          {STAGES.map((s, idx) => {
            const isFinished = progressPct >= ((idx + 1) * 16.6);
            const isCurrent = currentStage === s.id;

            return (
              <div key={s.id} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-3">
                  {isFinished ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : isCurrent ? (
                    <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                  ) : (
                    <Clock className="w-4 h-4 text-slate-600" />
                  )}
                  <span className={isFinished ? 'text-slate-200 font-medium' : isCurrent ? 'text-purple-300 font-semibold' : 'text-slate-500'}>
                    {s.label}
                  </span>
                </div>

                {isCurrent && (
                  <span className="text-xs font-semibold text-purple-400 bg-purple-950/80 px-2 py-0.5 rounded border border-purple-800/40 animate-pulse">
                    IN PROGRESS
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* Error Alert / Failed Tasks */}
        {job && job.failed_tasks > 0 && (
          <div className="p-3 bg-red-950/40 border border-red-900/60 rounded-xl flex items-center justify-between text-xs text-red-300">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{job.failed_tasks} scene(s) encountered API retry failures.</span>
            </div>
            <button
              onClick={handleRetryFailed}
              className="px-3 py-1 bg-red-800 hover:bg-red-700 text-white font-medium rounded-lg flex items-center gap-1 transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Retry Failed</span>
            </button>
          </div>
        )}

        {/* Footer Actions */}
        <div className="flex justify-end gap-3 pt-2">
          {job?.status === 'completed' ? (
            <button
              onClick={onComplete}
              className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl shadow-lg shadow-emerald-900/30 transition-all"
            >
              View Finished Video
            </button>
          ) : (
            <button
              onClick={onClose}
              className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-slate-300 font-medium rounded-xl transition-colors"
            >
              Minimize & Run in Background
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
