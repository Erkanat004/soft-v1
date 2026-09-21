import React, { useEffect, useState } from 'react';
import { Project, Script } from '../types';
import { api } from '../api';
import { FileText, Save, Wand2, Flame, Sparkles, AlertCircle } from 'lucide-react';

interface ScriptPageProps {
  project: Project;
}

export const ScriptPage: React.FC<ScriptPageProps> = ({ project }) => {
  const [script, setScript] = useState<Script | null>(null);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(true);
  const [isEnhancing, setIsEnhancing] = useState(false);

  const loadScript = async () => {
    setLoading(true);
    try {
      const data = await api.getScript(project.id);
      setScript(data);
      setText(data.text);
    } catch (err) {
      console.error("Failed to load script:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScript();
  }, [project.id]);

  const handleSave = async () => {
    try {
      const updated = await api.updateScript(project.id, text);
      setScript(updated);
      alert("Script saved successfully!");
    } catch (err) {
      alert("Failed to save script");
    }
  };

  const handleEnhance = async (instruction: string) => {
    setIsEnhancing(true);
    try {
      const updated = await api.enhanceScript(project.id, instruction);
      setScript(updated);
      setText(updated.text);
    } catch (err) {
      alert("AI Script enhancement failed.");
    } finally {
      setIsEnhancing(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-6 space-y-6">
      <div className="flex items-center justify-between border-b border-dark-700 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <FileText className="w-6 h-6 text-purple-400" />
            <span>Story Script Editor</span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Edit full story narration text manually or refine tone with AI actions.
          </p>
        </div>

        <button
          onClick={handleSave}
          className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded-xl text-xs flex items-center gap-2 shadow-lg shadow-purple-900/30 transition-all"
        >
          <Save className="w-4 h-4" />
          <span>Save Script</span>
        </button>
      </div>

      {/* AI Refinement Buttons Toolbar */}
      <div className="bg-dark-800 border border-dark-700 rounded-2xl p-4 flex flex-wrap items-center gap-3 shadow-md">
        <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5 mr-2">
          <Wand2 className="w-4 h-4 text-purple-400" />
          <span>AI Refinements:</span>
        </span>

        <button
          onClick={() => handleEnhance("Make scarier and darker atmospheric suspense")}
          disabled={isEnhancing}
          className="px-3 py-1.5 bg-dark-700 hover:bg-dark-600 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors disabled:opacity-50"
        >
          <Flame className="w-3.5 h-3.5 text-red-400" />
          <span>Make Scarier</span>
        </button>

        <button
          onClick={() => handleEnhance("Make narration more emotional and gripping")}
          disabled={isEnhancing}
          className="px-3 py-1.5 bg-dark-700 hover:bg-dark-600 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors disabled:opacity-50"
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span>More Emotional</span>
        </button>

        <button
          onClick={() => handleEnhance("Add a strong hook in the first 2 sentences")}
          disabled={isEnhancing}
          className="px-3 py-1.5 bg-dark-700 hover:bg-dark-600 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors disabled:opacity-50"
        >
          <span>Stronger Hook</span>
        </button>

        <button
          onClick={() => handleEnhance("Add an unexpected shocking twist ending")}
          disabled={isEnhancing}
          className="px-3 py-1.5 bg-dark-700 hover:bg-dark-600 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors disabled:opacity-50"
        >
          <span>Twist Ending</span>
        </button>
      </div>

      {/* Main Textarea */}
      <div className="bg-dark-800 border border-dark-700 rounded-2xl p-6 shadow-xl relative">
        {loading ? (
          <div className="text-center py-12 text-slate-500 text-sm">Loading script...</div>
        ) : (
          <textarea
            rows={18}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full bg-dark-900 border border-dark-700 rounded-xl p-5 text-slate-100 text-sm leading-relaxed font-mono focus:outline-none focus:border-purple-500 resize-y"
            placeholder="Story narration script..."
          />
        )}
      </div>
    </div>
  );
};
