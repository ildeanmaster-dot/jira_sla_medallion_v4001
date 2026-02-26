# JIRA SLA Medallion Pipeline (v4)

This is a Python data engineering project implementing a **Medallion** architecture (Bronze / Silver / Gold) to ingest JIRA issues (JSON), normalize them, and compute SLA in business hours (excluding weekends and Brazilian national holidays).

**Table of Contents**
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [SLA Calculation Logic](#sla-calculation-logic)
- [Data Dictionary](#data-dictionary)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Windows 10/11
- Python 3.9+
- PowerShell
- (Optional) Azure account with Storage Blob read access for Service Principal authentication

### 1. Clone & Setup Environment

```powershell
# Clone the repository
git clone <repository-url>
cd jira_sla_medallion_v4

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Azure (Optional)

Create a `.env` file at the project root with your Azure credentials:

```env
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_ID=<your-client-id>
AZURE_CLIENT_SECRET=<your-client-secret>
AZURE_STORAGE_ACCOUNT=<your-storage-account-name>
AZURE_STORAGE_CONTAINER=<your-container-name>
AZURE_STORAGE_BLOB=jira_issues_raw.json
AZURE_CA_BUNDLE=<optional-path-to-ca-cert>
```

If Azure is not configured or unavailable, the pipeline will automatically fall back to `data/raw/jira_issues_raw.json`.

### 3. Run the Pipeline

```powershell
# Default: step-by-step execution with validations
.\scripts\run_pipeline.ps1

# Or: full mode (runs main.py if present)
.\scripts\run_pipeline.ps1 -Mode full
```

The pipeline will:
1. **Bronze**: Ingest raw JIRA JSON (Azure Blob or local)
2. **Silver**: Normalize JSON into a structured CSV
3. **Gold**: Apply business rules and calculate SLA

Output files are generated under `data/` directory.

---

## Architecture

The pipeline follows a **3-layer Medallion** pattern, where data flows left-to-right with increasing business value:

### Layer 1: Bronze

**Purpose**: Faithful copy of source data (no transformations)

**Inputs**:
- Azure Blob Storage (JIRA JSON export via Service Principal)
- Or local fallback: `data/raw/jira_issues_raw.json`

**Outputs**:
- `data/bronze/bronze_jira.json` - Raw JIRA payload
- `data/bronze/bronze_jira_source.json` - Audit trail (source: AZURE_BLOB or LOCAL_FALLBACK)

**Script**: `src/bronze/ingest_jira.py`

The Bronze layer also produces a sidecar evidence file documenting:
- Source (AZURE_BLOB or LOCAL_FALLBACK)
- Timestamp (UTC)
- Azure connection parameters (for audit)

### Layer 2: Silver

**Purpose**: Normalize nested JSON into a flat, structured CSV table

**Inputs**:
- `data/bronze/bronze_jira.json`

**Outputs**:
- `data/silver/silver_jira.csv`

**Normalization rules**:
- Extracts 8 core fields required for SLA calculation
- Handles nested JIRA structures (e.g., `fields.status.name`, `fields.priority.name`)
- Defensive parsing: missing fields return `None` without raising errors
- Filters out records without `created` timestamp (mandatory field)
- Keeps all status values (filtering to Done/Resolved happens in Gold)

**Script**: `src/silver/transform_jira.py`

### Layer 3: Gold

**Purpose**: Apply business logic and calculate SLA metrics

**Inputs**:
- `data/silver/silver_jira.csv`

**Outputs**:
- `data/gold/gold_jira_sla.csv` - Main SLA table
- `data/gold/gold_sla_by_analyst.csv` - Aggregated by assignee
- `data/gold/gold_sla_by_type.csv` - Aggregated by issue type
- `data/gold/gold_sla_by_issue_type.csv` - Alias for the above

**Business Rules**:
1. **Filtering**: Only issues with `status` in {Done, Resolved} and a non-empty `resolved` timestamp
2. **SLA Mapping**: Based on issue priority:
   - High → 24 hours
   - Medium → 72 hours
   - Low → 120 hours
3. **Calculation**: Computes `actual_hours` using business-hour rules (see below)
4. **Reporting**: Aggregates by analyst and issue type

**Script**: `src/gold/calculate_sla.py`

---

## SLA Calculation Logic

### Business Hours Definition

The pipeline calculates SLA using **real business hours**, defined as:

- **Inclusion**: All minutes on a business day (no fixed 9-5 boundaries)
- **Exclusion**: 
  - Saturdays and Sundays (weekends)
  - Brazilian national holidays (via `holidays.Brazil` library)

### Calculation Method

1. Parse ISO 8601 timestamps (`created` and `resolved`)
2. Iterate **minute-by-minute** between timestamps
3. For each minute:
   - Check if the date is a weekend (Saturday=5, Sunday=6)
   - Check if the date is a Brazilian holiday
   - If neither, count it as a business minute
4. Sum all business minutes and divide by 60 to get hours
5. Round to 2 decimal places

### Example

```
Created:  2024-01-08 14:30:00 (Monday)
Resolved: 2024-01-09 10:15:00 (Tuesday)

Business minutes:
  - Mon 14:30 to 23:59 = 570 minutes
  - Tue 00:00 to 10:15 = 615 minutes
  Total = 1185 minutes
  
Actual hours = 1185 / 60 = 19.75 hours

SLA Expected (if High priority) = 24 hours
SLA Met = 19.75 ≤ 24 → TRUE
```

### Robustness

The calculation is defensive:
- If `created` or `resolved` is missing/invalid, returns 0.0 hours
- If `resolved` < `created`, returns 0.0 hours
- Handles both timezone-aware and naive datetime strings (assumes UTC for naive)

---

## Data Dictionary

### Silver CSV (Normalized Layer)

**File**: `data/silver/silver_jira.csv`

| Column | Type | Description |
|--------|------|-------------|
| `issue_id` | string | Unique JIRA issue identifier (usually numeric) |
| `issue_key` | string | JIRA key (e.g., "PROJ-123") |
| `created` | ISO 8601 | Timestamp when issue was created (UTC) |
| `resolved` | ISO 8601 or null | Timestamp when issue was resolved (UTC), null if unresolved |
| `status` | string | Current status (e.g., "Open", "In Progress", "Done", "Resolved") |
| `priority` | string | Issue priority (e.g., "High", "Medium", "Low") |
| `issue_type` | string | Issue type (e.g., "Bug", "Feature", "Task") |
| `assignee` | string or null | Name/email of assigned person, null if unassigned |

**Example rows**:
```csv
issue_id,issue_key,created,resolved,status,priority,issue_type,assignee
12345,PROJ-001,2024-01-08T10:00:00Z,2024-01-10T15:30:00Z,Done,High,Bug,alice@example.com
12346,PROJ-002,2024-01-09T14:20:00Z,,In Progress,Medium,Feature,bob@example.com
12347,PROJ-003,2024-01-08T09:15:00Z,2024-01-12T11:00:00Z,Resolved,Low,Task,charlie@example.com
```

### Gold CSV (SLA Metrics)

**File**: `data/gold/gold_jira_sla.csv`

| Column | Type | Description |
|--------|------|-------------|
| `issue_id` | string | Unique JIRA issue identifier |
| `issue_key` | string | JIRA key |
| `created` | ISO 8601 | Issue creation timestamp |
| `resolved` | ISO 8601 | Issue resolution timestamp (only Done/Resolved) |
| `status` | string | Status (always "Done" or "Resolved") |
| `priority` | string | Priority (normalized: "high", "medium", "low") |
| `issue_type` | string | Issue type |
| `assignee` | string or null | Assigned person |
| `actual_hours` | float | Business hours elapsed from created to resolved (2 decimals) |
| `sla_expected_hours` | float | Expected SLA hours based on priority |
| `is_sla_met` | boolean | TRUE if actual_hours ≤ sla_expected_hours |

**Example rows**:
```csv
issue_id,issue_key,created,resolved,status,priority,issue_type,assignee,actual_hours,sla_expected_hours,is_sla_met
12345,PROJ-001,2024-01-08T10:00:00Z,2024-01-10T15:30:00Z,Done,high,Bug,alice@example.com,19.75,24.0,True
12347,PROJ-003,2024-01-08T09:15:00Z,2024-01-12T11:00:00Z,Resolved,low,Task,charlie@example.com,72.5,120.0,True
```

### Analyst Report

**File**: `data/gold/gold_sla_by_analyst.csv`

| Column | Type | Description |
|--------|------|-------------|
| `assignee` | string or null | Analyst/person name |
| `avg_actual_hours` | float | Average business hours per issue (2 decimals) |
| `sla_met_rate` | float | Percentage of issues meeting SLA (0-100, 2 decimals) |

**Example**:
```csv
assignee,avg_actual_hours,sla_met_rate
alice@example.com,15.30,85.50
bob@example.com,22.10,65.00
charlie@example.com,50.25,100.00
```

### Issue Type Report

**File**: `data/gold/gold_sla_by_type.csv` (or `gold_sla_by_issue_type.csv`)

| Column | Type | Description |
|--------|------|-------------|
| `issue_type` | string | Issue type (e.g., Bug, Feature, Task) |
| `avg_actual_hours` | float | Average business hours per issue |
| `sla_met_rate` | float | Percentage of issues meeting SLA (0-100) |

**Example**:
```csv
issue_type,avg_actual_hours,sla_met_rate
Bug,18.50,90.00
Feature,45.20,75.00
Task,25.10,80.00
```

---

## Configuration

### Environment Variables (.env)

Create a `.env` file at the project root. Only `AZURE_*` variables are optional if using local fallback.

```env
# Azure Authentication (Service Principal)
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=your-client-secret
AZURE_STORAGE_ACCOUNT=mystorageaccount
AZURE_STORAGE_CONTAINER=mycontainer
AZURE_STORAGE_BLOB=jira_issues_raw.json

# Optional: Custom CA Bundle (for corporate proxies)
AZURE_CA_BUNDLE=C:\Certs\corp-root-ca.pem
```

### Local Fallback

If Azure credentials are missing or the connection fails, the pipeline automatically reads from:
```
data/raw/jira_issues_raw.json
```

Prepare a sample JSON file with this structure:
```json
{
  "issues": [
    {
      "id": "12345",
      "key": "PROJ-001",
      "fields": {
        "created": "2024-01-08T10:00:00Z",
        "resolutiondate": "2024-01-10T15:30:00Z",
        "status": { "name": "Done" },
        "priority": { "name": "High" },
        "issuetype": { "name": "Bug" },
        "assignee": { "displayName": "alice@example.com" }
      }
    }
  ]
}
```

---

## Running Individual Stages

You can run each layer independently:

### Bronze (Ingest)
```powershell
python .\src\bronze\ingest_jira.py
```
Outputs: `data/bronze/bronze_jira.json`, `data/bronze/bronze_jira_source.json`

### Silver (Normalize)
```powershell
python .\src\silver\transform_jira.py
```
Outputs: `data/silver/silver_jira.csv`

### Gold (Calculate SLA)
```powershell
python .\src\gold\calculate_sla.py
```
Outputs: `data/gold/gold_jira_sla.csv`, `data/gold/gold_sla_by_analyst.csv`, `data/gold/gold_sla_by_type.csv`

### Validation Scripts

Validate each layer:
```powershell
python .\scripts\validate_bronze.py
python .\scripts\validate_silver.py
python .\scripts\validate_gold.py
python .\scripts\validate_azure_connection.py
```

---

## File Structure

```
jira_sla_medallion_v4/
├── data/
│   ├── raw/
│   │   └── jira_issues_raw.json          (local fallback)
│   ├── bronze/
│   │   ├── bronze_jira.json              (output)
│   │   └── bronze_jira_source.json       (output - audit)
│   ├── silver/
│   │   └── silver_jira.csv               (output)
│   └── gold/
│       ├── gold_jira_sla.csv             (output)
│       ├── gold_sla_by_analyst.csv       (output)
│       ├── gold_sla_by_type.csv          (output)
│       └── gold_sla_by_issue_type.csv    (output - alias)
├── src/
│   ├── bronze/
│   │   ├── __init__.py
│   │   └── ingest_jira.py                (Bronze logic)
│   ├── silver/
│   │   ├── __init__.py
│   │   └── transform_jira.py             (Silver logic)
│   ├── gold/
│   │   ├── __init__.py
│   │   └── calculate_sla.py              (Gold logic)
│   └── utils/
│       ├── __init__.py
│       ├── azure_blob.py                 (Azure integration)
│       ├── date_utils.py                 (Business hour calculation)
│       ├── holiday_api.py                (Brazilian holiday lookup)
│       └── validators.py                 (Layer-specific validations)
├── scripts/
│   ├── run_pipeline.ps1                  (Main orchestration script)
│   ├── scaffold.ps1                      (Initialize project structure)
│   ├── validate_bronze.py                (Bronze validation)
│   ├── validate_silver.py                (Silver validation)
│   ├── validate_gold.py                  (Gold validation)
│   ├── validate_bronze_source.py         (Audit source)
│   ├── validate_azure_connection.py      (Azure connection test)
│   └── publish_github.ps1                (Release and tag)
├── .env.example                          (Example environment file)
├── requirements.txt                      (Python dependencies)
├── main.py                               (Optional entry point)
├── .github/
│   └── copilot-instructions.md           (AI assistant guidelines)
└── README.md                             (This file)
```

---

## Troubleshooting

### 1. ModuleNotFoundError: No module named 'src'

**Cause**: `PYTHONPATH` not set to project root.  
**Solution**: The pipeline script automatically sets `PYTHONPATH`. If running scripts directly:
```powershell
$env:PYTHONPATH = (Get-Location).Path
python .\src\bronze\ingest_jira.py
```

### 2. Azure Connection Fails

**Cause**: Missing/invalid credentials or network issues.  
**Solution**: 
- Check `.env` file for typos in `AZURE_*` variables
- Run `python .\scripts\validate_azure_connection.py` to diagnose
- Verify Service Principal has read access to the Storage Blob container
- For corporate proxies, set `AZURE_CA_BUNDLE` to your CA certificate path

**Fallback**: The pipeline will automatically use `data/raw/jira_issues_raw.json` if Azure fails.

### 3. No Rows in Gold Output

**Cause**: No issues with status "Done" or "Resolved" + filled `resolved` timestamp.  
**Solution**:
- Check that Silver CSV has rows with `status` in {Done, Resolved}
- Verify `resolved` field is not empty for those rows
- Run `python .\scripts\validate_silver.py` to inspect the Silver layer

### 4. Business Hours Calculation Seems Wrong

**Cause**: Timezone or holiday configuration issues.  
**Solution**:
- All timestamps are expected in ISO 8601 format (UTC)
- If data uses a different timezone, convert to UTC in Bronze or Silver layer
- Verify Brazilian holidays are correct: `holidays.Brazil` should handle this automatically

### 5. CSV Parsing Errors

**Cause**: Encoding or special characters in JIRA data.  
**Solution**: All CSV files are written with `encoding="utf-8"`. If reading in Excel, ensure UTF-8 is set.

---

## Performance Notes

- **Business hour calculation**: O(n) where n = minutes between created and resolved. For typical 1-30 day windows, this is fast.
- **Large datasets**: For >10k issues, consider:
  - Increasing recursion limit if needed
  - Running in batches
  - Using a more efficient date calculation (currently minute-by-minute for determinism)
- **Azure I/O**: Blob download happens once per pipeline run; subsequent runs reuse Bronze cache.

---

## Support & Feedback

For issues, questions, or contributions:
- Review `.github/copilot-instructions.md` for AI agent guidance
- Check the validation scripts output for layer-specific errors
- Inspect the sidecar file `data/bronze/bronze_jira_source.json` to confirm data source

---

## License

This project is provided as-is. Modify and distribute according to your organization's policies.
