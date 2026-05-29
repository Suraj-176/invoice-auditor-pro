from schema import InvoiceState, OverallDecision
from tools.compliance_tools import log_processed_invoice, update_vendor_annual_total
from typing import Dict
import json
import os
import datetime

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
        
        # Save individual invoice report to reports/results/ directory
        results_dir = "reports/results"
        os.makedirs(results_dir, exist_ok=True)
        report_path = os.path.join(results_dir, f"{data.invoice_id}.json")
        with open(report_path, "w") as f:
            json.dump(output, f, indent=2)
        
        state.audit_trail.append(f"ReporterAgent: Report saved to {report_path}.")
        state.audit_trail.append("ReporterAgent: Final report generated successfully.")
        return state

    def generate_output_json(self, state: InvoiceState) -> Dict:
        res = state.validation_results
        
        # Recalculate compliance score from results
        total_passed = sum(cat.score for cat in [res.category_a_authenticity, res.category_b_gst, res.category_c_arithmetic, res.category_d_tds, res.category_e_policy]) if res else 0
        max_possible = sum(cat.max_score for cat in [res.category_a_authenticity, res.category_b_gst, res.category_c_arithmetic, res.category_d_tds, res.category_e_policy]) if res else 1
        
        comp_score_pct = int((total_passed / max_possible) * 100)

        data = state.extracted_data

        # Build gst_summary from line items
        gst_summary = None
        if data:
            cgst_total = sum(item.cgst or 0 for item in data.line_items)
            sgst_total = sum(item.sgst or 0 for item in data.line_items)
            igst_total = sum(item.igst or 0 for item in data.line_items)
            sub = data.subtotal if data.subtotal else 1
            gst_summary = {
                "cgst_amount": cgst_total,
                "cgst_rate": round(cgst_total / sub * 100, 1) if cgst_total > 0 else 0,
                "sgst_amount": sgst_total,
                "sgst_rate": round(sgst_total / sub * 100, 1) if sgst_total > 0 else 0,
                "igst_amount": igst_total,
                "igst_rate": round(igst_total / sub * 100, 1) if igst_total > 0 else 0,
            }

        output = {
            "invoice_id": data.invoice_id if data else "UNKNOWN",
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
            "tds_summary": None,
            "gst_summary": gst_summary,
            "audit_trail": self._build_audit_trail(state.audit_trail)
        }
        return output

    def _format_cat(self, cat):
        return {
            "score": cat.score,
            "max_score": cat.max_score,
            "checks": {id: {"status": "PASS" if c.status else "FAIL", "message": c.message} for id, c in cat.checks.items()}
        }

    def _build_audit_trail(self, audit_trail: list) -> list:
        agent_map = {
            "ExtractorAgent": "Extractor",
            "ValidatorAgent": "Validator",
            "ResolverAgent": "Resolver",
            "ReporterAgent": "Reporter",
        }
        confidence_defaults = {
            "Extractor": 0.95, "Validator": 0.9,
            "Resolver": 1.0, "Reporter": 1.0, "System": 1.0,
        }
        base_time = datetime.datetime.now()
        structured = []
        for i, entry in enumerate(audit_trail):
            if isinstance(entry, dict):
                structured.append(entry)
                continue
            agent = "System"
            for key, name in agent_map.items():
                if entry.startswith(key):
                    agent = name
                    break
            reasoning = entry
            for key in agent_map:
                if reasoning.startswith(key + ": "):
                    reasoning = reasoning[len(key) + 2:]
                    break
            r_lower = reasoning.lower()
            if "starting" in r_lower or "start" in r_lower:
                action = "Start"
            elif "complete" in r_lower or "success" in r_lower or "generated" in r_lower:
                action = "Complete"
            elif "critical failure" in r_lower:
                action = "Critical Failure"
            elif "final decision" in r_lower or "decision is" in r_lower:
                action = "Final Decision"
            elif "duplicate" in r_lower:
                action = "Duplicate Check"
            elif "error" in r_lower:
                action = "Error"
            else:
                action = "Processing"
            structured.append({
                "timestamp": (base_time + datetime.timedelta(milliseconds=i * 200)).isoformat(),
                "agent": agent,
                "action": action,
                "reasoning": reasoning,
                "confidence": confidence_defaults.get(agent, 1.0)
            })
        return structured
