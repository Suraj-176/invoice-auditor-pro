# Agentic AI Compliance Validator

End-to-end AI system for automated invoice compliance auditing.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `config_template.env` to `.env` and add your keys, or configure them directly in the UI.

### 3. Start the Mock GST Server
```bash
python src/mock_gst_server.py
```

### 3. Initialize the Database
```bash
python src/init_db.py
```

### 4. Run the Processor
```bash
python src/main.py --input data/invoices/test_invoices.json --output reports/output.json
```

### 5. Launch the Web UI
```bash
streamlit run src/app.py
```

## 📂 Project Structure
*   `src/`: Core logic, agents, tools, and mock server.
*   `data/`: Master regulatory data and test invoices.
*   `db/`: Persistent state storage.
*   `reports/`: Generated compliance reports.
*   `tests/`: Automated regression and unit tests.

## 🛡️ Compliance Checks
The system implements the 10 core checks across Authenticity, GST, Arithmetic, TDS, and Policy categories as defined in the `checks_manifest.json`.
