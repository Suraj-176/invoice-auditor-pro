from schema import InvoiceState, OverallDecision
import json

class ResolverAgent:
    def process(self, state: InvoiceState) -> InvoiceState:
        if not state.validation_results:
            state.audit_trail.append("ResolverAgent: No validation results found. Setting to HOLD.")
            state.overall_decision = OverallDecision.HOLD_FOR_VERIFICATION
            return state

        state.audit_trail.append("ResolverAgent: Analyzing validation results and making final decision.")
        
        results = state.validation_results
        
        # Calculate total passed vs total possible
        total_passed = (
            results.category_a_authenticity.score +
            results.category_b_gst.score +
            results.category_c_arithmetic.score +
            results.category_d_tds.score +
            results.category_e_policy.score
        )
        
        max_possible = (
            results.category_a_authenticity.max_score +
            results.category_b_gst.max_score +
            results.category_c_arithmetic.max_score +
            results.category_d_tds.max_score +
            results.category_e_policy.max_score
        )
        
        compliance_score = total_passed / max_possible if max_possible > 0 else 0
        state.compliance_score = compliance_score
        
        # Confidence reflects the RELIABILITY of the validation
        # We drop confidence if any critical validation check failed or if extraction errors exist
        confidence = 1.0
        if state.errors:
            confidence = 0.5
        
        # Check for critical failures in data (mismatches, etc)
        if total_passed < max_possible:
            # If rules didn't pass, we are 100% sure about the failure, 
            # BUT if it's a messy data issue (like arithmetic mismatch), we drop confidence
            if not results.category_c_arithmetic.checks["C1"].status:
                confidence = 0.8 # Lower confidence because math was bad
        
        state.confidence = confidence
        # We'll store compliance_score in the state to be used by Reporter
        state.audit_trail.append(f"ResolverAgent: Compliance Score is {compliance_score*100:.1f}%.")

        # Logic for decision
        critical_fail = False
        # Check for critical failures (A2 Duplicate, B1 GSTIN Format, C2 Subtotal)
        if not results.category_a_authenticity.checks["A2"].status:
            critical_fail = True
            state.audit_trail.append("ResolverAgent: Critical failure - Duplicate detected.")
        if not results.category_b_gst.checks["B1"].status:
            critical_fail = True
            state.audit_trail.append("ResolverAgent: Critical failure - Invalid GSTIN or Inactive vendor.")
        if not results.category_b_gst.checks["B11"].status:
            critical_fail = True
            state.audit_trail.append("ResolverAgent: Critical failure - Composition dealer charging GST.")

        if critical_fail:
            state.overall_decision = OverallDecision.REJECTED
        elif confidence >= 0.9:
            state.overall_decision = OverallDecision.APPROVED
        elif confidence < 0.7:
            state.overall_decision = OverallDecision.ESCALATE_TO_HUMAN
            state.requires_human_review = True
        else:
            state.overall_decision = OverallDecision.HOLD_FOR_VERIFICATION

        # High value escalation (> 10 Lakhs)
        if state.extracted_data and state.extracted_data.total_amount > 1000000:
             state.audit_trail.append(f"ResolverAgent: High value invoice (> 10L). Escalating for approval.")
             state.overall_decision = OverallDecision.ESCALATE_TO_HUMAN
             state.requires_human_review = True

        state.audit_trail.append(f"ResolverAgent: Final decision is {state.overall_decision} with confidence {confidence*100:.1f}%.")
        return state
