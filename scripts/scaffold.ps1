# ================================================================
# SCRIPT: scaffold.ps1
# OBJETIVO:
# - Criar a estrutura do projeto Medallion (Bronze/Silver/Gold)
# - Criar arquivos vazios (placeholders). NAO preencher conteudo.
# POR QUE:
# - Separar "estrutura" de "conteudo" facilita versionamento e revisao
# ================================================================

Write-Host "Starting scaffold..."

# 1) Pastas do projeto
$folders = @(
    "data/raw",
    "data/bronze",
    "data/silver",
    "data/gold",
    "src/bronze",
    "src/silver",
    "src/gold",
    "src/utils",
    "scripts",
    "logs"
)

foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder | Out-Null
        Write-Host "Created folder: $folder"
    }
}

# 2) Arquivos vazios (placeholders)
$files = @(
    "src/bronze/__init__.py",
    "src/silver/__init__.py",
    "src/gold/__init__.py",
    "src/utils/__init__.py",
    "src/bronze/ingest_jira.py",
    "src/silver/transform_jira.py",
    "src/gold/calculate_sla.py",
    "src/utils/azure_blob.py",
    "src/utils/date_utils.py",
    "src/utils/holiday_api.py",
    "src/utils/validators.py",
    "main.py",
    ".gitignore",
    ".env.example",
    "requirements.txt",
    "README.md",
    "scripts/run_pipeline.ps1",
    "scripts/validate_bronze.py",
    "scripts/validate_silver.py",
    "scripts/validate_gold.py",
    "scripts/publish_github.ps1"
)

foreach ($file in $files) {
    if (-not (Test-Path $file)) {
        New-Item -ItemType File -Path $file | Out-Null
        Write-Host "Created file: $file"
    }
}

# 3) JSON fallback (exemplo minimo)
$rawJsonPath = "data/raw/jira_issues_raw.json"
if (-not (Test-Path $rawJsonPath)) {
@"
{
  "issues": []
}
"@ | Out-File -FilePath $rawJsonPath -Encoding utf8
    Write-Host "Created fallback JSON: $rawJsonPath"
}

Write-Host "Scaffold completed."