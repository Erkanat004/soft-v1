import React, { useState } from 'react';
import { api, apiErrorMessage, NicheAnalysis, ReferenceAnalysis } from '../api';

interface ResearchPageProps {
  onUseBrief: (topic: string, brief: string) => void;
}

export const ResearchPage: React.FC<ResearchPageProps> = ({ onUseBrief }) => {
  const [video, setVideo] = useState<File | null>(null);
  const [confirmedRights, setConfirmedRights] = useState(false);
  const [reference, setReference] = useState<ReferenceAnalysis | null>(null);
  const [nicheRows, setNicheRows] = useState('');
  const [niche, setNiche] = useState<NicheAnalysis | null>(null);
  const [topic, setTopic] = useState('');
  const [angle, setAngle] = useState('');
  const [brief, setBrief] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const analyzeVideo = async () => {
    if (!video || !confirmedRights) return;
    setBusy(true); setError(''); setReference(null);
    try { setReference(await api.analyzeReference(video)); }
    catch (err) { setError(apiErrorMessage(err, 'Не удалось разобрать видео.')); }
    finally { setBusy(false); }
  };

  const analyzeNiche = async () => {
    setBusy(true); setError(''); setNiche(null);
    try {
      const videos = nicheRows.split('\n').map(line => line.trim()).filter(Boolean).map(line => {
        const pieces = line.split('|').map(part => part.trim());
        if (pieces.length !== 3 || !/^\d+$/.test(pieces[1]) || !/^\d+(\.\d+)?$/.test(pieces[2])) {
          throw new Error('Формат строки: название | просмотры | возраст в днях');
        }
        return { title: pieces[0], views: Number(pieces[1]), age_days: Number(pieces[2]) };
      });
      setNiche(await api.analyzeNiche(videos));
    } catch (err) { setError(err instanceof Error && !('response' in err) ? err.message : apiErrorMessage(err, 'Не удалось сравнить ролики.')); }
    finally { setBusy(false); }
  };

  const createBrief = () => {
    if (!topic.trim() || !angle.trim()) { setError('Укажите собственную тему и новый угол подачи.'); return; }
    const parts = [
      `Новая тема: ${topic.trim()}.`,
      `Самостоятельный угол подачи: ${angle.trim()}.`,
      reference ? `Структурный ориентир: формат ${reference.width}×${reference.height}, приблизительно ${reference.cuts_per_minute} смен кадра в минуту (${reference.pace} темп).` : '',
      niche ? `Ориентир по введённой выборке из ${niche.sample_size} роликов: медиана ${niche.median_views_per_day} просмотров в день. Это не оценка всего рынка.` : '',
      'Создать самостоятельный сценарий и собственные визуальные решения. Не повторять текст, кадры, персонажей или узнаваемую последовательность сцен референса.'
    ];
    setBrief(parts.filter(Boolean).join('\n'));
    setError('');
  };

  return <div className="max-w-5xl mx-auto py-8 px-6 space-y-6">
    <div><h1 className="text-3xl font-bold">Исследование и референс</h1>
      <p className="text-slate-400 mt-2">Локальный анализ без AI-запросов и расхода кредитов. Референс нужен для понимания формата, не для копирования.</p></div>
    {error && <div role="alert" className="rounded-xl border border-red-700 bg-red-950/50 p-3 text-red-200">{error}</div>}
    <section className="rounded-2xl border border-slate-800 bg-slate-900 p-5 space-y-4">
      <h2 className="font-semibold text-lg">1. Разобрать видеофайл</h2>
      <p className="text-sm text-slate-400">Только собственный или разрешённый к анализу файл MP4/MOV/MKV/WebM до 250 МБ. Файл временно обрабатывается локально и удаляется после анализа. Программа не скачивает ролики с YouTube.</p>
      <input type="file" accept=".mp4,.mov,.mkv,.webm" onChange={event => { setVideo(event.target.files?.[0] || null); setReference(null); }} className="block w-full text-sm text-slate-300" />
      <label className="flex gap-2 text-sm text-slate-300"><input type="checkbox" checked={confirmedRights} onChange={event => setConfirmedRights(event.target.checked)} />Я имею право использовать этот файл для анализа.</label>
      <button disabled={!video || !confirmedRights || busy} onClick={analyzeVideo} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold disabled:opacity-40">{busy ? 'Анализ…' : 'Проанализировать локально'}</button>
      {reference && <div className="text-sm text-slate-200 rounded-xl bg-slate-950 p-4 space-y-1">
        <p>Длительность: {Math.round(reference.duration_seconds)} сек · Кадр: {reference.width}×{reference.height}</p>
        <p>Первые {Math.round(reference.analyzed_seconds)} сек: {reference.detected_cuts} смен кадра, ~{reference.cuts_per_minute}/мин · темп {reference.pace}.</p>
        {!reference.cut_detection_available && <p className="text-amber-300">Темп не удалось измерить; доступна только информация о файле.</p>}
        <p className="text-slate-500">Оценка приблизительная: анализируются не все кадры и только первые 3 минуты.</p>
      </div>}
    </section>
    <section className="rounded-2xl border border-slate-800 bg-slate-900 p-5 space-y-4">
      <h2 className="font-semibold text-lg">2. Сравнить нишу без API</h2>
      <p className="text-sm text-slate-400">Введите наблюдаемые данные вручную, по одному ролику в строке: название | просмотры | возраст в днях. Показатель просмотров в день — грубое сравнение, не прогноз спроса.</p>
      <textarea rows={4} value={nicheRows} onChange={event => setNicheRows(event.target.value)} placeholder="История королевы | 120000 | 30" className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm" />
      <button disabled={!nicheRows.trim() || busy} onClick={analyzeNiche} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold disabled:opacity-40">Сравнить</button>
      {niche && <div className="rounded-xl bg-slate-950 p-4 text-sm space-y-2"><p>Медиана выборки: {niche.median_views_per_day} просмотров/день</p>
        {niche.ranked_videos.map((item, index) => <p key={index} className="text-slate-300">{item.title}: {item.views_per_day}/день {item.relative_to_median ? `· ${item.relative_to_median}× медианы` : ''}</p>)}
      </div>}
    </section>
    <section className="rounded-2xl border border-slate-800 bg-slate-900 p-5 space-y-4">
      <h2 className="font-semibold text-lg">3. Создать собственный замысел</h2>
      <input value={topic} onChange={event => setTopic(event.target.value)} placeholder="Ваша новая тема" className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm" />
      <textarea rows={2} value={angle} onChange={event => setAngle(event.target.value)} placeholder="Чем ваша подача отличается? Новый вопрос, точка зрения или аудитория" className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm" />
      <button onClick={createBrief} className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-semibold">Составить бриф без AI</button>
      <textarea rows={6} value={brief} onChange={event => setBrief(event.target.value)} placeholder="Здесь появится редактируемый бриф" className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm" />
      <button disabled={!topic.trim() || !brief.trim()} onClick={() => onUseBrief(topic.trim(), brief.trim())} className="rounded-lg bg-purple-600 px-5 py-3 font-semibold disabled:opacity-40">Перенести в новый проект</button>
    </section>
  </div>;
};
