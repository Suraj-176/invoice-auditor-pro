import requests
import sqlite3
import re
from datetime import datetime

MOCK_API_BASE = "http://localhost:8080/api/gst"
DB_PATH = "db/compliance.db"

def validate_gstin_format(gstin: str) -> bool:
    """Check if GSTIN matches the standard 15-char alphanumeric format."""
    pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    return bool(re.match(pattern, gstin))

def call_validate_gstin_api(gstin: str):
    try:
        response = requests.post(f"{MOCK_API_BASE}/validate-gstin", json={"gstin": gstin})
        return response.json()
    except Exception as e:
        return {"valid": False, "error": "API_ERROR", "message": str(e)}

def call_hsn_rate_api(hsn_code: str, date: str):
    try:
        response = requests.get(f"{MOCK_API_BASE}/hsn-rate", params={"code": hsn_code, "date": date})
        return response.json()
    except Exception as e:
        return {"error": "API_ERROR", "message": str(e)}

def check_duplicate_invoice(invoice_id: str, vendor_gstin: str) -> bool:
    if not invoice_id or not vendor_gstin:
        return False
    
    inv_id = str(invoice_id).strip()
    gstin = str(vendor_gstin).strip()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM invoices_processed WHERE invoice_id = ? AND vendor_gstin = ?", (inv_id, gstin))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_vendor_annual_total(pan: str, date_str: str) -> float:
    # Determine fiscal year (April to March)
    date = datetime.strptime(date_str, "%Y-%m-%d")
    if date.month >= 4:
        fiscal_year = f"{date.year}-{date.year + 1}"
    else:
        fiscal_year = f"{date.year - 1}-{date.year}"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT total_amount FROM vendor_annual_totals WHERE vendor_pan = ? AND fiscal_year = ?", (pan, fiscal_year))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0.0

def update_vendor_annual_total(pan: str, date_str: str, amount: float):
    date = datetime.strptime(date_str, "%Y-%m-%d")
    if date.month >= 4:
        fiscal_year = f"{date.year}-{date.year + 1}"
    else:
        fiscal_year = f"{date.year - 1}-{date.year}"
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO vendor_annual_totals (vendor_pan, fiscal_year, total_amount)
        VALUES (?, ?, ?)
        ON CONFLICT(vendor_pan, fiscal_year) DO UPDATE SET total_amount = total_amount + ?
    ''', (pan, fiscal_year, amount, amount))
    conn.commit()
    conn.close()

def log_processed_invoice(invoice_id: str, vendor_gstin: str, date: str, amount: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO invoices_processed (invoice_id, vendor_gstin, invoice_date, amount) VALUES (?, ?, ?, ?)",
                       (invoice_id, vendor_gstin, date, amount))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Already logged
    conn.close()

def call_verify_206ab_api(pan: str):
    try:
        response = requests.post(f"{MOCK_API_BASE}/verify-206ab", json={"pan": pan})
        return response.json()
    except Exception as e:
        return {"error": "API_ERROR", "message": str(e)}
