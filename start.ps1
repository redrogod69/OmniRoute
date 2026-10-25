# Starts OmniRoute: the local backup model (Ollama, port 11434), the gateway (port 4000) and the web console (port 8000), then opens the browser.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) { Write-Host "Run setup.ps1 first." -ForegroundColor Red; exit 1 }
if (-not (Test-Path ".env")) { Write-Host "Create .env from .env.example and add your keys." -ForegroundColor Red; exit 1 }

Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $k, $v = $line.Split("=", 2)
        Set-Item -Path "env:$($k.Trim())" -Value $v.Trim()
    }
}
foreach ($k in "GEMINI_API_KEY","GROQ_API_KEY","OPENROUTER_API_KEY") {
    if (-not (Get-Item "env:$k" -ErrorAction SilentlyContinue).Value) { Write-Host "Warning: $k is empty in .env, that provider will fail and the gateway will fall back." -ForegroundColor Yellow }
}
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"

# Local backup model: Ollama runs from the bundled folder and reads the bundled model files.
$OllamaExe = Join-Path $PSScriptRoot "ollama\app\ollama.exe"
$env:OLLAMA_MODELS = Join-Path $PSScriptRoot "ollama\models"
if (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "Ollama already running - local backup model available."
} elseif (Test-Path $OllamaExe) {
    Write-Host "Starting the local backup model (Ollama) ..."
    Start-Process -FilePath $OllamaExe -ArgumentList "serve" -WindowStyle Minimized -WorkingDirectory $PSScriptRoot
} else {
    Write-Host "Ollama not found - the local backup model will be offline. Run setup.ps1 to unpack it." -ForegroundColor Yellow
}

$busy = Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue
if ($busy) {
    Write-Host "Port 4000 already in use - assuming the gateway is running."
} else {
    Write-Host "Starting OmniRoute gateway on http://127.0.0.1:4000 ..."
    Start-Process -FilePath ".venv\Scripts\litellm.exe" -ArgumentList "--config config.yaml --host 127.0.0.1 --port 4000" -WorkingDirectory $PSScriptRoot
}

Write-Host "Waiting for the gateway to be ready (can take up to a minute)..."
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try { if ((Invoke-WebRequest "http://127.0.0.1:4000/health/liveliness" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { $ready = $true; break } } catch {}
    Start-Sleep -Seconds 2
}
if (-not $ready) { Write-Host "Gateway did not start. Check its window for errors." -ForegroundColor Red; exit 1 }
Write-Host "Gateway ready." -ForegroundColor Green

if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "app\ui_server.py" -WorkingDirectory $PSScriptRoot
    Start-Sleep -Seconds 2
}
Start-Process "http://127.0.0.1:8000"
Write-Host "OmniRoute console: http://127.0.0.1:8000   (close the black windows to stop)" -ForegroundColor Green
