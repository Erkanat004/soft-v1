import React, { useState } from 'react';
import { Project } from '../types';
import { api } from '../api';
import { Sparkles, Wand2, Clock, Globe, BookOpen, Palette, FileText, Bot, Trash2, Tag } from 'lucide-react';

interface HomePageProps {
  onProjectCreated: (p: Project, jobId?: string) => void;
  onClearAllProjects?: () => void;
}

export const HomePage: React.FC<HomePageProps> = ({ onProjectCreated, onClearAllProjects }) => {
  const [projectName, setProjectName] = useState('');
  const [topicOrScript, setTopicOrScript] = useState('');
  const [durationPreset, setDurationPreset] = useState('40');
  const [language, setLanguage] = useState('English');
  const [storyType, setStoryType] = useState('Horror');
  const [visualStyle, setVisualStyle] = useState('Cinematic');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Input Type classification helper
  const wordCount = topicOrScript.trim().split(/\s+/).filter(Boolean).length;
  const detectedInputType = wordCount > 60 ? 'FULL SCRIPT' : 'TOPIC';

  const handleGenerate = async () => {
    if (!topicOrScript.trim()) return;

    setIsSubmitting(true);
    try {
      const project = await api.createProject({
        name: projectName.trim(),
        topic_or_script: topicOrScript.trim(),
        input_type: 'auto',
        duration_preset: durationPreset,
        language: language,
        story_type: storyType,
        visual_style: visualStyle,
      });

      onProjectCreated(project);
    } catch (err) {
      console.error("Failed to launch auto video generation:", err);
      alert("Failed to start project. Check backend server logs.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-6 space-y-8">
      {/* Header Banner */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-purple-950/70 border border-purple-800/60 text-purple-300 text-xs font-semibold shadow-inner">
          <Sparkles className="w-4 h-4 text-purple-400" />
          <span>StoryForge AI Auto Mode</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Transform Topics into <span className="bg-gradient-to-r from-purple-400 to-indigo-400 bg-clip-text text-transparent">Long YouTube Videos</span>
        </h1>
        <p className="text-slate-400 text-sm max-w-xl mx-auto">
          Paste a quick topic or a complete story. AI handles script writing, character consistency, voiceover, camera motion, and MP4 render in 1-click.
        </p>
      </div>

      {/* Main Form Card */}
      <div className="bg-dark-800 border border-dark-700 rounded-2xl p-6 sm:p-8 shadow-2xl space-y-6 relative overflow-hidden">
        
        {/* Project Name Input */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Tag className="w-4 h-4 text-purple-400" />
            <span>Название проекта (Project Name)</span>
            <span className="text-xs text-slate-500 font-normal">(Задайте свое название или оставьте пустым)</span>
          </label>
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="Например: Таинственный попутчик на ночном шоссе"
            className="w-full bg-dark-900 border border-dark-700 rounded-xl px-4 py-3 text-slate-100 text-sm placeholder:text-slate-600 focus:outline-none focus:border-purple-500 transition-colors"
          />
        </div>

        {/* Topic or Script Input */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <FileText className="w-4 h-4 text-purple-400" />
              <span>Enter topic or paste full script</span>
            </label>
            {topicOrScript.trim() && (
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-dark-700 text-purple-300 border border-dark-600">
                DETECTED: {detectedInputType} ({wordCount} words)
              </span>
            )}
          </div>

          <textarea
            rows={6}
            value={topicOrScript}
            onChange={(e) => setTopicOrScript(e.target.value)}
            placeholder="e.g. 'A truck driver receives a phone call from himself 20 years in the future on a lonely highway at 3 AM.'"
            className="w-full bg-dark-900 border border-dark-700 rounded-xl p-4 text-slate-100 text-sm placeholder:text-slate-600 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-colors resize-none"
          />
        </div>

        {/* Configuration Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          
          {/* Duration */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-purple-400" />
              <span>Target Duration</span>
            </label>
            <select
              value={durationPreset}
              onChange={(e) => setDurationPreset(e.target.value)}
              className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-purple-500"
            >
              <option value="10">10 Min Video</option>
              <option value="20">20 Min Video</option>
              <option value="30">30 Min Video</option>
              <option value="40">40 Min Video (Default)</option>
              <option value="60">60 Min Longform</option>
            </select>
          </div>

          {/* Language */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-purple-400" />
              <span>Language</span>
            </label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-purple-500"
            >
              <option value="English">English</option>
              <option value="Russian">Russian (Русский)</option>
              <option value="Auto">Auto-Detect</option>
            </select>
          </div>

          {/* Story Category */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-purple-400" />
              <span>Story Type</span>
            </label>
            <select
              value={storyType}
              onChange={(e) => setStoryType(e.target.value)}
              className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-purple-500"
            >
              <option value="Horror">Horror & Suspense</option>
              <option value="Mystery">Mystery & Thriller</option>
              <option value="Reddit">Reddit Story</option>
              <option value="Crime">True Crime</option>
              <option value="Sci-Fi">Sci-Fi & Cyberpunk</option>
              <option value="History">Historical Drama</option>
            </select>
          </div>

          {/* Visual Style */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <Palette className="w-3.5 h-3.5 text-purple-400" />
              <span>Visual Style</span>
            </label>
            <select
              value={visualStyle}
              onChange={(e) => setVisualStyle(e.target.value)}
              className="w-full bg-dark-900 border border-dark-700 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-purple-500"
            >
              <option value="Auto">Auto Style</option>
              <option value="Cinematic">Cinematic 35mm</option>
              <option value="Realistic">Realistic Photo</option>
              <option value="Dark">Dark Atmospheric</option>
              <option value="Illustration">Digital Illustration</option>
            </select>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="pt-4 flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleGenerate}
            disabled={!topicOrScript.trim() || isSubmitting}
            className="flex-1 py-4 bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-700 hover:from-purple-500 hover:to-indigo-500 text-white font-extrabold text-base rounded-xl shadow-xl shadow-purple-900/40 flex items-center justify-center gap-3 transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none"
          >
            <Wand2 className="w-6 h-6 animate-pulse" />
            <span>GENERATE VIDEO</span>
          </button>

          {onClearAllProjects && (
            <button
              onClick={onClearAllProjects}
              type="button"
              title="Очистить все проекты и сбросить зависшие задачи"
              className="py-4 px-5 bg-red-950/40 hover:bg-red-900/60 border border-red-800/60 text-red-300 font-semibold text-sm rounded-xl flex items-center justify-center gap-2 transition-colors shrink-0"
            >
              <Trash2 className="w-5 h-5 text-red-400" />
              <span>Очистить всё</span>
            </button>
          )}
        </div>

        {/* Helper Note */}
        <div className="flex items-center justify-center gap-2 text-xs text-slate-500 pt-1">
          <Bot className="w-4 h-4 text-purple-400" />
          <span>AUTO MODE executes all 13 pipeline steps: script, bibles, scenes, TTS, images, motion & MP4 render.</span>
        </div>

      </div>
    </div>
  );
};
