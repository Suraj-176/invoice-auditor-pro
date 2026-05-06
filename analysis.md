# Compliance Analysis & Decision Framework

## Executive Summary (Non-Technical)
The **Invoice Auditor Pro** is an intelligent assistant designed to automate the complex task of auditing financial invoices. Instead of a simple "yes/no" program, it uses a team of **specialized AI agents** that work together like a human accounting team. 
*   It reads the invoice.
*   It cross-checks details with official government records (GST/TDS).
*   It "remembers" past invoices to prevent double payments.
*   It flags high-risk or confusing cases for human review, ensuring total financial safety.

## Technical Approach (Specialized Logic)
The system is built on **LangGraph**, enabling a stateful, multi-agent workflow that mirrors human reasoning.

### 1. Handling Messy Data & OCR Errors
The **Resolver Agent** acts as a quality control layer. If a critical identifier (like a GSTIN) fails validation, the agent doesn't immediately reject it. Instead, it performs **OCR Error Correction**, checking for common character swaps (e.g., '0' instead of 'O'). This reduces "False Rejections" caused by poor scan quality.

### 2. The "Historical Trap" Resolution
A key challenge was the presence of incorrect historical decisions (15% error rate in past data). Our system avoids this by using **Deterministic Regulatory Logic**. We prioritize the official **Master Data** (GST rates, Vendor Registry) over historical patterns, ensuring the AI learns the *rules*, not the *mistakes* of the past.

### 3. Stateful Validation & Memory
Using an **SQLite backend**, the system maintains a persistent registry of all processed invoices. This enables:
*   **A2 Duplicate Detection:** Instant rejection if the same Invoice ID is submitted twice.
*   **D1/D2 TDS Aggregation:** Tracking cumulative payments to a vendor within a fiscal year to trigger mandatory tax deductions once legal thresholds are met.

## Risk & Safety Controls
*   **High-Value Trigger:** Any invoice exceeding **₹10,00,000** is automatically escalated to **ESCALATE_TO_HUMAN**, regardless of how "perfect" the data appears.
*   **Confidence Scoring:** We use a dual-scoring system. The **Compliance Score** measures rule adherence, while **Agent Confidence** measures data reliability. If either falls below safety thresholds, human intervention is mandated.
