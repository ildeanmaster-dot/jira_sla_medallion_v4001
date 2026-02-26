# Project Overview for AI Coding Agents

This repository implements a **Medallion data pipeline** for JIRA issues in Python.  It's structured to be small but realistic, with clear Bronze/Silver/Gold layers and supporting utilities. The main goal is to convert raw JIRA JSON into SLA reports measured in Brazilian business hours.

## Big Picture Architecture

- **Bronze**: `src/bronze/ingest_jira.py` reads either Azure Blob Storage or a local fallback (`data/raw/jira_issues_raw.json`). It writes a faithful JSON copy to `data/bronze/bronze_jira.json` and a side‑car evidence file `data/bronze/bronze_jira_source.json`.
- **Silver**: `src/silver/transform_jira.py` normalizes arbitrary nested JSON into a flat CSV `data/silver/silver_jira.csv`. It focuses on the eight fields required for SLA later and ignores records without `created`.
- **Gold**: `src/gold/calculate_sla.py` loads the Silver CSV, filters Done/Resolved issues with a `resolved` date, computes `actual_hours` using business‑hour rules from `src/utils/date_utils.py`, maps expected SLA by priority, and outputs several CSVs under `data/gold/`.
- Utilities under `src/utils` provide shared functionality:
  - `azure_blob.py` handles Azure authentication + fallback logic.
  - `date_utils.py` calculates business hours minute‑by‑minute, calling `holiday_api.get_br_holidays` for Brazilian holidays.
  - `validators.py` contains layer‑specific contract checks used by the validation scripts.
  - `holiday_api.py` wraps the `holidays` library.

Data flows strictly forward: Bronze JSON → Silver CSV → Gold CSV(s).  Each stage is independent and can be re‑run; the `ps1` pipeline script resets previous outputs before running.

## Developer Workflows & Commands

- **Pipeline execution**: use `scripts/run_pipeline.ps1` from the project root (Windows). By default it runs in `step` mode (execute + validate each layer). `.






















































Ask the maintainers if anything above is unclear or missing; they prefer concrete examples rather than generic advice.---- Update validation logic whenever the output contract of a stage changes; unit tests are manual but validators are automated.- Keep environment handling centralized with `dotenv` and clearly document new variables in README.- When writing new utility functions, follow the defensive, return‑default style used in `date_utils` and `_safe_get` in `transform_jira`.- Look at `run_pipeline.ps1` for the intended sequence of operations and failure handling; any new script should integrate similarly.- Focus on the three temples (Bronze/Silver/Gold) when adding or modifying logic; changes usually ripple along the pipeline.## Tips for AI Assistance- **Holiday library**: `holidays.Brazil` is the only external data source used; swapable via `src/utils/holiday_api.py`.- **Azure Blob Storage**: credentials obtained from environment, uses `azure.identity` and `azure.storage.blob` clients.## Integration Points- Validation scripts provide quick checks and can be called on arbitrary files.  ```  python src/silver/transform_jira.py  ```powershell- To debug a stage, run the corresponding script directly with Python, e.g.- There are no formal unit tests in the repo; developers generally run the pipeline on sample data and inspect output CSVs.## Testing & Debugging- The project avoids external dependencies in core modules except `pandas` for CSV read/write and `holidays` for holiday lookup.- Comments and docstrings are English and self‑documenting; look at examples above for style.- Business‑hour calculation iterates minute by minute to achieve deterministic results.- Validation functions raise `ValueError` with explicit messages; callers are expected to propagate or fail-fast.- Defensive coding: parsing functions return defaults (e.g. `0.0` hours) on malformed input rather than raising.- Logging is minimal; most modules print summaries to stdout.- The pipeline script ensures `PYTHONPATH` is set to the repository root so imports use `src.*`.- **Paths** are hardcoded strings rather than parameters in most functions but can be overridden via arguments for unit tests.## Conventions & Patterns  - `AZURE_CA_BUNDLE` for custom CA bundle paths when behind corporate proxy  - `AZURE_STORAGE_ACCOUNT`, `AZURE_STORAGE_CONTAINER`, `AZURE_STORAGE_BLOB`  - `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`- Configuration is via a `.env` file read by `dotenv`. Key variables:  ```  python -m pip install --upgrade pip  .\.venv\Scripts\Activate.ps1  ```powershell- Project uses a virtualenv (`.venv`). Activate with- Windows 10/11 with PowerShell and Python 3.9+ recommended.### Environment Setup- **Publishing**: `scripts/publish_github.ps1` pushes to a remote and tags the release; it warns if `.env` is tracked.- **Scaffolding**: `scripts/scaffold.ps1` builds the directory/file skeleton (placeholders only).- **Azure connection test**: `scripts/validate_azure_connection.py` checks environment variables, obtains an AAD token, and attempts a partial blob download.- **Validation scripts**: each layer has a dedicated Python validator under `scripts/validate_*.py` which call `src/utils/validators.py`. These are invoked by the pipeline script and can be run manually.un_pipeline.ps1 -Mode full` runs `main.py` if present and then validates artifacts.