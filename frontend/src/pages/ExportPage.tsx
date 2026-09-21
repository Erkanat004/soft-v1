import React, { useState } from 'react';
import { Project } from '../types';
import { api } from '../api';
import { Download, Play, Film, CheckCircle2, Loader2, FileVideo, Sparkles } from 'lucide-react';

interface ExportPageProps {
  project: Project;
}

export const ExportPage: React.FC<ExportPageProps> = ({ project }) => {
  const [isRendering, setIsRendering] = useState(false);
  const [renderedUrl, setRenderedUrl] = useState<string | null>(
    project.status === 'completed' ? `/api/projects/${project.id}/render/output.mp4` : null
  );

  const handleRender = async () => {
    setIsRendering(true);
    try {
      await api.startRender(project.id);
      setRenderedUrl(`/api/projects/${project.id}/render/output.mp4?t=${Date.now()}`);
    } catch (err) {
      alert("FFmpeg final video rendering failed. Make sure all scene images & TTS audio are generated.");
    } finally {
      setIsRendering(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-6 space-y-8">
      <div className="border-b border-dark-700 pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Download className="w-6 h-6 text-purple-400" />
            <span>Render & Export MP4</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Local FFmpeg video assembly with Ken Burns camera motion, transitions, background music, and burned subtitles.
          </p>
        </div>

        <button
          onClick={handleRender}
          disabled={isRendering}
          className="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-purple-900/30 flex items-center gap-2 transition-all hover:scale-[1.02] disabled:opacity-50"
        >
          {isRendering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Film className="w-4 h-4" />}
          <span>{isRendering ? 'Rendering Video...' : 'Render Final MP4'}</span>
        </button>
      </div>

      {/* Video Player & Status Card */}
      <div className="bg-dark-800 border border-dark-700 rounded-2xl p-6 shadow-2xl space-y-6">
        {renderedUrl ? (
          <div className="space-y-4">
            <div className="aspect-video bg-black rounded-xl overflow-hidden border border-dark-700 shadow-2xl relative">
              <video
                controls
                src={renderedUrl}
                className="w-full h-full object-contain"
              />
            </div>

            <div className="flex items-center justify-between p-4 bg-dark-900/80 rounded-xl border border-dark-700/60">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <div>
                  <h4 className="text-sm font-semibold text-white">Video Render Complete</h4>
                  <p className="text-xs text-slate-400">Ready for YouTube upload (1080p H.264 AAC MP4)</p>
                </div>
              </div>

              <a
                href={renderedUrl}
                download={`storyforge_${project.id}.mp4`}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl shadow-md flex items-center gap-2 transition-all hover:scale-105"
              >
                <Download className="w-4 h-4" />
                <span>Download MP4</span>
              </a>
            </div>
          </div>
        ) : (
          <div className="py-20 text-center space-y-4">
            <FileVideo className="w-16 h-16 text-slate-600 mx-auto animate-pulse" />
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-300">Final MP4 Video Not Rendered Yet</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Click "Render Final MP4" or launch AUTO MODE to execute the complete video creation pipeline.
              </p>
            </div>
          </div>
        )}

        {/* Video Settings Summary */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-dark-700/60">
          <div className="p-3 bg-dark-900/60 rounded-xl border border-dark-700/60">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Resolution</span>
            <span className="text-xs font-semibold text-slate-200">1920×1080 (16:9)</span>
          </div>

          <div className="p-3 bg-dark-900/60 rounded-xl border border-dark-700/60">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">FPS / Codec</span>
            <span className="text-xs font-semibold text-slate-200">30 FPS • H.264</span>
          </div>

          <div className="p-3 bg-dark-900/60 rounded-xl border border-dark-700/60">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Audio Codec</span>
            <span className="text-xs font-semibold text-slate-200">AAC (192kbps)</span>
          </div>

          <div className="p-3 bg-dark-900/60 rounded-xl border border-dark-700/60">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Subtitles</span>
            <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              <span>Burned SRT Overlay</span>
            </span>
          </div>
        </div>

      </div>
    </div>
  );
};
