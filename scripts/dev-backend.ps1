$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
if (-not (Test-Path .\.venv\Scripts\uvicorn.exe)) {
  Write-Error "Missing .venv. Create it and install backend requirements first (see README)."
}
.\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --reload --port 8000
