import React, { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { AutoProgressOverlay } from './components/AutoProgressOverlay';
import { HomePage } from './pages/HomePage';
import { StoryboardPage } from './pages/StoryboardPage';
import { ScriptPage } from './pages/ScriptPage';
import { CharactersPage } from './pages/CharactersPage';
import { LocationsPage } from './pages/LocationsPage';
import { ExportPage } from './pages/ExportPage';
import { SettingsPage } from './pages/SettingsPage';
import { Project } from './types';
import { api } from './api';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('home');
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | undefined>(undefined);
  const [showProgressOverlay, setShowProgressOverlay] = useState(false);

  const loadProjects = async () => {
    try {
      const data = await api.listProjects();
      setProjects(data);
      if (data.length > 0 && !activeProject) {
        setActiveProject(data[0]);
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleProjectCreated = (p: Project) => {
    setProjects([p, ...projects]);
    setActiveProject(p);
    setActiveJobId(p.active_job_id);
    setShowProgressOverlay(true);
  };

  const handleClearAllProjects = async () => {
    if (window.confirm("Удалить ВСЕ проекты и сбросить зависшие задачи? Это действие нельзя отменить.")) {
      try {
        await api.clearAllProjects();
        setProjects([]);
        setActiveProject(null);
        setActiveJobId(undefined);
        setShowProgressOverlay(false);
      } catch (err) {
        console.error("Failed to clear all projects:", err);
        alert("Не удалось очистить проекты. Проверьте подключение к серверу.");
      }
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-dark-900 text-slate-100">
      {/* Left Sidebar */}
      <Sidebar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        activeProject={activeProject}
        projects={projects}
        onSelectProject={(p) => setActiveProject(p)}
        onNewProject={() => setCurrentTab('home')}
        onClearAllProjects={handleClearAllProjects}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Header */}
        <Header
          activeProject={activeProject}
          onOpenProgressOverlay={() => {
            if (activeProject?.active_job_id) {
              setActiveJobId(activeProject.active_job_id);
            }
            setShowProgressOverlay(true);
          }}
        />


        {/* Dynamic Page Views */}
        <main className="flex-1 overflow-y-auto">
          {currentTab === 'home' && (
            <HomePage 
              onProjectCreated={handleProjectCreated} 
              onClearAllProjects={handleClearAllProjects}
            />
          )}

          {currentTab === 'storyboard' && activeProject && (
            <StoryboardPage project={activeProject} />
          )}

          {currentTab === 'script' && activeProject && (
            <ScriptPage project={activeProject} />
          )}

          {currentTab === 'characters' && activeProject && (
            <CharactersPage project={activeProject} />
          )}

          {currentTab === 'locations' && activeProject && (
            <LocationsPage project={activeProject} />
          )}

          {currentTab === 'export' && activeProject && (
            <ExportPage project={activeProject} />
          )}

          {currentTab === 'settings' && (
            <SettingsPage />
          )}
        </main>
      </div>

      {/* Auto Mode Live Pipeline Progress Overlay */}
      {showProgressOverlay && activeProject && (
        <AutoProgressOverlay
          project={activeProject}
          jobId={activeJobId}
          onClose={() => setShowProgressOverlay(false)}
          onComplete={() => {
            setShowProgressOverlay(false);
            setCurrentTab('export');
            loadProjects();
          }}
        />
      )}
    </div>
  );
};

export default App;
