import React, { useState, useEffect } from 'react';
import { Play, Sliders, Network } from 'lucide-react';
import { SuggestedVictim, SyndicateRingSummary, fetchSuggestedVictims, fetchDetectedRings } from '../api';

interface LeftPanelProps {
  onTrace: (account: string) => void;
  onIsolateRing?: (account: string) => void;
  loading?: boolean;
  activeVictim?: string;
}

export const LeftPanel: React.FC<LeftPanelProps> = ({
  onTrace,
  onIsolateRing,
  loading = false,
  activeVictim = '',
}) => {
  const [accountInput, setAccountInput] = useState('910000000001');
  const [hops, setHops] = useState(4);
  const [strictMode, setStrictMode] = useState(false);

  const [suggestedVictims, setSuggestedVictims] = useState<SuggestedVictim[]>([]);
  const [rings, setRings] = useState<SyndicateRingSummary[]>([]);
  const [activeTab, setActiveTab] = useState<'victims' | 'rings'>('victims');

  useEffect(() => {
    fetchSuggestedVictims().then(setSuggestedVictims).catch(console.error);
    fetchDetectedRings().then(setRings).catch(console.error);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (accountInput.trim()) {
      onTrace(accountInput.trim());
    }
  };

  return (
    <aside className="w-80 bg-[#0b1329]/95 border-r border-cyan-950/40 flex flex-col h-full z-20 overflow-hidden">
      {/* Search & Trace Form */}
      <div className="p-4 border-b border-slate-800/80 bg-slate-900/40">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-cyan-400 mb-3 flex items-center gap-1.5">
          <Play className="w-3.5 h-3.5" />
          Money Flow Tracing Engine
        </h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">
              Victim Account Number (12 Digits)
            </label>
            <input
              type="text"
              value={accountInput}
              onChange={(e) => setAccountInput(e.target.value)}
              placeholder="e.g. 910000000001"
              className="w-full bg-[#0f172a] border border-slate-700/70 rounded-xl px-3 py-2 text-sm text-slate-100 font-mono focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Downstream Hops</label>
              <select
                value={hops}
                onChange={(e) => setHops(Number(e.target.value))}
                className="w-full bg-[#0f172a] border border-slate-700/70 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value={2}>2 Hops</option>
                <option value={3}>3 Hops</option>
                <option value={4}>4 Hops (Default)</option>
                <option value={5}>5 Hops</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Time Window</label>
              <button
                type="button"
                onClick={() => setStrictMode(!strictMode)}
                className={`w-full px-2 py-1.5 rounded-xl border text-xs font-medium transition flex items-center justify-center gap-1 ${
                  strictMode
                    ? 'bg-amber-950/60 border-amber-500/60 text-amber-300'
                    : 'bg-slate-800 border-slate-700 text-slate-300'
                }`}
              >
                <Sliders className="w-3 h-3" />
                {strictMode ? 'Strict 60m' : 'Standard 24h'}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-black font-semibold text-xs rounded-xl shadow-lg shadow-cyan-500/20 transition flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                <span>Tracing Downstream Flow...</span>
              </>
            ) : (
              <>
                <Network className="w-4 h-4" />
                <span>TRACE DOWNSTREAM FLOW</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Tabs Header */}
      <div className="flex border-b border-slate-800 bg-slate-900/60">
        <button
          onClick={() => setActiveTab('victims')}
          className={`flex-1 py-2.5 text-xs font-semibold text-center border-b-2 transition ${
            activeTab === 'victims'
              ? 'border-cyan-400 text-cyan-400 bg-cyan-950/20'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Suggested Victims ({suggestedVictims.length})
        </button>
        <button
          onClick={() => setActiveTab('rings')}
          className={`flex-1 py-2.5 text-xs font-semibold text-center border-b-2 transition ${
            activeTab === 'rings'
              ? 'border-cyan-400 text-cyan-400 bg-cyan-950/20'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Syndicate Rings ({rings.length})
        </button>
      </div>

      {/* Tab Content List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 divide-y divide-slate-800/40">
        {activeTab === 'victims' ? (
          suggestedVictims.map((v, idx) => {
            const isActive = activeVictim === v.victim_account;
            return (
              <div
                key={idx}
                onClick={() => {
                  setAccountInput(v.victim_account);
                  onTrace(v.victim_account);
                }}
                className={`pt-2 p-2.5 rounded-xl cursor-pointer transition border ${
                  isActive
                    ? 'bg-cyan-950/40 border-cyan-500/60'
                    : 'bg-slate-900/40 border-slate-800/60 hover:bg-slate-800/50 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-slate-200">{v.victim_account}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                    {v.bank_name}
                  </span>
                </div>
                <div className="flex items-center justify-between mt-2 text-xs">
                  <span className="text-slate-400">Stolen:</span>
                  <span className="font-semibold text-rose-400">₹{v.total_stolen_amount.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between mt-1 text-[11px] text-slate-400">
                  <span>Mule Targets: {v.mule_targets_count}</span>
                  <span>{v.first_loss?.split(' ')[0]}</span>
                </div>
              </div>
            );
          })
        ) : (
          rings.map((r, idx) => (
            <div
              key={idx}
              onClick={() => {
                setAccountInput(r.lead_suspect_account);
                if (onIsolateRing) {
                  onIsolateRing(r.lead_suspect_account);
                } else {
                  onTrace(r.lead_suspect_account);
                }
              }}
              className="pt-2 p-2.5 rounded-xl bg-slate-900/40 border border-slate-800/60 hover:bg-slate-800/50 cursor-pointer transition"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-amber-400">Ring #{r.ring_id}</span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800/40">
                  Score {r.risk_score}
                </span>
              </div>
              <div className="text-[11px] font-mono text-slate-300 mt-1">Lead: {r.lead_suspect_account}</div>
              <div className="flex items-center justify-between mt-2 text-xs">
                <span className="text-slate-400">Volume:</span>
                <span className="font-semibold text-cyan-300">₹{r.total_volume.toLocaleString()}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  );
};
