import json
import os
from typing import Dict, Any, Optional
from schema import InvoiceState, InvoiceData, LineItem
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

class ExtractorAgent:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.llm = self._init_llm()

    def _init_llm(self):
        provider = self.config.get("provider", "openai")
        api_key = self.config.get("api_key")
        
        if not api_key:
            return None

        if provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=self.config.get("model", "gpt-4o"), api_key=api_key, temperature=0)
            
        elif provider == "azure":
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                azure_deployment=self.config.get("deployment"),
                openai_api_version=self.config.get("api_version"),
                azure_endpoint=self.config.get("endpoint"),
                api_key=api_key,
                temperature=0
            )
            
        elif provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=self.config.get("model", "gemini-1.5-flash"),
                google_api_key=api_key,
                temperature=0
            )
        elif provider == "claude":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=self.config.get("model", "claude-3-5-sonnet-20240620"),
                anthropic_api_key=api_key,
                temperature=0
            )
        return None

    def process(self, state: InvoiceState) -> InvoiceState:
        state.audit_trail.append("ExtractorAgent: Starting extraction process.")
        
        file_path = state.raw_file_path
        file_ext = os.path.splitext(file_path)[1].lower()

        # Handle multi-invoice JSON files
        if file_ext in ['.json']:
             state.audit_trail.append(f"ExtractorAgent: Detected JSON input. Parsing directly.")
             try:
                 with open(file_path, 'r') as f:
                     data = json.load(f)
                     # Handle if it's a list or single object
                     if isinstance(data, list):
                         # BATCH MODE: Process first invoice, store metadata for batch reporting
                         if len(data) > 0:
                             invoice_data_raw = data[0]
                             state.audit_trail.append(f"ExtractorAgent: Found {len(data)} invoices. Processing invoice 1 of {len(data)}.")
                         else:
                             raise ValueError("Empty invoice list")
                     else:
                         invoice_data_raw = data
                     
                     state.extracted_data = self._map_to_schema(invoice_data_raw)
                     state.audit_trail.append(f"ExtractorAgent: Successfully extracted invoice {state.extracted_data.invoice_id}")
             except Exception as e:
                 state.errors.append(f"Extraction Error: {str(e)}")
        else:
            state.audit_trail.append(f"ExtractorAgent: Non-JSON file detected. Attempting LLM extraction (Simulated).")
            # In a real implementation with keys:
            # result = self.llm.with_structured_output(InvoiceData).invoke(...)
            # state.extracted_data = result
            state.errors.append("LLM Extraction not fully implemented without API keys. Please use JSON test files.")

        return state

    def _map_to_schema(self, raw: Dict[str, Any]) -> InvoiceData:
        line_items = []
        for item in raw.get('line_items', []):
            line_items.append(LineItem(
                description=item.get('description', ''),
                quantity=float(item.get('quantity', 0)),
                rate=float(item.get('rate', 0)),
                amount=float(item.get('amount', 0)),
                hsn_sac=item.get('hsn_sac'),
                tax_rate=item.get('tax_rate', 0.0),
                cgst=item.get('cgst_amount', 0.0),
                sgst=item.get('sgst_amount', 0.0),
                igst=item.get('igst_amount', 0.0)
            ))
        
        vendor = raw.get('vendor', {})
        return InvoiceData(
            invoice_id=raw.get('invoice_id', raw.get('invoice_number', 'UNKNOWN')),
            invoice_date=raw.get('invoice_date', ''),
            vendor_name=vendor.get('name', ''),
            vendor_gstin=vendor.get('gstin'),
            buyer_gstin=raw.get('buyer', {}).get('gstin'),
            line_items=line_items,
            subtotal=float(raw.get('subtotal', 0)),
            total_tax=float(raw.get('total_tax', 0)),
            total_amount=float(raw.get('total_amount', 0)),
            currency=raw.get('currency', 'INR'),
            pan=vendor.get('pan'),
            irn=raw.get('irn')
        )
