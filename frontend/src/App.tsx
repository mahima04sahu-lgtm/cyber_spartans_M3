import * as React from 'react';
import { useState, useEffect, useCallback, useRef } from 'react';
import { TopBar } from './components/TopBar';
import { LeftPanel } from './components/LeftPanel';
import { GraphCanvas, GraphFilterOptions, GraphCanvasRef } from './components/GraphCanvas';
import { RightPanel } from './components/RightPanel';
import { FilterBar } from './components/FilterBar';
import { CaseDiaryNoticeModal } from './components/CaseDiaryNoticeModal';
import { IngestScreen } from './components/IngestScreen';
import {
  TraceResult,
  TraceNode,
  traceMoneyFlow,
  fetchSyndicateRing,
  fetchStats,
} from './api';
import { Play, Pause, SkipBack, SkipForward, ArrowLeft } from 'lucide-react';

const defaultFilters: GraphFilterOptions = {
  minAmount: 0,
  paymentRail: 'ALL',
  riskBand: 'ALL',
  layer: 'ALL',
  foreignIpOnly: false,
  headlessOnly: false,
};

export const App: React.FC = () => {
  // Database Ingestion Check State
  const [needsIngestion, setNeedsIngestion] = useState<boolean>(false);

  // Trace & Isolated Ring State
  const [fullTraceResult, setFullTraceResult] = useState<TraceResult | null>(null);
  const [activeTraceResult, setActiveTraceResult] = useState<TraceResult | null>(null);
  const [selectedNode, setSelectedNode] = useState<TraceNode | null>(null);
  const [isIsolatedRing, setIsIsolatedRing] = useState<boolean>(false);
  const [isolatedAccount, setIsolatedAccount] = useState<string | null>(null);

  useEffect(() => {
    fetchStats()
      .then((stats) => {
        if (!stats.total_transactions || stats.total_transactions === 0) {
          setNeedsIngestion(true);
        }
      })
      .catch(() => {
        // Default to workspace view
      });
  }, []);

  // Case Diary & Notice Modal State
  const [isNoticeModalOpen, setIsNoticeModalOpen] = useState<boolean>(false);
  const [selectedNoticeAccounts, setSelectedNoticeAccounts] = useState<string[]>([]);

  // Loading & Error States
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Graph Layout & Display Filters
  const [useForceLayout, setUseForceLayout] = useState<boolean>(false);
  const [strictMode, setStrictMode] = useState<boolean>(false);
  const [filters, setFilters] = useState<GraphFilterOptions>(defaultFilters);

  // Temporal Playback Slider State
  const [minTime, setMinTime] = useState<number>(0);
  const [maxTime, setMaxTime] = useState<number>(Infinity);
  const [currentTime, setCurrentTime] = useState<number>(Infinity);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playSpeed, setPlaySpeed] = useState<number>(1); // 1x = 60s/sec, 10x = 600s/sec, 100x = 6000s/sec

  const graphCanvasRef = useRef<GraphCanvasRef>(null);
  const animFrameRef = useRef<number | null>(null);
  const lastTickTimeRef = useRef<number>(0);

  // Initialize time boundaries whenever activeTraceResult changes
  useEffect(() => {
    if (!activeTraceResult || !activeTraceResult.edges || activeTraceResult.edges.length === 0) {
      setMinTime(0);
      setMaxTime(Infinity);
      setCurrentTime(Infinity);
      setIsPlaying(false);
      return;
    }

    const epochs = activeTraceResult.edges.map((e) => e.epoch_sec).filter(Boolean);
    if (epochs.length > 0) {
      const minEp = Math.min(...epochs);
      const maxEp = Math.max(...epochs);
      setMinTime(minEp);
      setMaxTime(maxEp);
      setCurrentTime(maxEp);
    }
  }, [activeTraceResult]);

  // Smooth requestAnimationFrame Playback Loop
  useEffect(() => {
    if (!isPlaying) {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      return;
    }

    lastTickTimeRef.current = performance.now();

    const loop = (now: number) => {
      const deltaMs = now - lastTickTimeRef.current;
      lastTickTimeRef.current = now;

      // Advance simulated playback time (minute resolution = 60s per 1x real second)
      const secondsToAdvance = (deltaMs / 1000) * 60 * playSpeed;

      setCurrentTime((prev) => {
        const next = prev + secondsToAdvance;
        if (next >= maxTime) {
          setIsPlaying(false);
          return maxTime;
        }
        return next;
      });

      animFrameRef.current = requestAnimationFrame(loop);
    };

    animFrameRef.current = requestAnimationFrame(loop);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isPlaying, maxTime, playSpeed]);

  // Trace Money Flow from Victim Account
  const handleTrace = useCallback(
    async (victimAccount: string) => {
      if (!victimAccount) return;
      setLoading(true);
      setError(null);
      setSelectedNode(null);
      setIsIsolatedRing(false);
      setIsolatedAccount(null);

      try {
        const res = await traceMoneyFlow(victimAccount, 4, strictMode);
        setFullTraceResult(res);
        setActiveTraceResult(res);

        if (res.nodes && res.nodes.length > 0) {
          const vNode = res.nodes.find((n) => n.account === victimAccount) || res.nodes[0];
          setSelectedNode(vNode);
        }
      } catch (err: any) {
        console.error('Trace error:', err);
        setError(err.message || 'Failed to trace money flow for victim account');
        setFullTraceResult(null);
        setActiveTraceResult(null);
      } finally {
        setLoading(false);
      }
    },
    [strictMode]
  );

  // One-Click Syndicate Ring Isolation
  const handleIsolateRing = useCallback(
    async (account: string) => {
      setLoading(true);
      setError(null);
      setSelectedNode(null);

      try {
        const res = await fetchSyndicateRing(account);
        setIsIsolatedRing(true);
        setIsolatedAccount(account);
        setActiveTraceResult(res);

        if (res.nodes && res.nodes.length > 0) {
          const leadNode = res.nodes.find((n) => n.account === account) || res.nodes[0];
          setSelectedNode(leadNode);
        }
      } catch (err: any) {
        console.error('Ring error:', err);
        setError(err.message || 'Failed to isolate syndicate ring');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Return from Ring Isolation to Full Trace
  const handleBackToFullTrace = useCallback(() => {
    if (fullTraceResult) {
      setIsIsolatedRing(false);
      setIsolatedAccount(null);
      setActiveTraceResult(fullTraceResult);
      if (fullTraceResult.nodes && fullTraceResult.nodes.length > 0) {
        setSelectedNode(fullTraceResult.nodes[0]);
      }
    }
  }, [fullTraceResult]);

  // Handle Search Selection
  const handleSearchResult = useCallback(
    (type: 'account' | 'transaction', id: string) => {
      if (type === 'account') {
        handleTrace(id);
      }
    },
    [handleTrace]
  );

  // Calculate Cumulative Amount Moved up to currentTime
  const cumulativeAmountMoved = React.useMemo(() => {
    if (!activeTraceResult || !activeTraceResult.edges) return 0;
    return activeTraceResult.edges
      .filter((e) => currentTime === Infinity || e.epoch_sec <= currentTime)
      .reduce((sum, e) => sum + e.amount, 0);
  }, [activeTraceResult, currentTime]);

  const handleOpenNoticeModal = useCallback((accounts: string[]) => {
    setSelectedNoticeAccounts(accounts);
    setIsNoticeModalOpen(true);
  }, []);

  if (needsIngestion) {
    return (
      <IngestScreen
        onIngestComplete={() => {
          setNeedsIngestion(false);
          window.location.reload();
        }}
      />
    );
  }

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Top Header Bar */}
      <TopBar onSearchResultSelect={handleSearchResult} />

      {/* Main Workspace Layout */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Side Navigation & Tracing Panel */}
        <LeftPanel
          onTrace={handleTrace}
          onIsolateRing={handleIsolateRing}
          loading={loading}
          activeVictim={activeTraceResult?.victim_account}
        />

        {/* Central Visualization Canvas */}
        <div className="flex-1 flex flex-col relative overflow-hidden bg-slate-950">
          {/* Central Canvas Header Bar with Controls */}
          <div className="h-11 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur px-4 flex items-center justify-between z-10">
            <div className="flex items-center gap-3">
              {/* Layout Toggle */}
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Layout:
              </span>
              <div className="flex bg-slate-950 rounded p-0.5 border border-slate-800 text-xs">
                <button
                  onClick={() => setUseForceLayout(false)}
                  className={`px-3 py-1 rounded transition font-medium ${
                    !useForceLayout
                      ? 'bg-cyan-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Layered DAG
                </button>
                <button
                  onClick={() => setUseForceLayout(true)}
                  className={`px-3 py-1 rounded transition font-medium ${
                    useForceLayout
                      ? 'bg-cyan-600 text-white shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Force-Directed
                </button>
              </div>

              {/* Strict Dwell Toggle */}
              <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer select-none ml-2">
                <input
                  type="checkbox"
                  checked={strictMode}
                  onChange={(e) => setStrictMode(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-0"
                />
                <span>Strict Dwell (&lt;60m)</span>
              </label>

              {/* Graph Filter Bar */}
              <FilterBar
                filters={filters}
                onChange={setFilters}
                onReset={() => setFilters(defaultFilters)}
              />
            </div>

            {/* Header Right Status Badges */}
            {activeTraceResult && (
              <div className="flex items-center gap-3 text-xs font-mono">
                {isIsolatedRing && (
                  <button
                    onClick={handleBackToFullTrace}
                    className="px-2.5 py-1 bg-amber-900/80 hover:bg-amber-800 text-amber-200 rounded text-xs font-semibold flex items-center gap-1 border border-amber-500/40 transition"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" /> Back to Full Trace
                  </button>
                )}
                <span className="text-slate-400">
                  Nodes: <strong className="text-cyan-400">{activeTraceResult.nodes.length}</strong>
                </span>
                <span className="text-slate-400">
                  Edges: <strong className="text-cyan-400">{activeTraceResult.edges.length}</strong>
                </span>
                <span className="text-slate-400">
                  Cumulative Moved:{' '}
                  <strong className="text-emerald-400">
                    ₹{cumulativeAmountMoved.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </strong>
                </span>
              </div>
            )}
          </div>

          {/* Graph Canvas Component */}
          <div className="flex-1 relative">
            <GraphCanvas
              ref={graphCanvasRef}
              traceResult={activeTraceResult}
              selectedNode={selectedNode}
              onNodeClick={setSelectedNode}
              useForceLayout={useForceLayout}
              maxTimeEpoch={currentTime}
              filters={filters}
            />

            {/* Loading Overlay */}
            {loading && (
              <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm z-20 flex flex-col items-center justify-center space-y-3">
                <div className="w-10 h-10 border-4 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin" />
                <div className="text-sm font-semibold text-cyan-400 tracking-wide font-mono">
                  Tracing Money Flow across 2M Transactions...
                </div>
              </div>
            )}

            {/* Error Banner */}
            {error && (
              <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-red-950/90 text-red-200 border border-red-500/50 px-4 py-2.5 rounded-lg text-xs font-medium shadow-xl z-20 flex items-center gap-3">
                <span>⚠️ {error}</span>
                <button onClick={() => setError(null)} className="text-red-400 hover:text-white font-bold">
                  ✕
                </button>
              </div>
            )}

            {/* Empty State Banner */}
            {!loading && !activeTraceResult && !error && (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center z-10 pointer-events-none">
                <div className="w-16 h-16 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-600 mb-4">
                  <Play className="w-8 h-8 text-cyan-500/40 ml-1" />
                </div>
                <h3 className="text-base font-bold text-slate-300">
                  Ready for Fraud Network Tracing
                </h3>
                <p className="text-xs text-slate-500 max-w-md mt-1 leading-relaxed">
                  Select a victim account from the left panel or search an account number to visualize the complete downstream money trail across L1, L2, and L3 mule layers.
                </p>
              </div>
            )}
          </div>

          {/* Temporal Playback Slider Controls Bar */}
          {activeTraceResult && activeTraceResult.edges && activeTraceResult.edges.length > 0 && (
            <div className="h-14 border-t border-slate-800 bg-slate-900/90 backdrop-blur px-6 flex items-center gap-4 z-10">
              {/* Step Backward (-1 min / 60s) */}
              <button
                onClick={() => setCurrentTime((prev) => Math.max(minTime, prev - 60))}
                className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                title="Step Backward 1 minute"
              >
                <SkipBack className="w-4 h-4" />
              </button>

              {/* Play / Pause Toggle */}
              <button
                onClick={() => {
                  if (currentTime >= maxTime) setCurrentTime(minTime);
                  setIsPlaying(!isPlaying);
                }}
                className={`p-2 rounded-full text-white transition shadow-lg ${
                  isPlaying ? 'bg-rose-600 hover:bg-rose-500' : 'bg-cyan-600 hover:bg-cyan-500'
                }`}
                title={isPlaying ? 'Pause Timeline Playback' : 'Play Timeline Playback'}
              >
                {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
              </button>

              {/* Step Forward (+1 min / 60s) */}
              <button
                onClick={() => setCurrentTime((prev) => Math.min(maxTime, prev + 60))}
                className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                title="Step Forward 1 minute"
              >
                <SkipForward className="w-4 h-4" />
              </button>

              {/* Speed Control Selector (1x, 10x, 100x) */}
              <div className="flex bg-slate-950 rounded p-0.5 border border-slate-800 text-[10px] font-mono">
                {[1, 10, 100].map((s) => (
                  <button
                    key={s}
                    onClick={() => setPlaySpeed(s)}
                    className={`px-2 py-0.5 rounded transition ${
                      playSpeed === s ? 'bg-cyan-600 text-white font-bold' : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {s}x
                  </button>
                ))}
              </div>

              {/* Slider & Timestamp metrics */}
              <div className="flex-1 flex flex-col gap-1">
                <div className="flex justify-between text-[10px] font-mono text-slate-400">
                  <span>Start: {minTime ? new Date(minTime * 1000).toLocaleString() : 'N/A'}</span>
                  <span className="text-cyan-400 font-bold">
                    Timestamp: {currentTime !== Infinity ? new Date(currentTime * 1000).toLocaleString() : 'Full Timeline'}
                  </span>
                  <span>End: {maxTime !== Infinity ? new Date(maxTime * 1000).toLocaleString() : 'N/A'}</span>
                </div>
                <input
                  type="range"
                  min={minTime || 0}
                  max={maxTime !== Infinity ? maxTime : 100}
                  step={60}
                  value={currentTime !== Infinity ? currentTime : maxTime !== Infinity ? maxTime : 100}
                  onChange={(e) => setCurrentTime(Number(e.target.value))}
                  className="w-full accent-cyan-500 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                />
              </div>

              <button
                onClick={() => {
                  setIsPlaying(false);
                  setCurrentTime(maxTime);
                }}
                className="text-xs px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-700 font-mono"
              >
                Reset
              </button>
            </div>
          )}
        </div>

        {/* Right Side Node & Trace Details Panel */}
        <RightPanel
          selectedNode={selectedNode}
          traceResult={activeTraceResult}
          onSelectNode={setSelectedNode}
          onIsolateRing={handleIsolateRing}
          isIsolatedRing={isIsolatedRing}
          onBackToFullTrace={handleBackToFullTrace}
          onOpenNoticeModal={handleOpenNoticeModal}
        />
      </div>

      {/* Case Diary & Freeze Notice Modal */}
      <CaseDiaryNoticeModal
        isOpen={isNoticeModalOpen}
        onClose={() => setIsNoticeModalOpen(false)}
        victimAccount={activeTraceResult?.victim_account || ''}
        selectedAccounts={selectedNoticeAccounts}
      />
    </div>
  );
};
