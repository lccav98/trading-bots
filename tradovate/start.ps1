# Apex Claude Trader - Launcher
Set-Location $PSScriptRoot

Write-Host ''
Write-Host '  APEX CLAUDE TRADER v3 - Iniciando...' -ForegroundColor Cyan
Write-Host ''

Remove-Item -Recurse -Force __pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force core\__pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force config\__pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force skills\__pycache__ -ErrorAction SilentlyContinue

python main.py

Write-Host ''
Write-Host '  Bot encerrado.' -ForegroundColor Yellow
Write-Host ''
