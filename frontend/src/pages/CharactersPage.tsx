import React, { useEffect, useState } from 'react';
import { Project, Character } from '../types';
import { api } from '../api';
import { Users, UserCheck, Sparkles, Shirt, Eye } from 'lucide-react';

interface CharactersPageProps {
  project: Project;
}

export const CharactersPage: React.FC<CharactersPageProps> = ({ project }) => {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadChars = async () => {
      setLoading(true);
      try {
        const data = await api.listCharacters(project.id);
        setCharacters(data);
      } catch (err) {
        console.error("Failed to load characters:", err);
      } finally {
        setLoading(false);
      }
    };
    loadChars();
  }, [project.id]);

  return (
    <div className="max-w-5xl mx-auto py-8 px-6 space-y-6">
      <div className="border-b border-dark-700 pb-4">
        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
          <Users className="w-6 h-6 text-purple-400" />
          <span>Character Bible ({characters.length})</span>
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Auto-extracted character descriptions injected into scene prompts for visual consistency.
        </p>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-500 text-sm">Loading Character Bible...</div>
      ) : characters.length === 0 ? (
        <div className="text-center py-16 bg-dark-800 border border-dark-700 rounded-2xl p-8 space-y-3">
          <UserCheck className="w-10 h-10 text-slate-600 mx-auto" />
          <h4 className="text-base font-semibold text-slate-300">No characters extracted yet</h4>
          <p className="text-xs text-slate-500">Run AUTO MODE on the launcher home screen to automatically generate Character Bibles.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {characters.map((c) => (
            <div key={c.id} className="bg-dark-800 border border-dark-700 rounded-2xl p-6 space-y-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-dark-700/60 pb-3">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <span>{c.name}</span>
                  {c.age && <span className="text-xs font-normal text-slate-400">({c.age})</span>}
                </h3>
                {c.is_auto_generated && (
                  <span className="text-[10px] font-bold uppercase px-2.5 py-0.5 rounded bg-purple-950/80 text-purple-300 border border-purple-800/40 flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-purple-400" />
                    Auto Injected
                  </span>
                )}
              </div>

              <div className="space-y-2 text-xs text-slate-300">
                <div className="p-3 bg-dark-900 rounded-xl border border-dark-700/60">
                  <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">Visual Appearance Descriptor</span>
                  <p className="italic text-purple-200">{c.appearance}</p>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2 text-slate-400">
                  <div><span className="text-slate-500">Hair:</span> {c.hair || 'N/A'}</div>
                  <div><span className="text-slate-500">Eyes:</span> {c.eyes || 'N/A'}</div>
                  <div><span className="text-slate-500">Clothes:</span> {c.clothes || 'N/A'}</div>
                  <div><span className="text-slate-500">Gender:</span> {c.gender || 'N/A'}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
