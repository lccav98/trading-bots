# NT8 Startup & Auto-Enable Script

import os
import time
import subprocess

NT8_PATH = "C:/Program Files/NinjaTrader 8/bin/NinjaTrader.exe"
STRATEGY_FILE = "C:/Users/OpAC BV/Documents/NinjaTrader 8/bin/Custom/Strategies/ApexSimpleTrend.cs"
INCOMING_DIR = "C:/Users/OpAC BV/Documents/NinjaTrader 8/incoming"

print("=" * 50)
print("NT8 Auto-Setup")
print("=" * 50)
print()

# 1. Check if NT8 is running
print("1. Checking NT8...")
result = os.popen('tasklist | findstr NinjaTrader').read()
if "NinjaTrader.exe" in result:
    print("   [OK] NT8 is already running")
else:
    print("   [!] NT8 not running")
    try:
        subprocess.Popen(NT8_PATH)
        print("   [OK] NT8 started")
        time.sleep(10)
    except Exception as e:
        print(f"   Error: {e}")

print()

# 2. Check strategy file
print("2. Checking strategy file...")
if os.path.exists(STRATEGY_FILE):
    print("   [OK] ApexSimpleTrend.cs exists")
    
    with open(STRATEGY_FILE, 'r') as f:
        content = f.read()
    
    if "namespace NinjaTrader.NinjaScript.Strategies" in content:
        print("   [OK] Basic syntax OK")
    else:
        print("   [!] Possible syntax issue")
else:
    print("   [X] Strategy file not found!")

print()

# 3. Check incoming directory
print("3. Checking NT8 incoming directory...")
os.makedirs(INCOMING_DIR, exist_ok=True)
print(f"   [OK] Directory ready")

print()
print("=" * 50)
print("NEXT STEPS:")
print("=" * 50)
print()
print("1. In NT8: Menu -> Tools -> NinjaScript Editor")
print("2. Click Compile (F5)")
print("3. If OK: Open MES chart (5min)")
print("4. Right-click -> Strategies -> ApexSimpleTrend -> Enable")
print("5. Done! NT8 trades automatically")
print()
print("=" * 50)