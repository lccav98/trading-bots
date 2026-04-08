# Check NT8 ATI Status and Setup

import os
import time

INCOMING_DIR = os.path.expanduser("~/Documents/NinjaTrader 8/incoming")

print("=" * 60)
print("NT8 Automated Trading Interface (ATI) Setup Check")
print("=" * 60)
print()

# Check incoming folder
print("1. Checking incoming folder...")
if os.path.exists(INCOMING_DIR):
    print(f"   [OK] {INCOMING_DIR}")
    
    # List files
    files = os.listdir(INCOMING_DIR)
    if files:
        print(f"   Files found: {len(files)}")
        for f in files[:5]:
            print(f"     - {f}")
    else:
        print("   [OK] Empty (ready for orders)")
else:
    print(f"   [CREATE] Creating folder...")
    os.makedirs(INCOMING_DIR, exist_ok=True)
    print(f"   [OK] Created")

print()

# Enable ATI instructions
print("2. How to enable ATI in NT8:")
print("   " + "-" * 50)
print("   a) Open NT8")
print("   b) Menu: Tools -> Options")
print("   c) Go to: Automated Trading tab")
print("   d) Check: Enable Automated Trading Interface")
print("   e) Check: Enable ATI file interface")
print("   f) Click OK")
print()

print("3. How to use with strategies:")
print("   " + "-" * 50)
print("   a) Compile strategy (Ctrl+N, F5)")
print("   b) Add to chart: Right-click -> Strategies")
print("   c) Enable your strategy")
print("   d) Orders sent via OIF will be processed")
print()

print("4. Files created by this system:")
print("   " + "-" * 50)
print("   - nt8_ati_bridge.py: Send orders to NT8")
print("   - nt8_oif_client.py: Client to manage orders")
print()

print("=" * 60)
print("Ready to send orders!")
print("=" * 60)