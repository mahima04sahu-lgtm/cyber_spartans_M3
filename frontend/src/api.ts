/**
 * Typed API Client for Abhedya-Chakra Backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export interface SystemStats {
  total_transactions: number;
  total_accounts: number;
  min_timestamp?: string;
  max_timestamp?: string;
  ingest_benchmark: { stage_name: string; duration_seconds: number }[];
}

export interface SearchResult {
  type: 'account' | 'transaction';
  id: string;
  description: string;
}

export interface SuggestedVictim {
  victim_account: string;
  bank_name: string;
  mule_targets_count: number;
  total_stolen_amount: number;
  first_loss: string;
  last_loss: string;
}

export interface SyndicateRingSummary {
  ring_id: number;
  lead_suspect_account: string;
  layer: string;
  risk_score: number;
  total_volume: number;
  connected_degree: number;
}

export interface TraceNode {
  account: string;
  hop: number;
  first_arrival_time: string;
  amount_received: number;
  amount_forwarded: number;
  residual_balance: number;
  mule_risk_score: number;
  layer: string;
  bank_name: string;
}

export interface TraceEdge {
  txn_id: string;
  sender_account: string;
  receiver_account: string;
  amount: number;
  traced_amount: number;
  timestamp: string;
  epoch_sec: number;
  payment_mode: string;
  hop: number;
}

export interface HoldingAccount {
  account: string;
  residual_balance: number;
  layer: string;
  risk_score: number;
}

export interface TraceResult {
  victim_account: string;
  found: boolean;
  hops_searched: number;
  strict_mode: boolean;
  is_truncated: boolean;
  execution_time_ms: number;
  summary: {
    total_siphoned: number;
    nodes_in_trail: number;
    edges_in_trail: number;
    l1_total_amount: number;
    l2_total_amount: number;
    l3_total_amount: number;
    holding_accounts: HoldingAccount[];
    terminal_cashout_accounts: HoldingAccount[];
  };
  nodes: TraceNode[];
  edges: TraceEdge[];
}

export interface NarrationSummary {
  category: string;
  count: number;
  total_amount: number;
}

export interface DeviceSummary {
  device_type: string;
  count: number;
  is_headless: boolean;
}

export interface IPSummary {
  ip_address: string;
  count: number;
  is_foreign: boolean;
}

export interface AccountProfile {
  account_number: string;
  bank_name: string;
  first_seen?: string;
  last_seen?: string;
  total_received: number;
  total_sent: number;
  in_txn_count: number;
  out_txn_count: number;
  total_txn_count: number;
  distinct_counterparties: number;
  distinct_senders: number;
  distinct_receivers: number;
  top_narrations: NarrationSummary[];
  device_summary: DeviceSummary[];
  ip_summary: IPSummary[];
  mule_risk_score: number;
  mule_layer: string;
}

export interface TransactionItem {
  txn_id: string;
  sender_acc: string;
  receiver_acc: string;
  sender_bank: string;
  receiver_bank: string;
  amount: number;
  ts: string;
  payment_mode: string;
  narration: string;
  narration_category: string;
  ip_address: string;
  ip_foreign: boolean;
  device_type: string;
  device_headless: boolean;
  near_threshold: boolean;
}

export interface PaginatedTransactions {
  account_number: string;
  total_count: number;
  limit: number;
  offset: number;
  transactions: TransactionItem[];
}

export async function fetchStats(): Promise<SystemStats> {
  const res = await fetch(`${API_BASE_URL}/stats`);
  if (!res.ok) throw new Error('Failed to fetch system stats');
  return res.json();
}

export async function searchEntities(q: string): Promise<SearchResult[]> {
  if (!q || q.trim().length === 0) return [];
  const res = await fetch(`${API_BASE_URL}/search?q=${encodeURIComponent(q.trim())}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.results || [];
}

export async function fetchSuggestedVictims(): Promise<SuggestedVictim[]> {
  const res = await fetch(`${API_BASE_URL}/victims/suggest`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.suggested_victims || [];
}

export async function fetchDetectedRings(): Promise<SyndicateRingSummary[]> {
  const res = await fetch(`${API_BASE_URL}/rings`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.rings || [];
}

export async function traceMoneyFlow(
  victimAccount: string,
  hops: number = 4,
  strict: boolean = false
): Promise<TraceResult> {
  const res = await fetch(
    `${API_BASE_URL}/trace/${encodeURIComponent(victimAccount)}?hops=${hops}&strict=${strict}`
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to trace money flow' }));
    throw new Error(err.detail || 'Victim account not found');
  }
  return res.json();
}

export async function fetchAccountProfile(accountNumber: string): Promise<AccountProfile> {
  const res = await fetch(`${API_BASE_URL}/account/${encodeURIComponent(accountNumber)}`);
  if (!res.ok) throw new Error('Account profile not found');
  return res.json();
}

export async function fetchAccountTransactions(
  accountNumber: string,
  limit: number = 20,
  offset: number = 0
): Promise<PaginatedTransactions> {
  const res = await fetch(
    `${API_BASE_URL}/account/${encodeURIComponent(accountNumber)}/transactions?limit=${limit}&offset=${offset}`
  );
  if (!res.ok) throw new Error('Failed to fetch account transactions');
  return res.json();
}

export async function fetchSyndicateRing(accountNumber: string): Promise<TraceResult> {
  const res = await fetch(`${API_BASE_URL}/ring/${encodeURIComponent(accountNumber)}`);
  if (!res.ok) throw new Error('Failed to fetch syndicate ring');
  return res.json();
}

export function getRingExportUrl(accountNumber: string, format: 'csv' | 'json' = 'csv'): string {
  return `${API_BASE_URL}/ring/${encodeURIComponent(accountNumber)}/export?format=${format}`;
}

export interface CaseDiaryResponse {
  victim_account: string;
  evidence_pack: Record<string, any>;
  evidence_pack_hash: string;
  dataset_hash: string;
  validation_report: {
    is_valid: boolean;
    total_checked: number;
    hallucinated_count: number;
    hallucinated_numbers: string[];
    valid_numbers: string[];
  };
  case_diary: Record<string, any>;
  case_diary_text: string;
  case_diary_html: string;
  execution_time_ms: number;
}

export interface BankNoticeItem {
  bank_name: string;
  account_count: number;
  filename: string;
  format: string;
  html_preview: string;
  validation_report: {
    is_valid: boolean;
    total_checked: number;
    hallucinated_count: number;
    hallucinated_numbers: string[];
    valid_numbers: string[];
  };
}

export interface NoticeResponse {
  victim_account: string;
  total_banks: number;
  evidence_pack_hash: string;
  dataset_hash: string;
  validation_report: {
    is_valid: boolean;
    total_checked: number;
    hallucinated_count: number;
    hallucinated_numbers: string[];
    valid_numbers: string[];
  };
  notices: BankNoticeItem[];
}

export async function fetchCaseDiary(
  victimAccount: string,
  useLlm: boolean = false
): Promise<CaseDiaryResponse> {
  const res = await fetch(`${API_BASE_URL}/case-diary`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      victim_account: victimAccount,
      options: { use_llm: useLlm, model: 'qwen2.5:7b', strict_mode: false },
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to generate case diary' }));
    throw new Error(err.detail || 'Case diary generation failed');
  }
  return res.json();
}

export async function fetchNoticePreviews(
  victimAccount: string,
  accountsSelected: string[] = [],
  language: 'en' | 'bilingual' = 'en'
): Promise<NoticeResponse> {
  const res = await fetch(`${API_BASE_URL}/notices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      victim_account: victimAccount,
      accounts_selected: accountsSelected,
      language: language,
      export_format: 'json',
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to generate notice previews' }));
    throw new Error(err.detail || 'Notice preview generation failed');
  }
  return res.json();
}

export async function downloadNoticesZip(
  victimAccount: string,
  accountsSelected: string[] = [],
  language: 'en' | 'bilingual' = 'en'
): Promise<Blob> {
  const res = await fetch(`${API_BASE_URL}/notices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      victim_account: victimAccount,
      accounts_selected: accountsSelected,
      language: language,
      export_format: 'zip',
    }),
  });
  if (!res.ok) throw new Error('Failed to download notices ZIP');
  return res.blob();
}

