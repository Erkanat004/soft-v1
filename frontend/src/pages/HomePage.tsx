import React, { useState } from 'react';
import { Project } from '../types';
import { api, apiErrorMessage } from '../api';
import { Sparkles, Wand2, Clock, Globe, BookOpen, Palette, FileText, Bot, Trash2, Tag, Monitor, Zap } from 'lucide-react';

interface HomePageProps {
  onProjectCreated: (p: Project, jobId?: string) => void;
  onClearAllProjects?: () => void;
  prefill?: { topic: string; brief: string } | null;
}

export const HomePage: React.FC<HomePageProps> = ({ onProjectCreated, onClearAllProjects, prefill }) => {
  const [projectName, setProjectName] = useState('');
  const [topicOrScript, setTopicOrScript] = useState('');
  const [creativeBrief, setCreativeBrief] = useState(prefill?.brief || '');
  const [durationPreset, setDurationPreset] = useState('15');
  const [language, setLanguage] = useState('Russian');
  const [storyType, setStoryType] = useState('Horror');
  const [visualStyle, setVisualStyle] = useState('Cinematic');
  const [textProvider, setTextProvider] = useState('');
  const [imageProvider, setImageProvider] = useState('local_cards');
  const [ttsProvider, setTtsProvider] = useState('windows_tts');
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [resolution, setResolution] = useState('1080p');
  const [isAutoMode, setIsAutoMode] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  React.useEffect(() => {
    if (prefill) { setTopicOrScript(prefill.topic); setCreativeBrief(prefill.brief); }
  }, [prefill]);

  const wordCount = topicOrScript.trim().split(/\s+/).filter(Boolean).length;
  const detectedInputType = wordCount > 60 ? 'FULL SCRIPT' : 'TOPIC';

  const handleCreateProject = async () => {
    if (!topicOrScript.trim()) return;
    if (isAutoMode && !window.confirm('Авторежим отправит запросы выбранным AI-провайдерам. Их тариф и расход зависят от ваших ключей. Продолжить?')) return;

    setIsSubmitting(true);
    try {
      const project = await api.createProject({
        name: projectName.trim(),
        topic_or_script: topicOrScript.trim(),
        input_type: wordCount > 60 ? 'full_script' : 'topic',
        duration_preset: durationPreset,
        language: language,
        story_type: storyType,
        visual_style: visualStyle,
        creative_brief: creativeBrief.trim() || undefined,
        active_text_provider: textProvider || undefined,
        active_image_provider: imageProvider,
        active_tts_provider: ttsProvider,
        aspect_ratio: aspectRatio,
        resolution: resolution
      });

      if (isAutoMode) {
        const job = await api.triggerAutoRemaining(project.id);
        onProjectCreated(project, job.id);
      } else {
        onProjectCreated(project);
      }
    } catch (err) {
      console.error("Failed to create project:", err);
      alert(apiErrorMessage(err, "Не удалось создать проект. Проверьте подключение к серверу."));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-6 space-y-8">
      {/* Header Banner */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-950/70 border border-indigo-800/60 text-indigo-300 text-xs font-semibold shadow-inner">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <span>StoryForge AI Studio v1.0</span>
        </div>

        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Создание <span className="bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">YouTube Видео</span>
        </h1>
        <p className="text-slate-400 text-sm max-w-xl mx-auto">
          Создавайте сценарии, раскадровки, генерацию изображений, дикторскую озвучку и сборку роликов в пошаговом редакторе.
        </p>
      </div>

      {/* Main Form Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl space-y-6 relative overflow-hidden">
        
        {/* Project Name Input */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Tag className="w-4 h-4 text-indigo-400" />
            <span>Название проекта</span>
            <span className="text-xs text-slate-500 font-normal">(Необязательно — можно задать сейчас или позже)</span>
          </label>
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="Например: История ночного попутчика"
            className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-slate-100 text-sm placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        {/* Topic or Script Input */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <FileText className="w-4 h-4 text-indigo-400" />
              <span>Тема ролика или готовый сценарий</span>
            </label>
            {topicOrScript.trim() && (
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-slate-800 text-indigo-300 border border-slate-700">
                ТИП: {detectedInputType} ({wordCount} слов)
              </span>
            )}
          </div>

          <textarea
            rows={6}
            value={topicOrScript}
            onChange={(e) => setTopicOrScript(e.target.value)}
            placeholder="Вставьте тему (например: 'Мистический случай на туманной дороге в 3 часа ночи') или вставьте свой готовый текст сценария..."
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-slate-100 text-sm placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors resize-none"
          />
        </div>

        {/* Configuration Controls */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-slate-200">Творческий бриф · необязательно</label>
          <textarea rows={4} maxLength={4000} value={creativeBrief} onChange={event => setCreativeBrief(event.target.value)} placeholder="Собственная перспектива, темп и структура. Можно подготовить во вкладке «Исследование»." className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-slate-100 text-sm resize-y" />
          <p className="text-xs text-slate-500">Бриф направляет сценарий. AI-запрос начнётся только при запуске генерации или авторежима.</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          
          {/* Aspect Ratio */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <Monitor className="w-3.5 h-3.5 text-indigo-400" />
              <span>Формат кадра</span>
            </label>
            <select
              value={aspectRatio}
              onChange={(e) => setAspectRatio(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="16:9">16:9 (YouTube Горизонтальное)</option>
              <option value="9:16">9:16 (Shorts / Reels Вертикальное)</option>
              <option value="1:1">1:1 (Квадрат)</option>
            </select>
          </div>

          {/* Duration */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
              <span>Длительность</span>
            </label>
            <select
              value={durationPreset}
              onChange={(e) => setDurationPreset(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="1">1 мин (Короткий тест)</option>
              <option value="3">3 мин (Тестовый ролик)</option>
              <option value="5">5 мин</option>
              <option value="10">10 мин</option>
              <option value="15">15 мин (По умолчанию)</option>
              <option value="30">30 мин</option>
              <option value="60">60 мин</option>
            </select>
          </div>

          {/* Language */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-indigo-400" />
              <span>Язык ролика</span>
            </label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="Russian">Русский</option>
              <option value="English">English</option>
            </select>
          </div>

          {/* Story Category */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-indigo-400" />
              <span>Жанр история</span>
            </label>
            <select
              value={storyType}
              onChange={(e) => setStoryType(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-xs font-medium text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="Horror">Ужасы и Мистика</option>
              <option value="Mystery">Детектив и Триллер</option>
              <option value="Reddit">История из Жизни / Reddit</option>
              <option value="Crime">True Crime</option>
              <option value="Sci-Fi">Научная фантастика</option>
              <option value="History">Историческая драма</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <label className="space-y-1.5 text-xs text-slate-400">
            <span>Сценарий</span>
            <select value={textProvider} onChange={event => setTextProvider(event.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-slate-200">
              <option value="">Авто: Gemini / OpenRouter</option>
              <option value="gemini">Gemini</option>
              <option value="openrouter">OpenRouter</option>
            </select>
          </label>
          <label className="space-y-1.5 text-xs text-slate-400">
            <span>Изображения</span>
            <select value={imageProvider} onChange={event => setImageProvider(event.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-slate-200">
              <option value="local_cards">Локальные карточки · бесплатно</option>
              <option value="ai_horde_image">AI Horde · бесплатно, очередь</option>
              <option value="gemini_image">Gemini Image · платный API</option>
              <option value="openai_image">OpenAI Image · платный API</option>
            </select>
          </label>
          <label className="space-y-1.5 text-xs text-slate-400">
            <span>Озвучка</span>
            <select value={ttsProvider} onChange={event => setTtsProvider(event.target.value)} className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-slate-200">
              <option value="windows_tts">Голос Windows · бесплатно</option>
              <option value="elevenlabs">ElevenLabs · внешний API</option>
              <option value="fish_audio">Fish Audio · внешний API</option>
              <option value="openai_tts">OpenAI TTS · платный API</option>
            </select>
          </label>
        </div>

        {/* Execution Mode Selector Card */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4 shadow-inner">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center border transition-all ${
              isAutoMode ? 'bg-amber-950/80 border-amber-600 text-amber-300 shadow-md shadow-amber-950/50' : 'bg-slate-900 border-slate-800 text-slate-500'
            }`}>
              <Zap className={`w-5 h-5 ${isAutoMode ? 'fill-amber-400 text-amber-400 animate-pulse' : ''}`} />
            </div>
            <div>
              <div className="text-xs font-bold text-white flex items-center gap-2">
                <span>Режим работы:</span>
                <span className={`px-2.5 py-0.5 rounded text-[10px] uppercase font-extrabold border ${
                  isAutoMode ? 'bg-amber-950 text-amber-300 border-amber-700' : 'bg-slate-900 text-slate-400 border-slate-800'
                }`}>
                  {isAutoMode ? '⚡ Авторежим (Полная авто-сборка)' : '🛠 Пошаговый режим (Ручной контроль)'}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                {isAutoMode
                  ? 'После создания проекта автоматически подготовит сценарий, сцены, озвучку, изображения и MP4.'
                  : 'Создаст черновик проекта. Вы сможете вручную править текст, промпты и пошагово запускать генерации.'}
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsAutoMode(!isAutoMode)}
            className={`px-3.5 py-2 rounded-xl border text-xs font-extrabold transition-all shrink-0 flex items-center gap-2 shadow-md ${
              isAutoMode
                ? 'bg-amber-950 border-amber-600 text-amber-200 hover:bg-amber-900'
                : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-600 hover:bg-slate-800'
            }`}
          >
            <Zap className="w-4 h-4 text-amber-400 fill-amber-400" />
            <span>{isAutoMode ? 'Авторежим ВКЛ ⚡' : 'Переключить в Авторежим ⚡'}</span>
          </button>
        </div>

        {/* Action Buttons */}
        <div className="pt-2 flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleCreateProject}
            disabled={!topicOrScript.trim() || isSubmitting}
            className="flex-1 py-4 bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-700 hover:from-indigo-500 hover:to-purple-500 text-white font-extrabold text-base rounded-xl shadow-xl shadow-indigo-900/40 flex items-center justify-center gap-3 transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none"
          >
            <Wand2 className="w-6 h-6" />
            <span>СОЗДАТЬ ПРОЕКТ</span>
          </button>

          {onClearAllProjects && (
            <button
              onClick={() => {
                if (window.confirm("Вы уверены, что хотите полностью очистить все проекты и файлы?")) {
                  onClearAllProjects();
                }
              }}
              type="button"
              title="Очистить все проекты и сбросить зависшие задачи"
              className="py-4 px-5 bg-red-950/40 hover:bg-red-900/60 border border-red-800/60 text-red-300 font-semibold text-sm rounded-xl flex items-center justify-center gap-2 transition-colors shrink-0"
            >
              <Trash2 className="w-5 h-5 text-red-400" />
              <span>Очистить всё</span>
            </button>
          )}
        </div>

        <div className="flex items-center justify-center gap-2 text-xs text-amber-300/90 pt-1">
          <Bot className="w-4 h-4 text-indigo-400" />
          <span>Бесплатный режим по умолчанию: локальные карточки и голос Windows. Карточки не являются AI-иллюстрациями; их можно заменить.</span>
        </div>

      </div>
    </div>
  );
};
