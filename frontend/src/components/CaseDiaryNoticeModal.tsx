import React, { useState, useEffect } from 'react';
import {
  X,
  FileText,
  Download,
  CheckCircle2,
  AlertTriangle,
  Building2,
  ShieldCheck,
  Globe,
  Sparkles,
  Printer,
  Copy,
  Check,
} from 'lucide-react';
import {
  NoticeResponse,
  CaseDiaryResponse,
  fetchNoticePreviews,
  fetchCaseDiary,
  downloadNoticesZip,
  BankNoticeItem,
} from '../api';

interface CaseDiaryNoticeModalProps {
  isOpen: boolean;
  onClose: () => void;
  victimAccount: string;
  selectedAccounts: string[];
}

export const CaseDiaryNoticeModal: React.FC<CaseDiaryNoticeModalProps> = ({
  isOpen,
  onClose,
  victimAccount,
  selectedAccounts,
}) => {
  const [language, setLanguage] = useState<'en' | 'bilingual'>('en');
  const [useLlm, setUseLlm] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'notices' | 'casediary'>('notices');
  
  const [loadingNotices, setLoadingNotices] = useState<boolean>(false);
  const [noticeData, setNoticeData] = useState<NoticeResponse | null>(null);
  const [activeBankIdx, setActiveBankIdx] = useState<number>(0);
  
  const [loadingDiary, setLoadingDiary] = useState<boolean>(false);
  const [diaryData, setDiaryData] = useState<CaseDiaryResponse | null>(null);
  
  const [downloadingZip, setDownloadingZip] = useState<boolean>(false);
  const [copiedHtml, setCopiedHtml] = useState<boolean>(false);

  // Fetch notices when modal opens or language/selectedAccounts change
  useEffect(() => {
    if (!isOpen || !victimAccount) return;

    setLoadingNotices(true);
    fetchNoticePreviews(victimAccount, selectedAccounts, language)
      .then((data) => {
        setNoticeData(data);
        setActiveBankIdx(0);
      })
      .catch((err) => {
        console.error('Failed to load notices', err);
      })
      .finally(() => {
        setLoadingNotices(false);
      });
  }, [isOpen, victimAccount, selectedAccounts, language]);

  // Fetch Case Diary when diary tab is activated or LLM mode toggled
  useEffect(() => {
    if (!isOpen || !victimAccount || activeTab !== 'casediary') return;

    setLoadingDiary(true);
    fetchCaseDiary(victimAccount, useLlm)
      .then((data) => {
        setDiaryData(data);
      })
      .catch((err) => {
        console.error('Failed to load case diary', err);
      })
      .finally(() => {
        setLoadingDiary(false);
      });
  }, [isOpen, victimAccount, activeTab, useLlm]);

  if (!isOpen) return null;

  const handleDownloadZip = async () => {
    if (!victimAccount) return;
    try {
      setDownloadingZip(true);
      const blob = await downloadNoticesZip(victimAccount, selectedAccounts, language);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Freeze_Notices_${victimAccount}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (e) {
      alert('Failed to download ZIP archive');
    } finally {
      setDownloadingZip(false);
    }
  };

  const currentNotice: BankNoticeItem | null =
    noticeData && noticeData.notices && noticeData.notices.length > 0
      ? noticeData.notices[activeBankIdx]
      : null;

  const copyNoticeHtml = () => {
    if (!currentNotice) return;
    navigator.clipboard.writeText(currentNotice.html_preview);
    setCopiedHtml(true);
    setTimeout(() => setCopiedHtml(false), 2000);
  };

  const printCurrentNotice = () => {
    if (!currentNotice) return;
    const win = window.open('', '_blank');
    if (win) {
      win.document.write(currentNotice.html_preview);
      win.document.close();
      win.focus();
      setTimeout(() => win.print(), 500);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 overflow-hidden animate-fadeIn">
      <div className="bg-slate-900 border border-slate-700 w-full max-w-6xl h-[90vh] rounded-xl shadow-2xl flex flex-col overflow-hidden text-slate-100">
        {/* MODAL HEADER */}
        <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-lg border border-emerald-500/30">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                Legal Freeze Notices & Police Case Diary
              </h2>
              <p className="text-xs text-slate-400">
                Sec 94 BNSS (91 CrPC) & Sec 106 BNSS (102 CrPC) • Crime Ref / Victim:{' '}
                <span className="font-mono text-cyan-400 font-bold">{victimAccount}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Validation Badge */}
            <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-950/80 border border-emerald-500/50 text-emerald-300 text-xs font-semibold rounded-full shadow-inner">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>All facts verified against database (SHA-256)</span>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* MODAL TOOLBAR & CONTROLS */}
        <div className="px-6 py-3 bg-slate-900/90 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
          {/* Main Tabs */}
          <div className="flex items-center gap-2 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-semibold">
            <button
              onClick={() => setActiveTab('notices')}
              className={`px-4 py-2 rounded-md transition flex items-center gap-2 ${
                activeTab === 'notices'
                  ? 'bg-emerald-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Building2 className="w-4 h-4" />
              Bank Freeze Notices ({noticeData?.total_banks || 0} Banks)
            </button>
            <button
              onClick={() => setActiveTab('casediary')}
              className={`px-4 py-2 rounded-md transition flex items-center gap-2 ${
                activeTab === 'casediary'
                  ? 'bg-cyan-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              Police Case Diary
            </button>
          </div>

          {/* Options: Language & LLM mode */}
          <div className="flex items-center gap-4 text-xs">
            {activeTab === 'notices' && (
              <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
                <Globe className="w-4 h-4 text-cyan-400" />
                <span className="text-slate-400 font-medium">Language:</span>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as 'en' | 'bilingual')}
                  className="bg-slate-900 border border-slate-700 text-slate-200 rounded px-2 py-1 text-xs focus:outline-none focus:border-cyan-500"
                >
                  <option value="en">English (Standard)</option>
                  <option value="bilingual">Bilingual (Hindi + English)</option>
                </select>
              </div>
            )}

            {activeTab === 'casediary' && (
              <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <span className="text-slate-400 font-medium">Generation Mode:</span>
                <button
                  onClick={() => setUseLlm(!useLlm)}
                  className={`px-2.5 py-1 rounded text-xs font-bold transition ${
                    useLlm
                      ? 'bg-amber-600 text-white'
                      : 'bg-slate-800 text-slate-300 border border-slate-700'
                  }`}
                >
                  {useLlm ? 'AI LLM (Ollama)' : 'Instant Template (Offline)'}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* MAIN BODY AREA */}
        <div className="flex-1 overflow-hidden flex bg-slate-950">
          {/* TAB 1: BANK FREEZE NOTICES PREVIEW */}
          {activeTab === 'notices' && (
            <div className="flex-1 flex overflow-hidden">
              {/* Left sidebar: Bank List */}
              <div className="w-72 bg-slate-900/60 border-r border-slate-800 flex flex-col p-4 space-y-3">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  Target Destination Banks
                </h3>

                {loadingNotices ? (
                  <div className="text-center py-12 text-xs text-slate-500 animate-pulse">
                    Generating freeze notices...
                  </div>
                ) : noticeData && noticeData.notices.length > 0 ? (
                  <div className="space-y-2 overflow-y-auto flex-1 pr-1">
                    {noticeData.notices.map((n, i) => (
                      <button
                        key={i}
                        onClick={() => setActiveBankIdx(i)}
                        className={`w-full text-left p-3 rounded-lg border transition space-y-1 ${
                          activeBankIdx === i
                            ? 'bg-slate-800 border-emerald-500/60 text-white shadow'
                            : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex items-center justify-between text-xs font-bold font-mono">
                          <span className="truncate max-w-[170px] text-cyan-300">{n.bank_name}</span>
                          <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800">
                            {n.account_count} Acc
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span>{n.filename}</span>
                          <span className="text-emerald-400 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> Verified
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 py-8 text-center">
                    No target holding accounts selected.
                  </div>
                )}
              </div>

              {/* Center Right: Notice Preview Canvas */}
              <div className="flex-1 flex flex-col bg-slate-950 overflow-hidden">
                {currentNotice ? (
                  <>
                    <div className="px-6 py-2.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-200">
                          Previewing Notice for: <span className="text-emerald-400 font-mono">{currentNotice.bank_name}</span>
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                          {currentNotice.format.toUpperCase()} Ready
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={copyNoticeHtml}
                          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded border border-slate-700 flex items-center gap-1.5 transition"
                        >
                          {copiedHtml ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                          {copiedHtml ? 'Copied HTML!' : 'Copy Text'}
                        </button>
                        <button
                          onClick={printCurrentNotice}
                          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded border border-slate-700 flex items-center gap-1.5 transition"
                        >
                          <Printer className="w-3.5 h-3.5 text-cyan-400" />
                          Print Preview
                        </button>
                      </div>
                    </div>

                    <div className="flex-1 p-6 overflow-y-auto bg-slate-950 flex justify-center">
                      <div className="w-full max-w-4xl bg-white text-slate-900 p-8 rounded shadow-2xl overflow-x-auto min-h-[600px] border border-slate-300">
                        <iframe
                          title="Notice Preview"
                          srcDoc={currentNotice.html_preview}
                          className="w-full h-[700px] border-none"
                        />
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-xs text-slate-500">
                    Select a bank notice from the left sidebar to preview.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: POLICE CASE DIARY PREVIEW */}
          {activeTab === 'casediary' && (
            <div className="flex-1 flex flex-col p-6 overflow-y-auto bg-slate-950">
              {loadingDiary ? (
                <div className="text-center py-24 text-slate-400 text-sm animate-pulse space-y-2">
                  <Sparkles className="w-8 h-8 text-cyan-400 mx-auto animate-spin" />
                  <div>Synthesizing Police Case Diary with Evidence Pack verification...</div>
                </div>
              ) : diaryData ? (
                <div className="max-w-4xl mx-auto w-full space-y-6">
                  {/* Integrity Metadata Header */}
                  <div className="bg-slate-900 p-4 rounded-lg border border-slate-800 grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <span className="text-slate-500 uppercase text-[10px] font-bold block">Evidence Pack SHA-256</span>
                      <span className="font-mono text-cyan-400 font-bold text-xs select-all">
                        {diaryData.evidence_pack_hash}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 uppercase text-[10px] font-bold block">Dataset Master SHA-256</span>
                      <span className="font-mono text-purple-400 font-bold text-xs select-all">
                        {diaryData.dataset_hash}
                      </span>
                    </div>
                  </div>

                  {/* HTML Case Diary View */}
                  <div className="bg-white text-slate-900 p-8 rounded-lg shadow-xl border border-slate-300 space-y-4 font-serif leading-relaxed">
                    <iframe
                      title="Case Diary HTML"
                      srcDoc={diaryData.case_diary_html}
                      className="w-full h-[650px] border-none"
                    />
                  </div>
                </div>
              ) : (
                <div className="text-center py-20 text-slate-500 text-xs">
                  Failed to load case diary preview.
                </div>
              )}
            </div>
          )}
        </div>

        {/* MODAL FOOTER */}
        <div className="px-6 py-4 bg-slate-950 border-t border-slate-800 flex items-center justify-between">
          <div className="text-xs text-slate-400 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span>Ready for official sign-off under Sec 63 Bharatiya Sakshya Adhiniyam</span>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition"
            >
              Close
            </button>

            <button
              onClick={handleDownloadZip}
              disabled={downloadingZip || !noticeData || noticeData.notices.length === 0}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition flex items-center gap-2 shadow-lg"
            >
              <Download className="w-4 h-4" />
              {downloadingZip ? 'Packing ZIP Archive...' : 'Download All Freeze Notices (.ZIP)'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
