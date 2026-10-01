"""
Unit tests for Legal Freeze Notice Generator & WeasyPrint/HTML Export.
"""

import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db import init_db, close_db, get_db
from backend.core.notice import (
    generate_bank_freeze_notices,
    render_bank_freeze_notice,
    group_target_accounts_by_bank,
)
from backend.core.evidence import build_evidence_pack
from backend.core.trace import trace_money_flow

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    candidates = ["data/db/abhedya.duckdb", "abhedya/data/db/abhedya.duckdb"]
    db_path = None
    for cand in candidates:
        if os.path.exists(cand):
            db_path = cand
            break
            
    if not db_path:
        pytest.skip("Test database abhedya.duckdb does not exist. Run ingestion first.")
    
    init_db(db_path)
    yield
    close_db()


def get_test_victim():
    con = get_db()
    row = con.execute("SELECT sender_acc FROM txn LIMIT 1").fetchone()
    return row[0] if row else "HDFC10000336"


def test_bank_grouping_and_notice_rendering():
    con = get_db()
    victim_acc = get_test_victim()
    
    trace_res = trace_money_flow(con, victim_account=victim_acc, max_hops=4)
    evidence_pack = build_evidence_pack(con, trace_res)
    
    groups = group_target_accounts_by_bank(con, evidence_pack)
    assert isinstance(groups, dict)

    if groups:
        first_bank = list(groups.keys())[0]
        acc_list = groups[first_bank]
        
        # Test English rendering
        html_en = render_bank_freeze_notice(first_bank, acc_list, evidence_pack, language="en")
        assert "POLICE COMMISSIONERATE INDORE" in html_en
        assert "SECTION 94 BNSS" in html_en
        assert first_bank in html_en

        # Test Bilingual rendering
        html_bi = render_bank_freeze_notice(first_bank, acc_list, evidence_pack, language="bilingual")
        assert "धारा 94 बीएनएसएस" in html_bi
        assert "NOTICE U/S 94 BNSS" in html_bi


def test_generate_bank_freeze_notices_zip():
    con = get_db()
    victim_acc = get_test_victim()
    
    res = generate_bank_freeze_notices(
        con,
        victim_account=victim_acc,
        language="en",
        export_format="zip"
    )
    
    assert res["victim_account"] == victim_acc
    assert "evidence_pack_hash" in res
    assert "validation_report" in res
    assert res["validation_report"]["passed"] is True
    assert isinstance(res["zip_bytes"], bytes)
    assert len(res["zip_bytes"]) > 0


def test_post_notices_api_endpoint_json():
    victim_acc = get_test_victim()
    payload = {
        "victim_account": victim_acc,
        "language": "en",
        "export_format": "json"
    }
    response = client.post("/api/notices", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["victim_account"] == victim_acc
    assert "notices" in data
    assert isinstance(data["notices"], list)
    assert data["validation_report"]["passed"] is True


def test_post_notices_api_endpoint_zip_download():
    victim_acc = get_test_victim()
    payload = {
        "victim_account": victim_acc,
        "language": "bilingual",
        "export_format": "zip"
    }
    response = client.post("/api/notices", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert len(response.content) > 0
