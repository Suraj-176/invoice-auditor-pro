"""
Batch processing test - simulates how the UI processes multiple invoices.
Runs all invoices from test_invoices.json through the workflow and prints a full report.
"""
import json
import os
import sqlite3
import tempfile
import sys

sys.path.insert(0, os.getcwd())

from src.workflow import create_workflow
from src.schema import InvoiceState
from src.agents.report_builder import ReporterAgent

DB_PATH = "db/compliance.db"
INPUT_FILE = "data/invoices/test_invoices.json"

DECISION_ICON = {
    "APPROVED": "✅",
    "REJECTED": "❌",
    "ESCALATE_TO_HUMAN": "⚠️",
    "HOLD_FOR_VERIFICATION": "⏸️",
}

# Maps test_invoices.json _expected_result values → our system decisions
EXPECTED_MAP = {
    "PASS":                     ["APPROVED"],
    "PASS_WITH_TDS":            ["APPROVED"],
    "PASS_WITH_FLAGS":          ["APPROVED", "ESCALATE_TO_HUMAN", "HOLD_FOR_VERIFICATION"],
    "PASS_WITH_HIGHER_TDS":     ["APPROVED"],
    "PASS_WITH_TDS_ON_GROSS":   ["APPROVED"],
    "PASS_CHECK_194Q":          ["APPROVED"],
    "PASS_WITH_RCM_LIABILITY":  ["APPROVED"],
    "PASS_LINKED":              ["APPROVED"],
    "PASS_WITH_CFO_APPROVAL":   ["APPROVED", "ESCALATE_TO_HUMAN"],
    "FLAG_FOR_REVIEW":          ["ESCALATE_TO_HUMAN", "HOLD_FOR_VERIFICATION"],
    "FAIL":                     ["REJECTED"],
    "NOT_APPLICABLE":           ["REJECTED", "HOLD_FOR_VERIFICATION"],
    "COMPLEX_ANALYSIS_REQUIRED":["ESCALATE_TO_HUMAN", "HOLD_FOR_VERIFICATION", "APPROVED"],
}

def reset_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM invoices_processed")
    conn.execute("DELETE FROM vendor_annual_totals")
    conn.commit()
    conn.close()

def run_batch():
    reset_db()
    print("=" * 75)
    print("  BATCH PROCESSING TEST — All invoices from test_invoices.json")
    print("=" * 75)

    with open(INPUT_FILE) as f:
        invoices = json.load(f)

    print(f"\n  Total invoices to process: {len(invoices)}\n")

    workflow = create_workflow()
    reporter = ReporterAgent()

    results = []
    passed = failed = warned = 0

    for idx, invoice in enumerate(invoices, 1):
        inv_id    = invoice.get("invoice_id", f"UNKNOWN-{idx}")
        category  = invoice.get("_test_category", "N/A")
        expected  = invoice.get("_expected_result", None)

        # Write single invoice to temp file (same pattern as UI)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as tmp:
            json.dump([invoice], tmp)
            tmp_path = tmp.name

        try:
            result = workflow.invoke(InvoiceState(raw_file_path=tmp_path).model_dump())
            # Convert nested models to dicts for Pydantic v2 validation
            if isinstance(result.get('extracted_data'), dict):
                pass  # Already a dict
            elif result.get('extracted_data'):
                result['extracted_data'] = result['extracted_data'].model_dump() if hasattr(result['extracted_data'], 'model_dump') else result['extracted_data']
            
            if isinstance(result.get('validation_results'), dict):
                pass  # Already a dict
            elif result.get('validation_results'):
                result['validation_results'] = result['validation_results'].model_dump() if hasattr(result['validation_results'], 'model_dump') else result['validation_results']
            
            state  = InvoiceState(**result)
            report = reporter.generate_output_json(state)

            decision    = state.overall_decision.value if hasattr(state.overall_decision, 'value') else str(state.overall_decision).split('.')[-1]
            compliance  = report["compliance_score"]
            confidence  = report["confidence"]
            icon        = DECISION_ICON.get(decision, "ℹ️")

            # Check against expected result using mapping table
            match_str = ""
            if expected:
                accepted = EXPECTED_MAP.get(expected.upper(), [])
                if decision in accepted:
                    match_str = f"  ← ✔ matches expected ({expected})"
                    passed += 1
                else:
                    match_str = f"  ← ✘ expected={expected}"
                    warned += 1
            else:
                passed += 1

            print(f"  [{idx:02d}] {inv_id:20s} {icon} {decision:22s} | score={compliance:3d}% | conf={confidence*100:.0f}%{match_str}")

            results.append({
                "idx": idx,
                "invoice_id": inv_id,
                "category": category,
                "decision": decision,
                "compliance_score": compliance,
                "confidence": confidence,
                "expected": expected,
            })

        except Exception as e:
            print(f"  [{idx:02d}] {inv_id:20s} ❌ ERROR: {e}")
            failed += 1
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass

    # Summary
    total = len(invoices)
    print("\n" + "=" * 75)
    print("  BATCH SUMMARY")
    print("=" * 75)

    decision_counts = {}
    for r in results:
        decision_counts[r["decision"]] = decision_counts.get(r["decision"], 0) + 1

    for decision, count in sorted(decision_counts.items()):
        icon = DECISION_ICON.get(decision, "ℹ️")
        bar  = "█" * count
        print(f"  {icon} {decision:25s}  {count:3d}  {bar}")

    print(f"\n  Total Processed : {total}")
    print(f"  Errors          : {failed}")
    print(f"  Expected Match  : {passed} / {total - failed}")
    print(f"  Unexpected      : {warned}")
    print("=" * 75)

    # Save batch report
    out_path = "reports/batch_test_report.json"
    os.makedirs("reports", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Full report saved to: {out_path}")

if __name__ == "__main__":
    run_batch()
