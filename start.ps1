# Start Keeper API (8000) and frontend (8080) together.
# Usage:  .\start.ps1
# Stop:   Ctrl+C
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Backend virtualenv not found at backend\.venv. Create it first (see README.md)."
}
if (-not (Test-Path (Join-Path $Backend ".env"))) {
    Write-Error "Missing backend\.env — copy backend\.env.example and fill it in."
}
if (-not (Test-Path (Join-Path $Frontend ".env"))) {
    Write-Error "Missing frontend\.env — copy frontend\.env.example and fill it in."
}

$jobs = @()

function Stop-Keeper {
    foreach ($job in $jobs) {
        if ($job -and -not $job.HasExited) {
            Stop-Process -Id $job.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

try {
    Write-Host "Starting Keeper API on http://127.0.0.1:8000"
    $jobs += Start-Process -FilePath $Python -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory $Backend -PassThru -NoNewWindow

    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
        Write-Host "Installing frontend dependencies..."
        Push-Location $Frontend
        try { npm install } finally { Pop-Location }
    }

    Write-Host "Starting frontend on http://localhost:8080"
    $jobs += Start-Process -FilePath "npm" -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "8080", "--strictPort") -WorkingDirectory $Frontend -PassThru -NoNewWindow

    Write-Host ""
    Write-Host "Keeper is running:"
    Write-Host "  Frontend   http://localhost:8080"
    Write-Host "  API        http://127.0.0.1:8000"
    Write-Host "  Mock bank  embedded at http://127.0.0.1:8000/_internal/mock-bank"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop all services."

    Wait-Process -Id ($jobs | ForEach-Object { $_.Id })
}
finally {
    Stop-Keeper
}
