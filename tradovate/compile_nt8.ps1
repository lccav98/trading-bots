# NT8 Auto-Compile Script
# Tries to compile NinjaScript strategies

$nt8Path = "C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe"

Write-Host "Attempting to trigger NT8 compile..." -ForegroundColor Yellow
Write-Host ""

# Try to find if there's a command-line compile option
$compileArgs = @(
    "/compile",
    "C:\Users\OpAC BV\Documents\NinjaTrader 8\bin\Custom\Strategies\ApexSimpleTrend.cs"
)

# Try running with possible compile flags
try {
    $proc = Start-Process -FilePath $nt8Path -ArgumentList "/compile" -PassThru -ErrorAction Stop
    Start-Sleep -Seconds 3
    if (!$proc.HasExited) {
        Write-Host "[OK] NT8 started with compile flag" -ForegroundColor Green
        $proc | Stop-Process -Force
    }
} catch {
    Write-Host "[!] Could not auto-compile" -ForegroundColor Red
    Write-Host $_.Exception.Message
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Manual compile required:" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Open NT8 (already running)" 
Write-Host "2. Press Ctrl+N (NinjaScript Editor)"
Write-Host "3. Press F5 (Compile)"
Write-Host ""
Write-Host "Strategies to compile:"
Write-Host "  - ApexSimpleTrend.cs (NEW - simple)"
Write-Host "  - ApexFileTrader.cs (NEW - file-based)"
Write-Host "  - ApexTrendHunterPro.cs (original)"
Write-Host ""
Write-Host "After compile:"
Write-Host "  - Add to chart: right-click -> Strategies"
Write-Host "  - Enable strategy"
Write-Host "  - Configure parameters"
Write-Host ""
Write-Host "The automation depends on successful compile!"