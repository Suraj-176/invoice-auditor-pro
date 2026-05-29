# Installation & Setup Guide

## Prerequisites
- **Python**: 3.10 or higher
- **pip**: Python package manager (included with Python)
- **Operating System**: Windows, macOS, or Linux

## Quick Start (5 minutes)

### 1. Extract the Project
```bash
unzip invoice-auditor-pro.zip
cd invoice-auditor-pro
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
streamlit run src/app.py
```

The app will open automatically at: **http://localhost:8501**

---

## First-Time Usage

### Configure LLM Provider
1. Click the **"● Not configured"** status pill (top-right)
2. Select your AI provider:
   - **OpenAI** (GPT-4)
   - **Azure OpenAI**
   - **Google Gemini**
   - **Anthropic Claude**
3. Enter your API key
4. Click **"Save"**

### Upload & Process Invoices
1. **Supported formats**: JSON, CSV, XLSX, PNG, JPG
2. Click **"Execute"** to start batch processing
3. Results display with compliance scores
4. Download individual or batch reports

---

## Running Tests

### Test Compliance Validation
```bash
$env:PYTHONPATH="src"
pytest tests/test_compliance.py -v
```

### Test Regression Suite
```bash
$env:PYTHONPATH="src"
python tests/regression_runner.py
```

### Test Batch Processing (21 invoices)
```bash
$env:PYTHONPATH="src"
python tests/batch_test.py
```

---

## System Architecture

### 4-Agent Pipeline
1. **Document Parser** - Extracts invoice data (JSON/CSV/XLSX/Image)
2. **Compliance Checker** - Executes 11 validation checks across 5 categories
3. **Decision Resolver** - Determines final decision with confidence scoring
4. **Report Builder** - Generates audit reports & persists results

### Validation Categories (A-E)
- **A**: Authenticity (invoice format, duplicate detection)
- **B**: GST Compliance (GSTIN validation, tax consistency)
- **C**: Arithmetic (line items, totals, calculations)
- **D**: TDS (Tax Deducted at Source applicability)
- **E**: Policy (PO tolerance, vendor approval)

### Database
- **SQLite**: `db/compliance.db` (auto-created on first run)
- **Tables**: 
  - `invoices_processed` (duplicate detection)
  - `vendor_annual_totals` (TDS tracking)
  - `vendors` (vendor registry)

---

## Features

✅ **Multi-Format Support**
- JSON invoices
- CSV/XLSX spreadsheets
- PNG/JPG images (OCR-ready)

✅ **Real-Time Compliance Validation**
- 11 automated compliance checks
- AI-powered decision logic
- Confidence scoring

✅ **Batch Processing**
- Process 1-1000+ invoices simultaneously
- Progress tracking
- Aggregate statistics

✅ **Audit Trail**
- Complete decision reasoning
- Agent-by-agent analysis
- Confidence metrics

✅ **Multi-LLM Support**
- OpenAI (GPT-4, GPT-4o)
- Azure OpenAI
- Google Gemini
- Anthropic Claude

✅ **Mock GST API**
- Auto-starts on app launch
- Simulates GST portal validation
- GSTIN, IRN, HSN rate checking

---

## Troubleshooting

### App won't start
```bash
# Verify Python version
python --version  # Should be 3.10+

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### ModuleNotFoundError
```bash
# Ensure PYTHONPATH is set for tests
$env:PYTHONPATH="src"
pytest tests/
```

### Database locked error
```bash
# Delete and recreate database
Remove-Item db/compliance.db
# App will auto-create on next run
```

### Port 8501 already in use
```bash
# Run on different port
streamlit run src/app.py --server.port 8502
```

---

## File Structure

```
invoice-auditor-pro/
├── src/
│   ├── app.py                 # Streamlit UI
│   ├── workflow.py            # LangGraph orchestration
│   ├── schema.py              # Pydantic data models
│   ├── init_db.py             # Database initialization
│   ├── mock_gst_server.py     # Flask mock API
│   ├── agents/
│   │   ├── document_parser.py
│   │   ├── compliance_checker.py
│   │   ├── decision_resolver.py
│   │   └── report_builder.py
│   └── tools/
│       └── compliance_tools.py
├── tests/
│   ├── test_compliance.py
│   ├── regression_runner.py
│   └── batch_test.py
├── data/
│   ├── invoices/test_invoices.json    (21 test invoices)
│   └── master_data/                   (GST/TDS reference data)
├── db/                        # SQLite database
├── reports/                   # Generated audit reports
├── README.md                  # Project overview
├── GETTING_STARTED.md        # Quick start guide
├── requirements.txt          # Python dependencies
└── INSTALLATION.md           # This file
```

---

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `langchain` | LLM integration |
| `langgraph` | Agentic workflow orchestration |
| `pydantic` | Data validation |
| `pandas` | CSV/XLSX parsing |
| `flask` | Mock GST API server |
| `requests` | HTTP client |
| `pytest` | Testing framework |

---

## Environment Variables (Optional)

Create `.env` file if using external APIs:
```
OPENAI_API_KEY=your-key-here
AZURE_OPENAI_KEY=your-key-here
GOOGLE_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
```

**Note**: App uses session-only credentials (never auto-loaded from disk for security).

---

## Support & Documentation

- **README.md** - Project overview & features
- **GETTING_STARTED.md** - Quick tutorial
- **analysis.md** - Compliance framework details
- **architecture.md** - System design documentation

---

**Ready to audit invoices? Launch the app with: `streamlit run src/app.py`** 🚀
