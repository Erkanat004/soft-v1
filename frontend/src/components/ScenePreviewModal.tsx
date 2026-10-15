import React from 'react';
import { Scene } from '../types';

interface ScenePreviewModalProps {
  scene: Scene;
  onClose: () => void;
}

export const ScenePreviewModal: React.FC<ScenePreviewModalProps> = ({ scene, onClose }) => {
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-3xl w-full p-5 shadow-2xl flex flex-col gap-4">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-bold text-white">Предпросмотр сцены #{scene.scene_order}</h3>
            <span className="text-xs font-mono bg-slate-800 text-indigo-400 px-2 py-0.5 rounded">
              {scene.scene_uuid}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white text-xl font-bold w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-800"
          >
            ✕
          </button>
        </div>

        {/* Video / Image Display */}
        <div className="relative aspect-video bg-black rounded-lg overflow-hidden flex items-center justify-center border border-slate-800">
          {scene.video_clip_path ? (
            <video
              src={getMediaUrl(scene.video_clip_path)}
              controls
              autoPlay
              className="w-full h-full object-contain"
            />
          ) : scene.image_path ? (
            <div className="relative w-full h-full">
              <img
                src={getMediaUrl(scene.image_path)}
                alt={`Scene ${scene.scene_order}`}
                className="w-full h-full object-contain"
              />
              {scene.audio_path && (
                <div className="absolute bottom-3 left-3 right-3">
                  <audio
                    src={getMediaUrl(scene.audio_path)}
                    controls
                    autoPlay
                    className="w-full"
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="text-slate-500 text-sm">Медиаконтент отсутствует</div>
          )}
        </div>

        {/* Narration Info */}
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
          <div className="text-xs font-bold text-slate-400 mb-1">Дикторский текст:</div>
          <p className="text-sm text-slate-200 leading-relaxed font-sans">{scene.narration}</p>
        </div>

        {/* Footer */}
        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg border border-slate-700"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
};
