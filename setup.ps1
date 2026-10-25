# One-time setup: creates .venv, installs LiteLLM and unpacks Ollama (local backup model).
# Works offline when the bundled files are present (wheels\, installers\, ollama\). Run:
#   powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. Find Python 3.12 (the bundled wheels are built for it). Install the bundled copy if missing.
function Get-Python312 {
    try {
        $exe = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
    } catch {}
    $default = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $default) { return $default }
    return $null
}

$PyExe = Get-Python312
if (-not $PyExe) {
    if (-not (Test-Path "installers\python-3.12.10-amd64.exe")) {
        Write-Host "Python 3.12 not found. Install it from python.org, then run setup.ps1 again." -ForegroundColor Red
        exit 1
    }
    Write-Host "Python 3.12 not found - installing the bundled copy for the current user (about a minute)..."
    Start-Process -FilePath "installers\python-3.12.10-amd64.exe" -ArgumentList "/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0" -Wait
    $PyExe = Get-Python312
    if (-not $PyExe) { Write-Host "Python installation failed. Install Python 3.12 from python.org and run setup.ps1 again." -ForegroundColor Red; exit 1 }
}
Write-Host "Using Python: $PyExe"

# 2. Virtual environment and LiteLLM. Uses the bundled wheels when present, so no internet is needed.
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    & $PyExe -m venv .venv
}
if (Test-Path "wheels") {
    Write-Host "Installing LiteLLM from the bundled packages (offline, a minute or two)..."
    & .\.venv\Scripts\python.exe -m pip install --quiet --no-index --find-links wheels -r requirements.txt
} else {
    Write-Host "Installing LiteLLM from the internet (a few minutes the first time)..."
    & .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
}

# 3. Ollama (runs the local backup model). Unpacked next to the project, not installed system-wide.
if (Test-Path "ollama\ollama-windows-amd64.zip") {
    if (-not (Test-Path "ollama\app\ollama.exe")) {
        Write-Host "Unpacking Ollama (about 1.5 GB of files, a minute or two)..."
        New-Item -ItemType Directory -Force -Path "ollama\app" | Out-Null
        & tar.exe -xf "ollama\ollama-windows-amd64.zip" -C "ollama\app"
        if ($LASTEXITCODE -ne 0) { Expand-Archive -Path "ollama\ollama-windows-amd64.zip" -DestinationPath "ollama\app" -Force }
    }
} else {
    Write-Host "Ollama bundle not found - the local backup model will be unavailable." -ForegroundColor Yellow
}

# 4. Keys file.
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env - open it and paste your API keys (the local backup works without them)." -ForegroundColor Yellow
}
Write-Host "Setup complete. Next: run start.ps1 (or START-HERE.bat)." -ForegroundColor Green
