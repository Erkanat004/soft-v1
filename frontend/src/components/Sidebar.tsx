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
  Trash2,
  Activity,
  Search
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
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0 h-screen select-none">
      <div>
        {/* Brand Logo */}
        <div className="p-5 border-b border-slate-800 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-900/30">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg text-white tracking-wide leading-tight">StoryForge <span className="text-indigo-400">AI</span></h1>
            <p className="text-xs text-slate-400">YouTube Studio 1.0</p>
          </div>
        </div>

        {/* Primary Action Button */}
        <div className="p-4">
          <button
            onClick={onNewProject}
            className="w-full py-3 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-indigo-900/40 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <Wand2 className="w-5 h-5" />
            <span>НОВЫЙ ПРОЕКТ</span>
          </button>
        </div>

        {/* Navigation Section */}
        <div className="px-3 py-2 space-y-1">
          <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Этапы работы
          </div>

          <button onClick={() => setCurrentTab('research')} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${currentTab === 'research' ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'}`}>
            <Search className="w-4 h-4" /><span>0. Исследование</span>
          </button>
          
          <button
            onClick={() => setCurrentTab('home')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'home'
                ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <PlayCircle className="w-4 h-4" />
            <span>1. Настройки проекта</span>
          </button>

          <button
            onClick={() => setCurrentTab('script')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'script'
                ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>2. Сценарий</span>
          </button>

          <button
            onClick={() => setCurrentTab('storyboard')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'storyboard'
                ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <Film className="w-4 h-4" />
            <span>3. Раскадровка & Сцены</span>
          </button>

          <button
            onClick={() => setCurrentTab('characters')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'characters'
                ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>4. Персонажи</span>
          </button>

          <button
            onClick={() => setCurrentTab('locations')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'locations'
                ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <MapPin className="w-4 h-4" />
            <span>5. Локации</span>
          </button>

          <button
            onClick={() => setCurrentTab('export')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              currentTab === 'export'
                ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            <Download className="w-4 h-4" />
            <span>6. Экспорт & Сборка</span>
          </button>
        </div>

        {/* Projects List */}
        {projects.length > 0 && (
          <div className="px-3 py-2 space-y-1 border-t border-slate-800 mt-2 max-h-36 overflow-y-auto">
            <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>Проекты ({projects.length})</span>
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
                    ? 'bg-slate-800 text-indigo-300 font-semibold'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-300'
                }`}
              >
                {p.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Settings Footer */}
      <div className="p-3 border-t border-slate-800 space-y-1">
        <button
          onClick={() => setCurrentTab('diagnostics')}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
            currentTab === 'diagnostics'
              ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500'
              : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>Диагностика систем</span>
        </button>

        <button
          onClick={() => setCurrentTab('settings')}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
            currentTab === 'settings'
              ? 'bg-indigo-600/20 text-indigo-300 border-l-2 border-indigo-500'
              : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
          }`}
        >
          <Settings className="w-4 h-4" />
          <span>Настройки & Ключи API</span>
        </button>
      </div>
    </aside>
  );
};
