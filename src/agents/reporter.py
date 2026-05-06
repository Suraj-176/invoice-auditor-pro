from src.schema import InvoiceState, OverallDecision
from src.tools.compliance_tools import log_processed_invoice, update_vendor_annual_total
from typing import Dict
import json
import os

class ReporterAgent:
    def process(self, state: InvoiceState) -> InvoiceState:
        state.audit_trail.append(f"ReporterAgent: Final decision is {state.overall_decision}")
        
        # Update processed list for Duplicate Detection (TRACK ALL)
        data = state.extracted_data
        state.audit_trail.append(f"ReporterAgent: Logging invoice {data.invoice_id} to processed registry...")
        log_processed_invoice(data.invoice_id, data.vendor_gstin, data.invoice_date, data.total_amount)
        
        if state.overall_decision == OverallDecision.APPROVED:
            # Update financial totals for TDS (APPROVED ONLY)
            if data.pan:
                state.audit_trail.append("ReporterAgent: Updating vendor annual totals for TDS...")
                update_vendor_annual_total(data.pan, data.invoice_date, data.total_amount)
            state.audit_trail.append("ReporterAgent: ✅ Financial records updated.")
        else:
            state.audit_trail.append(f"ReporterAgent: Invoice not approved, skipping financial total update.")

        output = self.generate_output_json(state)
        
        # In a real system, we'd save this to a file
        state.audit_trail.append("ReporterAgent: Final report generated successfully.")
        return state

    def generate_output_json(self, state: InvoiceState) -> Dict:
        res = state.validation_results
        
        # Recalculate compliance score from results
        total_passed = sum(cat.score for cat in [res.category_a_authenticity, res.category_b_gst, res.category_c_arithmetic, res.category_d_tds, res.category_e_policy]) if res else 0
        max_possible = sum(cat.max_score for cat in [res.category_a_authenticity, res.category_b_gst, res.category_c_arithmetic, res.category_d_tds, res.category_e_policy]) if res else 1
        
        comp_score_pct = int((total_passed / max_possible) * 100)

        output = {
            "invoice_id": state.extracted_data.invoice_id if state.extracted_data else "UNKNOWN",
            "overall_decision": state.overall_decision,
            "compliance_score": comp_score_pct,
            "confidence": state.confidence,
            "requires_human_review": state.requires_human_review,
            "validation_results": {
                "category_a_authenticity": self._format_cat(res.category_a_authenticity) if res else {},
                "category_b_gst": self._format_cat(res.category_b_gst) if res else {},
                "category_c_arithmetic": self._format_cat(res.category_c_arithmetic) if res else {},
                "category_d_tds": self._format_cat(res.category_d_tds) if res else {},
                "category_e_policy": self._format_cat(res.category_e_policy) if res else {},
            },
            "tds_summary": {}, # Add detail if needed
            "gst_summary": {}, # Add detail if needed
            "audit_trail": state.audit_trail
        }
        return output

    def _format_cat(self, cat):
        return {
            "score": cat.score,
            "max_score": cat.max_score,
            "checks": {id: {"status": c.status, "message": c.message} for id, c in cat.checks.items()}
        }
