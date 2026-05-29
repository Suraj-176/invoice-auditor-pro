# 🚀 Getting Started with Invoice Auditor Pro

Welcome! This guide will walk you through the setup and usage of the **Invoice Auditor Pro**, an agentic AI system for automated compliance auditing.

---

## 🛠️ Step 1: Environment Setup

Ensure you have **Python 3.10+** installed.

1. **Install Dependencies:**
   Open your terminal in the project root and run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Keys (Template):**
   You don't need to manually edit files yet. We provided `.env.example` for reference. Copy it to `.env` and fill in your keys, or configure everything directly in the Web UI.

---

## ⚙️ Step 2: Initialize Infrastructure

Before running the auditor, you must start the background services.

1. **Start the Mock GST Server:**
   This simulates the government portal for real-time validation.
   ```bash
   python src/mock_gst_server.py
   ```
   *Keep this terminal window open.*

2. **Initialize the Database:**
   Run this once to set up the local SQLite storage (for duplicate detection and TDS tracking).
   ```bash
   python src/init_db.py
   ```

---

## 🖥️ Step 3: Launch the Auditor Dashboard

For the best experience, use our interactive Streamlit dashboard:

1. **Start the Web UI:**
   ```bash
   streamlit run src/app.py
   ```
2. **Access the Dashboard:**
   Open `http://localhost:8501` in your browser.

---

## 🔍 Step 4: Performing Your First Audit

1. **Configure LLM:**
   - Click the **⚙️ Options** icon at the top right.
   - Select your provider (e.g., **Azure OpenAI** or **Google Gemini**).
   - Enter your credentials and click **Test Connection**.
   - Click **Save** if you want the app to remember your keys for the next session.

2. **Upload an Invoice:**
   - Drag and drop a `.json` invoice file from the `data/invoices/` folder into the upload area.
   - Watch the **Agent Reasoning** unfold in real-time.

3. **Review Results:**
   - **Summary Tab:** Quick view of vendor and invoice data.
   - **Compliance Matrix:** Detailed pass/fail status for all 11 regulatory checks.
   - **Export:** Click **📥 Export Report** to download the official JSON audit trail.

---

## 🧪 Step 5: Automated Verification (Optional)

If you want to run the full regression test suite to verify the logic across multiple scenarios (Duplicates, High Value, etc.):
```bash
python tests/regression_runner.py
```

---

## 📂 Project Structure at a Glance
- `src/`: Core AI Agents and Logic.
- `data/master_data/`: Regulatory rules and vendor registry.
- `db/`: Stateful database storage.
- `reports/`: Folder for downloaded audit results.
- `tests/`: Automated unit and regression tests.

---
**Happy Auditing!** 🛡️
