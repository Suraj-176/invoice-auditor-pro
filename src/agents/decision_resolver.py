from schema import InvoiceState, OverallDecision
from tools.compliance_tools import get_vendor_annual_total
from config import Config
import json
from typing import Tuple

class ResolverAgent:
    """
    Decision resolver using Bayesian confidence scoring.
    Combines rule-based decisions with probabilistic confidence assessment.
    """
    
    def __init__(self):
        self.config = Config()
    
    def process(self, state: InvoiceState) -> InvoiceState:
        if not state.validation_results:
            state.audit_trail.append("ResolverAgent: No validation results found. Setting to HOLD.")
            state.overall_decision = OverallDecision.HOLD_FOR_VERIFICATION
            state.confidence = 0.0
            return state

        state.audit_trail.append("ResolverAgent: Analyzing validation results and making final decision.")
        
        results = state.validation_results
        
        # Calculate compliance score (rules-based)
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
        
        # Calculate Bayesian confidence
        confidence = self._calculate_bayesian_confidence(state, results)
        state.confidence = confidence
        
        state.audit_trail.append(f"ResolverAgent: Compliance Score = {compliance_score*100:.1f}%, Confidence = {confidence*100:.1f}%")

        # Determine decision based on rules and confidence
        state.overall_decision = self._determine_decision(state, results, compliance_score, confidence)
        
        state.audit_trail.append(f"ResolverAgent: Final Decision = {state.overall_decision}")
        return state
    
    def _calculate_bayesian_confidence(self, state: InvoiceState, results) -> float:
        """
        Calculate confidence using Bayesian approach:
        - Start at 1.0 (100% confident)
        - Reduce for each type of evidence of unreliability:
          * Extraction errors
          * Data inconsistencies (arithmetic failures)
          * Missing critical fields
          * OCR-suspicious patterns
        """
        confidence = 1.0
        
        # Factor 1: Extraction errors reduce confidence significantly
        if state.errors:
            num_errors = len(state.errors)
            error_penalty = min(0.4, 0.1 * num_errors)  # Each error -10%, capped at -40%
            confidence -= error_penalty
            state.audit_trail.append(f"ResolverAgent: Confidence penalty for errors: -{error_penalty*100:.0f}%")
        
        # Factor 2: Arithmetic failures indicate data quality issues
        if not results.category_c_arithmetic.checks["C1"].status or not results.category_c_arithmetic.checks["C2"].status:
            confidence *= 0.75  # 25% confidence reduction for arithmetic issues
            state.audit_trail.append("ResolverAgent: Confidence penalty for arithmetic mismatch: -25%")
        
        # Factor 3: GST validation failures
        if not results.category_b_gst.checks["B1"].status:
            confidence *= 0.70  # 30% reduction for GSTIN issues
            state.audit_trail.append("ResolverAgent: Confidence penalty for GSTIN issues: -30%")
        
        # Factor 4: Missing vendor data
        if state.extracted_data and (not state.extracted_data.vendor_gstin or not state.extracted_data.vendor_name):
            confidence *= 0.80  # 20% reduction for missing vendor data
            state.audit_trail.append("ResolverAgent: Confidence penalty for incomplete vendor data: -20%")
        
        # Factor 5: High variance in data (suspicious patterns)
        if state.extracted_data and self._has_suspicious_patterns(state.extracted_data):
            confidence *= 0.85  # 15% reduction for suspicious patterns
            state.audit_trail.append("ResolverAgent: Confidence penalty for suspicious data patterns: -15%")
        
        # Factor 6: Success in critical checks increases confidence
        critical_passes = sum([
            1 if results.category_a_authenticity.checks.get("A1", {}).status else 0,
            1 if results.category_a_authenticity.checks.get("A2", {}).status else 0,
            1 if results.category_b_gst.checks.get("B1", {}).status else 0,
            1 if results.category_c_arithmetic.checks.get("C1", {}).status else 0,
            1 if results.category_c_arithmetic.checks.get("C2", {}).status else 0,
        ])
        
        # Boost confidence if critical checks pass (but cap at 1.0)
        if critical_passes == 5:
            confidence = min(1.0, confidence * 1.15)  # 15% boost for all critical checks
            state.audit_trail.append("ResolverAgent: Confidence boost for all critical checks passing: +15%")
        
        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, confidence))
        return confidence
    
    def _has_suspicious_patterns(self, data) -> bool:
        """Detect suspicious patterns that indicate data quality issues"""
        suspicious = False
        
        # Check for round numbers (could indicate estimation)
        if data.total_amount > 0:
            if data.total_amount % 10000 == 0 and data.total_amount > 100000:
                suspicious = True  # Very round amounts often suspicious
        
        # Check for missing line item details
        for item in data.line_items:
            if not item.hsn_sac or item.rate == 0 or item.amount == 0:
                suspicious = True
                break
        
        # Check for extreme tax rates
        for item in data.line_items:
            if item.tax_rate and (item.tax_rate > 0.50 or item.tax_rate < 0):
                suspicious = True
                break
        
        return suspicious
    
    def _determine_decision(self, state: InvoiceState, results, compliance_score: float, confidence: float) -> OverallDecision:
        """
        Determine final decision using decision tree:
        1. Critical failures → REJECTED
        2. High-value → ESCALATE_TO_HUMAN
        3. High confidence + high compliance → APPROVED
        4. Low confidence or moderate compliance → HOLD or ESCALATE
        """
        
        # Step 1: Check for critical failures
        critical_failures = self._check_critical_failures(results)
        if critical_failures:
            state.audit_trail.append(f"ResolverAgent: Critical failures detected: {critical_failures}")
            return OverallDecision.REJECTED
        
        # Step 2: Check high-value threshold
        if state.extracted_data and state.extracted_data.total_amount > self.config.HIGH_VALUE_THRESHOLD:
            state.audit_trail.append(
                f"ResolverAgent: High-value invoice (₹{state.extracted_data.total_amount:,.0f} > ₹{self.config.HIGH_VALUE_THRESHOLD:,.0f}). Escalating."
            )
            state.requires_human_review = True
            return OverallDecision.ESCALATE_TO_HUMAN
        
        # Step 3: Decision matrix based on compliance and confidence
        thresholds = {
            'approved': self.config.CONFIDENCE_THRESHOLD_APPROVED,
            'hold': self.config.CONFIDENCE_THRESHOLD_HOLD,
            'escalate': self.config.CONFIDENCE_THRESHOLD_ESCALATE,
        }
        
        # High confidence + high compliance → APPROVED
        if confidence >= thresholds['approved'] and compliance_score >= 0.95:
            state.audit_trail.append(f"ResolverAgent: High confidence ({confidence*100:.0f}%) + high compliance ({compliance_score*100:.0f}%) → APPROVED")
            return OverallDecision.APPROVED
        
        # Medium-high confidence + good compliance → HOLD or APPROVE
        elif confidence >= thresholds['hold'] and compliance_score >= 0.85:
            if compliance_score >= 0.95:
                return OverallDecision.APPROVED
            else:
                state.audit_trail.append(f"ResolverAgent: Medium confidence ({confidence*100:.0f}%) + moderate compliance ({compliance_score*100:.0f}%) → HOLD")
                return OverallDecision.HOLD_FOR_VERIFICATION
        
        # Low confidence or data issues → ESCALATE
        elif confidence < thresholds['escalate'] or compliance_score < 0.70:
            state.audit_trail.append(f"ResolverAgent: Low confidence ({confidence*100:.0f}%) or low compliance ({compliance_score*100:.0f}%) → ESCALATE")
            state.requires_human_review = True
            return OverallDecision.ESCALATE_TO_HUMAN
        
        # Default: HOLD for verification
        else:
            state.audit_trail.append(f"ResolverAgent: Moderate metrics, holding for verification")
            return OverallDecision.HOLD_FOR_VERIFICATION
    
    def _check_critical_failures(self, results) -> list:
        """Identify critical failures that warrant automatic rejection"""
        failures = []
        
        # A2: Duplicate invoice
        if not results.category_a_authenticity.checks.get("A2", {}).status:
            failures.append("Duplicate invoice detected")
        
        # B1: Invalid/Inactive GSTIN
        if not results.category_b_gst.checks.get("B1", {}).status:
            failures.append("Invalid or inactive GSTIN")
        
        # B11: Composition dealer charging GST
        if not results.category_b_gst.checks.get("B11", {}).status:
            failures.append("Composition dealer charging GST (violation)")
        
        # C2: Subtotal mismatch (critical arithmetic error)
        if not results.category_c_arithmetic.checks.get("C2", {}).status:
            failures.append("Subtotal mismatch (arithmetic error)")
        
        return failures

        state.audit_trail.append(f"ResolverAgent: Final decision is {state.overall_decision} with confidence {confidence*100:.1f}%.")
        return state
