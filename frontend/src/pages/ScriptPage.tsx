import React, { useEffect, useRef, useState } from 'react';
import { Project, Script } from '../types';
import { api, apiErrorMessage } from '../api';
import { FileText, Save, Wand2, Flame, Sparkles, Layers, Check, X, Zap } from 'lucide-react';

interface ScriptPageProps {
  project: Project;
  onNavigateToStoryboard?: () => void;
}

export const ScriptPage: React.FC<ScriptPageProps> = ({ project, onNavigateToStoryboard }) => {
  const [script, setScript] = useState<Script | null>(null);
  const [text, setText] = useState('');
  const [creativeBrief, setCreativeBrief] = useState(project.creative_brief || '');
  const [loading, setLoading] = useState(true);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [enhancedDraft, setEnhancedDraft] = useState<string | null>(null);
  const [isDecomposing, setIsDecomposing] = useState(false);

  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const beginAction = () => {
    if (busyRef.current) return false;
    busyRef.current = true;
    setBusy(true);
    return true;
  };
  const endAction = () => {
    busyRef.current = false;
    setBusy(false);
  };

  const wordCount = text.trim().split(/\s+/).filter(Boolean).length;
  const estimatedSeconds = Math.round(wordCount / 2.5);
  const estimatedMin = Math.floor(estimatedSeconds / 60);
  const estimatedSec = estimatedSeconds % 60;

  useEffect(() => {
    let active = true;
    setLoading(true);
    setEnhancedDraft(null);
    setCreativeBrief(project.creative_brief || '');
    api.getScript(project.id).then(data => {
      if (!active) return;
      setScript(data);
      setText(data?.text || project.topic_or_script || '');
    }).catch(err => {
      if (!active) return;
      alert(apiErrorMessage(err, 'Не удалось загрузить сценарий'));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [project.id]);

  const handleSave = async () => {
    if (!beginAction()) return;
    try {
      const updated = await api.updateScript(project.id, text);
      setScript(updated);
      alert("Сценарий успешно сохранен!");
    } catch (err) {
      alert(apiErrorMessage(err, "Ошибка при сохранении сценария"));
    } finally {
      endAction();
    }
  };

  const handleSaveBrief = async () => {
    if (!beginAction()) return;
    try {
      await api.updateProject(project.id, { creative_brief: creativeBrief.trim() });
      alert('Бриф сохранён. Он повлияет на следующую генерацию сценария, но не перепишет уже сохранённый текст.');
    } catch (err) { alert(apiErrorMessage(err, 'Не удалось сохранить бриф')); }
    finally { endAction(); }
  };

  const handleEnhance = async (instruction: string) => {
    if (!window.confirm('Улучшение сценария отправит запрос выбранному текстовому AI-провайдеру. Продолжить?')) return;
    if (!beginAction()) return;
    setIsEnhancing(true);
    try {
      await api.updateScript(project.id, text);
      const updated = await api.enhanceScript(project.id, instruction);
      setEnhancedDraft(updated.text);
    } catch (err) {
      alert(apiErrorMessage(err, "Ошибка ИИ-улучшения сценария"));
    } finally {
      setIsEnhancing(false);
      endAction();
    }
  };

  const handleDecompose = async () => {
    if (!beginAction()) return;
    setIsDecomposing(true);
    try {
      // Save current text first
      await api.updateScript(project.id, text);
      await api.decomposeScenes(project.id);
      if (onNavigateToStoryboard) {
        onNavigateToStoryboard();
      } else {
        alert("Сценарий успешно разбит на сцены!");
      }
    } catch (err) {
      alert(apiErrorMessage(err, "Ошибка при разбивке сценария на сцены"));
    } finally {
      setIsDecomposing(false);
      endAction();
    }
  };

  const handleTriggerAutoMode = async () => {
    if (!window.confirm('Авторежим может вызвать внешние AI API. Расходы зависят от ваших ключей и тарифа. Продолжить?')) return;
    if (!beginAction()) return;
    try {
      await api.updateScript(project.id, text);
      await api.triggerAutoRemaining(project.id);
      if (onNavigateToStoryboard) {
        onNavigateToStoryboard();
      }
    } catch (err) {
      alert(apiErrorMessage(err, "Ошибка запуска авторежима"));
    } finally {
      endAction();
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-6 space-y-6">
      <section className="rounded-xl border border-slate-800 bg-slate-900 p-4 space-y-2">
        <label className="text-sm font-semibold">Творческий бриф проекта</label>
        <textarea rows={3} maxLength={4000} value={creativeBrief} onChange={event => setCreativeBrief(event.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm" />
        <div className="flex items-center justify-between gap-3"><p className="text-xs text-slate-500">Только ориентиры формата и ваша новая идея; не копируйте чужие сцены или текст.</p>
          <button disabled={busy} onClick={handleSaveBrief} className="shrink-0 rounded-lg bg-slate-700 px-3 py-2 text-xs font-semibold disabled:opacity-40">Сохранить бриф</button></div>
      </section>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <FileText className="w-6 h-6 text-indigo-400" />
            <span>Редактор Сценария</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Словосочетаний: <strong className="text-slate-200">{wordCount}</strong> | Примерная длительность: <strong className="text-indigo-300">~{estimatedMin}м {estimatedSec}с</strong> (Рассчитана из 2.5 слов/сек)
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={busy || loading}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white font-semibold rounded-xl text-xs flex items-center gap-2 border border-slate-700 transition-all"
          >
            <Save className="w-4 h-4" />
            <span>Сохранить</span>
          </button>

          <button
            onClick={handleDecompose}
            disabled={busy || loading || !text.trim()}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl text-xs flex items-center gap-2 shadow-lg shadow-indigo-900/40 transition-all disabled:opacity-50"
          >
            <Layers className="w-4 h-4" />
            <span>Разбить на сцены →</span>
          </button>

          <button
            onClick={handleTriggerAutoMode}
            disabled={busy || loading || !text.trim()}
            className="px-4 py-2 bg-gradient-to-r from-amber-600 to-indigo-600 hover:from-amber-500 hover:to-indigo-500 text-white font-extrabold rounded-xl text-xs flex items-center gap-2 shadow-lg shadow-indigo-950/40 transition-all disabled:opacity-50"
            title="Запустить полную автоматическую доработку проекта"
          >
            <Zap className="w-4 h-4 text-amber-300 fill-amber-300" />
            <span>⚡ Авторежим</span>
          </button>
        </div>
      </div>

      {/* AI Refinement Buttons Toolbar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-wrap items-center gap-3 shadow-md">
        <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5 mr-2">
          <Wand2 className="w-4 h-4 text-indigo-400" />
          <span>ИИ-Улучшение сценария:</span>
        </span>

        <button
          onClick={() => handleEnhance("Сделай историю более атмосферной, темной и пугающей")}
          disabled={busy || loading || !text.trim()}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors disabled:opacity-50 border border-slate-700"
        >
          <Flame className="w-3.5 h-3.5 text-red-400" />
          <span>Сделать мрачнее</span>
        </button>

        <button
          onClick={() => handleEnhance("Сделай дикторскую речь более эмоциональной и увлекательной")}
          disabled={busy || loading || !text.trim()}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors disabled:opacity-50 border border-slate-700"
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span>Больше эмоций</span>
        </button>

        <button
          onClick={() => handleEnhance("Усили крючок в первых двух предложениях для YouTube удержания")}
          disabled={busy || loading || !text.trim()}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors disabled:opacity-50 border border-slate-700"
        >
          <span>Сильный крючок (Hook)</span>
        </button>
      </div>

      {/* Main Textarea */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative">
        {loading ? (
          <div className="text-center py-12 text-slate-500 text-sm">Загрузка сценария...</div>
        ) : (
          <textarea
            disabled={busy}
            rows={18}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl p-5 text-slate-100 text-sm leading-relaxed font-sans focus:outline-none focus:border-indigo-500 resize-y"
            placeholder="Вставьте сюда текст дикторской речи или темы..."
          />
        )}
      </div>

      {/* Enhanced Draft Preview Modal */}
      {enhancedDraft && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-4xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-amber-400" />
              <span>Предпросмотр ИИ-версии сценария</span>
            </h3>
            <p className="text-xs text-slate-400">
              Сравните предложенный вариант с текущим. Вы можете принять его или отклонить.
            </p>
            <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 text-sm text-slate-200 font-sans whitespace-pre-wrap leading-relaxed max-h-[50vh] overflow-y-auto">
              {enhancedDraft}
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setEnhancedDraft(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg flex items-center gap-2 border border-slate-700"
              >
                <X className="w-4 h-4" />
                <span>Отклонить</span>
              </button>
              <button
                onClick={() => {
                  setText(enhancedDraft);
                  setEnhancedDraft(null);
                }}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2"
              >
                <Check className="w-4 h-4" />
                <span>Принять версию</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
