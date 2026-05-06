import sqlite3
import json
import os

DB_PATH = 'db/compliance.db'

def init_db():
    # Ensure db directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create vendors table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vendors (
        vendor_id TEXT PRIMARY KEY,
        legal_name TEXT,
        gstin TEXT,
        pan TEXT,
        vendor_type TEXT,
        tds_section TEXT,
        turnover_last_fy REAL,
        status TEXT
    )
    ''')

    # Create invoices_processed table (for duplicate detection)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS invoices_processed (
        invoice_id TEXT,
        vendor_gstin TEXT,
        invoice_date TEXT,
        amount REAL,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (invoice_id, vendor_gstin)
    )
    ''')

    # Create vendor_annual_totals table (for TDS thresholds)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vendor_annual_totals (
        vendor_pan TEXT,
        fiscal_year TEXT,
        total_amount REAL DEFAULT 0,
        PRIMARY KEY (vendor_pan, fiscal_year)
    )
    ''')

    conn.commit()
    return conn

def seed_data(conn):
    cursor = conn.cursor()
    vendor_registry_path = 'data/master_data/vendor_registry.json'
    
    if os.path.exists(vendor_registry_path):
        with open(vendor_registry_path, 'r') as f:
            data = json.load(f)
            vendors = data.get('vendors', [])
            for v in vendors:
                cursor.execute('''
                INSERT OR REPLACE INTO vendors (vendor_id, legal_name, gstin, pan, vendor_type, tds_section, turnover_last_fy, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    v.get('vendor_id'),
                    v.get('legal_name'),
                    v.get('gstin'),
                    v.get('pan'),
                    v.get('vendor_type'),
                    v.get('tds_section'),
                    v.get('turnover_last_fy'),
                    v.get('status')
                ))
    
    conn.commit()
    print("Database initialized and seeded successfully.")

if __name__ == '__main__':
    conn = init_db()
    seed_data(conn)
    conn.close()
