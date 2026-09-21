import React from 'react';
import { Project } from '../types';
import { Bot, Layers, CheckCircle2, AlertCircle, Clock, Eye } from 'lucide-react';

interface HeaderProps {
  activeProject: Project | null;
  onOpenProgressOverlay?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ activeProject, onOpenProgressOverlay }) => {
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
            No active project selected
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Live Generating Progress Indicator */}
        {activeProject?.status === 'generating' && onOpenProgressOverlay && (
          <button
            onClick={onOpenProgressOverlay}
            className="px-3.5 py-1.5 rounded-full bg-purple-950/80 border border-purple-600/50 text-purple-200 text-xs font-semibold flex items-center gap-2 shadow-lg shadow-purple-900/30 hover:scale-105 transition-all animate-pulse"
          >
            <Clock className="w-4 h-4 text-purple-400 animate-spin" />
            <span>AUTO PIPELINE RUNNING</span>
            <Eye className="w-3.5 h-3.5 text-purple-300 ml-1" />
          </button>
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
