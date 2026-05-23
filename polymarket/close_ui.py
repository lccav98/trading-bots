#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def main():
    funder = os.environ.get("FUNDER_ADDRESS")

    print("=== CHECKING POSITIONS ===\n")

    urls = [
        f"https://clob.polymarket.com/balance?user={funder}",
        f"https://clob.polymarket.com/positions?user={funder}",
    ]

    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            print(f"{url}")
            print(f"  Status: {r.status_code}")
            if r.status_code == 200:
                print(f"  Data: {r.text[:500]}")
                print()
                break
            else:
                print(f"  Response: {r.text[:200]}")
        except Exception as e:
            print(f"{url}: {e}")
        print()


if __name__ == "__main__":
    main()
