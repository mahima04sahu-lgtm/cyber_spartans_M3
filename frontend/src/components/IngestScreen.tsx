import React, { useState } from 'react';
import { Database, Play, CheckCircle2, AlertCircle, RefreshCw, Layers, ShieldCheck } from 'lucide-react';

interface IngestScreenProps {
  onIngestComplete: () => void;
}

export const IngestScreen: React.FC<IngestScreenProps> = ({ onIngestComplete }) => {
  const [ingesting, setIngesting] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);
  const [stageMessage, setStageMessage] = useState<string>('Ready to ingest raw dataset.');
  const [error, setError] = useState<string | null>(null);

  const startIngestion = () => {
    setIngesting(true);
    setProgress(5);
    setStageMessage('Initiating DuckDB ingestion pipeline...');
    setError(null);

    const eventSource = new EventSource('/api/ingest/stream');

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.stage === 'error') {
          setError(data.message || 'Ingestion failed');
          setIngesting(false);
          eventSource.close();
        } else if (data.stage === 'complete') {
          setProgress(100);
          setStageMessage(data.message || 'Ingestion complete!');
          setIngesting(false);
          eventSource.close();
          setTimeout(() => {
            onIngestComplete();
          }, 1000);
        } else if (data.percent) {
          setProgress(data.percent);
          setStageMessage(data.message || 'Processing stage...');
        }
      } catch (e) {
        console.error('SSE parse error', e);
      }
    };

    eventSource.onerror = (e) => {
      console.error('SSE connection error', e);
      eventSource.close();
      // If server doesn't support SSE streaming, fallback to direct trigger
      fetch('/api/stats')
        .then((res) => res.json())
        .then((stats) => {
          if (stats.total_transactions > 0) {
            setProgress(100);
            setStageMessage('Dataset verified in database!');
            setIngesting(false);
            onIngestComplete();
          } else {
            setError('Ingestion connection lost. Please verify server logs.');
            setIngesting(false);
          }
        })
        .catch(() => {
          setError('Failed to connect to backend ingestion server.');
          setIngesting(false);
        });
    };
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen w-screen bg-slate-950 text-slate-100 p-6">
      <div className="max-w-xl w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-6">
        {/* Header */}
        <div className="text-center space-y-3">
          <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center mx-auto text-cyan-400 shadow-inner">
            <Database className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight">
            Abhedya-Chakra Ingestion Engine
          </h1>
          <p className="text-xs text-slate-400 leading-relaxed max-w-md mx-auto">
            Ingest, clean, normalize, and index 2,000,000+ CSV transactions into high-speed persistent DuckDB ART indexes & CSR graph representation.
          </p>
        </div>

        {/* Action / Progress Box */}
        <div className="bg-slate-950 p-6 rounded-xl border border-slate-800 space-y-4">
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="text-slate-400 flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              Pipeline Status
            </span>
            <span className="font-mono text-cyan-400">{progress}%</span>
          </div>

          {/* Progress Bar */}
          <div className="w-full h-3 bg-slate-900 rounded-full overflow-hidden p-0.5 border border-slate-800">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 via-teal-400 to-emerald-400 rounded-full transition-all duration-300 shadow-lg"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Message Indicator */}
          <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
            {ingesting ? (
              <RefreshCw className="w-4 h-4 text-cyan-400 animate-spin" />
            ) : progress === 100 ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : error ? (
              <AlertCircle className="w-4 h-4 text-red-400" />
            ) : (
              <ShieldCheck className="w-4 h-4 text-slate-500" />
            )}
            <span className="truncate">{stageMessage}</span>
          </div>

          {error && (
            <div className="p-3 bg-red-950/60 border border-red-500/40 text-red-300 text-xs rounded-lg font-mono">
              ⚠️ {error}
            </div>
          )}
        </div>

        {/* Start Button */}
        <div className="pt-2">
          <button
            onClick={startIngestion}
            disabled={ingesting || progress === 100}
            className="w-full py-3.5 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 disabled:opacity-50 text-white font-bold text-sm rounded-xl transition shadow-xl flex items-center justify-center gap-2"
          >
            {ingesting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Ingesting 2,000,000 Transactions...</span>
              </>
            ) : progress === 100 ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Dataset Ready — Launching Workspace...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>Start Automated Ingestion (2M Rows)</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
