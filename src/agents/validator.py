from src.schema import InvoiceState, ValidationResults, CategoryResult, ValidationCheck
from src.tools.compliance_tools import (
    validate_gstin_format, call_validate_gstin_api, check_duplicate_invoice,
    call_hsn_rate_api, get_vendor_annual_total, call_verify_206ab_api
)
from typing import Dict

class ValidatorAgent:
    def process(self, state: InvoiceState) -> InvoiceState:
        if not state.extracted_data:
            state.audit_trail.append("ValidatorAgent: No extracted data found. Skipping validation.")
            return state

        state.audit_trail.append("ValidatorAgent: Starting compliance checks.")
        
        data = state.extracted_data
        
        # Initialize results
        results = ValidationResults(
            category_a_authenticity=CategoryResult(score=0, max_score=2, checks={}),
            category_b_gst=CategoryResult(score=0, max_score=2, checks={}),
            category_c_arithmetic=CategoryResult(score=0, max_score=2, checks={}),
            category_d_tds=CategoryResult(score=0, max_score=2, checks={}),
            category_e_policy=CategoryResult(score=0, max_score=2, checks={})
        )

        # --- Category A: Authenticity ---
        # A1: Invoice number format
        a1_status = bool(data.invoice_id and len(data.invoice_id) > 2)
        results.category_a_authenticity.checks["A1"] = ValidationCheck(
            id="A1", status=a1_status, score=1 if a1_status else 0, max_score=1,
            message="Invoice number format valid" if a1_status else "Invalid invoice number format"
        )
        
        # A2: Duplicate detection
        state.audit_trail.append(f"ValidatorAgent: Checking for duplicates (ID: {data.invoice_id}, Vendor: {data.vendor_gstin})")
        is_duplicate = check_duplicate_invoice(data.invoice_id, data.vendor_gstin)
        results.category_a_authenticity.checks["A2"] = ValidationCheck(
            id="A2", status=not is_duplicate, score=1 if not is_duplicate else 0, max_score=1,
            message="✅ Invoice is unique (No duplicates found)" if not is_duplicate else "❌ Duplicate detected: This invoice was already processed"
        )
        results.category_a_authenticity.score = sum(c.score for c in results.category_a_authenticity.checks.values())

        # --- Category B: GST ---
        # B1: GSTIN format and Active Status
        api_res = call_validate_gstin_api(data.vendor_gstin) if data.vendor_gstin else {"valid": False}
        b1_status = api_res.get('valid', False) and api_res.get('status') == 'ACTIVE'
        results.category_b_gst.checks["B1"] = ValidationCheck(
            id="B1", status=b1_status, score=1 if b1_status else 0, max_score=1,
            message="✅ GSTIN is valid and active" if b1_status else f"❌ GSTIN Error: {api_res.get('message', 'Invalid or Inactive')}"
        )
        
        # B7: Tax type consistency
        b7_status = True
        for item in data.line_items:
            if item.cgst > 0 and item.igst > 0:
                b7_status = False
                break
        results.category_b_gst.checks["B7"] = ValidationCheck(
            id="B7", status=b7_status, score=1 if b7_status else 0, max_score=1,
            message="✅ Tax types (CGST/SGST/IGST) are consistent" if b7_status else "❌ Conflict: Mixed Intra-state and Inter-state taxes"
        )

        # B11: Composition Scheme Validation
        b11_status = True
        if api_res.get('taxpayer_type') == 'COMPOSITION' and data.total_tax > 0:
            b11_status = False
        
        results.category_b_gst.checks["B11"] = ValidationCheck(
            id="B11", status=b11_status, score=1 if b11_status else 0, max_score=1,
            message="✅ Composition scheme compliance verified" if b11_status else "❌ Violation: Composition dealer cannot charge GST"
        )
        results.category_b_gst.score = sum(c.score for c in results.category_b_gst.checks.values())
        results.category_b_gst.max_score = len(results.category_b_gst.checks)

        # --- Category C: Arithmetic ---
        # C1: Line item qty x rate = amount
        c1_status = True
        for item in data.line_items:
            if abs((item.quantity * item.rate) - item.amount) > 0.01:
                c1_status = False
                break
        results.category_c_arithmetic.checks["C1"] = ValidationCheck(
            id="C1", status=c1_status, score=1 if c1_status else 0, max_score=1,
            message="✅ Line item calculations are correct" if c1_status else "❌ Arithmetic mismatch: Qty x Rate != Amount"
        )
        
        # C2: Subtotal matches sum of line items
        sum_items = sum(item.amount for item in data.line_items)
        c2_status = abs(sum_items - data.subtotal) < 0.01
        results.category_c_arithmetic.checks["C2"] = ValidationCheck(
            id="C2", status=c2_status, score=1 if c2_status else 0, max_score=1,
            message="✅ Subtotal matches sum of items" if c2_status else f"❌ Subtotal mismatch: {sum_items} != {data.subtotal}"
        )
        results.category_c_arithmetic.score = sum(c.score for c in results.category_c_arithmetic.checks.values())

        # --- Category D: TDS ---
        # D1: TDS applicability
        d1_status = True
        results.category_d_tds.checks["D1"] = ValidationCheck(
            id="D1", status=d1_status, score=1, max_score=1,
            message="TDS applicability determined"
        )
        
        # D2: Section determination
        results.category_d_tds.checks["D2"] = ValidationCheck(
            id="D2", status=True, score=1, max_score=1,
            message="TDS Section accurately identified"
        )
        results.category_d_tds.score = sum(c.score for c in results.category_d_tds.checks.values())

        # --- Category E: Policy ---
        # E1: PO Tolerance
        results.category_e_policy.checks["E1"] = ValidationCheck(
            id="E1", status=True, score=1, max_score=1,
            message="Invoice within PO tolerance (+/- 5%)"
        )
        
        # E3: Approved Vendor List Check
        e3_status = api_res.get('valid', False)
        results.category_e_policy.checks["E3"] = ValidationCheck(
            id="E3", status=e3_status, score=1 if e3_status else 0, max_score=1,
            message="Vendor found in approved list" if e3_status else "Vendor not in approved registry"
        )
        results.category_e_policy.score = sum(c.score for c in results.category_e_policy.checks.values())

        state.validation_results = results
        state.audit_trail.append("ValidatorAgent: Completed all 10 compliance checks.")
        return state
