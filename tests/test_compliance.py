import pytest
import json
import os
import sqlite3
from src.tools.compliance_tools import (
    validate_gstin_format, check_duplicate_invoice, log_processed_invoice,
    get_vendor_annual_total, update_vendor_annual_total
)
from src.workflow import create_workflow
from src.schema import InvoiceState, OverallDecision

DB_PATH = "db/compliance.db"

def test_gstin_regex():
    assert validate_gstin_format("27AABCT1234F1ZP") == True
    assert validate_gstin_format("INVALID") == False
    assert validate_gstin_format("27AABCT1234F1Z") == False

def test_duplicate_detection_logic():
    invoice_id = "UNIT-TEST-INV-999"
    gstin = "27AABCT1234F1ZP"
    
    # Clean up if exists
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM invoices_processed WHERE invoice_id = ?", (invoice_id,))
    conn.commit()
    conn.close()

    # Should be False initially
    assert check_duplicate_invoice(invoice_id, gstin) == False
    
    # Log it
    log_processed_invoice(invoice_id, gstin, "2024-10-01", 5000)
    
    # Should be True now
    assert check_duplicate_invoice(invoice_id, gstin) == True

def test_annual_totals_logic():
    pan = "TESTPAN123"
    date = "2024-10-01"
    amount = 10000
    
    # Get initial
    initial = get_vendor_annual_total(pan, date)
    
    # Update
    update_vendor_annual_total(pan, date, amount)
    
    # Check new total
    new_total = get_vendor_annual_total(pan, date)
    assert new_total == initial + amount

def test_workflow_execution():
    invoice_id = "TEST-INV-WORKFLOW"
    gstin = "27AABCT1234F1ZP"
    
    # Clean up DB to ensure not a duplicate
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM invoices_processed WHERE invoice_id = ? AND vendor_gstin = ?", (invoice_id, gstin))
    conn.commit()
    conn.close()

    # Create a small sample invoice file for testing
    sample_invoice = {
        "invoice_id": invoice_id,
        "invoice_number": invoice_id,
        "invoice_date": "2024-10-20",
        "vendor": {
            "name": "TechSoft Solutions Private Limited",
            "gstin": gstin,
            "pan": "AABCT1234F"
        },
        "line_items": [
            {
                "description": "Test Service",
                "quantity": 2,
                "rate": 500,
                "amount": 1000
            }
        ],
        "subtotal": 1000,
        "total_tax": 180,
        "total_amount": 1180
    }
    
    with open("tests/sample.json", "w") as f:
        json.dump(sample_invoice, f)
    
    workflow = create_workflow()
    initial_state = InvoiceState(raw_file_path="tests/sample.json")
    final_state = workflow.invoke(initial_state.model_dump())
    
    assert final_state.get("extracted_data") is not None
    assert final_state.get("overall_decision") == OverallDecision.APPROVED
    assert final_state.get("confidence") >= 0.9
    
    # Clean up
    if os.path.exists("tests/sample.json"):
        os.remove("tests/sample.json")

def test_arithmetic_failure():
    # Invoice with wrong arithmetic
    bad_invoice = {
        "invoice_id": "TEST-INV-FAIL",
        "invoice_date": "2024-10-20",
        "vendor": {"name": "Test", "gstin": "27AABCT1234F1ZP"},
        "line_items": [{"description": "Bad", "quantity": 10, "rate": 10, "amount": 500}], # 10x10 != 500
        "subtotal": 500,
        "total_tax": 0,
        "total_amount": 500
    }
    
    with open("tests/bad.json", "w") as f:
        json.dump(bad_invoice, f)
        
    workflow = create_workflow()
    result = workflow.invoke(InvoiceState(raw_file_path="tests/bad.json").model_dump())
    
    # In LangGraph 0.2+, invoke returns the state as a dict if it was a dict or model if it was a model
    # Our workflow uses InvoiceState model
    
    # Check if result is dict or object
    if isinstance(result, dict):
        val_res = result["validation_results"]
        # If val_res is still an object (common in Pydantic states)
        try:
            c1_status = val_res.category_c_arithmetic.checks["C1"].status
            confidence = result["confidence"]
        except AttributeError:
            c1_status = val_res["category_c_arithmetic"]["checks"]["C1"]["status"]
            confidence = result["confidence"]
    else:
        c1_status = result.validation_results.category_c_arithmetic.checks["C1"].status
        confidence = result.confidence

    assert c1_status == False
    assert confidence < 1.0
    
    if os.path.exists("tests/bad.json"):
        os.remove("tests/bad.json")
