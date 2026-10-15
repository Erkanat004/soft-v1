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
import { DiagnosticsPage } from './pages/DiagnosticsPage';
import { ResearchPage } from './pages/ResearchPage';
import { Job, Project } from './types';
import { api, apiErrorMessage } from './api';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('home');
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | undefined>(undefined);
  const [showProgressOverlay, setShowProgressOverlay] = useState(false);
  const [sceneRefresh, setSceneRefresh] = useState(0);
  const [researchDraft, setResearchDraft] = useState<{ topic: string; brief: string } | null>(null);

  const loadProjects = async () => {
    try {
      const data = await api.listProjects();
      setProjects(data);
      setActiveProject(current => data.find(p => p.id === current?.id) || data[0] || null);
    } catch (err) {
      console.error("Failed to load projects:", err);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    const projectId = activeProject?.id;
    const jobId = activeProject?.active_job_id;
    if (!projectId || !jobId) return;
    const timer = window.setInterval(async () => {
      try {
        const updated = await api.getProject(projectId);
        setProjects(current => current.map(p => p.id === projectId ? updated : p));
        setActiveProject(current => current?.id === projectId ? updated : current);
        if (!updated.active_job_id) setSceneRefresh(current => current + 1);
      } catch (err) {
        console.error('Failed to refresh project status:', err);
      }
    }, 4000);
    return () => window.clearInterval(timer);
  }, [activeProject?.id, activeProject?.active_job_id]);

  const handleProjectCreated = (p: Project, jobId?: string) => {
    setProjects(current => [p, ...current]);
    setActiveProject(jobId ? { ...p, status: 'generating', active_job_id: jobId } : p);
    if (jobId) {
      setActiveJobId(jobId);
      setShowProgressOverlay(true);
      setCurrentTab('storyboard');
    } else {
      setCurrentTab('script');
    }
  };

  const handleJobStarted = (job: Job) => {
    setActiveJobId(job.id);
    setActiveProject(current => current?.id === job.project_id
      ? { ...current, active_job_id: job.id, status: job.job_type === 'auto_remaining' ? 'generating' : current.status }
      : current);
    setShowProgressOverlay(true);
  };

  const handleTriggerAutoPipeline = async () => {
    if (!activeProject) return;
    try {
      const job = await api.triggerAutoRemaining(activeProject.id);
      handleJobStarted(job);
    } catch (err) {
      console.error("Failed to trigger auto pipeline:", err);
      alert(apiErrorMessage(err, "Не удалось запустить авторежим."));
    }
  };

  const handleClearAllProjects = async () => {
    try {
      const result = await api.clearAllProjects();
      if (result.media_cleanup_warnings?.length) {
        alert('Проекты удалены из базы, но некоторые медиафайлы не удалось удалить. Закройте программы, которые используют эти файлы.');
      }
      setProjects([]);
      setActiveProject(null);
      setActiveJobId(undefined);
      setShowProgressOverlay(false);
      setCurrentTab('home');
    } catch (err) {
      console.error("Failed to clear all projects:", err);
      alert(apiErrorMessage(err, "Не удалось очистить проекты."));
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100">
      {/* Left Sidebar */}
      <Sidebar
        currentTab={currentTab}
        setCurrentTab={setCurrentTab}
        activeProject={activeProject}
        projects={projects}
        onSelectProject={(p) => {
          setActiveProject(p);
          setActiveJobId(p.active_job_id);
          setShowProgressOverlay(false);
        }}
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
          onTriggerAutoPipeline={handleTriggerAutoPipeline}
        />

        {/* Dynamic Page Views */}
        <main className="flex-1 overflow-y-auto">
          {currentTab === 'home' && (
            <HomePage 
              onProjectCreated={handleProjectCreated} 
              onClearAllProjects={handleClearAllProjects}
              prefill={researchDraft}
            />
          )}
          {currentTab === 'research' && (
            <ResearchPage onUseBrief={(topic, brief) => {
              setResearchDraft({ topic, brief });
              setCurrentTab('home');
            }} />
          )}

          {currentTab === 'script' && activeProject && (
            <ScriptPage
              project={activeProject}
              onNavigateToStoryboard={() => setCurrentTab('storyboard')}
            />
          )}

          {currentTab === 'storyboard' && activeProject && (
            <StoryboardPage
              key={`${activeProject.id}-${sceneRefresh}`}
              project={activeProject}
              onNavigateToExport={() => setCurrentTab('export')}
              onJobStarted={handleJobStarted}
            />
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

          {currentTab === 'diagnostics' && (
            <DiagnosticsPage />
          )}
        </main>
      </div>

      {/* Auto Mode Live Pipeline Progress Overlay */}
      {showProgressOverlay && activeProject && (
        <AutoProgressOverlay
          project={activeProject}
          jobId={activeJobId}
          onClose={() => setShowProgressOverlay(false)}
          onComplete={(job) => {
            setShowProgressOverlay(false);
            setActiveJobId(undefined);
            setSceneRefresh(current => current + 1);
            setCurrentTab(job.job_type === 'auto_remaining' ? 'export' : 'storyboard');
            void loadProjects();
          }}
        />
      )}
    </div>
  );
};

export default App;
