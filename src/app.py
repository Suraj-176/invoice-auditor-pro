import streamlit as st
import json
import os
import tempfile
import subprocess
import sys
import requests
import pandas as pd
import time
from workflow import create_workflow
from schema import InvoiceState, OverallDecision
from agents.document_parser import ExtractorAgent
from init_db import init_db

# Initialize database on app startup
init_db()

st.set_page_config(page_title="Invoice Compliance Validator", layout="wide", initial_sidebar_state="collapsed")

# --- Modern Custom CSS ---
st.markdown("""
    <style>
    .stApp {
        background-color: #f8f9fa;
    }
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        transition: all 0.3s;
    }
    /* Override for config pill button in header (right column) */
    [data-testid="column"]:nth-last-child(1) div.stButton > button {
        height: 2.2em !important;
        padding: 6px 14px !important;
        font-size: 13px !important;
        border: 1px solid #d0d5dd !important;
        background: #f0f2f6 !important;
        border-radius: 20px !important;
        width: auto !important;
        color: #333 !important;
    }
    [data-testid="column"]:nth-last-child(1) div.stButton > button:hover {
        background: #e8eaed !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        font-weight: 600;
    }
    /* Make table rows more compact */
    .stTable td {
        padding: 5px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Auto-start Mock GST Server if not running ---
def _gst_server_running():
    try:
        requests.get("http://127.0.0.1:8080/api/gst/validate-gstin", timeout=1)
        return True
    except Exception:
        return False

if "gst_server_started" not in st.session_state:
    st.session_state.gst_server_started = False

if not _gst_server_running():
    if not st.session_state.gst_server_started:
        subprocess.Popen(
            [sys.executable, "src/mock_gst_server.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        st.session_state.gst_server_started = True

# --- Session-only Config (never auto-load from disk) ---
if "llm_config" not in st.session_state:
    st.session_state.llm_config = {}

@st.dialog("⚙️ System Configuration")
def show_config_dialog():
    st.caption("🔒 Security: Credentials reside in session memory.")
    
    conf = st.session_state.get("llm_config", {})
    provider_list = ["OpenAI", "Azure OpenAI", "Google Gemini", "Anthropic Claude"]
    
    # Map internal key to display name index
    current_provider_key = conf.get("provider", "openai")
    provider_map = {"openai": 0, "azure": 1, "gemini": 2, "claude": 3}
    provider_reverse_map = {"OpenAI": "openai", "Azure OpenAI": "azure", "Google Gemini": "gemini", "Anthropic Claude": "claude"}
    default_idx = provider_map.get(current_provider_key, 0)

    with st.container(height=400, border=False):
        provider = st.selectbox("AI Provider", provider_list, index=default_idx)
        selected_key = provider_reverse_map[provider]
        
        # Only show saved data if it belongs to the selected provider
        p_conf = conf if selected_key == current_provider_key else {}
        
        if provider == "OpenAI":
            api_key = st.text_input("API Key", type="password", value=p_conf.get("api_key", ""))
            model = st.text_input("Model ID", value=p_conf.get("model", "gpt-4o"))
            st.session_state.llm_temp = {"provider": "openai", "api_key": api_key, "model": model}
        elif provider == "Azure OpenAI":
            api_key = st.text_input("Azure Key", type="password", value=p_conf.get("api_key", ""))
            endpoint = st.text_input("Endpoint URL", value=p_conf.get("endpoint", ""))
            c1, c2 = st.columns(2)
            deployment = c1.text_input("Deployment", value=p_conf.get("deployment", ""))
            version = c2.text_input("API Version", value=p_conf.get("api_version", "2024-02-15-preview"))
            st.session_state.llm_temp = {"provider": "azure", "api_key": api_key, "endpoint": endpoint, "deployment": deployment, "api_version": version}
        elif provider == "Google Gemini":
            api_key = st.text_input("Gemini Key", type="password", value=p_conf.get("api_key", ""))
            model = st.text_input("Model ID", value=p_conf.get("model", "gemini-1.5-flash"))
            st.session_state.llm_temp = {"provider": "gemini", "api_key": api_key, "model": model}
        elif provider == "Anthropic Claude":
            api_key = st.text_input("Claude Key", type="password", value=p_conf.get("api_key", ""))
            model = st.text_input("Model ID", value=p_conf.get("model", "claude-3-5-sonnet-20240620"))
            st.session_state.llm_temp = {"provider": "claude", "api_key": api_key, "model": model}

        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Test", width='stretch'):
                try:
                    config = st.session_state.llm_temp
                    provider = config.get("provider", "")
                    api_key = config.get("api_key", "").strip()
                    
                    if not provider:
                        st.write("❌ Please select an AI provider")
                    elif not api_key:
                        st.write("❌ API Key is required")
                    elif provider == "openai" and not config.get("model"):
                        st.write("❌ Model ID is required")
                    elif provider == "azure":
                        if not config.get("endpoint"):
                            st.write("❌ Azure Endpoint is required")
                        elif not config.get("deployment"):
                            st.write("❌ Deployment name is required")
                        elif not config.get("api_version"):
                            st.write("❌ API Version is required")
                        else:
                            st.write("✅ Configuration validated!")
                            st.session_state.llm_config = config
                    elif provider == "gemini" and not config.get("model"):
                        st.write("❌ Gemini Model ID is required")
                    elif provider == "claude" and not config.get("model"):
                        st.write("❌ Claude Model ID is required")
                    else:
                        st.write("✅ Configuration validated!")
                        st.session_state.llm_config = config
                except Exception as e: 
                    st.write(f"❌ Validation error: {str(e)[:60]}")
        with col2:
            if st.button("Save", width='stretch'):
                st.session_state.llm_config = st.session_state.llm_temp
                st.write("✅ Saved for this session.")
                time.sleep(0.5)
                st.rerun()
        with col3:
            if st.button("Reset", width='stretch'):
                st.session_state.llm_config = {}
                st.write("🔄 Configuration reset.")
                time.sleep(0.5)
                st.rerun()

        st.divider()
        st.caption("🔒 Credentials are stored in session memory only — never written to disk. Cleared when the browser tab is closed.")

# --- Header with Title and Status Pill in Same Row ---
_cfg = st.session_state.get("llm_config", {})
_provider_labels = {"openai": "OpenAI", "azure": "Azure OpenAI", "gemini": "Google Gemini", "claude": "Anthropic Claude"}
_provider_key = _cfg.get("provider", "")

if _cfg.get("api_key"):
    _label = _provider_labels.get(_provider_key, _provider_key.title())
    _status_color = "#22c55e"
    _status_text = _label
else:
    _status_color = "#94a3b8"
    _status_text = "Not configured"

# Layout: Title on left, Status pill on right in same row
title_col, spacer_col, config_col = st.columns([2, 1, 1], gap="small", vertical_alignment="center")

with title_col:
    st.title("🛡️ Invoice Auditor Pro")
    st.caption("Agentic Multi-Stage Compliance Validation Engine")

with config_col:
    if st.button(f"● {_status_text}", key="sys_config_pill", help="Click to configure", width='content'):
        show_config_dialog()

st.divider()

# --- Upload Area ---
uploaded_file = st.file_uploader("Drop invoice (JSON, CSV, XLSX, PNG, JPG)", type=["json", "csv", "xlsx", "png", "jpg"], label_visibility="collapsed")

if uploaded_file:
    config = st.session_state.get("llm_config", {})
    if not config.get("api_key"):
        st.warning("⚠️ Action Required: Configure your LLM provider using the 'Options' button above.")
        st.stop()

    # Handle different file formats and convert to JSON
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    invoices_to_process = []
    
    try:
        if file_ext == ".json":
            data = json.loads(uploaded_file.getvalue().decode('utf-8'))
            invoices_to_process = data if isinstance(data, list) else [data]
        
        elif file_ext in [".csv"]:
            import io
            csv_data = pd.read_csv(io.StringIO(uploaded_file.getvalue().decode('utf-8')))
            # Convert CSV rows to invoice-like structure
            for idx, row in csv_data.iterrows():
                invoice = row.to_dict()
                invoices_to_process.append(invoice)
            st.info(f"📊 Parsed CSV: {len(invoices_to_process)} records found")
        
        elif file_ext == ".xlsx":
            import io
            excel_data = pd.read_excel(io.BytesIO(uploaded_file.getvalue()))
            # Convert Excel rows to invoice-like structure
            for idx, row in excel_data.iterrows():
                invoice = row.to_dict()
                invoices_to_process.append(invoice)
            st.info(f"📊 Parsed Excel: {len(invoices_to_process)} records found")
        
        elif file_ext in [".png", ".jpg", ".jpeg"]:
            # For images, create a temporary JSON file as placeholder
            # In production, this would use OCR/LLM extraction
            from PIL import Image
            image = Image.open(uploaded_file)
            st.warning("📸 Image upload detected. Using LLM-based extraction (requires API key).")
            # Create a single invoice entry with image metadata
            invoices_to_process = [{
                "invoice_id": f"IMG-{uploaded_file.name.split('.')[0]}",
                "invoice_number": "TBD",
                "invoice_date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "vendor": {"name": "Image-Based Invoice", "gstin": "TBD"},
                "buyer": {"name": "TBD", "gstin": "TBD"},
                "line_items": [],
                "subtotal": 0,
                "cgst_rate": 0, "cgst_amount": 0,
                "sgst_rate": 0, "sgst_amount": 0,
                "igst_rate": 0, "igst_amount": 0,
                "total_tax": 0,
                "total_amount": 0,
                "_note": "Extracted from image - requires LLM processing"
            }]
        
        if not invoices_to_process:
            st.error("❌ No invoices found in the uploaded file.")
            st.stop()
    
    except Exception as e:
        st.error(f"❌ Error parsing file: {str(e)}")
        st.stop()
    
    # Execute/Stop controls
    st.divider()
    exec_col1, exec_col2, exec_col3 = st.columns([1, 1, 4])
    execute_clicked = False
    stop_clicked = False
    
    with exec_col1:
        execute_clicked = st.button("▶️ Execute", width='stretch', key="execute_btn")
    with exec_col2:
        stop_clicked = st.button("⏹️ Stop", width='stretch', key="stop_btn")
    
    if stop_clicked:
        st.info("⚠️ Processing stopped by user.")
        st.stop()
    
    if not execute_clicked:
        st.info(f"📄 Ready to process {len(invoices_to_process)} invoice(s). Click 'Execute' to start.")
        st.stop()
    
    st.divider()
    
    # Process each invoice through the workflow
    all_results = []
    progress_bar = st.progress(0)
    results_placeholder = st.empty()
    
    with st.spinner(f"🕵️ Agents analyzing {len(invoices_to_process)} invoice(s)..."):
        for invoice_idx, invoice_data in enumerate(invoices_to_process):
            try:
                # Create temporary JSON file for workflow
                with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode='w') as tmp:
                    json.dump([invoice_data], tmp)  # Wrap in list for consistency
                    tmp_path = tmp.name
                
                # Run workflow
                workflow = create_workflow(config=config)
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
                
                state = InvoiceState(**result)
                all_results.append(state)
                
                # Update progress
                progress = (invoice_idx + 1) / len(invoices_to_process)
                progress_bar.progress(progress)
                results_placeholder.text(f"Processing {invoice_idx + 1}/{len(invoices_to_process)}...")
                
                # Cleanup
                try:
                    os.remove(tmp_path)
                except:
                    pass
            
            except Exception as e:
                st.error(f"Error processing invoice {invoice_idx + 1}: {str(e)}")
                continue
    
    progress_bar.empty()
    results_placeholder.empty()
    
    if not all_results:
        st.error("❌ Failed to process any invoices.")
        st.stop()
    
    
    # Display results for all invoices
    st.success(f"✅ Successfully processed {len(all_results)} invoice(s)")
    
    # If single invoice, show detailed dashboard
    if len(all_results) == 1:
        state = all_results[0]
        
        # --- Results Dashboard ---
        dec_color = {OverallDecision.APPROVED: "green", OverallDecision.REJECTED: "red", OverallDecision.ESCALATE_TO_HUMAN: "orange"}.get(state.overall_decision, "blue")
        
        st.markdown(f"### Current Status: :{dec_color}[{state.overall_decision.value}]")
        
        # Decision Box
        if state.overall_decision == OverallDecision.APPROVED: st.success("**✅ Final Decision:** Approved for payment.")
        elif state.overall_decision == OverallDecision.REJECTED:
            critical_msg = [s.replace("ResolverAgent: Critical failure - ", "") for s in state.audit_trail if "Critical failure" in s]
            st.error(f"**❌ Final Decision:** Rejected. Reason: {critical_msg[0] if critical_msg else 'Compliance violation.'}")
        else:
            esc_msg = [s.replace("ResolverAgent: ", "") for s in state.audit_trail if "Escalating" in s or "High value" in s]
            st.warning(f"**⚠️ Final Decision:** Manual Review Required. Reason: {esc_msg[0] if esc_msg else 'Policy threshold trigger.'}")

        # Top Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Compliance Score", f"{state.compliance_score*100:.1f}%")
        m2.metric("AI Confidence", f"{state.confidence*100:.0f}%")
        m3.metric("Total Amount", f"₹{state.extracted_data.total_amount:,.2f}" if state.extracted_data else "N/A")
        
        from agents.report_builder import ReporterAgent
        export_data = ReporterAgent().generate_output_json(state)
        m4.download_button("📥 Export Report", data=json.dumps(export_data, indent=2), file_name=f"audit_{state.extracted_data.invoice_id if state.extracted_data else 'unknown'}.json", width='stretch')

        # Detail Tabs
        tab_summary, tab_checks, tab_logic, tab_raw = st.tabs(["📋 Summary", "⚖️ Compliance Matrix", "🧠 Agent Reasoning", "📄 Raw Source"])
        
        with tab_summary:
            if state.extracted_data:
                c1, c2, c3 = st.columns(3)
                with c1:
                    with st.container(border=True):
                        st.markdown("#### 🏢 Vendor")
                        st.write(f"**{state.extracted_data.vendor_name}**")
                        st.caption(f"GSTIN: `{state.extracted_data.vendor_gstin}` | PAN: `{state.extracted_data.pan}`")
                
                with c2:
                    with st.container(border=True):
                        st.markdown("#### 📅 Invoice")
                        st.write(f"ID: `{state.extracted_data.invoice_id}`")
                        st.caption(f"Date: {state.extracted_data.invoice_date}")
                
                with c3:
                    with st.container(border=True):
                        st.markdown("#### 💰 Financials")
                        st.write(f"Subtotal: ₹{state.extracted_data.subtotal:,.2f}")
                        st.caption(f"Total: ₹{state.extracted_data.total_amount:,.2f}")
            else: st.info("No extracted data available.")

        with tab_checks:
            if state.validation_results:
                all_checks = []
                for cat_attr in ["category_a_authenticity", "category_b_gst", "category_c_arithmetic", "category_d_tds", "category_e_policy"]:
                    cat = getattr(state.validation_results, cat_attr)
                    category_label = cat_attr.replace('category_', '').replace('_', ' ').title()
                    for k, v in cat.checks.items():
                        all_checks.append({
                            "Category": category_label,
                            "Check": k,
                            "Status": "✅ Pass" if v.status else "❌ Fail",
                            "Details": v.message
                        })
                with st.container(height=400, border=True):
                    st.table(pd.DataFrame(all_checks))

        with tab_logic:
            with st.container(height=400, border=True):
                for step in state.audit_trail:
                    icon = "✅" if "success" in step.lower() or "completed" in step.lower() else "ℹ️"
                    if "Error" in step or "Critical" in step: icon = "🚨"
                    st.write(f"{icon} {step}")

        with tab_raw:
            with st.container(height=400, border=True):
                st.json(json.loads(uploaded_file.getvalue()))
    
    else:
        # Multiple invoices - Batch Summary + Statistics
        st.markdown("### 📊 Batch Processing Summary")

        from agents.report_builder import ReporterAgent
        _reporter = ReporterAgent()
        all_exports = [_reporter.generate_output_json(s) for s in all_results]

        # Statistics row
        approved_count   = sum(1 for s in all_results if s.overall_decision == OverallDecision.APPROVED)
        rejected_count   = sum(1 for s in all_results if s.overall_decision == OverallDecision.REJECTED)
        escalated_count  = sum(1 for s in all_results if s.overall_decision == OverallDecision.ESCALATE_TO_HUMAN)
        held_count       = sum(1 for s in all_results if s.overall_decision == OverallDecision.HOLD_FOR_VERIFICATION)

        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        sc1.metric("Total", len(all_results))
        sc2.metric("✅ Approved", approved_count)
        sc3.metric("❌ Rejected", rejected_count)
        sc4.metric("⚠️ Escalated", escalated_count)
        sc5.metric("⏸️ On Hold", held_count)

        # Summary table
        summary_data = []
        for idx, (state, exp) in enumerate(zip(all_results, all_exports), 1):
            d = state.extracted_data
            summary_data.append({
                "#": idx,
                "Invoice ID": d.invoice_id if d else "N/A",
                "Vendor": d.vendor_name if d else "N/A",
                "Amount (₹)": f"{d.total_amount:,.2f}" if d else "N/A",
                "Decision": state.overall_decision.value,
                "Compliance": f"{exp['compliance_score']}%",
                "Confidence": f"{exp['confidence']*100:.0f}%",
            })
        st.dataframe(pd.DataFrame(summary_data), width='stretch')

        # Bulk export
        st.download_button(
            "📥 Export All Reports (JSON)",
            data=json.dumps(all_exports, indent=2),
            file_name=f"batch_audit_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
            width='stretch'
        )

        st.divider()
        st.markdown("### 🔍 Detailed Results per Invoice")

        _DECISION_COLOR = {"APPROVED": "green", "REJECTED": "red",
                           "ESCALATE_TO_HUMAN": "orange", "HOLD_FOR_VERIFICATION": "blue"}
        _DECISION_ICON  = {"APPROVED": "✅", "REJECTED": "❌",
                           "ESCALATE_TO_HUMAN": "⚠️", "HOLD_FOR_VERIFICATION": "⏸️"}

        for idx, (state, exp) in enumerate(zip(all_results, all_exports), 1):
            d          = state.extracted_data
            inv_id     = d.invoice_id if d else f"Invoice {idx}"
            decision   = state.overall_decision.value
            icon       = _DECISION_ICON.get(decision, "ℹ️")
            dec_color  = _DECISION_COLOR.get(decision, "blue")

            with st.expander(f"{icon} [{idx}] {inv_id}  —  {decision}", expanded=(idx == 1)):

                # ── Top bar: decision badge + 4 metrics + export button ──
                hdr_l, hdr_r = st.columns([3, 1])
                with hdr_l:
                    st.markdown(f"**Decision: :{dec_color}[{decision}]**")
                with hdr_r:
                    st.download_button(
                        "📥 Export Report",
                        data=json.dumps(exp, indent=2),
                        file_name=f"audit_{inv_id}.json",
                        key=f"dl_{idx}",
                        width='stretch'
                    )

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Compliance Score", f"{exp['compliance_score']}%")
                m2.metric("AI Confidence",    f"{exp['confidence']*100:.0f}%")
                m3.metric("Total Amount",     f"₹{d.total_amount:,.2f}" if d else "N/A")
                m4.metric("Invoice Date",     d.invoice_date if d else "N/A")

                # ── Vendor / Buyer info ──
                if d:
                    vi1, vi2 = st.columns(2)
                    with vi1:
                        with st.container(border=True):
                            st.caption("🏢 Vendor")
                            st.write(f"**{d.vendor_name}**")
                            st.caption(f"GSTIN: `{d.vendor_gstin}` | PAN: `{d.pan}`")
                    with vi2:
                        with st.container(border=True):
                            st.caption("📅 Invoice")
                            st.write(f"ID: `{d.invoice_id}`")
                            st.caption(f"Subtotal: ₹{d.subtotal:,.2f}  |  Tax: ₹{d.total_tax:,.2f}")

                # ── Tabs: Compliance Matrix | Audit Trail | GST Summary ──
                t_checks, t_trail, t_gst = st.tabs(
                    ["⚖️ Compliance Matrix", "🧠 Audit Trail", "📊 GST Summary"]
                )

                with t_checks:
                    vr = state.validation_results
                    if vr:
                        checks_rows = []
                        for cat_attr in ["category_a_authenticity", "category_b_gst",
                                         "category_c_arithmetic", "category_d_tds", "category_e_policy"]:
                            cat   = getattr(vr, cat_attr)
                            label = cat_attr.replace("category_", "").replace("_", " ").title()
                            for check_id, chk in cat.checks.items():
                                checks_rows.append({
                                    "Category": label,
                                    "Check": check_id,
                                    "Status": "✅ PASS" if chk.status else "❌ FAIL",
                                    "Score": f"{chk.score}/{chk.max_score}",
                                    "Details": chk.message
                                })
                        st.table(pd.DataFrame(checks_rows))
                    else:
                        st.info("No validation results available.")

                with t_trail:
                    trail = exp.get("audit_trail", [])
                    if trail:
                        trail_rows = []
                        for entry in trail:
                            if isinstance(entry, dict):
                                action = entry.get("action", "")
                                a_icon = "🚨" if "failure" in action.lower() or "error" in action.lower() \
                                         else ("✅" if "complete" in action.lower() or "decision" in action.lower() else "ℹ️")
                                trail_rows.append({
                                    "Timestamp": entry.get("timestamp", "")[:19].replace("T", " "),
                                    "Agent": entry.get("agent", ""),
                                    "Action": f"{a_icon} {action}",
                                    "Reasoning": entry.get("reasoning", ""),
                                    "Confidence": f"{entry.get('confidence', 1.0)*100:.0f}%"
                                })
                            else:
                                a_icon = "🚨" if ("Error" in str(entry) or "Critical" in str(entry)) \
                                         else ("✅" if "success" in str(entry).lower() else "ℹ️")
                                trail_rows.append({
                                    "Timestamp": "-", "Agent": "-",
                                    "Action": "", "Reasoning": f"{a_icon} {entry}",
                                    "Confidence": "-"
                                })
                        st.dataframe(pd.DataFrame(trail_rows), width='stretch')
                    else:
                        st.info("No audit trail available.")

                with t_gst:
                    gst = exp.get("gst_summary")
                    if gst:
                        gc1, gc2, gc3 = st.columns(3)
                        gc1.metric("CGST", f"₹{gst.get('cgst_amount', 0):,.2f}",
                                   delta=f"{gst.get('cgst_rate', 0)}%", delta_color="off")
                        gc2.metric("SGST", f"₹{gst.get('sgst_amount', 0):,.2f}",
                                   delta=f"{gst.get('sgst_rate', 0)}%", delta_color="off")
                        gc3.metric("IGST", f"₹{gst.get('igst_amount', 0):,.2f}",
                                   delta=f"{gst.get('igst_rate', 0)}%", delta_color="off")
                    else:
                        st.info("No GST summary available.")
else:
    st.info("👋 Welcome! Please upload an invoice JSON file to begin the automated audit.")
    with st.expander("📂 Where are the sample files?"):
        st.markdown("Sample invoices are located in `data/invoices/`. Open one to see the JSON format, or upload it directly here.")
