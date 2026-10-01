import * as React from 'react';
import { useEffect, useState } from 'react';
import {
  TraceNode,
  TraceResult,
  AccountProfile,
  TransactionItem,
  fetchAccountProfile,
  fetchAccountTransactions,
  getRingExportUrl,
} from '../api';
import { Download, FileText, CheckSquare, Square, ArrowLeft, ShieldAlert, CheckCircle2 } from 'lucide-react';

interface RightPanelProps {
  selectedNode: TraceNode | null;
  traceResult: TraceResult | null;
  onSelectNode: (node: TraceNode | null) => void;
  onIsolateRing?: (account: string) => void;
  isIsolatedRing?: boolean;
  onBackToFullTrace?: () => void;
  onOpenNoticeModal?: (selectedAccounts: string[]) => void;
}

export const RightPanel: React.FC<RightPanelProps> = ({
  selectedNode,
  traceResult,
  onSelectNode,
  onIsolateRing,
  isIsolatedRing = false,
  onBackToFullTrace,
  onOpenNoticeModal,
}) => {
  const [profile, setProfile] = useState<AccountProfile | null>(null);
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [loadingProfile, setLoadingProfile] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'freeze' | 'timeline'>('overview');

  // Freeze List checkbox selection state
  const [selectedFreezeAccs, setSelectedFreezeAccs] = useState<Set<string>>(new Set());
  const [copiedNotice, setCopiedNotice] = useState<boolean>(false);

  // Initialize selected freeze accounts when traceResult updates
  useEffect(() => {
    if (traceResult?.summary?.holding_accounts) {
      const allAccs = new Set(traceResult.summary.holding_accounts.map((a) => a.account));
      setSelectedFreezeAccs(allAccs);
    } else {
      setSelectedFreezeAccs(new Set());
    }
  }, [traceResult]);

  useEffect(() => {
    if (!selectedNode) {
      setProfile(null);
      setTransactions([]);
      return;
    }

    setLoadingProfile(true);
    Promise.all([
      fetchAccountProfile(selectedNode.account).catch(() => null),
      fetchAccountTransactions(selectedNode.account, 15, 0).catch(() => null),
    ])
      .then(([prof, txns]) => {
        setProfile(prof);
        if (txns && txns.transactions) {
          setTransactions(txns.transactions);
        } else {
          setTransactions([]);
        }
      })
      .finally(() => {
        setLoadingProfile(false);
      });
  }, [selectedNode]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatTimestamp = (tsStr?: string) => {
    if (!tsStr) return 'N/A';
    const date = new Date(tsStr);
    return date.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const getReasonCodes = (score: number, layer: string, prof: AccountProfile | null) => {
    const reasons: { code: string; label: string; severity: 'high' | 'medium' | 'low' }[] = [];
    if (layer === 'Victim') {
      reasons.push({ code: 'VIC_ORIGIN', label: 'Fraud Inflow Origin / Victim', severity: 'low' });
      return reasons;
    }

    if (score >= 70) {
      reasons.push({ code: 'HIGH_PASSTHROUGH', label: '>90% Rapid Pass-Through (<15m)', severity: 'high' });
    }
    if (score >= 60) {
      reasons.push({ code: 'BURST_FANOUT', label: 'Multi-account Fanout Siphoning', severity: 'high' });
    }

    if (prof) {
      if (prof.ip_summary?.some((ip) => ip.is_foreign)) {
        reasons.push({ code: 'FOREIGN_IP', label: 'Foreign IP Anonymizer Detected', severity: 'high' });
      }
      if (prof.device_summary?.some((d) => d.is_headless)) {
        reasons.push({ code: 'HEADLESS_BOT', label: 'Automated Headless Device', severity: 'high' });
      }
      if (prof.top_narrations?.some((n) => n.category === 'Crypto / P2P')) {
        reasons.push({ code: 'CRYPTO_NAR', label: 'Crypto Exchange / P2P Narration', severity: 'medium' });
      }
    }

    if (reasons.length === 0) {
      if (score >= 40) {
        reasons.push({ code: 'SUSP_FLOW', label: 'Suspicious Rapid Cashflow Velocity', severity: 'medium' });
      } else {
        reasons.push({ code: 'NORM_PROFILE', label: 'Low Suspicion / Normal Counterparty', severity: 'low' });
      }
    }
    return reasons;
  };

  const toggleFreezeAccount = (acc: string) => {
    const next = new Set(selectedFreezeAccs);
    if (next.has(acc)) next.delete(acc);
    else next.add(acc);
    setSelectedFreezeAccs(next);
  };

  const toggleAllFreezeAccounts = () => {
    if (!traceResult?.summary?.holding_accounts) return;
    if (selectedFreezeAccs.size === traceResult.summary.holding_accounts.length) {
      setSelectedFreezeAccs(new Set());
    } else {
      setSelectedFreezeAccs(new Set(traceResult.summary.holding_accounts.map((a) => a.account)));
    }
  };

  // Generate Section 91 CrPC Freeze Notice Text
  const copyLegalNoticeText = () => {
    if (!traceResult) return;
    const holdingAccs = traceResult.summary.holding_accounts.filter((a) => selectedFreezeAccs.has(a.account));
    
    let text = `=====================================================================\n`;
    text += `NOTICE UNDER SECTION 91 CrPC / SECTION 94 BNSS\n`;
    text += `INDORE POLICE COMMISSIONERATE - CYBER CRIME CELL\n`;
    text += `=====================================================================\n`;
    text += `SUBJECT: URGENT BANK ACCOUNT FREEZE INSTRUCTION\n`;
    text += `CRIME REF / VICTIM ACCOUNT: ${traceResult.victim_account}\n`;
    text += `TOTAL FRAUD SIPHONED: ₹${traceResult.summary.total_siphoned.toLocaleString('en-IN')}\n\n`;
    text += `LIST OF TARGET HOLDING ACCOUNTS TO FREEZE IMMEDIATELY:\n`;
    holdingAccs.forEach((acc, i) => {
      text += `${i + 1}. Account: ${acc.account} | Layer: ${acc.layer} | Trapped Balance: ₹${acc.residual_balance.toLocaleString('en-IN')} | Risk Index: ${acc.risk_score}/100\n`;
    });
    text += `\nAUTHORITY: OFFICE OF DEPUTY COMMISSIONER OF POLICE, INDORE\n`;
    text += `=====================================================================\n`;

    navigator.clipboard.writeText(text);
    setCopiedNotice(true);
    setTimeout(() => setCopiedNotice(false), 2000);
  };

  return (
    <div className="w-96 bg-slate-900 border-l border-slate-800 flex flex-col h-full overflow-hidden text-slate-200">
      {/* Header Banner if viewing Isolated Syndicate Ring */}
      {isIsolatedRing && onBackToFullTrace && (
        <div className="p-3 bg-amber-950/60 border-b border-amber-500/40 flex items-center justify-between">
          <span className="text-xs font-bold text-amber-300 flex items-center gap-1.5">
            <ShieldAlert className="w-4 h-4" />
            Isolated Syndicate Ring View
          </span>
          <button
            onClick={onBackToFullTrace}
            className="px-2.5 py-1 bg-amber-900 hover:bg-amber-800 text-amber-100 rounded text-[11px] font-semibold flex items-center gap-1 transition"
          >
            <ArrowLeft className="w-3 h-3" />
            Back to Full Trace
          </button>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex border-b border-slate-800 bg-slate-950/80 text-xs font-semibold">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex-1 py-3 text-center transition-colors border-b-2 ${
            activeTab === 'overview'
              ? 'border-cyan-500 text-cyan-400 bg-slate-900/60'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Node Details
        </button>
        <button
          onClick={() => setActiveTab('freeze')}
          className={`flex-1 py-3 text-center transition-colors border-b-2 relative ${
            activeTab === 'freeze'
              ? 'border-emerald-500 text-emerald-400 bg-slate-900/60'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Freeze List
          {traceResult?.summary.holding_accounts.length ? (
            <span className="ml-1 px-1.5 py-0.5 text-[10px] bg-emerald-500/20 text-emerald-400 rounded-full border border-emerald-500/40">
              {traceResult.summary.holding_accounts.length}
            </span>
          ) : null}
        </button>
        <button
          onClick={() => setActiveTab('timeline')}
          className={`flex-1 py-3 text-center transition-colors border-b-2 ${
            activeTab === 'timeline'
              ? 'border-purple-500 text-purple-400 bg-slate-900/60'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Mini Timeline
        </button>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <>
            {selectedNode ? (
              <div className="space-y-4">
                {/* Header Info */}
                <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase tracking-wider ${
                        selectedNode.layer === 'Victim'
                          ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                          : selectedNode.layer === 'L1'
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          : selectedNode.layer === 'L2'
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                          : 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                      }`}
                    >
                      {selectedNode.layer} Node
                    </span>
                    <span className="text-xs text-slate-400 font-mono">Hop #{selectedNode.hop}</span>
                  </div>

                  <h3 className="text-lg font-bold font-mono text-cyan-400 tracking-wide select-all">
                    {selectedNode.account}
                  </h3>
                  <div className="text-sm text-slate-300 font-medium">
                    {selectedNode.bank_name || profile?.bank_name || 'Bank N/A'}
                  </div>

                  {/* Ring Isolation Trigger */}
                  {onIsolateRing && (
                    <div className="mt-3">
                      <button
                        onClick={() => onIsolateRing(selectedNode.account)}
                        className="w-full px-3 py-2 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 text-xs font-semibold rounded border border-cyan-500/40 transition flex items-center justify-center gap-1.5"
                      >
                        <ShieldAlert className="w-4 h-4 text-cyan-400" />
                        Isolate Syndicate Ring around this Account
                      </button>
                    </div>
                  )}
                </div>

                {/* Mule Risk Index Score */}
                <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-400 font-medium">Mule Risk Index Score</span>
                    <span
                      className={`font-bold font-mono text-sm ${
                        selectedNode.mule_risk_score >= 70
                          ? 'text-red-400'
                          : selectedNode.mule_risk_score >= 40
                          ? 'text-amber-400'
                          : 'text-emerald-400'
                      }`}
                    >
                      {selectedNode.mule_risk_score} / 100
                    </span>
                  </div>
                  <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-500 ${
                        selectedNode.mule_risk_score >= 70
                          ? 'bg-gradient-to-r from-amber-500 to-red-500'
                          : selectedNode.mule_risk_score >= 40
                          ? 'bg-gradient-to-r from-yellow-500 to-amber-500'
                          : 'bg-emerald-500'
                      }`}
                      style={{ width: `${selectedNode.mule_risk_score}%` }}
                    />
                  </div>

                  {/* Reason Codes */}
                  <div className="pt-2">
                    <span className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold block mb-1.5">
                      Risk Indicators & Reason Codes
                    </span>
                    <div className="space-y-1.5">
                      {getReasonCodes(selectedNode.mule_risk_score, selectedNode.layer, profile).map((r, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between text-xs px-2.5 py-1 bg-slate-900 rounded border border-slate-800"
                        >
                          <span className="font-mono text-cyan-400 text-[11px]">[{r.code}]</span>
                          <span className="text-slate-300 text-[11px] flex-1 ml-2 font-medium">
                            {r.label}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Financial Summary */}
                <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 space-y-3">
                  <h4 className="text-xs uppercase tracking-wider text-slate-400 font-semibold border-b border-slate-800 pb-1.5">
                    Financial Flow Summary
                  </h4>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="bg-slate-900 p-2.5 rounded border border-slate-800">
                      <div className="text-slate-400 text-[11px]">Total Received</div>
                      <div className="font-mono font-bold text-emerald-400 text-sm mt-0.5">
                        {formatCurrency(selectedNode.amount_received)}
                      </div>
                    </div>
                    <div className="bg-slate-900 p-2.5 rounded border border-slate-800">
                      <div className="text-slate-400 text-[11px]">Total Forwarded</div>
                      <div className="font-mono font-bold text-rose-400 text-sm mt-0.5">
                        {formatCurrency(selectedNode.amount_forwarded)}
                      </div>
                    </div>
                  </div>

                  <div className="bg-emerald-950/40 p-3 rounded-lg border border-emerald-500/30 flex justify-between items-center">
                    <div>
                      <div className="text-emerald-400 text-[11px] font-semibold uppercase tracking-wide">
                        Residual Holding Balance
                      </div>
                      <div className="text-slate-400 text-[10px]">Trapped Fraud Money</div>
                    </div>
                    <div className="font-mono font-bold text-emerald-300 text-base">
                      {formatCurrency(selectedNode.residual_balance)}
                    </div>
                  </div>
                </div>

                {/* Technical Telemetry */}
                {loadingProfile ? (
                  <div className="text-center py-4 text-xs text-slate-500 animate-pulse">
                    Loading account profile metadata...
                  </div>
                ) : (
                  profile && (
                    <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 space-y-3">
                      <h4 className="text-xs uppercase tracking-wider text-slate-400 font-semibold border-b border-slate-800 pb-1.5">
                        Technical Telemetry
                      </h4>

                      <div className="space-y-2 text-xs">
                        <div className="flex justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Total Txns (In / Out):</span>
                          <span className="font-mono font-medium text-slate-200">
                            {profile.in_txn_count} / {profile.out_txn_count}
                          </span>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-900">
                          <span className="text-slate-400">Unique Counterparties:</span>
                          <span className="font-mono font-medium text-slate-200">
                            {profile.distinct_counterparties}
                          </span>
                        </div>

                        {profile.ip_summary?.length > 0 && (
                          <div className="pt-1">
                            <span className="text-slate-400 text-[11px] block mb-1">
                              IP Address Footprint:
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {profile.ip_summary.map((ip, i) => (
                                <span
                                  key={i}
                                  className={`px-2 py-0.5 font-mono text-[10px] rounded ${
                                    ip.is_foreign
                                      ? 'bg-red-500/20 text-red-300 border border-red-500/40'
                                      : 'bg-slate-800 text-slate-300'
                                  }`}
                                >
                                  {ip.ip_address} ({ip.count}x)
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {profile.device_summary?.length > 0 && (
                          <div className="pt-1">
                            <span className="text-slate-400 text-[11px] block mb-1">
                              Device Hardware Footprint:
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {profile.device_summary.map((dev, i) => (
                                <span
                                  key={i}
                                  className={`px-2 py-0.5 text-[10px] rounded ${
                                    dev.is_headless
                                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                      : 'bg-slate-800 text-slate-300'
                                  }`}
                                >
                                  {dev.device_type}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                )}
              </div>
            ) : (
              <div className="text-center py-12 px-4 space-y-3">
                <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-500">
                  <FileText className="w-6 h-6" />
                </div>
                <h3 className="text-sm font-semibold text-slate-300">No Node Selected</h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Click on any node in the central graph canvas to view its mule risk profile, reason codes, residual balance, and transaction history.
                </p>
              </div>
            )}
          </>
        )}

        {/* FREEZE LIST TAB */}
        {activeTab === 'freeze' && (
          <div className="space-y-4">
            {traceResult ? (
              <>
                {/* Trace Summary Header Card */}
                <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs uppercase tracking-wider text-slate-400 font-semibold">
                      Money Trail Summary
                    </h3>
                    <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800">
                      {traceResult.execution_time_ms.toFixed(1)} ms
                    </span>
                  </div>

                  <div className="bg-slate-900 p-3 rounded border border-slate-800">
                    <div className="text-slate-400 text-xs">Total Stolen Siphoned</div>
                    <div className="font-mono font-extrabold text-red-400 text-xl mt-0.5">
                      {formatCurrency(traceResult.summary.total_siphoned)}
                    </div>
                  </div>

                  {/* Layer Amounts Breakdown */}
                  <div className="space-y-2 text-xs pt-1">
                    <div className="flex justify-between items-center">
                      <span className="text-slate-400 flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-amber-500" />
                        L1 Collector Layer
                      </span>
                      <span className="font-mono font-medium text-amber-400">
                        {formatCurrency(traceResult.summary.l1_total_amount)}
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-400 flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-rose-500" />
                        L2 Distributor Layer
                      </span>
                      <span className="font-mono font-medium text-rose-400">
                        {formatCurrency(traceResult.summary.l2_total_amount)}
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-slate-400 flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-purple-500" />
                        L3 Cashout Layer
                      </span>
                      <span className="font-mono font-medium text-purple-400">
                        {formatCurrency(traceResult.summary.l3_total_amount)}
                      </span>
                    </div>
                  </div>

                  {/* CSV & JSON Export Buttons */}
                  {traceResult.victim_account && (
                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800">
                      <a
                        href={getRingExportUrl(traceResult.victim_account, 'csv')}
                        download
                        className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded transition flex items-center justify-center gap-1.5 border border-slate-700"
                      >
                        <Download className="w-3.5 h-3.5 text-cyan-400" />
                        Export CSV
                      </a>
                      <a
                        href={getRingExportUrl(traceResult.victim_account, 'json')}
                        download
                        className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded transition flex items-center justify-center gap-1.5 border border-slate-700"
                      >
                        <Download className="w-3.5 h-3.5 text-purple-400" />
                        Export JSON
                      </a>
                    </div>
                  )}
                </div>

                {/* Freeze List Selection Section */}
                <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <h3 className="text-xs uppercase tracking-wider text-emerald-400 font-semibold flex items-center gap-1.5">
                      Target Accounts to Freeze ({selectedFreezeAccs.size} Selected)
                    </h3>
                    <button
                      onClick={toggleAllFreezeAccounts}
                      className="text-[11px] text-cyan-400 hover:underline flex items-center gap-1"
                    >
                      {selectedFreezeAccs.size === traceResult.summary.holding_accounts.length ? (
                        <>
                          <CheckSquare className="w-3 h-3" /> Deselect All
                        </>
                      ) : (
                        <>
                          <Square className="w-3 h-3" /> Select All
                        </>
                      )}
                    </button>
                  </div>

                  {traceResult.summary.holding_accounts.length > 0 ? (
                    <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                      {traceResult.summary.holding_accounts
                        .sort((a, b) => b.residual_balance - a.residual_balance)
                        .map((acc, i) => {
                          const isChecked = selectedFreezeAccs.has(acc.account);
                          return (
                            <div
                              key={i}
                              className={`p-2.5 rounded border transition flex items-start gap-2.5 ${
                                isChecked
                                  ? 'bg-slate-900 border-emerald-500/40'
                                  : 'bg-slate-950 border-slate-800 opacity-60'
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => toggleFreezeAccount(acc.account)}
                                className="mt-1 rounded border-slate-700 bg-slate-950 text-emerald-500 focus:ring-0 cursor-pointer"
                              />

                              <div
                                onClick={() => {
                                  const n = traceResult.nodes.find((x) => x.account === acc.account);
                                  if (n) onSelectNode(n);
                                }}
                                className="flex-1 cursor-pointer"
                              >
                                <div className="flex justify-between items-center text-xs">
                                  <span className="font-mono font-bold text-slate-100">{acc.account}</span>
                                  <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800">
                                    {acc.layer}
                                  </span>
                                </div>
                                <div className="flex justify-between items-center text-xs pt-1">
                                  <span className="text-slate-400 text-[11px]">Trapped Balance:</span>
                                  <span className="font-mono font-bold text-emerald-300">
                                    {formatCurrency(acc.residual_balance)}
                                  </span>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500 text-center py-4">
                      No holding accounts with residual balance detected.
                    </div>
                  )}

                  {/* Legal Notice & Case Diary Action Buttons */}
                  <div className="pt-2 space-y-2">
                    <button
                      onClick={() => {
                        if (onOpenNoticeModal) {
                          onOpenNoticeModal(Array.from(selectedFreezeAccs));
                        }
                      }}
                      disabled={selectedFreezeAccs.size === 0}
                      className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-xs rounded transition flex items-center justify-center gap-2 shadow-lg"
                    >
                      <FileText className="w-4 h-4" />
                      <span>Generate Case Diary + Freeze Notices ({selectedFreezeAccs.size})</span>
                    </button>

                    <button
                      onClick={copyLegalNoticeText}
                      disabled={selectedFreezeAccs.size === 0}
                      className="w-full py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 font-semibold text-[11px] rounded transition flex items-center justify-center gap-1.5 border border-slate-700"
                    >
                      {copiedNotice ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Copied Sec 91 CrPC Text to Clipboard!</span>
                        </>
                      ) : (
                        <>
                          <FileText className="w-3.5 h-3.5 text-slate-400" />
                          <span>Copy Raw Sec 91 CrPC Text</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-12 px-4 text-slate-500 text-xs">
                No active money flow trace. Initiate a trace from the left panel to generate recommendations.
              </div>
            )}
          </div>
        )}

        {/* TIMELINE TAB */}
        {activeTab === 'timeline' && (
          <div className="space-y-3">
            {selectedNode ? (
              <>
                <div className="flex justify-between items-center pb-2 border-b border-slate-800">
                  <h3 className="text-xs uppercase tracking-wider text-slate-400 font-semibold">
                    Transaction Timeline
                  </h3>
                  <span className="text-xs text-slate-400 font-mono">{transactions.length} Txns Loaded</span>
                </div>

                {transactions.length > 0 ? (
                  <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                    {transactions.map((tx) => {
                      const isOut = tx.sender_acc === selectedNode.account;
                      return (
                        <div
                          key={tx.txn_id}
                          className="p-2.5 bg-slate-950 rounded border border-slate-800 hover:border-slate-700 transition text-xs space-y-1.5"
                        >
                          <div className="flex justify-between items-center text-[11px]">
                            <span
                              className={`font-semibold px-2 py-0.5 rounded text-[10px] ${
                                isOut
                                  ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                                  : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                              }`}
                            >
                              {isOut ? 'OUTFLOW' : 'INFLOW'} [{tx.payment_mode}]
                            </span>
                            <span className="text-slate-400 font-mono">{formatTimestamp(tx.ts)}</span>
                          </div>

                          <div className="flex justify-between items-baseline">
                            <div className="font-mono text-slate-300 text-[11px] truncate max-w-[180px]">
                              {isOut ? `To: ${tx.receiver_acc}` : `From: ${tx.sender_acc}`}
                            </div>
                            <div
                              className={`font-mono font-bold text-sm ${
                                isOut ? 'text-rose-400' : 'text-emerald-400'
                              }`}
                            >
                              {isOut ? '-' : '+'}{formatCurrency(tx.amount)}
                            </div>
                          </div>

                          {tx.narration && (
                            <div className="text-[10px] text-slate-500 italic truncate border-t border-slate-900 pt-1">
                              "{tx.narration}"
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-8 text-xs text-slate-500">
                    No individual transactions recorded for this account.
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-12 px-4 text-slate-500 text-xs">
                Select a node to view its transaction timeline.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
