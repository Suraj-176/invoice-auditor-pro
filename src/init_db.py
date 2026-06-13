import sqlite3
import json
import os
import logging
from pathlib import Path

# Setup logging
logger = logging.getLogger(__name__)

DB_PATH = 'db/compliance.db'

def init_db():
    """Initialize SQLite database with proper error handling and schema validation"""
    try:
        # Ensure db directory exists
        db_dir = os.path.dirname(DB_PATH)
        os.makedirs(db_dir, exist_ok=True)
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        cursor = conn.cursor()
        
        logger.info(f"Initializing database at {DB_PATH}")

        # Create vendors table (master data)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendors (
            vendor_id TEXT PRIMARY KEY,
            legal_name TEXT NOT NULL,
            gstin TEXT UNIQUE,
            pan TEXT UNIQUE,
            vendor_type TEXT,
            tds_section TEXT,
            turnover_last_fy REAL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        logger.debug("Created/verified 'vendors' table")

        # Create invoices_processed table (duplicate detection)
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
        logger.debug("Created/verified 'invoices_processed' table")
        
        # Create indexes for performance
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_vendor_gstin_date 
        ON invoices_processed(vendor_gstin, processed_at)
        ''')
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_invoice_date 
        ON invoices_processed(invoice_date)
        ''')
        logger.debug("Created/verified indexes on 'invoices_processed'")

        # Create vendor_annual_totals table (TDS thresholds)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendor_annual_totals (
            vendor_pan TEXT,
            fiscal_year TEXT,
            total_amount REAL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (vendor_pan, fiscal_year)
        )
        ''')
        logger.debug("Created/verified 'vendor_annual_totals' table")
        
        # Create index on fiscal year for queries
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_fiscal_year 
        ON vendor_annual_totals(fiscal_year)
        ''')
        logger.debug("Created/verified indexes on 'vendor_annual_totals'")

        conn.commit()
        logger.info("Database schema initialized successfully")
        return conn
    
    except sqlite3.DatabaseError as e:
        logger.error(f"Database error during initialization: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {str(e)}")
        raise

def seed_data(conn):
    """Seed database with master data from JSON files with validation"""
    try:
        cursor = conn.cursor()
        vendor_registry_path = 'data/master_data/vendor_registry.json'
        
        if not os.path.exists(vendor_registry_path):
            logger.warning(f"Vendor registry file not found at {vendor_registry_path}")
            return
        
        with open(vendor_registry_path, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as je:
                logger.error(f"Invalid JSON in vendor registry: {str(je)}")
                return
        
        vendors = data.get('vendors', [])
        if not vendors:
            logger.warning("No vendors found in registry")
            return
        
        inserted = 0
        skipped = 0
        
        for v in vendors:
            try:
                # Validate required fields
                if not v.get('vendor_id') or not v.get('legal_name'):
                    logger.warning(f"Skipping vendor with missing required fields: {v}")
                    skipped += 1
                    continue
                
                cursor.execute('''
                INSERT OR REPLACE INTO vendors 
                (vendor_id, legal_name, gstin, pan, vendor_type, tds_section, turnover_last_fy, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    v.get('vendor_id'),
                    v.get('legal_name'),
                    v.get('gstin'),
                    v.get('pan'),
                    v.get('vendor_type'),
                    v.get('tds_section'),
                    v.get('turnover_last_fy'),
                    v.get('status', 'ACTIVE')
                ))
                inserted += 1
            except sqlite3.IntegrityError as ie:
                logger.warning(f"Integrity constraint violated for vendor {v.get('vendor_id')}: {str(ie)}")
                skipped += 1
            except Exception as e:
                logger.error(f"Error seeding vendor {v.get('vendor_id')}: {str(e)}")
                skipped += 1
        
        conn.commit()
        logger.info(f"Database seeded: {inserted} vendors inserted, {skipped} skipped")
    
    except Exception as e:
        logger.error(f"Error during database seeding: {str(e)}")
        raise

def verify_database():
    """Verify database integrity and schema correctness"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check PRAGMA integrity
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()
        if integrity_result[0] != "ok":
            logger.error(f"Database integrity check failed: {integrity_result[0]}")
            return False
        
        # Verify table existence
        cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name IN ('vendors', 'invoices_processed', 'vendor_annual_totals')
        """)
        tables = {row[0] for row in cursor.fetchall()}
        required_tables = {'vendors', 'invoices_processed', 'vendor_annual_totals'}
        
        if tables != required_tables:
            logger.error(f"Missing tables: {required_tables - tables}")
            return False
        
        logger.info("Database verification passed")
        conn.close()
        return True
    
    except Exception as e:
        logger.error(f"Error verifying database: {str(e)}")
        return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        conn = init_db()
        seed_data(conn)
        if verify_database():
            print("✅ Database initialized and verified successfully.")
        else:
            print("❌ Database verification failed.")
        conn.close()
    except Exception as e:
        print(f"❌ Database initialization failed: {str(e)}")
        exit(1)
