param(
    [string]$ProjectPath = "C:\projetos\afiliados-mvp",
    [string]$VenvPath = ".venv"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $ProjectPath

$activatePath = Join-Path $ProjectPath "$VenvPath\Scripts\Activate.ps1"
if (-not (Test-Path $activatePath)) {
    throw "Virtualenv não encontrado em: $activatePath"
}

. $activatePath

$env:VPS_BASE_URL="https://minhaoferta.com"
$env:WORKER_API_TOKEN="afiliados_worker_caio_2026"
$env:WORKER_ID="pc_caio_01"
$env:WORKER_POLL_INTERVAL_SECONDS="3"
$env:CHROME_BINARY_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"
$env:CHROME_PROFILE_DIR="C:\projetos\afiliados-mvp\data\chrome_profile"
$env:METADATA_CHROME_PROFILE_DIR="C:\projetos\afiliados-mvp\data\chrome_profile_metadata"

py start_workers.py
