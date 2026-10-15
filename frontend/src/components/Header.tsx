import React from 'react';
import { Project } from '../types';
import { Bot, Layers, CheckCircle2, AlertCircle, Clock, Eye, Zap, Play } from 'lucide-react';

interface HeaderProps {
  activeProject: Project | null;
  onOpenProgressOverlay?: () => void;
  onTriggerAutoPipeline?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ activeProject, onOpenProgressOverlay, onTriggerAutoPipeline }) => {
  return (
    <header className="h-16 bg-dark-800 border-b border-dark-700 px-6 flex items-center justify-between shrink-0 select-none">
      <div className="flex items-center gap-4">
        {activeProject ? (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-600/20 text-purple-400 border border-purple-500/30 flex items-center justify-center">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white truncate max-w-xs">{activeProject.name}</h2>
              <p className="text-xs text-slate-400 flex items-center gap-2">
                <span>{activeProject.story_type}</span>
                <span>•</span>
                <span>{activeProject.duration_preset} min</span>
                <span>•</span>
                <span>{activeProject.language}</span>
              </p>
            </div>
          </div>
        ) : (
          <div className="text-sm font-medium text-slate-400">
            Проект не выбран
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Auto Mode Toggle / Trigger Button */}
        {activeProject && (
          activeProject.active_job_id ? (
            <button
              onClick={onOpenProgressOverlay}
              className="px-3.5 py-1.5 rounded-xl bg-purple-950/90 border border-purple-500/60 text-purple-200 text-xs font-extrabold flex items-center gap-2 shadow-lg shadow-purple-950/50 hover:scale-105 transition-all animate-pulse"
              title="Открыть статус фоновой задачи"
            >
              <Zap className="w-4 h-4 text-purple-400 fill-purple-400 animate-spin" />
              <span>⚡ ЗАДАЧА В РАБОТЕ</span>
              <Eye className="w-3.5 h-3.5 text-purple-300 ml-1" />
            </button>
          ) : (
            <button
              onClick={onTriggerAutoPipeline}
              className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-amber-600 to-indigo-600 hover:from-amber-500 hover:to-indigo-500 text-white text-xs font-extrabold flex items-center gap-2 shadow-lg shadow-indigo-950/40 hover:scale-[1.02] active:scale-[0.98] transition-all"
              title="Запустить полную автоматическую генерацию всех недостающих этапов ролика"
            >
              <Zap className="w-4 h-4 text-amber-300 fill-amber-300" />
              <span>⚡ ЗАПУСТИТЬ АВТОРЕЖИМ</span>
            </button>
          )
        )}

        {/* Project Status Pill */}
        {activeProject && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-700 text-xs font-medium text-slate-300 border border-dark-600">
            {activeProject.status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
            {activeProject.status === 'generating' && <Clock className="w-3.5 h-3.5 text-amber-400 animate-spin" />}
            {activeProject.status === 'failed' && <AlertCircle className="w-3.5 h-3.5 text-red-400" />}
            <span className="capitalize">{activeProject.status}</span>
          </div>
        )}
      </div>
    </header>
  );
};
