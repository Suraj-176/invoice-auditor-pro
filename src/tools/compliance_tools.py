import requests
import sqlite3
import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Setup logging
logger = logging.getLogger(__name__)

MOCK_API_BASE = "http://localhost:8080/api/gst"
DB_PATH = "db/compliance.db"

def validate_gstin_format(gstin: str) -> bool:
    """Check if GSTIN matches the standard 15-char alphanumeric format."""
    try:
        pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
        return bool(re.match(pattern, gstin))
    except Exception as e:
        logger.error(f"Error validating GSTIN format: {str(e)}")
        return False

def call_validate_gstin_api(gstin: str) -> Dict[str, Any]:
    """Call mock GST API to validate GSTIN with error handling"""
    try:
        if not gstin:
            return {"valid": False, "error": "EMPTY_GSTIN", "message": "GSTIN cannot be empty"}
        
        response = requests.post(
            f"{MOCK_API_BASE}/validate-gstin", 
            json={"gstin": gstin},
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        logger.error(f"GST API connection error - is mock server running on {MOCK_API_BASE}?")
        return {"valid": False, "error": "API_UNAVAILABLE", "message": f"Cannot reach GST API at {MOCK_API_BASE}"}
    except requests.exceptions.Timeout:
        logger.error(f"GST API timeout for GSTIN: {gstin}")
        return {"valid": False, "error": "API_TIMEOUT", "message": "GST API request timed out"}
    except requests.exceptions.HTTPError as he:
        logger.warning(f"GST API HTTP error for GSTIN {gstin}: {he.response.status_code}")
        try:
            return he.response.json()
        except:
            return {"valid": False, "error": f"HTTP_{he.response.status_code}", "message": str(he)}
    except Exception as e:
        logger.error(f"Unexpected error calling GSTIN API: {str(e)}")
        return {"valid": False, "error": "API_ERROR", "message": str(e)}

def call_hsn_rate_api(hsn_code: str, date: str) -> Dict[str, Any]:
    """Call mock GST API for HSN rates with error handling"""
    try:
        if not hsn_code:
            return {"error": "MISSING_HSN", "message": "HSN code cannot be empty"}
        
        response = requests.get(
            f"{MOCK_API_BASE}/hsn-rate",
            params={"code": hsn_code, "date": date},
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        logger.error(f"HSN Rate API connection error")
        return {"error": "API_UNAVAILABLE", "message": "Cannot reach GST API"}
    except requests.exceptions.Timeout:
        logger.error(f"HSN Rate API timeout for HSN: {hsn_code}")
        return {"error": "API_TIMEOUT", "message": "HSN Rate API request timed out"}
    except Exception as e:
        logger.error(f"Error calling HSN Rate API: {str(e)}")
        return {"error": "API_ERROR", "message": str(e)}

def check_duplicate_invoice(invoice_id: str, vendor_gstin: str) -> bool:
    """Check if invoice already processed with proper error handling"""
    try:
        if not invoice_id or not vendor_gstin:
            return False
        
        inv_id = str(invoice_id).strip()
        gstin = str(vendor_gstin).strip()
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM invoices_processed WHERE invoice_id = ? AND vendor_gstin = ?",
            (inv_id, gstin)
        )
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    except sqlite3.DatabaseError as de:
        logger.error(f"Database error checking duplicate: {str(de)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in duplicate check: {str(e)}")
        return False

def get_vendor_annual_total(pan: str, date_str: str) -> float:
    """Get vendor annual total with error handling and fiscal year calculation"""
    try:
        if not pan or not date_str:
            return 0.0
        
        # Determine fiscal year (April to March in India)
        date = datetime.strptime(date_str, "%Y-%m-%d")
        if date.month >= 4:
            fiscal_year = f"{date.year}-{date.year + 1}"
        else:
            fiscal_year = f"{date.year - 1}-{date.year}"
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT total_amount FROM vendor_annual_totals WHERE vendor_pan = ? AND fiscal_year = ?",
            (pan, fiscal_year)
        )
        result = cursor.fetchone()
        conn.close()
        
        return float(result[0]) if result else 0.0
    except ValueError as ve:
        logger.error(f"Date format error: {str(ve)}")
        return 0.0
    except sqlite3.DatabaseError as de:
        logger.error(f"Database error getting vendor total: {str(de)}")
        return 0.0
    except Exception as e:
        logger.error(f"Unexpected error in get_vendor_annual_total: {str(e)}")
        return 0.0

def update_vendor_annual_total(pan: str, date_str: str, amount: float) -> bool:
    """Update vendor annual total with error handling"""
    try:
        if not pan or not date_str or amount < 0:
            logger.warning(f"Invalid parameters for update_vendor_annual_total: pan={pan}, amount={amount}")
            return False
        
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
        logger.info(f"Updated vendor total for {pan} in {fiscal_year}: +₹{amount:,.2f}")
        return True
    except sqlite3.DatabaseError as de:
        logger.error(f"Database error updating vendor total: {str(de)}")
        return False
    except ValueError as ve:
        logger.error(f"Date format error: {str(ve)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in update_vendor_annual_total: {str(e)}")
        return False

def log_processed_invoice(invoice_id: str, vendor_gstin: str, date: str, amount: float) -> bool:
    """Log processed invoice with error handling"""
    try:
        if not invoice_id or not vendor_gstin:
            logger.warning("Cannot log invoice: missing invoice_id or vendor_gstin")
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO invoices_processed (invoice_id, vendor_gstin, invoice_date, amount)
               VALUES (?, ?, ?, ?)""",
            (invoice_id, vendor_gstin, date, amount)
        )
        conn.commit()
        conn.close()
        logger.info(f"Logged invoice {invoice_id} from {vendor_gstin}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Invoice {invoice_id} already logged")
        return False  # Already logged, not an error
    except sqlite3.DatabaseError as de:
        logger.error(f"Database error logging invoice: {str(de)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in log_processed_invoice: {str(e)}")
        return False

def call_verify_206ab_api(pan: str) -> Dict[str, Any]:
    """Verify Section 206AB applicability with error handling"""
    try:
        if not pan:
            return {"valid": False, "error": "EMPTY_PAN", "message": "PAN cannot be empty"}
        
        response = requests.post(
            f"{MOCK_API_BASE}/verify-206ab",
            json={"pan": pan},
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        logger.error(f"206AB API connection error")
        return {"error": "API_UNAVAILABLE", "message": "Cannot reach GST API"}
    except Exception as e:
        logger.error(f"Error calling 206AB API: {str(e)}")
        return {"error": "API_ERROR", "message": str(e)}
