param(
    [ValidateSet("full","step")]
    [string]$Mode = "step"
)

# ================================================================
# SCRIPT: run_pipeline.ps1
# OBJETIVO:
# - Executar pipeline Medallion (Bronze -> Silver -> Gold)
# - Modo "step" (padrao): executa e valida cada camada separadamente
# - Modo "full": executa main.py (quando existir) e valida no final
#
# PRINCIPIOS:
# - Fail fast: se algo falhar, parar imediatamente com mensagem clara
# - 3+ validacoes por etapa (ambiente, execucao, artefatos/contrato)
# - Garantir PYTHONPATH na raiz do projeto para imports "src.*"
# - Evitar python -c para validacoes complexas (usar scripts dedicados)
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
    # Evitar conflito com variavel automatica $Args do PowerShell:
    # usamos $PyArgs como array de argumentos para o python.
    Write-Host "RUN: python $($PyArgs -join ' ')"
    & python @PyArgs
    if ($LASTEXITCODE -ne 0) {
        Fail "$Context - python execution failed (exit code $LASTEXITCODE)"
    }
}

# ------------------------------------------------
# Validacao 1 (global): estamos na raiz do projeto
# ------------------------------------------------
if (-not (Test-Path ".\src")) {
    Fail "Project root not detected. Ensure you are running from the project root where .\src exists."
}

# ------------------------------------------------
# Validacao 2 (global): python esta acessivel
# ------------------------------------------------
try {
    $py = (Get-Command python).Source
    Write-Host "Python: $py"
} catch {
    Fail "Python not found in PATH. Activate .venv or install Python."
}

# ------------------------------------------------
# Validacao 3 (global): setar PYTHONPATH na raiz
# Isso resolve: ModuleNotFoundError: No module named 'src'
# ------------------------------------------------
$env:PYTHONPATH = (Get-Location).Path
Write-Host "PYTHONPATH set to: $env:PYTHONPATH"

# ------------------------------------------------
# Caminhos de artefatos
# ------------------------------------------------
$BronzeFile = ".\data\bronze\bronze_jira.json"
$BronzeEvidence = ".\data\bronze\bronze_jira_source.json"

$SilverFile = ".\data\silver\silver_jira.csv"

$GoldFile = ".\data\gold\gold_jira_sla.csv"
$GoldReportAnalyst = ".\data\gold\gold_sla_by_analyst.csv"
$GoldReportType = ".\data\gold\gold_sla_by_type.csv"
$GoldReportType2 = ".\data\gold\gold_sla_by_issue_type.csv"

# ------------------------------------------------
# Execucao
# ------------------------------------------------
if ($Mode -eq "full") {

    # Modo full: usa main.py (quando existir)
    CheckFileExists ".\main.py" "FULL"
    RunPython @(".\main.py") "FULL"

    # Validacoes finais (artefatos principais)
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
# Modo STEP (padrao) - executa etapa por etapa com fail-fast
# ================================================================

# -----------------------------
# STEP 1: Bronze
# Validacoes:
# 1) Execucao do script
# 2) Artefato existe e nao vazio
# 3) Contrato Bronze ok (validate_bronze.py)
# 4) Evidencia de origem existe (azure vs fallback)
# -----------------------------
Write-Host "STEP 1/3 - BRONZE"

RunPython @(".\src\bronze\ingest_jira.py") "BRONZE-RUN"
CheckFileNotEmpty $BronzeFile "BRONZE-ARTIFACT"
CheckFileExists $BronzeEvidence "BRONZE-EVIDENCE"
RunPython @(".\scripts\validate_bronze.py") "BRONZE-VALIDATOR"

# Validacao extra: origem registrada (se o script existir)
if (Test-Path ".\scripts\validate_bronze_source.py") {
    RunPython @(".\scripts\validate_bronze_source.py") "BRONZE-SOURCE-VALIDATOR"
} else {
    Write-Host "WARN: scripts/validate_bronze_source.py not found. Skipping source validation."
}

# -----------------------------
# STEP 2: Silver
# Validacoes:
# 1) Execucao do script
# 2) Artefato existe
# 3) Contrato Silver ok (validate_silver.py)
# 4) Arquivo contem cabecalho esperado (primeira linha)
# -----------------------------
Write-Host "STEP 2/3 - SILVER"

# Reset controlado da Silver (evita cache de execucao anterior)
if (Test-Path $SilverFile) {
    Remove-Item $SilverFile -Force
    Write-Host "Removed old Silver file: $SilverFile"
}

RunPython @(".\src\silver\transform_jira.py") "SILVER-RUN"
CheckFileExists $SilverFile "SILVER-ARTIFACT"
RunPython @(".\scripts\validate_silver.py") "SILVER-VALIDATOR"

# Validacao extra: cabecalho CSV
$header = (Get-Content $SilverFile -TotalCount 1)
if ($header -notmatch "issue_id" -or $header -notmatch "created") {
    Fail "SILVER-HEADER - missing expected columns in header"
}

# -----------------------------
# STEP 3: Gold
# Validacoes:
# 1) Execucao do script
# 2) Artefatos existem (gold + reports)
# 3) Contrato Gold ok (validate_gold.py)
# 4) Relatorio alternativo por tipo (gold_sla_by_issue_type.csv) existe
# -----------------------------
Write-Host "STEP 3/3 - GOLD"

# Reset controlado da Gold
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