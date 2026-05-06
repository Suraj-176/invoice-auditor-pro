# System Architecture: Agentic AI Compliance Validator

## Overview
This system is an AI-powered compliance auditor for financial invoices. It uses a **Multi-Agent Architecture** orchestrated by **LangGraph** to perform complex regulatory validations against Indian GST and TDS laws.

## Core Components

### 1. Orchestration (LangGraph)
The system follows a directed graph workflow:
`Extractor` -> `Validator` -> `Resolver` -> `Reporter`

*   **Extractor Agent:** Normalizes unstructured data (PDF/Image/JSON) into a structured `InvoiceData` Pydantic model.
*   **Validator Agent:** Executes 10 mandated compliance checks using a suite of Python tools.
*   **Resolver Agent:** Acts as the "brain," analyzing validation failures, handling OCR errors, and assigning a confidence score. It makes the final decision (APPROVED, REJECTED, ESCALATE).
*   **Reporter Agent:** Formats the final output and updates the stateful database for approved invoices.

### 2. Stateful Database (SQLite)
Maintains "memory" across invoices to handle:
*   **Duplicate Detection:** Prevents processing the same invoice twice.
*   **TDS Aggregation:** Tracks cumulative payments to vendors within a fiscal year to trigger threshold-based tax deductions (e.g., Section 194Q).

### 3. External Tooling
*   **Mock GST API:** A Flask-based simulation of the GST portal for real-time validation of GSTINs, HSN rates, and e-invoice mandates.

## 58-Point Validation Framework (Highlights)
While 10 core checks are strictly implemented, the system architecture supports expanding to the full 58 points by adding new tool definitions to the `ValidatorAgent`.

## UI & Interaction
*   **Automation Interface:** Mandated interface for automated batch processing.
*   **Streamlit Web UI:** An interactive dashboard for human reviewers to see the agent's thought process (audit trail) and verify decisions.
