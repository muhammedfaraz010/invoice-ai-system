$ErrorActionPreference = "Stop"

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Resolve-Path (Join-Path $backendDir "..\..\.venv\Scripts\python.exe")

Set-Location $backendDir
& $python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
