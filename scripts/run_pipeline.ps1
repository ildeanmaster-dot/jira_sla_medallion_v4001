param(
    [ValidateSet("full","step")]
    [string]$Mode = "step"
)

# ================================================================
# SCRIPT: run_pipeline.ps1
# OBJECTIVE:
# - Execute the Medallion pipeline (Bronze -> Silver -> Gold)
# - "step" mode (default): run and validate each layer separately
# - "full" mode: run main.py (if present) and validate at the end
#
# PRINCIPLES:
# - Fail fast: stop immediately on error with clear message
# - 3+ validations per step (environment, execution, artifacts/contract)
# - Ensure PYTHONPATH at project root for "src.*" imports
# - Avoid python -c for complex validations (use dedicated scripts)
# ================================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Fail([string]$Message) {
    Write-Host "ERROR: $Message"
    exit 1
}

function CheckFileExists([string]$Path, [string]$Context) {
    if (-not (Test-Path $Path)) {
        Fail "$Context - file not found: $Path"
    }
}

function CheckFileNotEmpty([string]$Path, [string]$Context) {
    CheckFileExists $Path $Context
    $len = (Get-Item $Path).Length
    if ($len -le 0) {
        Fail "$Context - file is empty: $Path"
    }
}

function RunPython([string[]]$PyArgs, [string]$Context) {
    # Avoid conflict with automatic $Args variable in PowerShell:
    # use $PyArgs as the array of arguments for python.
    Write-Host "RUN: python $($PyArgs -join ' ')"
    & python @PyArgs
    if ($LASTEXITCODE -ne 0) {
        Fail "$Context - python execution failed (exit code $LASTEXITCODE)"
    }
}

# ------------------------------------------------
# Validation 1 (global): ensure project root
# ------------------------------------------------
if (-not (Test-Path ".\src")) {
    Fail "Project root not detected. Ensure you are running from the project root where .\src exists."
}

# ------------------------------------------------
# Validation 2 (global): python is accessible
# ------------------------------------------------
try {
    $py = (Get-Command python).Source
    Write-Host "Python: $py"
} catch {
    Fail "Python not found in PATH. Activate .venv or install Python."
}

# ------------------------------------------------
# Validation 3 (global): set PYTHONPATH to root
# This resolves: ModuleNotFoundError: No module named 'src'
# ------------------------------------------------
$env:PYTHONPATH = (Get-Location).Path
Write-Host "PYTHONPATH set to: $env:PYTHONPATH"

# ------------------------------------------------
# Artifact paths
# ------------------------------------------------
$BronzeFile = ".\data\bronze\bronze_jira.json"
$BronzeEvidence = ".\data\bronze\bronze_jira_source.json"

$SilverFile = ".\data\silver\silver_jira.csv"

$GoldFile = ".\data\gold\gold_jira_sla.csv"
$GoldReportAnalyst = ".\data\gold\gold_sla_by_analyst.csv"
$GoldReportType = ".\data\gold\gold_sla_by_type.csv"
$GoldReportType2 = ".\data\gold\gold_sla_by_issue_type.csv"

# ------------------------------------------------
# Execution
# ------------------------------------------------
if ($Mode -eq "full") {

    # Full mode: use main.py (if present)
    CheckFileExists ".\main.py" "FULL"
    RunPython @(".\main.py") "FULL"

    # Final validations (main artifacts)
    CheckFileNotEmpty $BronzeFile "FULL-BRONZE"
    CheckFileExists $BronzeEvidence "FULL-BRONZE-EVIDENCE"
    RunPython @(".\scripts\validate_bronze.py") "FULL-BRONZE-VALIDATOR"

    CheckFileExists $SilverFile "FULL-SILVER"
    RunPython @(".\scripts\validate_silver.py") "FULL-SILVER-VALIDATOR"

    CheckFileExists $GoldFile "FULL-GOLD"
    CheckFileExists $GoldReportAnalyst "FULL-GOLD-REPORT-ANALYST"
    CheckFileExists $GoldReportType "FULL-GOLD-REPORT-TYPE"
    RunPython @(".\scripts\validate_gold.py") "FULL-GOLD-VALIDATOR"

    Write-Host "Pipeline FULL completed successfully."
    exit 0
}

# ================================================================
# STEP mode (default) - execute step-by-step with fail-fast
# ================================================================

# -----------------------------
# STEP 1: Bronze
# Validations:
# 1) Script execution
# 2) Artifact exists and is not empty
# 3) Bronze contract ok (validate_bronze.py)
# 4) Source evidence exists (azure vs fallback)
# -----------------------------
Write-Host "STEP 1/3 - BRONZE"

RunPython @(".\src\bronze\ingest_jira.py") "BRONZE-RUN"
CheckFileNotEmpty $BronzeFile "BRONZE-ARTIFACT"
CheckFileExists $BronzeEvidence "BRONZE-EVIDENCE"
RunPython @(".\scripts\validate_bronze.py") "BRONZE-VALIDATOR"

# Extra validation: source recorded (if the script exists)
if (Test-Path ".\scripts\validate_bronze_source.py") {
    RunPython @(".\scripts\validate_bronze_source.py") "BRONZE-SOURCE-VALIDATOR"
} else {
    Write-Host "WARN: scripts/validate_bronze_source.py not found. Skipping source validation."
}

# -----------------------------
# STEP 2: Silver
# Validations:
# 1) Script execution
# 2) Artifact exists
# 3) Silver contract ok (validate_silver.py)
# 4) File contains expected header (first line)
# -----------------------------
Write-Host "STEP 2/3 - SILVER"

# Controlled reset of Silver file (avoids previous run cache)
if (Test-Path $SilverFile) {
    Remove-Item $SilverFile -Force
    Write-Host "Removed old Silver file: $SilverFile"
}

RunPython @(".\src\silver\transform_jira.py") "SILVER-RUN"
CheckFileExists $SilverFile "SILVER-ARTIFACT"
RunPython @(".\scripts\validate_silver.py") "SILVER-VALIDATOR"

# Extra validation: CSV header
$header = (Get-Content $SilverFile -TotalCount 1)
if ($header -notmatch "issue_id" -or $header -notmatch "created") {
    Fail "SILVER-HEADER - missing expected columns in header"
}

# -----------------------------
# STEP 3: Gold
# Validations:
# 1) Script execution
# 2) Artifacts exist (gold + reports)
# 3) Gold contract ok (validate_gold.py)
# 4) Alternate by-type report (gold_sla_by_issue_type.csv) exists
# -----------------------------
Write-Host "STEP 3/3 - GOLD"

# Controlled reset of Gold
if (Test-Path $GoldFile) { Remove-Item $GoldFile -Force }
if (Test-Path $GoldReportAnalyst) { Remove-Item $GoldReportAnalyst -Force }
if (Test-Path $GoldReportType) { Remove-Item $GoldReportType -Force }
if (Test-Path $GoldReportType2) { Remove-Item $GoldReportType2 -Force }

RunPython @(".\src\gold\calculate_sla.py") "GOLD-RUN"
CheckFileExists $GoldFile "GOLD-ARTIFACT"
CheckFileExists $GoldReportAnalyst "GOLD-REPORT-ANALYST"
CheckFileExists $GoldReportType "GOLD-REPORT-TYPE"
CheckFileExists $GoldReportType2 "GOLD-REPORT-TYPE-ALT"
RunPython @(".\scripts\validate_gold.py") "GOLD-VALIDATOR"

Write-Host "Pipeline STEP completed successfully."
exit 0