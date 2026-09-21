import React, { useEffect, useState } from 'react';
import { Project, Location } from '../types';
import { api } from '../api';
import { MapPin, Sparkles, Home } from 'lucide-react';

interface LocationsPageProps {
  project: Project;
}

export const LocationsPage: React.FC<LocationsPageProps> = ({ project }) => {
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadLocs = async () => {
      setLoading(true);
      try {
        const data = await api.listLocations(project.id);
        setLocations(data);
      } catch (err) {
        console.error("Failed to load locations:", err);
      } finally {
        setLoading(false);
      }
    };
    loadLocs();
  }, [project.id]);

  return (
    <div className="max-w-5xl mx-auto py-8 px-6 space-y-6">
      <div className="border-b border-dark-700 pb-4">
        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
          <MapPin className="w-6 h-6 text-purple-400" />
          <span>Location Bible ({locations.length})</span>
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Auto-extracted environment descriptors appended to scene prompts for spatial continuity.
        </p>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-500 text-sm">Loading Location Bible...</div>
      ) : locations.length === 0 ? (
        <div className="text-center py-16 bg-dark-800 border border-dark-700 rounded-2xl p-8 space-y-3">
          <Home className="w-10 h-10 text-slate-600 mx-auto" />
          <h4 className="text-base font-semibold text-slate-300">No locations extracted yet</h4>
          <p className="text-xs text-slate-500">Run AUTO MODE on the launcher home screen to automatically generate Location Bibles.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {locations.map((loc) => (
            <div key={loc.id} className="bg-dark-800 border border-dark-700 rounded-2xl p-6 space-y-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-dark-700/60 pb-3">
                <h3 className="text-lg font-bold text-white">{loc.name}</h3>
                {loc.is_auto_generated && (
                  <span className="text-[10px] font-bold uppercase px-2.5 py-0.5 rounded bg-purple-950/80 text-purple-300 border border-purple-800/40 flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-purple-400" />
                    Auto Injected
                  </span>
                )}
              </div>

              <div className="p-3.5 bg-dark-900 rounded-xl border border-dark-700/60">
                <span className="text-[10px] uppercase font-bold text-slate-500 block mb-1">Environment Descriptor</span>
                <p className="text-xs text-slate-200 leading-relaxed">{loc.description}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
