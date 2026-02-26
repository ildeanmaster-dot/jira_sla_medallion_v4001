param(
    [ValidateSet("full","step")]
    [string]$Mode = "step"
)

# ================================================================
# SCRIPT: run_pipeline.ps1
# GOAL:
# - Run Medallion pipeline (Bronze -> Silver -> Gold)
# - "step" mode (default): run each layer and validate immediately
# - "full" mode: run main.py (if present) and validate at the end
#
# PRINCIPLES:
# - Fail fast with clear messages
# - 3+ validations per stage (env, execution, artifacts/contract)
# - Ensure PYTHONPATH is set to project root for 'src.*' imports
# - Avoid complex validations via python -c; use dedicated scripts
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
    Write-Host "RUN: python $($PyArgs -join ' ')"
    & python @PyArgs
    if ($LASTEXITCODE -ne 0) {
        Fail "$Context - python execution failed (exit code $LASTEXITCODE)"
    }
}

# ------------------------------------------------
# Global validation 1: project root
# ------------------------------------------------
if (-not (Test-Path ".\src")) {
    Fail "Project root not detected. Run this script from the project root (where .\src exists)."
}

# ------------------------------------------------
# Global validation 2: python available
# ------------------------------------------------
try {
    $py = (Get-Command python).Source
    Write-Host "Python: $py"
} catch {
    Fail "Python not found in PATH. Activate .venv or install Python."
}

# ------------------------------------------------
# Global validation 3: set PYTHONPATH to root
# Fixes: ModuleNotFoundError: No module named 'src'
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

# IMPORTANT: keep only the canonical report file
$GoldReportIssueType = ".\data\gold\gold_sla_by_issue_type.csv"

# ------------------------------------------------
# Execution
# ------------------------------------------------
if ($Mode -eq "full") {

    # FULL mode uses main.py (if present)
    CheckFileExists ".\main.py" "FULL"
    RunPython @(".\main.py") "FULL"

    # Final validations (fail-fast)
    CheckFileNotEmpty $BronzeFile "FULL-BRONZE"
    CheckFileExists $BronzeEvidence "FULL-BRONZE-EVIDENCE"
    RunPython @(".\scripts\validate_bronze.py") "FULL-BRONZE-VALIDATOR"

    CheckFileExists $SilverFile "FULL-SILVER"
    RunPython @(".\scripts\validate_silver.py") "FULL-SILVER-VALIDATOR"

    CheckFileExists $GoldFile "FULL-GOLD"
    CheckFileExists $GoldReportAnalyst "FULL-GOLD-REPORT-ANALYST"
    CheckFileExists $GoldReportIssueType "FULL-GOLD-REPORT-ISSUE-TYPE"
    RunPython @(".\scripts\validate_gold.py") "FULL-GOLD-VALIDATOR"

    Write-Host "Pipeline FULL completed successfully."
    exit 0
}

# ================================================================
# STEP mode (default) - stage-by-stage with validations
# ================================================================

# -----------------------------
# STEP 1: Bronze
# Validations:
# 1) Script execution
# 2) Artifact exists and not empty
# 3) Bronze contract validator
# 4) Source evidence exists (Azure vs fallback)
# -----------------------------
Write-Host "STEP 1/3 - BRONZE"

RunPython @(".\src\bronze\ingest_jira.py") "BRONZE-RUN"
CheckFileNotEmpty $BronzeFile "BRONZE-ARTIFACT"
CheckFileExists $BronzeEvidence "BRONZE-EVIDENCE"
RunPython @(".\scripts\validate_bronze.py") "BRONZE-VALIDATOR"

# Optional: explicit source validation script
if (Test-Path ".\scripts\validate_bronze_source.py") {
    RunPython @(".\scripts\validate_bronze_source.py") "BRONZE-SOURCE-VALIDATOR"
} else {
    Write-Host "WARN: scripts/validate_bronze_source.py not found. Skipping source validation."
}

# -----------------------------
# STEP 2: Silver
# Validations:
# 1) Controlled reset (avoid stale data)
# 2) Script execution
# 3) Artifact exists
# 4) Silver contract validator
# 5) Header sanity check
# -----------------------------
Write-Host "STEP 2/3 - SILVER"

if (Test-Path $SilverFile) {
    Remove-Item $SilverFile -Force
    Write-Host "Removed old Silver file: $SilverFile"
}

RunPython @(".\src\silver\transform_jira.py") "SILVER-RUN"
CheckFileExists $SilverFile "SILVER-ARTIFACT"
RunPython @(".\scripts\validate_silver.py") "SILVER-VALIDATOR"

$header = (Get-Content $SilverFile -TotalCount 1)
if ($header -notmatch "issue_id" -or $header -notmatch "created_at") {
    Fail "SILVER-HEADER - missing expected columns in header"
}

# -----------------------------
# STEP 3: Gold
# Validations:
# 1) Controlled reset
# 2) Script execution
# 3) Artifacts exist (gold + required reports)
# 4) Gold contract validator
# -----------------------------
Write-Host "STEP 3/3 - GOLD"

if (Test-Path $GoldFile) { Remove-Item $GoldFile -Force }
if (Test-Path $GoldReportAnalyst) { Remove-Item $GoldReportAnalyst -Force }
if (Test-Path $GoldReportIssueType) { Remove-Item $GoldReportIssueType -Force }

RunPython @(".\src\gold\calculate_sla.py") "GOLD-RUN"

CheckFileExists $GoldFile "GOLD-ARTIFACT"
CheckFileExists $GoldReportAnalyst "GOLD-REPORT-ANALYST"
CheckFileExists $GoldReportIssueType "GOLD-REPORT-TYPE"

RunPython @(".\scripts\validate_gold.py") "GOLD-VALIDATOR"

Write-Host "Pipeline STEP completed successfully."
exit 0