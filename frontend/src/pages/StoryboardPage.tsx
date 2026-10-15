import React, { useEffect, useState } from 'react';
import { Job, Project, Scene } from '../types';
import { api } from '../api';
import { Film, RefreshCw, Wand2, Plus, Play, Sparkles, Filter, CheckSquare, Layers } from 'lucide-react';
import { SceneCard } from '../components/SceneCard';
import { ScenePreviewModal } from '../components/ScenePreviewModal';

interface StoryboardPageProps {
  project: Project;
  onNavigateToExport?: () => void;
  onJobStarted?: (job: Job) => void;
}

export const StoryboardPage: React.FC<StoryboardPageProps> = ({ project, onNavigateToExport, onJobStarted }) => {
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedUuids, setSelectedUuids] = useState<Set<string>>(new Set());
  const [activeFilter, setActiveFilter] = useState<'all' | 'missing_image' | 'missing_tts' | 'outdated' | 'error'>('all');
  const [previewScene, setPreviewScene] = useState<Scene | null>(null);
  const [isRunningBatch, setIsRunningBatch] = useState(false);

  const confirmExternal = (provider: string, kind: string, count: number) => {
    if (provider === 'local_cards' || provider === 'windows_tts' || provider === 'mock') return true;
    return window.confirm(`${kind}: будет отправлено до ${count} запросов провайдеру ${provider}. Стоимость и лимиты определяются вашим тарифом. Продолжить?`);
  };

  const loadScenes = async () => {
    setLoading(true);
    try {
      const data = await api.listScenes(project.id);
      setScenes(data);
    } catch (err) {
      console.error("Failed to load scenes:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScenes();
  }, [project.id]);

  const handleSelectScene = (uuid: string, selected: boolean) => {
    const next = new Set(selectedUuids);
    if (selected) next.add(uuid);
    else next.delete(uuid);
    setSelectedUuids(next);
  };

  const handleSelectAll = (select: boolean) => {
    if (select) {
      setSelectedUuids(new Set(scenes.map(s => s.scene_uuid)));
    } else {
      setSelectedUuids(new Set());
    }
  };

  const handleUpdateScene = async (uuid: string, updates: Partial<Scene>) => {
    try {
      const updated = await api.patchScene(uuid, updates);
      setScenes(prev => prev.map(s => s.scene_uuid === uuid ? updated : s));
    } catch (err) {
      console.error("Failed to update scene:", err);
    }
  };

  const handleDeleteScene = async (uuid: string) => {
    if (!window.confirm("Удалить выбранную сцену?")) return;
    try {
      await api.deleteScene(uuid);
      loadScenes();
    } catch (err) {
      alert("Ошибка при удалении сцены");
    }
  };

  const handleSplitScene = async (uuid: string) => {
    try {
      await api.splitScene(uuid);
      loadScenes();
    } catch (err) {
      alert("Не удалось разбить сцену");
    }
  };

  const handleMergeScenes = async (uuid1: string) => {
    const idx = scenes.findIndex(s => s.scene_uuid === uuid1);
    if (idx === -1 || idx >= scenes.length - 1) return;
    const uuid2 = scenes[idx + 1].scene_uuid;
    try {
      await api.mergeScenes(uuid1, uuid2);
      loadScenes();
    } catch (err) {
      alert("Не удалось объединить сцены");
    }
  };

  const handleAddScene = async () => {
    const text = prompt("Введите дикторский текст для новой сцены:");
    if (!text || !text.trim()) return;
    try {
      await api.addScene(project.id, text.trim());
      loadScenes();
    } catch (err) {
      alert("Не удалось добавить сцену");
    }
  };

  const handleGenerateImage = async (uuid: string) => {
    if (!confirmExternal(project.active_image_provider, 'Изображение', 1)) return;
    try {
      const updated = await api.generateSceneImage(uuid);
      setScenes(prev => prev.map(s => s.scene_uuid === uuid ? updated : s));
    } catch (err: any) {
      alert(`Ошибка генерации изображения: ${err?.response?.data?.detail || err.message}`);
      loadScenes();
    }
  };

  const handleGenerateTTS = async (uuid: string) => {
    if (!confirmExternal(project.active_tts_provider, 'Озвучка', 1)) return;
    try {
      const updated = await api.generateSceneTTS(uuid);
      setScenes(prev => prev.map(s => s.scene_uuid === uuid ? updated : s));
    } catch (err: any) {
      alert(`Ошибка генерации озвучки: ${err?.response?.data?.detail || err.message}`);
      loadScenes();
    }
  };

  const handleRenderClip = async (uuid: string) => {
    try {
      const updated = await api.renderSceneClip(uuid);
      setScenes(prev => prev.map(s => s.scene_uuid === uuid ? updated : s));
    } catch (err: any) {
      alert(`Ошибка рендера клипа: ${err?.response?.data?.detail || err.message}`);
      loadScenes();
    }
  };

  const handleUploadImage = async (uuid: string, file: File) => {
    try {
      const updated = await api.uploadSceneImage(uuid, file);
      setScenes(prev => prev.map(s => s.scene_uuid === uuid ? updated : s));
    } catch (err) {
      alert("Ошибка загрузки изображения");
    }
  };

  const handleUploadAudio = async (uuid: string, file: File) => {
    try {
      const updated = await api.uploadSceneAudio(uuid, file);
      setScenes(prev => prev.map(s => s.scene_uuid === uuid ? updated : s));
    } catch (err) {
      alert("Ошибка загрузки аудиофайла");
    }
  };

  const handleBatchImages = async () => {
    if (!confirmExternal(project.active_image_provider, 'Пакет изображений', scenes.length)) return;
    setIsRunningBatch(true);
    try {
      const job = await api.triggerBatchImages(project.id);
      onJobStarted?.(job);
    } catch (err) {
      alert("Ошибка запуска пакетной генерации картинок");
    } finally {
      setIsRunningBatch(false);
    }
  };

  const handleBatchTTS = async () => {
    if (!confirmExternal(project.active_tts_provider, 'Пакет озвучки', scenes.length)) return;
    setIsRunningBatch(true);
    try {
      const job = await api.triggerBatchTTS(project.id);
      onJobStarted?.(job);
    } catch (err) {
      alert("Ошибка запуска пакетной озвучки");
    } finally {
      setIsRunningBatch(false);
    }
  };

  const handleBatchClips = async () => {
    setIsRunningBatch(true);
    try {
      const job = await api.triggerBatchClips(project.id);
      onJobStarted?.(job);
    } catch (err) {
      alert("Ошибка запуска пакетного рендера");
    } finally {
      setIsRunningBatch(false);
    }
  };

  const handleAutoRemaining = async () => {
    if (!window.confirm('Авторежим может вызвать внешние AI API для сценария, изображений и озвучки. Стоимость зависит от ваших ключей и тарифа. Продолжить?')) return;
    setIsRunningBatch(true);
    try {
      const job = await api.triggerAutoRemaining(project.id);
      onJobStarted?.(job);
    } catch (err) {
      alert("Ошибка запуска авто-доработки");
    } finally {
      setIsRunningBatch(false);
    }
  };

  const filteredScenes = scenes.filter(s => {
    if (activeFilter === 'missing_image') return s.image_status !== 'completed';
    if (activeFilter === 'missing_tts') return s.tts_status !== 'completed';
    if (activeFilter === 'outdated') return s.image_status === 'outdated' || s.tts_status === 'outdated' || s.clip_status === 'outdated';
    if (activeFilter === 'error') return s.image_status === 'error' || s.tts_status === 'error' || s.clip_status === 'error';
    return true;
  });

  return (
    <div className="max-w-6xl mx-auto py-8 px-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Film className="w-6 h-6 text-indigo-400" />
            <span>Раскадровка & Сцены ({scenes.length})</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Управляйте каждой сценой отдельно: редактируйте промпты, озвучку, анимации и клипы.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleAddScene}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-xl flex items-center gap-2 border border-slate-700"
          >
            <Plus className="w-4 h-4 text-indigo-400" />
            <span>Добавить сцену</span>
          </button>

          <button
            onClick={loadScenes}
            className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl flex items-center gap-2 border border-slate-700"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Обновить</span>
          </button>

          {onNavigateToExport && (
            <button
              onClick={onNavigateToExport}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl text-xs flex items-center gap-2 shadow-lg shadow-indigo-900/40"
            >
              <span>Сборка & Экспорт →</span>
            </button>
          )}
        </div>
      </div>

      {/* Batch Action Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3 shadow-md">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5 mr-1">
            <Wand2 className="w-4 h-4 text-indigo-400" />
            <span>Пакетные действия:</span>
          </span>

          <button
            onClick={handleBatchImages}
            disabled={isRunningBatch}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-indigo-300 text-xs font-medium rounded-lg border border-slate-700 disabled:opacity-50"
          >
            🎨 Сгенерировать все картинки
          </button>

          <button
            onClick={handleBatchTTS}
            disabled={isRunningBatch}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-emerald-300 text-xs font-medium rounded-lg border border-slate-700 disabled:opacity-50"
          >
            🎙 Сгенерировать всю озвучку
          </button>

          <button
            onClick={handleBatchClips}
            disabled={isRunningBatch}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-amber-300 text-xs font-medium rounded-lg border border-slate-700 disabled:opacity-50"
          >
            🎬 Рендерить клипы
          </button>

          <button
            onClick={handleAutoRemaining}
            disabled={isRunningBatch}
            className="px-3 py-1.5 bg-indigo-950 hover:bg-indigo-900 text-indigo-200 text-xs font-bold rounded-lg border border-indigo-700 disabled:opacity-50"
          >
            ⚡ Выполнить недостающие шаги
          </button>
        </div>

        {/* Selection summary */}
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <button
            onClick={() => handleSelectAll(selectedUuids.size < scenes.length)}
            className="flex items-center gap-1 text-slate-300 hover:text-white"
          >
            <CheckSquare className="w-4 h-4 text-indigo-400" />
            <span>{selectedUuids.size === scenes.length ? 'Снять выделение' : 'Выделить все'}</span>
          </button>
          <span>({selectedUuids.size}/{scenes.length})</span>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
        <span className="text-slate-500 font-semibold flex items-center gap-1 mr-1">
          <Filter className="w-3.5 h-3.5" /> Фильтр:
        </span>
        {[
          { key: 'all', label: `Все сцены (${scenes.length})` },
          { key: 'missing_image', label: 'Без картинок' },
          { key: 'missing_tts', label: 'Без озвучки' },
          { key: 'outdated', label: 'Требуют обновления' },
          { key: 'error', label: 'Ошибки' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveFilter(tab.key as any)}
            className={`px-3 py-1.5 rounded-lg border font-medium transition-colors whitespace-nowrap ${
              activeFilter === tab.key
                ? 'bg-indigo-950 text-indigo-300 border-indigo-700'
                : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Main Scenes List */}
      {loading ? (
        <div className="text-center py-16 text-slate-500 text-sm">Загрузка сценария и раскадровки...</div>
      ) : filteredScenes.length === 0 ? (
        <div className="text-center py-16 bg-slate-900 border border-slate-800 rounded-2xl p-8 space-y-3">
          <Film className="w-10 h-10 text-slate-600 mx-auto" />
          <h4 className="text-base font-semibold text-slate-300">Сцены не найдены</h4>
          <p className="text-xs text-slate-500">Нажмите "Добавить сцену" или перейдите в Редактор Сценария для авто-разбивки.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredScenes.map((sc, idx) => (
            <SceneCard
              key={sc.scene_uuid}
              scene={sc}
              isSelected={selectedUuids.has(sc.scene_uuid)}
              onSelect={handleSelectScene}
              onUpdate={handleUpdateScene}
              onDelete={handleDeleteScene}
              onSplit={handleSplitScene}
              onMergeWithNext={idx < filteredScenes.length - 1 ? handleMergeScenes : undefined}
              onGenerateImage={handleGenerateImage}
              onGenerateTTS={handleGenerateTTS}
              onRenderClip={handleRenderClip}
              onUploadImage={handleUploadImage}
              onUploadAudio={handleUploadAudio}
              onPreviewScene={(s) => setPreviewScene(s)}
            />
          ))}
        </div>
      )}

      {/* Preview Modal */}
      {previewScene && (
        <ScenePreviewModal
          scene={previewScene}
          onClose={() => setPreviewScene(null)}
        />
      )}
    </div>
  );
};
