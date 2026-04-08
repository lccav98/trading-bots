# NT8 Compilation - Direct Attempt

import subprocess
import os

NT8_DIR = r"C:\Users\OpAC BV\Documents\NinjaTrader 8\bin\Custom\Strategies"

print("=" * 50)
print("NT8 Strategy Compilation Check")
print("=" * 50)
print()

# Check strategies exist
strategies = [
    "ApexSimpleTrendV2.cs",
    "ApexSimpleTrend.cs", 
    "ApexTrendHunterPro.cs",
    "ApexFileTrader.cs"
]

print("1. Checking strategy files...")
for s in strategies:
    path = os.path.join(NT8_DIR, s)
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"   [OK] {s} ({size} bytes)")
    else:
        print(f"   [X] {s} NOT FOUND")

print()

# Basic syntax check for C#
print("2. Basic syntax validation...")
for s in strategies:
    path = os.path.join(NT8_DIR, s)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for common issues
        issues = []
        
        # Check namespace
        if "namespace NinjaTrader.NinjaScript.Strategies" not in content:
            issues.append("Missing namespace")
        
        # Check class definition
        if "public class" not in content:
            issues.append("Missing class definition")
        
        # Check OnStateChange
        if "OnStateChange" not in content:
            issues.append("Missing OnStateChange")
        
        # Check OnBarUpdate
        if "OnBarUpdate" not in content:
            issues.append("Missing OnBarUpdate")
        
        if issues:
            print(f"   [!] {s}: {', '.join(issues)}")
        else:
            print(f"   [OK] {s} - basic syntax OK")

print()
print("=" * 50)
print("Manual Step Required:")
print("=" * 50)
print()
print("In NT8:")
print("  1. Press Ctrl+N (NinjaScript Editor)")
print("  2. Go to 'Strategies' tab")
print("  3. Select 'ApexSimpleTrendV2'")
print("  4. Press F5 (Compile)")
print()
print("If compile fails, copy the error message here.")
print("=" * 50)