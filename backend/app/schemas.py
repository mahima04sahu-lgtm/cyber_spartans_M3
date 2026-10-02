"""
Pydantic schemas for Abhedya-Chakra REST API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    version: str = "1.0.0"


class NarrationSummary(BaseModel):
    category: str
    count: int
    total_amount: float


class DeviceSummary(BaseModel):
    device_type: str
    count: int
    is_headless: bool


class IPSummary(BaseModel):
    ip_address: str
    count: int
    is_foreign: bool


class AccountProfile(BaseModel):
    account_number: str
    bank_name: str
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    total_received: float = 0.0
    total_sent: float = 0.0
    in_txn_count: int = 0
    out_txn_count: int = 0
    total_txn_count: int = 0
    distinct_counterparties: int = 0
    distinct_senders: int = 0
    distinct_receivers: int = 0
    top_narrations: List[NarrationSummary] = []
    device_summary: List[DeviceSummary] = []
    ip_summary: List[IPSummary] = []
    mule_risk_score: Optional[float] = 0.0
    mule_layer: Optional[str] = "none"


class TransactionItem(BaseModel):
    txn_id: str
    sender_acc: str
    receiver_acc: str
    sender_bank: str
    receiver_bank: str
    amount: float
    ts: str
    payment_mode: str
    narration: str
    narration_category: str
    ip_address: str
    ip_foreign: bool
    device_type: str
    device_headless: bool
    near_threshold: bool


class PaginatedTransactions(BaseModel):
    account_number: str
    total_count: int
    limit: int
    offset: int
    transactions: List[TransactionItem]


class CounterpartyItem(BaseModel):
    counterparty_account: str
    bank_name: str
    relation: str  # "sender" or "receiver"
    total_amount: float
    txn_count: int
    first_seen: str
    last_seen: str


class CounterpartiesResponse(BaseModel):
    account_number: str
    top_senders: List[CounterpartyItem]
    top_receivers: List[CounterpartyItem]


class SearchResultItem(BaseModel):
    type: str  # "account" or "transaction"
    id: str
    description: str


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]


class BenchmarkItem(BaseModel):
    stage_name: str
    duration_seconds: float


class SystemStatsResponse(BaseModel):
    total_transactions: int
    total_accounts: int
    total_fraud_accounts: int = 0
    fraud_percentage: float = 0.0
    min_timestamp: Optional[str] = None
    max_timestamp: Optional[str] = None
    db_size_mb: float = 0.0
    ingest_benchmark: List[BenchmarkItem] = []


class IngestStatusResponse(BaseModel):
    ingested: bool
    total_transactions: int = 0
    total_accounts: int = 0
    db_size_mb: float = 0.0


class CaseDiaryOptions(BaseModel):
    model: str = "qwen2.5:7b"
    use_llm: bool = True
    strict_mode: bool = False


class CaseDiaryRequest(BaseModel):
    victim_account: str
    options: Optional[CaseDiaryOptions] = CaseDiaryOptions()


class CaseDiaryResponse(BaseModel):
    victim_account: str
    evidence_pack: Dict[str, Any]
    evidence_pack_hash: str
    dataset_hash: str
    validation_report: Dict[str, Any]
    case_diary: Dict[str, Any]
    case_diary_text: str
    case_diary_html: str
    execution_time_ms: float


class NoticeRequest(BaseModel):
    victim_account: str
    accounts_selected: Optional[List[str]] = []
    language: str = "en"  # "en" or "bilingual"
    export_format: str = "zip"  # "zip", "pdf", "json"
    officer_details: Optional[Dict[str, str]] = None


class BankNoticeItem(BaseModel):
    bank_name: str
    account_count: int
    filename: str
    format: str
    html_preview: str
    validation_report: Dict[str, Any]


class NoticeResponse(BaseModel):
    victim_account: str
    total_banks: int
    evidence_pack_hash: str
    dataset_hash: str
    validation_report: Dict[str, Any]
    notices: List[BankNoticeItem]
