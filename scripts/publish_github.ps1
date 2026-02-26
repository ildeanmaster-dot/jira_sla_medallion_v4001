param(
    [Parameter(Mandatory=$true)]
    [string]$RepoUrl,

    [string]$TagName = "v1.0.0"
)

function Fail([string]$Message) { Write-Host "ERROR: $Message"; exit 1 }
function Run([string]$Cmd) { Write-Host "RUN: $Cmd"; Invoke-Expression $Cmd; if ($LASTEXITCODE -ne 0) { Fail "Command failed: $Cmd" } }

if (-not (Test-Path ".git")) { Fail "Git repository not found. Run: git init" }

# .env nao pode estar versionado (comparacao exata)
$trackedEnv = git ls-files | Where-Object { $_ -eq ".env" }
if ($null -ne $trackedEnv -and $trackedEnv.Count -gt 0) {
    Fail ".env is tracked by git. Remove it first: git rm --cached .env"
}

$currentBranch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($currentBranch -ne "main") { Run "git branch -M main" }

$hasOrigin = git remote | Where-Object { $_ -eq "origin" }
if ($null -eq $hasOrigin -or $hasOrigin.Count -eq 0) { Run "git remote add origin $RepoUrl" }
else { Run "git remote set-url origin $RepoUrl" }

Run "git push -u origin main"

$tagExists = git tag | Where-Object { $_ -eq $TagName }
if ($null -eq $tagExists -or $tagExists.Count -eq 0) { Run "git tag -a $TagName -m `"Release $TagName`"" }

Run "git push origin $TagName"
Write-Host "Publish completed successfully."