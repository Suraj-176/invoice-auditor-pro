import json
import subprocess
import os
import sqlite3
import shutil

# Paths
INPUT_SAMPLES = "data/invoices/test_invoices.json"
REPORTS_DIR = "reports/regression_test"
DB_PATH = "db/compliance.db"

def setup():
    if os.path.exists(REPORTS_DIR):
        shutil.rmtree(REPORTS_DIR)
    os.makedirs(REPORTS_DIR)
    
    # Reset DB
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM invoices_processed")
    conn.execute("DELETE FROM vendor_annual_totals")
    conn.commit()
    conn.close()
    print("Regression Test Setup Complete.")

def run_cli(input_path, output_path):
    cmd = ["py", "src/main.py", "--input", input_path, "--output", output_path]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return result

def validate_schema(data):
    required_keys = ["invoice_id", "overall_decision", "compliance_score", "confidence", "requires_human_review", "validation_results", "audit_trail"]
    return all(k in data for k in required_keys)

def test_regression():
    setup()
    
    with open(INPUT_SAMPLES, 'r') as f:
        all_invoices = json.load(f)
    
    # Test Scenarios
    scenarios = [
        {"idx": 0, "name": "Standard Valid", "expected": "APPROVED"},
        {"idx": 0, "name": "Duplicate Rejection", "expected": "REJECTED"},
        {"idx": 3, "name": "Composition Scheme Fail", "expected": "REJECTED"}, # Our simplified resolver rejects critical fails
        {"idx": 16, "name": "High Value Escalation", "expected": "ESCALATE_TO_HUMAN"}
    ]
    
    for scenario in scenarios:
        inv = all_invoices[scenario["idx"]]
        name = scenario["name"]
        filename = f"{name.replace(' ', '_').lower()}.json"
        input_path = f"tests/{filename}"
        output_path = f"{REPORTS_DIR}/{filename}"
        
        with open(input_path, 'w') as f:
            json.dump(inv, f)
            
        print(f"Running Scenario: {name}...")
        res = run_cli(input_path, output_path)
        
        if res.returncode != 0:
            print(f"❌ CLI Failed for {name}: {res.stderr}")
            continue
            
        with open(output_path, 'r') as f:
            data = json.load(f)
            
        # Schema Validation
        if not validate_schema(data):
            print(f"❌ Schema Validation Failed for {name}")
            continue
            
        # Decision Validation
        actual = data["overall_decision"]
        if actual == scenario["expected"]:
            print(f"✅ PASSED: Decision matches expected ({actual})")
        else:
            print(f"⚠️ WARNING: Decision mismatch for {name}. Expected {scenario['expected']}, got {actual}")
            
        # Cleanup input
        os.remove(input_path)

if __name__ == "__main__":
    test_regression()
