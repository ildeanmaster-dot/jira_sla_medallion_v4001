# JIRA SLA Medallion Pipeline (v4)

This is a Python data engineering project implementing a **Medallion** architecture (Bronze / Silver / Gold) to ingest JIRA issues (JSON), normalize them, and compute SLA in business hours (excluding weekends and Brazilian national holidays).

The pipeline supports:
- Ingestion from **Azure Blob Storage** using a **Service Principal** (read-only)
- **Local fallback** (offline) to `data/raw/jira_issues_raw.json`
- Corporate environments with TLS proxy and self-signed certificates via **CA bundle** (`AZURE_CA_BUNDLE`)
- **Step-by-step** execution with fail-fast validations (default)
- Optional **full** execution mode

---

## Architecture (Medallion)

### Bronze
- Goal: faithful copy of source data (no transformations)
- Input: Azure Blob JSON (or local fallback)
- Outputs:
  - `data/bronze/bronze_jira.json`
  - `data/bronze/bronze_jira_source.json` (evidence: AZURE_BLOB or LOCAL_FALLBACK)

### Silver
- Goal: normalize nested JSON into a lean CSV table focused on SLA
- Input: `data/bronze/bronze_jira.json`
- Output:
  - `data/silver/silver_jira.csv`

Silver columns:
- `issue_id`, `issue_key`, `created`, `resolved`, `status`, `priority`, `issue_type`, `assignee`

### Gold
- Goal: apply business rules and calculate SLA in business hours
- Input: `data/silver/silver_jira.csv`
- Outputs:
  - `data/gold/gold_jira_sla.csv`
  - `data/gold/gold_sla_by_analyst.csv`
  - `data/gold/gold_sla_by_type.csv`
  - `data/gold/gold_sla_by_issue_type.csv` (same content, alternate name)

Gold rules:
- Only consider `status` values of `Done` or `Resolved`
- `resolved` must be populated
- Expected SLA by priority:
  - High = 24
  - Medium = 72
  - Low = 120
- Calculate `actual_hours` in **business hours**:
  - exclude Saturday/Sunday
  - exclude Brazilian national holidays

Gold columns:
- `issue_id`, `issue_key`, `created`, `resolved`, `status`, `priority`,
  `issue_type`, `assignee`, `actual_hours`, `sla_expected_hours`, `is_sla_met`

---

## Requirements

- Windows 10/11
- Python 3.9+
- PowerShell
- Azure account & Storage Blob access with read permissions for the service principal

---

## Setup (Step by step)

### 1) Create virtual environment
At the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip