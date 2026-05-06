import streamlit as st
import json
import os
import tempfile
import pandas as pd
from src.workflow import create_workflow
from src.schema import InvoiceState, OverallDecision
from src.agents.extractor import ExtractorAgent

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

# --- Auto-load Config ---
if "llm_config" not in st.session_state:
    st.session_state.llm_config = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    st.session_state.llm_config[key.replace("LLM_", "").lower()] = val

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
        if col1.button("Test"):
            try:
                agent = ExtractorAgent(config=st.session_state.llm_temp)
                from langchain_core.messages import HumanMessage
                agent.llm.invoke([HumanMessage(content="hi")])
                st.success("Connected!")
                st.session_state.llm_config = st.session_state.llm_temp
            except Exception as e: st.error(f"Error: {str(e)}")
        if col2.button("Save"):
            st.session_state.llm_config = st.session_state.llm_temp
            with open(".env", "w") as f:
                for k, v in st.session_state.llm_config.items(): f.write(f"LLM_{k.upper()}={v}\n")
            st.success("Saved")
        if col3.button("Reset"):
            if os.path.exists(".env"): os.remove(".env")
            st.session_state.llm_config = {}; st.rerun()
            
        st.warning("⚠️ **Reset:** Clicking Reset will permanently delete saved credentials from this project.", icon="🚨")

# --- Header ---
head_l, head_r = st.columns([11, 1])
with head_l:
    st.title("🛡️ Invoice Auditor Pro")
    st.caption("Agentic Multi-Stage Compliance Validation Engine")
with head_r:
    st.write(" ")
    if st.button("⚙️", help="Configure AI Providers & Session Settings"):
        show_config_dialog()

st.divider()

# --- Upload Area ---
uploaded_file = st.file_uploader("Drop invoice JSON here", type=["json"], label_visibility="collapsed")

if uploaded_file:
    config = st.session_state.get("llm_config", {})
    if not config.get("api_key"):
        st.warning("⚠️ Action Required: Configure your LLM provider using the 'Options' button above.")
        st.stop()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    # Running Workflow
    with st.spinner("🕵️ Agents analyzing compliance..."):
        try:
            workflow = create_workflow(config=config)
            result = workflow.invoke(InvoiceState(raw_file_path=tmp_path).model_dump())
            state = InvoiceState(**result)
            
            # --- Results Dashboard ---
            dec_color = {"APPROVED": "green", "REJECTED": "red", "ESCALATE_TO_HUMAN": "orange"}.get(state.overall_decision, "blue")
            
            st.markdown(f"### Current Status: :{dec_color}[{state.overall_decision}]")
            
            # Decision Box
            if state.overall_decision == "APPROVED": st.success("**✅ Final Decision:** Approved for payment.")
            elif state.overall_decision == "REJECTED":
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
            
            from src.agents.reporter import ReporterAgent
            export_data = ReporterAgent().generate_output_json(state)
            m4.download_button("📥 Export Report", data=json.dumps(export_data, indent=2), file_name=f"audit_{state.extracted_data.invoice_id if state.extracted_data else 'unknown'}.json", use_container_width=True)

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

        except Exception as e: st.error(f"Analysis failed: {str(e)}")
    os.unlink(tmp_path)
else:
    st.info("👋 Welcome! Please upload an invoice JSON file to begin the automated audit.")
    with st.expander("📂 Where are the sample files?"):
        st.markdown("Sample invoices are located in `data/invoices/`. Open one to see the JSON format, or upload it directly here.")
