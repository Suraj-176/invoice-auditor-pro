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
                        # BATCH MODE: Process ALL invoices
                        if len(data) > 0:
                            # Store batch metadata in state
                            state.batch_size = len(data)
                            state.batch_index = 0
                            state.audit_trail.append(f"ExtractorAgent: Found {len(data)} invoices in batch.")
                            
                            # Process first invoice (subsequent ones handled by caller in loop)
                            invoice_data_raw = data[0]
                            state.extracted_data = self._map_to_schema(invoice_data_raw)
                            state.batch_index = 1
                            state.audit_trail.append(f"ExtractorAgent: Successfully extracted invoice {state.extracted_data.invoice_id} (1 of {len(data)})")
                            # Store remaining invoices for batch processing
                            if len(data) > 1:
                                state.pending_invoices = data[1:]
                                state.audit_trail.append(f"ExtractorAgent: Queued {len(data)-1} additional invoices for processing.")
                        else:
                            raise ValueError("Empty invoice list")
                    else:
                        invoice_data_raw = data
                        state.extracted_data = self._map_to_schema(invoice_data_raw)
                        state.batch_size = 1
                        state.batch_index = 1
                        state.audit_trail.append(f"ExtractorAgent: Successfully extracted single invoice {state.extracted_data.invoice_id}")
            except Exception as e:
                state.errors.append(f"Extraction Error: {str(e)}")
                state.audit_trail.append(f"ExtractorAgent: ERROR - {str(e)}")
        elif file_ext in ['.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
            state.audit_trail.append(f"ExtractorAgent: Non-JSON file detected ({file_ext}). Attempting LLM-based extraction...")
            try:
                extracted = self._extract_with_llm(file_path)
                state.extracted_data = extracted
                state.batch_size = 1
                state.batch_index = 1
                state.audit_trail.append(f"ExtractorAgent: Successfully extracted invoice {extracted.invoice_id} from {file_ext}")
            except Exception as e:
                state.errors.append(f"LLM Extraction Error: {str(e)}")
                state.audit_trail.append(f"ExtractorAgent: ERROR - LLM extraction failed: {str(e)}")
        else:
            state.errors.append(f"Unsupported file format: {file_ext}. Supported: JSON, PDF, PNG, JPG, JPEG, BMP, TIFF")
            state.audit_trail.append(f"ExtractorAgent: ERROR - Unsupported format {file_ext}")

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
    
    def _extract_with_llm(self, file_path: str) -> InvoiceData:
        """
        Extract invoice data from PDF/image using LLM with structured output.
        Falls back to error if no LLM is configured.
        """
        if not self.llm:
            raise ValueError(
                "LLM not configured. Please provide API key and provider in the app settings. "
                "Supported providers: OpenAI, Azure OpenAI, Google Gemini, Anthropic Claude"
            )
        
        import base64
        from pathlib import Path
        
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_ext = file_path_obj.suffix.lower()
        
        # Read file and encode as base64 for multimodal LLM
        with open(file_path, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode('utf-8')
        
        # Determine media type
        media_type_map = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff'
        }
        media_type = media_type_map.get(file_ext, 'application/octet-stream')
        
        # Create extraction prompt
        extraction_prompt = """
        Extract invoice information from the provided document. Return the data in JSON format matching this structure:
        {
            "invoice_id": "Invoice number or ID",
            "invoice_date": "Date in YYYY-MM-DD format",
            "vendor": {
                "name": "Vendor/Seller name",
                "gstin": "15-character GSTIN",
                "pan": "PAN if available"
            },
            "buyer": {
                "name": "Buyer name",
                "gstin": "Buyer GSTIN if available"
            },
            "line_items": [
                {
                    "description": "Item description",
                    "quantity": numeric_quantity,
                    "rate": numeric_rate,
                    "amount": numeric_amount,
                    "hsn_sac": "HSN or SAC code if present",
                    "cgst_amount": 0,
                    "sgst_amount": 0,
                    "igst_amount": 0
                }
            ],
            "subtotal": numeric_subtotal,
            "total_tax": numeric_total_tax,
            "total_amount": numeric_total_amount,
            "currency": "INR",
            "irn": "e-Invoice IRN if present"
        }
        
        Important:
        - All numeric values must be numbers, not strings
        - Be precise with amounts (e.g., 1000.50, not "1000.50")
        - If a field is not present, use null or default value (0 for numbers, "" for strings)
        - Extract HSN codes and tax amounts if visible
        - Dates must be YYYY-MM-DD format
        
        Return ONLY valid JSON, no explanations.
        """
        
        try:
            # Use structured output with Pydantic model
            if hasattr(self.llm, 'with_structured_output'):
                # LangChain v0.1+ with structured output
                structured_llm = self.llm.with_structured_output(InvoiceData)
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": extraction_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{file_content}"
                            }
                        }
                    ]
                )
                result = structured_llm.invoke([message])
                return result
            else:
                # Fallback: Regular LLM call and parse JSON
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": extraction_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{file_content}"
                            }
                        }
                    ]
                )
                response = self.llm.invoke([message])
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # Parse JSON from response
                import json
                try:
                    # Try to extract JSON from response
                    if '```json' in response_text:
                        json_str = response_text.split('```json')[1].split('```')[0].strip()
                    elif '```' in response_text:
                        json_str = response_text.split('```')[1].split('```')[0].strip()
                    else:
                        json_str = response_text
                    
                    extracted_dict = json.loads(json_str)
                    return self._map_to_schema(extracted_dict)
                except json.JSONDecodeError as je:
                    raise ValueError(f"LLM returned invalid JSON: {str(je)}. Response: {response_text[:200]}")
        
        except Exception as e:
            raise ValueError(f"LLM extraction failed: {str(e)}")
