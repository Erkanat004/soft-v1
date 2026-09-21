import React, { useEffect, useState } from 'react';
import { Project, Scene } from '../types';
import { api } from '../api';
import { Film, RefreshCw, Volume2, Image as ImageIcon, Camera, Sparkles } from 'lucide-react';

interface StoryboardPageProps {
  project: Project;
}

export const StoryboardPage: React.FC<StoryboardPageProps> = ({ project }) => {
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [loading, setLoading] = useState(true);

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

  const handleRegenerateImage = async (sceneId: number) => {
    try {
      await api.regenerateSceneImage(project.id, sceneId);
      loadScenes();
    } catch (err) {
      alert("Failed to regenerate image");
    }
  };

  const handleRegenerateTTS = async (sceneId: number) => {
    try {
      await api.regenerateSceneTTS(project.id, sceneId);
      loadScenes();
    } catch (err) {
      alert("Failed to regenerate TTS audio");
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-8 px-6 space-y-6">
      <div className="flex items-center justify-between border-b border-dark-700 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Film className="w-6 h-6 text-purple-400" />
            <span>Storyboard Scenes ({scenes.length})</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Visual scene decomposition with narration, camera motion presets, image prompts, and audio durations.
          </p>
        </div>
        <button
          onClick={loadScenes}
          className="px-3 py-1.5 bg-dark-700 hover:bg-dark-600 text-slate-300 text-xs font-medium rounded-lg flex items-center gap-1.5"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-500 text-sm">Loading scenes...</div>
      ) : scenes.length === 0 ? (
        <div className="text-center py-16 bg-dark-800 border border-dark-700 rounded-2xl p-8 space-y-3">
          <Film className="w-10 h-10 text-slate-600 mx-auto" />
          <h4 className="text-base font-semibold text-slate-300">No scenes found</h4>
          <p className="text-xs text-slate-500">Run AUTO MODE on the launcher home screen to automatically split script into visual scenes.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {scenes.map((sc) => (
            <div key={sc.id} className="bg-dark-800 border border-dark-700 rounded-2xl overflow-hidden shadow-xl flex flex-col justify-between">
              
              {/* Image Preview / Placeholder */}
              <div className="aspect-video bg-dark-900 relative border-b border-dark-700/60 overflow-hidden group">
                {sc.image_path ? (
                  <img
                    src={`/media/${sc.image_path.replace(/\\/g, '/')}`}
                    alt={`Scene ${sc.scene_order}`}
                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-slate-600 space-y-1">
                    <ImageIcon className="w-8 h-8" />
                    <span className="text-xs font-medium">Pending Image</span>
                  </div>
                )}

                {/* Scene Order Badge */}
                <div className="absolute top-2 left-2 px-2.5 py-1 rounded-lg bg-black/70 backdrop-blur-md text-white text-xs font-bold border border-white/10">
                  Scene {sc.scene_order}
                </div>

                {/* Shot Type & Motion Badge */}
                <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-purple-950/80 backdrop-blur-md text-purple-300 text-[10px] font-semibold border border-purple-800/40 flex items-center gap-1">
                  <Camera className="w-3 h-3" />
                  <span>{sc.shot_type} • {sc.camera_motion}</span>
                </div>
              </div>

              {/* Scene Content */}
              <div className="p-4 space-y-3 flex-1 flex flex-col justify-between">
                <div className="space-y-2">
                  <p className="text-xs text-slate-200 line-clamp-3 leading-relaxed font-medium">
                    "{sc.narration}"
                  </p>

                  <div className="p-2.5 bg-dark-900/60 rounded-xl border border-dark-700/60 space-y-1">
                    <span className="text-[10px] uppercase font-bold text-slate-500 flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-purple-400" />
                      Prompt
                    </span>
                    <p className="text-[11px] text-slate-400 line-clamp-2 italic">
                      {sc.image_prompt}
                    </p>
                  </div>
                </div>

                {/* Footer Controls */}
                <div className="pt-2 border-t border-dark-700/60 flex items-center justify-between text-xs text-slate-400">
                  <div className="flex items-center gap-1">
                    <Volume2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>{sc.actual_duration ? `${sc.actual_duration.toFixed(1)}s` : `${sc.duration_target}s`}</span>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => handleRegenerateTTS(sc.id)}
                      className="px-2.5 py-1 bg-dark-700 hover:bg-dark-600 text-slate-300 text-[11px] font-medium rounded-lg"
                    >
                      TTS
                    </button>
                    <button
                      onClick={() => handleRegenerateImage(sc.id)}
                      className="px-2.5 py-1 bg-purple-600 hover:bg-purple-500 text-white text-[11px] font-semibold rounded-lg shadow-md"
                    >
                      Image
                    </button>
                  </div>
                </div>

              </div>

            </div>
          ))}
        </div>
      )}
    </div>
  );
};
