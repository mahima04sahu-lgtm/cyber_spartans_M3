"""
Hallucination & Anti-Prompt-Injection Validator for Abhedya-Chakra.
Validates LLM placeholder integrity and ground-truth fact verification against Evidence Packs.
"""

import re
from typing import Dict, Any, List, Set, Tuple
from pydantic import BaseModel


class ValidationReport(BaseModel):
    passed: bool
    retries: int = 0
    fallback_used: bool = False
    errors: List[str] = []


def extract_ground_truth_entities(evidence_pack: Dict[str, Any]) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    """
    Extracts sets of all valid ground-truth accounts, amounts, IFSCs, and Txn IDs from Evidence Pack.
    """
    valid_accounts: Set[str] = set()
    valid_amounts: Set[str] = set()
    valid_ifscs: Set[str] = set()
    valid_txn_ids: Set[str] = set()

    # Victim
    if evidence_pack.get("victim_account"):
        valid_accounts.add(str(evidence_pack["victim_account"]).strip())
    if evidence_pack.get("victim_ifsc"):
        valid_ifscs.add(str(evidence_pack["victim_ifsc"]).strip())
    if evidence_pack.get("total_siphoned") is not None:
        amt = float(evidence_pack["total_siphoned"])
        valid_amounts.add(f"{amt:.2f}")
        valid_amounts.add(f"{int(amt)}")

    # Layered Accounts
    for acc in evidence_pack.get("layered_accounts", []):
        if acc.get("account"):
            valid_accounts.add(str(acc["account"]).strip())
        if acc.get("ifsc"):
            valid_ifscs.add(str(acc["ifsc"]).strip())
        for amt_field in ["amount_received", "amount_forwarded", "residual_balance"]:
            if acc.get(amt_field) is not None:
                amt = float(acc[amt_field])
                valid_amounts.add(f"{amt:.2f}")
                valid_amounts.add(f"{int(amt)}")

    # Transactions
    for tx in evidence_pack.get("transactions", []):
        if tx.get("txn_id"):
            valid_txn_ids.add(str(tx["txn_id"]).strip())
        if tx.get("sender_account"):
            valid_accounts.add(str(tx["sender_account"]).strip())
        if tx.get("receiver_account"):
            valid_accounts.add(str(tx["receiver_account"]).strip())
        for amt_field in ["amount", "traced_amount"]:
            if tx.get(amt_field) is not None:
                amt = float(tx[amt_field])
                valid_amounts.add(f"{amt:.2f}")
                valid_amounts.add(f"{int(amt)}")

    return valid_accounts, valid_amounts, valid_ifscs, valid_txn_ids


def substitute_placeholders(
    text: str,
    placeholder_to_real: Dict[str, str]
) -> Tuple[str, List[str]]:
    """
    Substitutes placeholders ({ACC_0}, {AMT_1}, etc.) with real values.
    Returns (substituted_text, unknown_placeholders).
    """
    unknown_placeholders: List[str] = []
    
    def replacer(match: re.Match) -> str:
        p = match.group(0)
        if p in placeholder_to_real:
            return placeholder_to_real[p]
        else:
            unknown_placeholders.append(p)
            return p

    # Find all {ACC_n}, {AMT_n}, {TXN_n}
    pattern = r"\{(?:ACC|AMT|TXN)_\d+\}"
    substituted_text = re.sub(pattern, replacer, text)
    return substituted_text, unknown_placeholders


def validate_case_diary_content(
    text: str,
    evidence_pack: Dict[str, Any],
    placeholder_to_real: Dict[str, str],
    retries: int = 0
) -> Tuple[str, ValidationReport]:
    """
    Validates placeholder integrity, substitutes real values, and enforces regex fact verification.
    """
    errors: List[str] = []

    # 1. Substitute Placeholders & check for unknown placeholders
    substituted_text, unknown_placeholders = substitute_placeholders(text, placeholder_to_real)
    if unknown_placeholders:
        errors.append(f"Unknown or unmapped placeholders found: {', '.join(set(unknown_placeholders))}")

    # Extract ground-truth entity sets
    valid_accs, valid_amts, valid_ifscs, valid_txns = extract_ground_truth_entities(evidence_pack)

    # 2. Extract and verify 12-character account numbers
    # Account format: 12 alphanumeric characters with digits (e.g. 910000024789, HDFC10000336)
    extracted_tokens = set(re.findall(r'\b[A-Za-z0-9]{12}\b', substituted_text))
    for acc in extracted_tokens:
        # Ignore pure alphabetic words (e.g., TRANSACTIONS, JURISDICTION, REGISTRATION)
        if not any(c.isdigit() for c in acc):
            continue
        if acc not in valid_accs:
            errors.append(f"Hallucinated or invalid account detected: '{acc}'")

    # 3. Extract and verify transaction IDs
    extracted_txns = set(re.findall(r'\bTXN[_\w\d]+\b', substituted_text))
    for tx_id in extracted_txns:
        if tx_id not in valid_txns:
            errors.append(f"Hallucinated or invalid Transaction ID detected: '{tx_id}'")

    # 4. Extract and verify IFSC patterns
    extracted_ifscs = set(re.findall(r'\b[A-Z]{4}0[A-Z0-9]{6}\b', substituted_text))
    for ifsc in extracted_ifscs:
        if ifsc not in valid_ifscs:
            errors.append(f"Hallucinated or invalid IFSC code detected: '{ifsc}'")

    # 5. Extract and verify currency amounts
    # Match numbers with ₹/Rs./INR prefix OR numbers with comma formatting / decimals
    currency_matches = set(re.findall(r'(?:₹|Rs\.|INR)\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', substituted_text))
    formatted_num_matches = set(re.findall(r'\b(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+\.\d{2})\b', substituted_text))
    
    # Combined candidate amount strings
    all_raw_amounts = currency_matches.union(formatted_num_matches)
    
    # Known non-amount integers (sections, standards, years) to ignore
    ignored_literals = {"91", "94", "102", "106", "256", "63", "2023", "2024", "2025", "2026", "2027"}

    for raw_num in all_raw_amounts:
        clean_num = raw_num.replace(",", "").strip()
        if clean_num in ignored_literals:
            continue
        try:
            val = float(clean_num)
            val_str = f"{val:.2f}"
            val_int = f"{int(val)}"
            # Ignore small zero/single digit indices or percentages
            if val > 10 and val_str not in valid_amts and val_int not in valid_amts:
                errors.append(f"Hallucinated or unverified amount detected: '{raw_num}'")
        except ValueError:
            pass

    passed = len(errors) == 0
    report = ValidationReport(
        passed=passed,
        retries=retries,
        fallback_used=not passed,
        errors=errors
    )

    return substituted_text, report
