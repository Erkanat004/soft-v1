import React, { useEffect, useState } from 'react';
import { Project, Scene } from '../types';
import { api } from '../api';
import { Download, Film, CheckCircle2, Loader2, FileVideo, Sparkles, AlertCircle, RefreshCw } from 'lucide-react';

interface ExportPageProps {
  project: Project;
}

export const ExportPage: React.FC<ExportPageProps> = ({ project }) => {
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [isRendering, setIsRendering] = useState(false);
  const [renderedUrl, setRenderedUrl] = useState<string | null>(null);
  const [hasFinalVideo, setHasFinalVideo] = useState(false);
  const [renderIsCurrent, setRenderIsCurrent] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setScenes([]);
    setHasFinalVideo(false);
    setRenderedUrl(null);
    setRenderIsCurrent(false);
    void Promise.all([api.listScenes(project.id), api.getRenderStatus(project.id)])
      .then(([items, status]) => {
        if (cancelled) return;
        setScenes(items);
        setRenderIsCurrent(status.current);
        if (status.exists) setRenderedUrl(`/media/projects/${project.id}/output/final.mp4`);
      })
      .catch(err => console.error("Failed to load export status:", err));
    return () => { cancelled = true; };
  }, [project.id]);

  const imagesReady = scenes.filter(s => s.image_status === 'completed').length;
  const ttsReady = scenes.filter(s => s.tts_status === 'completed').length;
  const clipsReady = scenes.filter(s => s.clip_status === 'completed').length;
  const isAllReady = scenes.length > 0 && imagesReady === scenes.length && ttsReady === scenes.length;
  const blockingScenes = scenes.filter(s => s.image_status !== 'completed' || ['outdated', 'error'].includes(s.tts_status));
  const staleClips = scenes.some(s => ['outdated', 'error'].includes(s.clip_status));

  const handleExport = async () => {
    setIsRendering(true);
    try {
      await api.exportProject(project.id);
      setRenderedUrl(`/media/projects/${project.id}/output/final.mp4?t=${Date.now()}`);
      setHasFinalVideo(true);
      setRenderIsCurrent(true);
      alert("Сборка видео успешно завершена!");
    } catch (err: any) {
      alert(`Ошибка рендера видео: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setIsRendering(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-6 space-y-8">
      {/* Header */}
      <div className="border-b border-slate-800 pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Download className="w-6 h-6 text-indigo-400" />
            <span>Предпросмотр & Сборка MP4</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Финальный рендер через локальный FFmpeg с поддержкой переходов, панорамирования камеры, встроенными субтитрами и фоновой музыкой.
          </p>
        </div>

        <button
          onClick={handleExport}
          disabled={isRendering || scenes.length === 0 || blockingScenes.length > 0}
          className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-700 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-indigo-900/40 flex items-center gap-2 transition-all hover:scale-[1.02] disabled:opacity-50"
        >
          {isRendering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Film className="w-4 h-4" />}
          <span>{isRendering ? 'Идет рендер...' : 'Собрать финальный MP4'}</span>
        </button>
      </div>

      {/* Pre-flight Check Dashboard */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-md">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
          Статус готовности материалов (Pre-flight Check)
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-center">
            <span className="text-xs text-slate-400 block">Всего сцен</span>
            <span className="text-lg font-bold text-white">{scenes.length}</span>
          </div>

          <div className={`p-3 rounded-xl border text-center ${imagesReady === scenes.length && scenes.length > 0 ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300' : 'bg-slate-950 border-slate-800 text-slate-300'}`}>
            <span className="text-xs text-slate-400 block">Изображения</span>
            <span className="text-lg font-bold">{imagesReady} / {scenes.length}</span>
          </div>

          <div className={`p-3 rounded-xl border text-center ${ttsReady === scenes.length && scenes.length > 0 ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300' : 'bg-slate-950 border-slate-800 text-slate-300'}`}>
            <span className="text-xs text-slate-400 block">Озвучка</span>
            <span className="text-lg font-bold">{ttsReady} / {scenes.length}</span>
          </div>

          <div className={`p-3 rounded-xl border text-center ${clipsReady === scenes.length && scenes.length > 0 ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300' : 'bg-slate-950 border-slate-800 text-slate-300'}`}>
            <span className="text-xs text-slate-400 block">Готовые клипы</span>
            <span className="text-lg font-bold">{clipsReady} / {scenes.length}</span>
          </div>
        </div>

        {!isAllReady && (
          <div className="mt-3 p-2.5 bg-amber-950/60 border border-amber-800/80 rounded-xl text-xs text-amber-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{blockingScenes.length > 0
              ? `Подготовьте изображения и обновите устаревшую озвучку для ${blockingScenes.length} сцен(ы) перед экспортом.`
              : 'Сцены без озвучки будут экспортированы с тишиной. Клипы будут созданы автоматически.'}</span>
          </div>
        )}
        {staleClips && <p className="mt-3 text-xs text-amber-300">Клипы с устаревшим движением будут пересобраны при экспорте.</p>}
      </div>

      {/* Video Player & Status Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6">
        {renderedUrl ? (
          <div className="space-y-4">
            <div className="aspect-video bg-black rounded-xl overflow-hidden border border-slate-800 shadow-2xl relative">
              <video
                controls
                src={renderedUrl}
                className="w-full h-full object-contain"
                onError={() => setHasFinalVideo(false)}
                onLoadedData={() => setHasFinalVideo(true)}
              />
            </div>

            {hasFinalVideo && (
              <div className="flex items-center justify-between p-4 bg-slate-950 rounded-xl border border-slate-800">
                <div className="flex items-center gap-3">
                  {renderIsCurrent
                    ? <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    : <AlertCircle className="w-5 h-5 text-amber-400" />}
                  <div>
                    <h4 className="text-sm font-semibold text-white">{renderIsCurrent ? 'Видео собрано из текущих сцен' : 'Это предыдущая версия видео'}</h4>
                    <p className="text-xs text-slate-400">{renderIsCurrent ? 'Готово для скачивания (H.264 AAC MP4)' : 'После изменений в сценах соберите MP4 заново.'}</p>
                  </div>
                </div>

                <a
                  href={renderedUrl}
                  download={`storyforge_${project.id}.mp4`}
                  className={`px-4 py-2 text-white font-bold text-xs rounded-xl shadow-md flex items-center gap-2 transition-all hover:scale-105 ${renderIsCurrent ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-amber-700 hover:bg-amber-600'}`}
                >
                  <Download className="w-4 h-4" />
                  <span>{renderIsCurrent ? 'Скачать MP4' : 'Скачать предыдущий MP4'}</span>
                </a>
              </div>
            )}
          </div>
        ) : (
          <div className="py-20 text-center space-y-4">
            <FileVideo className="w-16 h-16 text-slate-600 mx-auto animate-pulse" />
            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-300">Финальное видео еще не собрано</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Нажмите "Собрать финальный MP4" для запуска сборки всех сцен в единый ролик.
              </p>
            </div>
          </div>
        )}

        {/* Video Settings Summary */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-slate-800">
          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Формат кадра</span>
            <span className="text-xs font-semibold text-slate-200">{project.aspect_ratio || "16:9"} ({project.resolution || "1080p"})</span>
          </div>

          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Кадров/сек</span>
            <span className="text-xs font-semibold text-slate-200">30 FPS • H.264</span>
          </div>

          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Аудио кодек</span>
            <span className="text-xs font-semibold text-slate-200">AAC (192kbps)</span>
          </div>

          <div className="p-3 bg-slate-950 rounded-xl border border-slate-800">
            <span className="text-[10px] uppercase font-bold text-slate-500 block">Субтитры</span>
            <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              <span>SRT Наложение</span>
            </span>
          </div>
        </div>

      </div>
    </div>
  );
};
