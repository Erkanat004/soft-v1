import React from 'react';
import { 
  Wand2, 
  Film, 
  FileText, 
  Users, 
  MapPin, 
  Download, 
  Settings, 
  PlayCircle,
  Sparkles,
  FolderKanban,
  Trash2
} from 'lucide-react';
import { Project } from '../types';

interface SidebarProps {
  currentTab: string;
  setCurrentTab: (tab: string) => void;
  activeProject: Project | null;
  projects: Project[];
  onSelectProject: (p: Project) => void;
  onNewProject: () => void;
  onClearAllProjects?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  setCurrentTab,
  activeProject,
  projects,
  onSelectProject,
  onNewProject,
  onClearAllProjects
}) => {
  return (
    <aside className="w-64 bg-dark-800 border-r border-dark-700 flex flex-col justify-between shrink-0 h-screen select-none">
      <div>
        {/* Brand Logo */}
        <div className="p-5 border-b border-dark-700 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-600 to-red-500 flex items-center justify-center shadow-lg shadow-purple-900/30">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg text-white tracking-wide leading-tight">StoryForge <span className="text-purple-400">AI</span></h1>
            <p className="text-xs text-slate-400">YouTube Video Engine</p>
          </div>
        </div>

        {/* Primary Action Button */}
        <div className="p-4">
          <button
            onClick={onNewProject}
            className="w-full py-3 px-4 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-purple-900/40 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <Wand2 className="w-5 h-5" />
            <span>GENERATE VIDEO</span>
          </button>
        </div>

        {/* Navigation Section */}
        <div className="px-3 py-2 space-y-1">
          <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Main Pipeline
          </div>
          
          <button
            onClick={() => setCurrentTab('home')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'home'
                ? 'bg-purple-600/20 text-purple-300 border-l-2 border-purple-500'
                : 'text-slate-400 hover:bg-dark-700 hover:text-slate-200'
            }`}
          >
            <PlayCircle className="w-4 h-4" />
            <span>Auto Launcher</span>
          </button>

          <button
            onClick={() => setCurrentTab('export')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'export'
                ? 'bg-purple-600/20 text-purple-300 border-l-2 border-purple-500'
                : 'text-slate-400 hover:bg-dark-700 hover:text-slate-200'
            }`}
          >
            <Download className="w-4 h-4" />
            <span>Export & Render</span>
          </button>
        </div>

        {/* Advanced Editing Tools */}
        <div className="px-3 py-2 space-y-1 border-t border-dark-700/60 mt-2">
          <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Advanced Editing
          </div>

          <button
            onClick={() => setCurrentTab('storyboard')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'storyboard'
                ? 'bg-purple-600/20 text-purple-300 border-l-2 border-purple-500'
                : 'text-slate-400 hover:bg-dark-700 hover:text-slate-200'
            }`}
          >
            <Film className="w-4 h-4" />
            <span>Storyboard</span>
          </button>

          <button
            onClick={() => setCurrentTab('script')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'script'
                ? 'bg-purple-600/20 text-purple-300 border-l-2 border-purple-500'
                : 'text-slate-400 hover:bg-dark-700 hover:text-slate-200'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Script Editor</span>
          </button>

          <button
            onClick={() => setCurrentTab('characters')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'characters'
                ? 'bg-purple-600/20 text-purple-300 border-l-2 border-purple-500'
                : 'text-slate-400 hover:bg-dark-700 hover:text-slate-200'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Characters</span>
          </button>

          <button
            onClick={() => setCurrentTab('locations')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'locations'
                ? 'bg-purple-600/20 text-purple-300 border-l-2 border-purple-500'
                : 'text-slate-400 hover:bg-dark-700 hover:text-slate-200'
            }`}
          >
            <MapPin className="w-4 h-4" />
            <span>Locations</span>
          </button>
        </div>

        {/* Projects List */}
        {projects.length > 0 && (
          <div className="px-3 py-2 space-y-1 border-t border-dark-700/60 mt-2 max-h-40 overflow-y-auto">
            <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>Recent Projects</span>
              {onClearAllProjects && (
                <button
                  onClick={onClearAllProjects}
                  title="Очистить все проекты"
                  className="text-slate-500 hover:text-red-400 p-0.5 rounded transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            {projects.slice(0, 5).map(p => (
              <button
                key={p.id}
                onClick={() => onSelectProject(p)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium truncate transition-colors ${
                  activeProject?.id === p.id
                    ? 'bg-dark-700 text-purple-300 font-semibold'
                    : 'text-slate-400 hover:bg-dark-700/50 hover:text-slate-300'
                }`}
              >
                {p.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Settings Footer */}
      <div className="p-3 border-t border-dark-700">
        <button
          onClick={() => setCurrentTab('settings')}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            currentTab === 'settings'
              ? 'bg-purple-600/20 text-purple-300 border-l-2 border-purple-500'
              : 'text-slate-400 hover:bg-dark-700 hover:text-slate-200'
          }`}
        >
          <Settings className="w-4 h-4" />
          <span>API Providers & Settings</span>
        </button>
      </div>
    </aside>
  );
};
