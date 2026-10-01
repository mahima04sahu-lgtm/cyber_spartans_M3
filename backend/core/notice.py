"""
Legal Freeze Notice Generator & WeasyPrint PDF Exporter for Abhedya-Chakra.
Generates bank-grouped notices under Sec 94 BNSS (91 CrPC) & Sec 106 BNSS (102 CrPC).
"""

from datetime import datetime
import io
import os
import re

from typing import Dict, Any, List, Optional, Tuple
import zipfile
import duckdb
from jinja2 import Environment, FileSystemLoader

from backend.core.evidence import build_evidence_pack
from backend.core.validator import validate_case_diary_content, ValidationReport
from backend.core.trace import trace_money_flow

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def get_jinja_env() -> Environment:
    """Initialize Jinja2 template environment."""
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def try_generate_pdf_weasyprint(html_content: str) -> Tuple[bytes, str]:
    """
    Attempts to render PDF using WeasyPrint.
    Falls back to UTF-8 HTML bytes if WeasyPrint is not installed or errors out.
    """
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        return pdf_bytes, "pdf"
    except Exception as e:
        print(f"WeasyPrint PDF rendering fallback to print-optimized HTML ({e}).")
        return html_content.encode("utf-8"), "html"


def group_target_accounts_by_bank(
    con: duckdb.DuckDBPyConnection,
    evidence_pack: Dict[str, Any],
    accounts_selected: Optional[List[str]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Groups selected freeze target accounts by destination bank name.
    """
    selected_set = set(accounts_selected) if accounts_selected else set()

    # If no specific selection, use all holding accounts
    holding_accs = evidence_pack.get("freeze_recommendations", [])
    if not selected_set:
        selected_set = {a["account"] for a in holding_accs}

    bank_groups: Dict[str, List[Dict[str, Any]]] = {}

    for acc_info in evidence_pack.get("layered_accounts", []):
        acc_num = acc_info["account"]
        if acc_num not in selected_set:
            continue

        bank_name = acc_info.get("bank", "Unknown Bank")

        # Find transaction details for this account
        txns_for_acc = []
        for tx in evidence_pack.get("transactions", []):
            if tx["receiver_account"] == acc_num:
                txns_for_acc.append(tx)

        disputed_txns_str = ", ".join([t["txn_id"] for t in txns_for_acc[:5]]) or "TXN_MULTI"
        disputed_amount = sum(t["amount"] for t in txns_for_acc) or acc_info["amount_received"]
        first_ts = txns_for_acc[0]["timestamp"] if txns_for_acc else acc_info["first_seen"]

        item = {
            "account": acc_num,
            "ifsc": acc_info.get("ifsc", "UNKNOWN000"),
            "account_holder": "As per bank records",
            "disputed_txns": disputed_txns_str,
            "timestamp": first_ts,
            "disputed_amount": f"{disputed_amount:,.2f}",
            "residual_balance": f"{acc_info['residual_balance']:,.2f}",
            "layer": acc_info["layer"],
            "risk_score": acc_info["risk_score"],
        }

        if bank_name not in bank_groups:
            bank_groups[bank_name] = []
        bank_groups[bank_name].append(item)

    return bank_groups


def render_bank_freeze_notice(
    bank_name: str,
    bank_accounts: List[Dict[str, Any]],
    evidence_pack: Dict[str, Any],
    language: str = "en",
    officer_details: Optional[Dict[str, str]] = None
) -> str:
    """
    Renders Jinja2 HTML template for a single bank freeze notice.
    """
    env = get_jinja_env()
    template_file = "freeze_notice_bilingual.jinja" if language == "bilingual" else "freeze_notice_en.jinja"
    template = env.get_template(template_file)

    details = officer_details or {}

    context = {
        "bank_name": bank_name,
        "accounts": bank_accounts,
        "victim_account": evidence_pack.get("victim_account", ""),
        "total_siphoned": f"{evidence_pack.get('total_siphoned', 0.0):,.2f}",
        "evidence_pack_hash": evidence_pack.get("evidence_pack_hash", ""),
        "dataset_hash": evidence_pack.get("dataset_hash", ""),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notice_no": details.get("notice_no", ""),
        "date": details.get("date", datetime.now().strftime("%d/%m/%Y")),
        "crime_no": details.get("crime_no", ""),
        "police_station": details.get("police_station", "Cyber Crime Branch Indore"),
        "officer_name": details.get("officer_name", ""),
        "start_date": details.get("start_date", "First Transaction"),
    }

    return template.render(context)


def generate_bank_freeze_notices(
    con: duckdb.DuckDBPyConnection,
    victim_account: str,
    accounts_selected: Optional[List[str]] = None,
    language: str = "en",
    export_format: str = "zip",
    officer_details: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Main function to generate per-bank freeze notices, validate against evidence pack,
    render PDFs / HTMLs, and bundle into a ZIP package.
    """
    t0 = datetime.now()

    # 1. Fetch trace & evidence pack
    trace_res = trace_money_flow(con, victim_account=victim_account, max_hops=4, strict_mode=False)
    evidence_pack = build_evidence_pack(con, trace_res)

    # 2. Group accounts by destination bank
    bank_groups = group_target_accounts_by_bank(con, evidence_pack, accounts_selected)

    notices_output = []
    zip_buffer = io.BytesIO()
    zip_file = zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED)

    all_passed = True
    validation_errors = []

    # Map placeholders for fact verification
    p_to_real = {acc["account"]: acc["account"] for acc_list in bank_groups.values() for acc in acc_list}

    for bank_name, acc_list in bank_groups.items():
        html_content = render_bank_freeze_notice(
            bank_name=bank_name,
            bank_accounts=acc_list,
            evidence_pack=evidence_pack,
            language=language,
            officer_details=officer_details
        )

        # 3. Validate rendered HTML content against evidence pack
        _, val_rep = validate_case_diary_content(html_content, evidence_pack, p_to_real)
        if not val_rep.passed:
            all_passed = False
            validation_errors.extend(val_rep.errors)

        # 4. Generate PDF / HTML bytes
        file_bytes, ext = try_generate_pdf_weasyprint(html_content)

        clean_bank_filename = re.sub(r'[^A-Za-z0-9_]', '_', bank_name)
        filename = f"Notice_{clean_bank_filename}.{ext}"

        # Write to ZIP
        zip_file.writestr(filename, file_bytes)

        notices_output.append({
            "bank_name": bank_name,
            "account_count": len(acc_list),
            "filename": filename,
            "format": ext,
            "html_preview": html_content,
            "validation_report": val_rep.dict(),
        })

    # Close ZIP file
    zip_file.close()
    zip_bytes = zip_buffer.getvalue()

    overall_validation = ValidationReport(
        passed=all_passed,
        retries=0,
        fallback_used=not all_passed,
        errors=validation_errors
    )

    return {
        "victim_account": victim_account,
        "total_banks": len(notices_output),
        "evidence_pack_hash": evidence_pack.get("evidence_pack_hash", ""),
        "dataset_hash": evidence_pack.get("dataset_hash", ""),
        "validation_report": overall_validation.dict(),
        "notices": notices_output,
        "zip_bytes": zip_bytes,
    }
