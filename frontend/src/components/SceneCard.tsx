import React, { useState } from 'react';
import { Scene } from '../types';

interface SceneCardProps {
  scene: Scene;
  isSelected: boolean;
  onSelect: (uuid: string, selected: boolean) => void;
  onUpdate: (uuid: string, updates: Partial<Scene>) => void;
  onDelete: (uuid: string) => void;
  onSplit: (uuid: string) => void;
  onMergeWithNext?: (uuid: string) => void;
  onGenerateImage: (uuid: string) => void;
  onGenerateTTS: (uuid: string) => void;
  onRenderClip: (uuid: string) => void;
  onUploadImage: (uuid: string, file: File) => void;
  onUploadAudio: (uuid: string, file: File) => void;
  onPreviewScene?: (scene: Scene) => void;
}

export const SceneCard: React.FC<SceneCardProps> = ({
  scene,
  isSelected,
  onSelect,
  onUpdate,
  onDelete,
  onSplit,
  onMergeWithNext,
  onGenerateImage,
  onGenerateTTS,
  onRenderClip,
  onUploadImage,
  onUploadAudio,
  onPreviewScene
}) => {
  const [narration, setNarration] = useState(scene.narration);
  const [imagePrompt, setImagePrompt] = useState(scene.image_prompt || '');
  const [cameraMotion, setCameraMotion] = useState(scene.camera_motion || 'slow_zoom_in');
  const [isExpanded, setIsExpanded] = useState(false);

  const getMediaUrl = (path?: string) => {
    if (!path) return '';
    if (path.startsWith('http')) return path;
    const normalized = path.replace(/\\/g, '/');
    const idx = normalized.indexOf('projects/');
    if (idx !== -1) {
      return `/media/${normalized.substring(idx)}`;
    }
    return `/media/projects/${scene.project_id}/${path}`;
  };

  const handleNarrationBlur = () => {
    if (narration !== scene.narration) {
      onUpdate(scene.scene_uuid, { narration });
    }
  };

  const handlePromptBlur = () => {
    if (imagePrompt !== scene.image_prompt) {
      onUpdate(scene.scene_uuid, { image_prompt: imagePrompt });
    }
  };

  const handleMotionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const motion = e.target.value;
    setCameraMotion(motion);
    onUpdate(scene.scene_uuid, { camera_motion: motion, clip_status: 'outdated' });
  };

  const renderBadge = (label: string, status: string) => {
    let colorClass = 'bg-gray-800 text-gray-400 border-gray-700';
    if (status === 'completed') colorClass = 'bg-emerald-950/80 text-emerald-400 border-emerald-700';
    else if (status === 'running' || status === 'queued') colorClass = 'bg-amber-950/80 text-amber-400 border-amber-700 animate-pulse';
    else if (status === 'outdated') colorClass = 'bg-orange-950/80 text-orange-400 border-orange-700';
    else if (status === 'error') colorClass = 'bg-red-950/80 text-red-400 border-red-700';

    return (
      <span className={`px-2 py-0.5 text-xs rounded border font-mono ${colorClass}`}>
        {label}: {status}
      </span>
    );
  };

  return (
    <div className={`rounded-xl border transition-all duration-200 ${
      isSelected 
        ? 'border-indigo-500 bg-slate-900/90 shadow-lg shadow-indigo-500/10' 
        : 'border-slate-800 bg-slate-950/70 hover:border-slate-700'
    }`}>
      {/* Header Bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/80 bg-slate-900/50">
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={(e) => onSelect(scene.scene_uuid, e.target.checked)}
            className="w-4 h-4 rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 bg-slate-900"
          />
          <span className="font-bold text-white text-sm">Сцена {scene.scene_order}</span>
          <span className="text-xs font-mono text-slate-500 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
            {scene.scene_uuid.substring(0, 8)}
          </span>
          <span className="text-xs text-slate-400">
            ⏱ {scene.actual_duration ? `${scene.actual_duration}s` : `~${scene.duration_target}s`}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {renderBadge('Img', scene.image_status)}
          {renderBadge('Audio', scene.tts_status)}
          {renderBadge('Clip', scene.clip_status)}
        </div>
      </div>

      {/* Main Body */}
      <div className="p-4 grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Media Preview */}
        <div className="lg:col-span-4 flex flex-col gap-3">
          <div className="relative aspect-video rounded-lg overflow-hidden border border-slate-800 bg-slate-900 group flex items-center justify-center">
            {scene.image_path ? (
              <img
                src={getMediaUrl(scene.image_path)}
                alt={`Scene ${scene.scene_order}`}
                className="w-full h-full object-cover transition-transform group-hover:scale-105"
              />
            ) : (
              <div className="flex flex-col items-center justify-center text-slate-600 gap-1">
                <span className="text-2xl">🖼</span>
                <span className="text-xs">Изображение не создано</span>
              </div>
            )}

            {/* Overlay buttons */}
            <div className="absolute inset-0 bg-slate-950/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
              <label className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-white rounded cursor-pointer border border-slate-600">
                Загрузить
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files?.[0]) onUploadImage(scene.scene_uuid, e.target.files[0]);
                  }}
                />
              </label>
              {onPreviewScene && scene.image_path && (
                <button
                  onClick={() => onPreviewScene(scene)}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-xs text-white rounded border border-indigo-400"
                >
                  Предпросмотр
                </button>
              )}
            </div>
          </div>

          {/* Audio Player & Upload */}
          <div className="flex flex-col gap-1.5">
            {scene.audio_path ? (
              <audio
                controls
                src={getMediaUrl(scene.audio_path)}
                className="w-full h-8 border border-slate-800 rounded bg-slate-900"
              />
            ) : (
              <div className="text-xs text-slate-500 text-center py-1 bg-slate-900/50 rounded border border-slate-800">
                Озвучка не сгенерирована
              </div>
            )}

            <div className="flex items-center justify-between text-xs text-slate-400">
              <label className="text-indigo-400 hover:underline cursor-pointer">
                + Свой аудиофайл
                <input
                  type="file"
                  accept="audio/*"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files?.[0]) onUploadAudio(scene.scene_uuid, e.target.files[0]);
                  }}
                />
              </label>
            </div>
          </div>
        </div>

        {/* Right Column: Narration & Prompts */}
        <div className="lg:col-span-8 flex flex-col gap-3">
          {/* Narration Textarea */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Текст диктора (Дикторская речь)
              </label>
              {scene.tts_status === 'outdated' && (
                <span className="text-xs text-orange-400">⚠️ Текст изменен, требуется пере-озвучка</span>
              )}
            </div>
            <textarea
              value={narration}
              onChange={(e) => setNarration(e.target.value)}
              onBlur={handleNarrationBlur}
              rows={3}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 resize-y font-sans"
              placeholder="Введите дикторский текст для сцены..."
            />
          </div>

          {/* Image Prompt */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Промпт для изображения (Image Prompt)
            </label>
            <input
              type="text"
              value={imagePrompt}
              onChange={(e) => setImagePrompt(e.target.value)}
              onBlur={handlePromptBlur}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 font-mono"
              placeholder="Visual description for AI image generator..."
            />
          </div>

          {/* Settings Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800/80">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Анимация камеры:</span>
              <select
                value={cameraMotion}
                onChange={handleMotionChange}
                className="bg-slate-900 border border-slate-800 rounded text-xs text-slate-200 px-2 py-1 focus:border-indigo-500"
              >
                <option value="slow_zoom_in">🔍 Медленный зум-ин</option>
                <option value="slow_zoom_out">🔍 Медленный зум-аут</option>
                <option value="pan_left">⬅️ Панорама влево</option>
                <option value="pan_right">➡️ Панорама вправо</option>
                <option value="pan_up">⬆️ Панорама вверх</option>
                <option value="pan_down">⬇️ Панорама вниз</option>
                <option value="zoom_pan_left">↖️ Зум + Лево</option>
                <option value="zoom_pan_right">↗️ Зум + Право</option>
                <option value="static">⏸ Статично</option>
              </select>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <button
                onClick={() => onGenerateImage(scene.scene_uuid)}
                disabled={scene.image_status === 'running'}
                className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-xs text-indigo-300 rounded border border-slate-700 disabled:opacity-50"
              >
                🎨 Промпт в Изображение
              </button>
              <button
                onClick={() => onGenerateTTS(scene.scene_uuid)}
                disabled={scene.tts_status === 'running'}
                className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-xs text-emerald-300 rounded border border-slate-700 disabled:opacity-50"
              >
                🎙 Озвучка
              </button>
              <button
                onClick={() => onRenderClip(scene.scene_uuid)}
                disabled={scene.clip_status === 'running'}
                className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-xs text-amber-300 rounded border border-slate-700 disabled:opacity-50"
              >
                🎬 Клип
              </button>
              <button
                onClick={() => onSplit(scene.scene_uuid)}
                className="px-2 py-1 bg-slate-900 hover:bg-slate-800 text-xs text-slate-300 rounded border border-slate-800"
                title="Разбить сцену пополам"
              >
                ✂️ Разбить
              </button>
              {onMergeWithNext && (
                <button
                  onClick={() => onMergeWithNext(scene.scene_uuid)}
                  className="px-2 py-1 bg-slate-900 hover:bg-slate-800 text-xs text-slate-300 rounded border border-slate-800"
                  title="Объединить со следующей"
                >
                  🔗 Объединить
                </button>
              )}
              <button
                onClick={() => onDelete(scene.scene_uuid)}
                className="px-2 py-1 bg-slate-900 hover:bg-red-950 text-xs text-red-400 rounded border border-slate-800 hover:border-red-800"
                title="Удалить сцену"
              >
                🗑
              </button>
            </div>
          </div>

          {/* Error Banner */}
          {scene.error_message && (
            <div className="mt-2 p-2 bg-red-950/80 border border-red-800 rounded text-xs text-red-300 flex items-start gap-2">
              <span>⚠️</span>
              <span>{scene.error_message}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
