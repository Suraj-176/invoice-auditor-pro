from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class OverallDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
    HOLD_FOR_VERIFICATION = "HOLD_FOR_VERIFICATION"

class LineItem(BaseModel):
    description: str
    quantity: float
    rate: float
    amount: float
    hsn_sac: Optional[str] = None
    tax_rate: Optional[float] = 0.0
    cgst: Optional[float] = 0.0
    sgst: Optional[float] = 0.0
    igst: Optional[float] = 0.0

class InvoiceData(BaseModel):
    invoice_id: str
    invoice_date: str
    vendor_name: str
    vendor_gstin: Optional[str] = None
    buyer_gstin: Optional[str] = None
    line_items: List[LineItem]
    subtotal: float
    total_tax: float
    total_amount: float
    currency: str = "INR"
    pan: Optional[str] = None
    irn: Optional[str] = None

class ValidationCheck(BaseModel):
    id: str
    status: bool # True for Pass, False for Fail
    message: str
    score: int
    max_score: int

class CategoryResult(BaseModel):
    score: int
    max_score: int
    checks: Dict[str, ValidationCheck]

class ValidationResults(BaseModel):
    category_a_authenticity: CategoryResult
    category_b_gst: CategoryResult
    category_c_arithmetic: CategoryResult
    category_d_tds: CategoryResult
    category_e_policy: CategoryResult

class InvoiceState(BaseModel):
    raw_file_path: str
    raw_text: Optional[str] = None
    extracted_data: Optional[InvoiceData] = None
    validation_results: Optional[ValidationResults] = None
    overall_decision: Optional[OverallDecision] = None
    compliance_score: float = 0.0
    confidence: float = 0.0
    requires_human_review: bool = False
    audit_trail: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
